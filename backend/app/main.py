import base64
import os
import random
import secrets
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from . import auth, models as m, schemas as s
from .database import Base, SessionLocal, engine, get_db
from .parser import CATEGORIES, ParseError, parse_lines, solution
from .migrations import migrate


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        migrate(engine, db)
        if not db.scalar(select(m.User.id).limit(1)):
            password = base64.b64encode(secrets.token_bytes(24)).decode("ascii")
            credentials = Path(os.getenv("ADMIN_CREDENTIALS_PATH", ".admin_credentials"))
            credentials.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as file:
                file.write(f"Логин: admin\nПароль: {password}\n")
            credentials.chmod(0o600)
            db.add(m.User(username="admin", name="Администратор", password_hash=auth.passwords.hash(password), role="admin"))
            db.commit()
    yield


app = FastAPI(title="uTutor API", version="1.0.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def headers(request: Request, call_next):
    # Cookie-based refresh/logout are same-origin only; access uses Bearer.
    if request.method == "POST" and request.url.path in ("/api/auth/refresh", "/api/auth/logout"):
        if request.headers.get("sec-fetch-site") == "cross-site":
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Недопустимый источник запроса."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(data: s.LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    auth.rate_limit(request)
    user = db.scalar(select(m.User).where(m.User.username == data.username))
    # Verify a dummy hash as well so nonexistent usernames do not return instantly.
    valid = auth.passwords.verify(data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, "Неверный логин или пароль.")
    return auth.issue_tokens(user, db, response)


DUMMY_HASH = auth.passwords.hash(secrets.token_urlsafe(24))


@app.post("/api/auth/refresh")
def refresh(response: Response, refresh_token: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    user = auth.refresh_user(refresh_token, db)
    return auth.issue_tokens(user, db, response)


@app.post("/api/auth/logout", status_code=204)
def logout(response: Response, refresh_token: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    if refresh_token:
        try:
            auth.refresh_user(refresh_token, db)
            db.commit()
        except HTTPException:
            db.rollback()
    response.delete_cookie("refresh_token", path="/api/auth", secure=auth.SECURE_COOKIES, httponly=True, samesite="strict")


@app.get("/api/auth/me")
def me(user=Depends(auth.current_user)):
    return auth.public_user(user)


@app.get("/api/teachers")
def teachers(db: Session = Depends(get_db), user=Depends(auth.admin)):
    return [auth.public_user(u) for u in db.scalars(select(m.User).order_by(m.User.id))]


@app.post("/api/teachers", status_code=201)
def create_teacher(data: s.UserInput, db: Session = Depends(get_db), user=Depends(auth.admin)):
    if db.scalar(select(m.User.id).where(m.User.username == data.username)):
        raise HTTPException(409, "Этот логин уже занят.")
    password = data.password or secrets.token_urlsafe(18)
    teacher = m.User(username=data.username, name=data.name.strip(), password_hash=auth.passwords.hash(password))
    db.add(teacher)
    db.commit()
    return {**auth.public_user(teacher), "password": password}


def teacher_target(teacher_id, db):
    teacher = db.get(m.User, teacher_id)
    if not teacher:
        raise HTTPException(404, "Преподаватель не найден.")
    if teacher.role == "admin":
        raise HTTPException(403, "Нельзя удалить или сбросить пароль системного администратора.")
    return teacher


@app.post("/api/teachers/{teacher_id}/reset-password")
def reset_password(teacher_id: int, db: Session = Depends(get_db), user=Depends(auth.admin)):
    teacher = teacher_target(teacher_id, db)
    password = secrets.token_urlsafe(18)
    teacher.password_hash = auth.passwords.hash(password)
    teacher.token_version += 1
    db.execute(delete(m.RefreshSession).where(m.RefreshSession.user_id == teacher_id))
    db.commit()
    return {"password": password, "username": teacher.username}


@app.delete("/api/teachers/{teacher_id}", status_code=204)
def delete_teacher(teacher_id: int, db: Session = Depends(get_db), user=Depends(auth.admin)):
    db.delete(teacher_target(teacher_id, db))
    db.commit()


def owned(model, object_id, user, db):
    obj = db.get(model, object_id)
    if not obj or obj.owner_id != user.id:
        raise HTTPException(404, "Объект не найден.")
    return obj


def owned_list(list_id, user, db):
    task_list = db.get(m.TaskList, list_id)
    if not task_list:
        raise HTTPException(404, "Список не найден.")
    folder = owned(m.Folder, task_list.folder_id, user, db)
    return task_list, folder


def parse(raw, category):
    try:
        return parse_lines(raw, category)
    except ParseError as exc:
        raise HTTPException(422, str(exc))


def item_json(item):
    return {"id": item.id, "source": item.source, "data": item.data, "needs_review": item.needs_review, "solution": solution(item.data)}


@app.get("/api/library")
def library(db: Session = Depends(get_db), user=Depends(auth.current_user)):
    folders = list(db.scalars(select(m.Folder).where(m.Folder.owner_id == user.id).order_by(m.Folder.name)))
    lists = list(db.scalars(select(m.TaskList).join(m.Folder).where(m.Folder.owner_id == user.id).order_by(m.TaskList.updated_at.desc())))
    counts = defaultdict(lambda: {"count": 0, "review": 0})
    for item in db.scalars(select(m.Item).join(m.TaskList).join(m.Folder).where(m.Folder.owner_id == user.id)):
        counts[item.list_id]["count"] += 1
        counts[item.list_id]["review"] += int(item.needs_review)
    return {"folders": [{"id": f.id, "name": f.name, "category": f.category} for f in folders],
            "lists": [{"id": t.id, "folder_id": t.folder_id, "name": t.name, "updated_at": t.updated_at, **counts[t.id]} for t in lists]}


@app.post("/api/folders", status_code=201)
def create_folder(data: s.FolderInput, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    folder = m.Folder(owner_id=user.id, **data.model_dump())
    db.add(folder)
    db.commit()
    return {"id": folder.id}


@app.put("/api/folders/{folder_id}")
def rename_folder(folder_id: int, data: s.NameInput, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    folder = owned(m.Folder, folder_id, user, db)
    folder.name = data.name
    db.commit()
    return {"id": folder.id}


@app.delete("/api/folders/{folder_id}", status_code=204)
def delete_folder(folder_id: int, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    db.delete(owned(m.Folder, folder_id, user, db))
    db.commit()


@app.post("/api/parse")
def preview(data: s.ParseInput, user=Depends(auth.current_user)):
    return parse(data.raw, data.category)


@app.post("/api/import")
async def import_file(category: str, file: UploadFile, user=Depends(auth.current_user)):
    if not file.filename or not file.filename.lower().endswith(".txt"):
        raise HTTPException(422, "Выберите текстовый файл .txt.")
    content = await file.read(1024 * 1024 + 1)
    if len(content) > 1024 * 1024:
        raise HTTPException(413, "Максимальный размер файла — 1 МБ.")
    try:
        raw = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(422, "Файл должен быть в кодировке UTF-8.")
    return {"raw": raw, "items": parse(raw, category)}


def replace_items(task_list, entries, db):
    # Preserve stable item IDs and progress for unchanged entries; edits to an
    # answer create a new item and intentionally reset that item's progress.
    existing = defaultdict(list)
    for item in db.scalars(select(m.Item).where(m.Item.list_id == task_list.id).order_by(m.Item.position)):
        existing[item.source].append(item)
    for pos, entry in enumerate(entries):
        candidates = existing[entry["source"]]
        item = candidates.pop(0) if candidates else m.Item(list_id=task_list.id)
        item.position = pos
        item.source = entry["source"]
        item.data = entry["data"]
        item.needs_review = entry["needs_review"]
        db.add(item)
    for candidates in existing.values():
        for item in candidates:
            db.delete(item)


@app.post("/api/folders/{folder_id}/lists", status_code=201)
def create_list(folder_id: int, data: s.ListInput, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    folder = owned(m.Folder, folder_id, user, db)
    entries = parse(data.raw, folder.category)
    task_list = m.TaskList(folder_id=folder_id, name=data.name)
    db.add(task_list)
    db.flush()
    replace_items(task_list, entries, db)
    db.commit()
    return {"id": task_list.id}


@app.get("/api/lists/{list_id}")
def get_list(list_id: int, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    task_list, folder = owned_list(list_id, user, db)
    items = list(db.scalars(select(m.Item).where(m.Item.list_id == list_id).order_by(m.Item.position)))
    return {"id": task_list.id, "name": task_list.name, "category": folder.category, "folder_id": folder.id,
            "raw": "\n".join(i.source for i in items), "items": [item_json(i) for i in items]}


@app.put("/api/lists/{list_id}")
def update_list(list_id: int, data: s.ListInput, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    task_list, folder = owned_list(list_id, user, db)
    entries = parse(data.raw, folder.category)
    task_list.name = data.name
    task_list.updated_at = m.now()
    replace_items(task_list, entries, db)
    db.commit()
    return {"id": task_list.id}


@app.delete("/api/lists/{list_id}", status_code=204)
def delete_list(list_id: int, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    task_list, _ = owned_list(list_id, user, db)
    db.delete(task_list)
    db.commit()


def profile_lists(profile, db):
    result = []
    progress = {p.item_id: p.correct for p in db.scalars(select(m.Progress).where(m.Progress.profile_id == profile.id))}
    for task_list, folder in db.execute(select(m.TaskList, m.Folder).join(m.Folder).join(m.Attachment, m.Attachment.list_id == m.TaskList.id).where(m.Attachment.profile_id == profile.id)):
        items = list(db.scalars(select(m.Item).where(m.Item.list_id == task_list.id)))
        result.append({"id": task_list.id, "name": task_list.name, "category": folder.category, "folder": folder.name,
                       "total": len(items), "correct": sum(progress.get(i.id) is True for i in items),
                       "mistakes": sum(progress.get(i.id) is False for i in items), "review": sum(i.needs_review for i in items)})
    return result


def profile_json(profile, db):
    active = db.scalar(select(m.TrainingSession).where(m.TrainingSession.profile_id == profile.id, m.TrainingSession.status == "active"))
    return {"id": profile.id, "name": profile.name, "kind": profile.kind, "note": profile.note,
            "created_at": profile.created_at, "lists": profile_lists(profile, db),
            "active_session": {"id": active.id, "name": active.context.get("name", "Тренировка"),
                               "category": active.context.get("category"), "total": len(active.items),
                               "answered": sum(not k.startswith("partial:") for k in active.answers)} if active else None}


@app.get("/api/profiles")
def profiles(db: Session = Depends(get_db), user=Depends(auth.current_user)):
    return [profile_json(p, db) for p in db.scalars(select(m.Profile).where(m.Profile.owner_id == user.id).order_by(m.Profile.created_at.desc()))]


@app.post("/api/profiles", status_code=201)
def create_profile(data: s.ProfileInput, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    profile = m.Profile(owner_id=user.id, **data.model_dump())
    db.add(profile)
    db.commit()
    return {"id": profile.id}


@app.get("/api/profiles/{profile_id}")
def get_profile(profile_id: int, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    return profile_json(owned(m.Profile, profile_id, user, db), db)


@app.put("/api/profiles/{profile_id}")
def update_profile(profile_id: int, data: s.ProfileInput, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    profile = owned(m.Profile, profile_id, user, db)
    for key, value in data.model_dump().items():
        setattr(profile, key, value)
    db.commit()
    return {"id": profile.id}


@app.delete("/api/profiles/{profile_id}", status_code=204)
def delete_profile(profile_id: int, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    db.delete(owned(m.Profile, profile_id, user, db))
    db.commit()


@app.post("/api/profiles/{profile_id}/lists", status_code=201)
def attach(profile_id: int, data: s.AttachInput, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    owned(m.Profile, profile_id, user, db)
    owned_list(data.list_id, user, db)
    if db.scalar(select(m.Attachment.id).where(m.Attachment.profile_id == profile_id, m.Attachment.list_id == data.list_id)):
        raise HTTPException(409, "Список уже прикреплён.")
    db.add(m.Attachment(profile_id=profile_id, list_id=data.list_id))
    db.commit()
    return {"ok": True}


def attached(profile_id, list_id, user, db):
    owned(m.Profile, profile_id, user, db)
    task_list, folder = owned_list(list_id, user, db)
    if not db.scalar(select(m.Attachment.id).where(m.Attachment.profile_id == profile_id, m.Attachment.list_id == list_id)):
        raise HTTPException(404, "Список не прикреплён к профилю.")
    return task_list, folder


@app.delete("/api/profiles/{profile_id}/lists/{list_id}", status_code=204)
def detach(profile_id: int, list_id: int, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    attached(profile_id, list_id, user, db)
    db.execute(delete(m.Attachment).where(m.Attachment.profile_id == profile_id, m.Attachment.list_id == list_id))
    db.commit()


@app.delete("/api/profiles/{profile_id}/lists/{list_id}/progress", status_code=204)
def reset_progress(profile_id: int, list_id: int, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    attached(profile_id, list_id, user, db)
    db.execute(delete(m.Progress).where(m.Progress.profile_id == profile_id, m.Progress.item_id.in_(select(m.Item.id).where(m.Item.list_id == list_id))))
    db.commit()


@app.get("/api/profiles/{profile_id}/lists/{list_id}/items")
def selection_items(profile_id: int, list_id: int, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    attached(profile_id, list_id, user, db)
    progress = {p.item_id: p.correct for p in db.scalars(select(m.Progress).where(m.Progress.profile_id == profile_id))}
    items = [{**item_json(i), "status": "new" if i.id not in progress else "correct" if progress[i.id] else "mistake"}
             for i in db.scalars(select(m.Item).where(m.Item.list_id == list_id).order_by(m.Item.position))]
    return sorted(items, key=lambda i: {"correct": 0, "mistake": 1, "new": 2}[i["status"]])


def public_training_item(item, category):
    data = item.data
    if category == "stress":
        return {"id": item.id, "word": data["word"], "explanation": data.get("explanation", "")}
    parts = []
    for part in data["parts"]:
        if "text" in part:
            parts.append(part)
        else:
            options = part["options"][:]
            random.SystemRandom().shuffle(options)
            parts.append({"hint": part["hint"], "options": options})
    return {"id": item.id, "parts": parts, "explanation": data.get("explanation", "")}


@app.post("/api/profiles/{profile_id}/sessions", status_code=201)
def start_session(profile_id: int, data: s.SessionInput, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    owned(m.Profile, profile_id, user, db)
    if db.scalar(select(m.TrainingSession.id).where(m.TrainingSession.profile_id == profile_id, m.TrainingSession.status == "active")):
        raise HTTPException(409, "Сначала продолжите сохранённую тренировку или завершите её без сохранения.")
    list_ids = list(dict.fromkeys(data.list_ids or ([data.list_id] if data.list_id else [])))
    if not list_ids:
        raise HTTPException(422, "Выберите хотя бы один список.")
    sources = [attached(profile_id, list_id, user, db) for list_id in list_ids]
    task_list, folder = sources[0]
    if any(f.category != folder.category for _, f in sources):
        raise HTTPException(422, "Объединять можно только списки одного типа заданий.")
    ids = set(data.item_ids)
    items = list(db.scalars(select(m.Item).where(m.Item.list_id.in_(list_ids), m.Item.id.in_(ids))))
    if len(items) != len(ids):
        raise HTTPException(422, "Некоторые задания не принадлежат выбранным спискам.")
    if any(i.needs_review for i in items):
        raise HTTPException(422, "Сначала проверьте ударения в редакторе списка.")
    random.SystemRandom().shuffle(items)
    session = m.TrainingSession(id=secrets.token_urlsafe(24), profile_id=profile_id, list_id=task_list.id,
                                items=[{"id": i.id, "list_id": i.list_id, "data": i.data, "source": i.source} for i in items], answers={},
                                context={"category": folder.category, "name": " + ".join(t.name for t, _ in sources),
                                         "list_ids": list_ids, "public_items": [public_training_item(i, folder.category) for i in items]})
    db.add(session)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "В этом профиле уже есть незавершённая тренировка.")
    return session_json(session)


def session_json(session):
    current = session.items[session.cursor] if session.cursor < len(session.items) else None
    choices = session.answers.get(f"partial:{current['id']}", []) if current else []
    feedback = session.answers.get(str(current["id"])) if current else None
    if choices and not feedback:
        correct = [p["correct"] for p in current["data"]["parts"] if "options" in p]
        checks = [a == b for a, b in zip(choices, correct)]
        feedback = {"complete": False, "correct": all(checks), "results": checks, "correct_answers": correct[:len(choices)]}
    return {"id": session.id, "profile_id": session.profile_id, "status": session.status,
            "category": session.context.get("category"), "name": session.context.get("name"),
            "list_ids": session.context.get("list_ids", [session.list_id]),
            "items": session.context.get("public_items", []), "index": session.cursor,
            "choices": choices, "feedback": feedback,
            "answered": sum(not k.startswith("partial:") for k in session.answers)}


def owned_session(session_id, user, db):
    session = db.get(m.TrainingSession, session_id)
    if not session:
        raise HTTPException(404, "Тренировка не найдена.")
    owned(m.Profile, session.profile_id, user, db)
    return session


@app.get("/api/sessions/{session_id}")
def resume_session(session_id: str, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    return session_json(owned_session(session_id, user, db))


@app.post("/api/sessions/{session_id}/advance")
def advance_session(session_id: str, data: s.AdvanceInput, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    session = owned_session(session_id, user, db)
    if session.status != "active":
        raise HTTPException(409, "Тренировка уже завершена.")
    if session.items[session.cursor]["id"] == data.item_id:
        if str(data.item_id) not in session.answers:
            raise HTTPException(409, "Сначала ответьте на текущее задание.")
        if session.cursor + 1 < len(session.items):
            session.cursor += 1
        try:
            db.commit()
        except StaleDataError:
            db.rollback()
            raise HTTPException(409, "Тренировка изменена в другом окне. Обновите страницу.")
    return session_json(session)


@app.post("/api/sessions/{session_id}/answers")
def answer(session_id: str, data: s.AnswerInput, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    session = owned_session(session_id, user, db)
    if session.status != "active":
        raise HTTPException(409, "Тренировка уже завершена.")
    if str(data.item_id) in session.answers:
        return session.answers[str(data.item_id)]
    snapshot = next((i for i in session.items if i["id"] == data.item_id), None)
    if not snapshot:
        raise HTTPException(422, "Задание не входит в тренировку.")
    payload = snapshot["data"]
    correct_answers = [payload["stress"]] if "word" in payload else [p["correct"] for p in payload["parts"] if "options" in p]
    if len(data.choices) > len(correct_answers):
        raise HTTPException(422, "Слишком много ответов.")
    if "word" in payload:
        choice = data.choices[0]
        if not isinstance(choice, int) or choice < 0 or choice >= len(payload["word"]) or payload["word"][choice] not in "аеёиоуыэюя":
            raise HTTPException(422, "Выберите гласную.")
    else:
        gaps = [p for p in payload["parts"] if "options" in p]
        if any(c not in gaps[i]["options"] for i, c in enumerate(data.choices)):
            raise HTTPException(422, "Неизвестный вариант ответа.")
    # Partial answers reveal only already answered gaps. Persist only complete
    # items, and keep their first accepted result immutable in this round.
    key = f"partial:{data.item_id}"
    previous = session.answers.get(key, [])
    if data.choices[:len(previous)] != previous:
        raise HTTPException(409, "Нельзя изменить уже данный ответ.")
    results = [choice == correct for choice, correct in zip(data.choices, correct_answers)]
    complete = len(data.choices) == len(correct_answers)
    result = {"correct": all(results), "results": results, "correct_answers": correct_answers[:len(data.choices)], "complete": complete}
    answers = dict(session.answers)
    answers[key] = data.choices
    if complete:
        result["solution"] = solution(payload)
        answers[str(data.item_id)] = result
        item = db.get(m.Item, data.item_id)
        if item and item.data == payload:
            progress = db.scalar(select(m.Progress).where(m.Progress.profile_id == session.profile_id, m.Progress.item_id == data.item_id))
            if progress:
                progress.correct = all(results)
                progress.attempts += 1
                progress.updated_at = m.now()
            else:
                db.add(m.Progress(profile_id=session.profile_id, item_id=data.item_id, correct=all(results)))
    session.answers = answers
    try:
        db.commit()
    except (StaleDataError, IntegrityError):
        db.rollback()
        raise HTTPException(409, "Ответ обрабатывается другим запросом. Повторите отправку.")
    return result


@app.get("/api/sessions/{session_id}/results")
def results(session_id: str, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    session = owned_session(session_id, user, db)
    if all(str(i["id"]) in session.answers for i in session.items) and session.status == "active":
        session.status = "finished"
        db.commit()
    return session_results(session)


@app.post("/api/sessions/{session_id}/finish")
def finish_session(session_id: str, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    session = owned_session(session_id, user, db)
    session.status = "finished"
    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        raise HTTPException(409, "Тренировка изменена в другом окне. Повторите завершение.")
    return session_results(session)


def session_results(session):
    answers = {k: v for k, v in session.answers.items() if not k.startswith("partial:")}
    mistakes = [{"id": i["id"], "source": i["source"], "solution": solution(i["data"])} for i in session.items if str(i["id"]) in answers and not answers[str(i["id"])]["correct"]]
    return {"total": len(answers), "correct": sum(a["correct"] for a in answers.values()), "mistakes": mistakes,
            "complete": len(answers) == len(session.items), "profile_id": session.profile_id, "list_id": session.list_id,
            "list_ids": session.context.get("list_ids", [session.list_id]), "category": session.context.get("category")}
