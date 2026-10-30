import base64
import os
from pathlib import Path

import jwt

from app import auth


def post(client, path, headers, **data):
    response = client.post(f"/api{path}", headers=headers, json=data)
    assert response.status_code in (200, 201), response.text
    return response.json()


def setup_training(client, headers, category="spelling", raw="мыш(ь,)\nопас(,т)ный\nс(ло,ла)в(о,а,и,е)"):
    folder = post(client, "/folders", headers, name="11 класс", category=category)
    task_list = post(client, f"/folders/{folder['id']}/lists", headers, name="Список", raw=raw)
    profile = post(client, "/profiles", headers, name="Иван", kind="student")
    post(client, f"/profiles/{profile['id']}/lists", headers, list_id=task_list["id"])
    items = client.get(f"/api/profiles/{profile['id']}/lists/{task_list['id']}/items", headers=headers).json()
    return folder["id"], task_list["id"], profile["id"], items


def test_seed_and_auth_refresh_rotation(client, admin):
    credentials = Path(os.environ["ADMIN_CREDENTIALS_PATH"])
    password = credentials.read_text().split("Пароль: ")[1].strip()
    assert len(password) == 32 and len(base64.b64decode(password)) == 24
    assert credentials.stat().st_mode & 0o777 == 0o600
    assert client.get("/api/library").status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    old = client.cookies.get("refresh_token")
    result = client.post("/api/auth/refresh")
    assert result.status_code == 200
    assert "httponly" in result.headers["set-cookie"].lower()
    client.cookies.set("refresh_token", old)
    assert client.post("/api/auth/refresh").status_code == 401


def test_expired_access_and_logout(client, admin):
    payload = jwt.decode(admin["Authorization"][7:], auth.SECRET, algorithms=["HS256"])
    payload["exp"] = 0
    expired = jwt.encode(payload, auth.SECRET, algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    assert client.post("/api/auth/logout").status_code == 204
    assert client.post("/api/auth/refresh").status_code == 401


def test_role_isolation_and_admin_reset(client, admin, teacher):
    folder_id, list_id, profile_id, _ = setup_training(client, admin)
    assert client.get("/api/teachers", headers=teacher).status_code == 403
    assert client.get(f"/api/lists/{list_id}", headers=teacher).status_code == 404
    assert client.get(f"/api/profiles/{profile_id}", headers=teacher).status_code == 404
    assert client.delete(f"/api/folders/{folder_id}", headers=teacher).status_code == 404
    assert client.get("/api/library", headers=teacher).json()["folders"] == []
    teachers = client.get("/api/teachers", headers=admin).json()
    teacher_id = next(t["id"] for t in teachers if t["role"] == "teacher")
    assert client.post(f"/api/teachers/{teacher_id}/reset-password", headers=admin).status_code == 200
    assert client.get("/api/auth/me", headers=teacher).status_code == 401
    assert client.delete("/api/teachers/1", headers=admin).status_code == 403


def test_import_utf8_and_validation(client, admin):
    response = client.post("/api/import?category=spelling", headers=admin, files={"file": ("test.txt", "мыш(ь,)".encode())})
    assert response.status_code == 200
    assert response.json()["items"][0]["data"]["parts"][1]["options"] == ["ь", ""]
    assert client.post("/api/import?category=stress", headers=admin, files={"file": ("test.txt", b"\xff")}).status_code == 422
    assert client.post("/api/import?category=stress", headers=admin, files={"file": ("test.csv", b"test")}).status_code == 422
    assert client.post("/api/folders", headers=admin, json={"name": " ", "category": "stress"}).status_code == 422


def test_training_first_attempt_empty_answers_and_progress(client, admin):
    _, list_id, profile_id, items = setup_training(client, admin)
    session = post(client, f"/profiles/{profile_id}/sessions", admin, list_id=list_id, item_ids=[i["id"] for i in items])
    assert all("correct" not in str(part) for item in session["items"] for part in item["parts"])
    first = post(client, f"/sessions/{session['id']}/answers", admin, item_id=items[0]["id"], choices=[""])
    assert not first["correct"] and first["correct_answers"] == ["ь"]
    repeated = post(client, f"/sessions/{session['id']}/answers", admin, item_id=items[0]["id"], choices=["ь"])
    assert repeated == first
    empty = post(client, f"/sessions/{session['id']}/answers", admin, item_id=items[1]["id"], choices=[""])
    assert empty["correct"]
    partial = post(client, f"/sessions/{session['id']}/answers", admin, item_id=items[2]["id"], choices=["ла"])
    assert partial["correct_answers"] == ["ло"] and not partial["complete"]
    assert client.post(f"/api/sessions/{session['id']}/answers", headers=admin, json={"item_id": items[2]["id"], "choices": ["ло", "о"]}).status_code == 409
    multi = post(client, f"/sessions/{session['id']}/answers", admin, item_id=items[2]["id"], choices=["ла", "о"])
    assert not multi["correct"] and multi["complete"]
    results = client.get(f"/api/sessions/{session['id']}/results", headers=admin).json()
    assert results["total"] == 3 and results["correct"] == 1 and len(results["mistakes"]) == 2
    assert results["complete"]
    statuses = client.get(f"/api/profiles/{profile_id}/lists/{list_id}/items", headers=admin).json()
    assert [i["status"] for i in statuses] == ["correct", "mistake", "mistake"]
    retry = post(client, f"/profiles/{profile_id}/sessions", admin, list_id=list_id, item_ids=[items[0]["id"]])
    post(client, f"/sessions/{retry['id']}/answers", admin, item_id=items[0]["id"], choices=["ь"])
    profile = client.get(f"/api/profiles/{profile_id}", headers=admin).json()
    assert profile["lists"][0]["correct"] == 2
    assert client.delete(f"/api/profiles/{profile_id}/lists/{list_id}/progress", headers=admin).status_code == 204
    assert client.get(f"/api/profiles/{profile_id}", headers=admin).json()["lists"][0]["correct"] == 0


def test_stress_review_and_grammar(client, admin):
    _, list_id, profile_id, items = setup_training(client, admin, "stress", "замок\nкаталОг")
    assert client.post(f"/api/profiles/{profile_id}/sessions", headers=admin, json={"list_id": list_id, "item_ids": [items[0]["id"]]}).status_code == 422
    session = post(client, f"/profiles/{profile_id}/sessions", admin, list_id=list_id, item_ids=[items[1]["id"]])
    assert "stress" not in session["items"][0]
    answer = post(client, f"/sessions/{session['id']}/answers", admin, item_id=items[1]["id"], choices=[5])
    assert answer["correct"]
    _, list_id, profile_id, items = setup_training(client, admin, "grammar", "Он (сберечь|сбережёт,сберегёт) здоровье.")
    session = post(client, f"/profiles/{profile_id}/sessions", admin, list_id=list_id, item_ids=[items[0]["id"]])
    assert session["items"][0]["parts"][1]["hint"] == "сберечь"
    answer = post(client, f"/sessions/{session['id']}/answers", admin, item_id=items[0]["id"], choices=["сбережёт"])
    assert answer["correct"]


def test_stress_import_and_manual_review(client, admin):
    raw = "молоко\nзамок\nмука\nбутявковед"
    imported = client.post("/api/import?category=stress", headers=admin,
                           files={"file": ("stress.txt", raw.encode("utf-8"))})
    assert imported.status_code == 200
    entries = imported.json()["items"]
    assert [e["needs_review"] for e in entries] == [False, True, True, True]
    assert entries[0]["data"] == {"word": "молоко", "stress": 5}
    _, list_id, profile_id, items = setup_training(client, admin, "stress", raw)
    for item in items[1:]:
        response = client.post(f"/api/profiles/{profile_id}/sessions", headers=admin,
                               json={"list_id": list_id, "item_ids": [item["id"]]})
        assert response.status_code == 422
    response = client.put(f"/api/lists/{list_id}", headers=admin,
                          json={"name": "Проверено", "raw": "молоко\nзамОк\nмукА\nбутявковЕд"})
    assert response.status_code == 200
    updated = client.get(f"/api/lists/{list_id}", headers=admin).json()["items"]
    assert all(not item["needs_review"] for item in updated)
    post(client, f"/profiles/{profile_id}/sessions", admin, list_id=list_id,
         item_ids=[item["id"] for item in updated])


def test_edit_preserves_unchanged_item_ids_and_cascades(client, admin):
    folder, task_list, profile, items = setup_training(client, admin)
    response = client.put(f"/api/lists/{task_list}", headers=admin, json={"name": "Новое имя", "raw": "мыш(ь,)\nнов(ы,а)й"})
    assert response.status_code == 200
    updated = client.get(f"/api/lists/{task_list}", headers=admin).json()
    assert updated["items"][0]["id"] == items[0]["id"]
    assert client.delete(f"/api/folders/{folder}", headers=admin).status_code == 204
    assert client.get(f"/api/lists/{task_list}", headers=admin).status_code == 404
    assert client.get(f"/api/profiles/{profile}", headers=admin).json()["lists"] == []


def test_resume_partial_session_finish_and_new_round(client, admin, teacher):
    _, list_id, profile_id, items = setup_training(client, admin, raw="с(ло,ла)в(о,а)\nграм(,м)ота")
    session = post(client, f"/profiles/{profile_id}/sessions", admin, list_id=list_id, item_ids=[i["id"] for i in items])
    post(client, f"/sessions/{session['id']}/answers", admin, item_id=items[0]["id"], choices=["ла"])
    assert client.post(f"/api/profiles/{profile_id}/sessions", headers=admin,
                       json={"list_id": list_id, "item_ids": [items[0]["id"]]}).status_code == 409
    saved = client.get(f"/api/sessions/{session['id']}", headers=admin).json()
    assert saved["items"] == session["items"]  # Includes unchanged shuffled options.
    # The current cursor may point at either shuffled word; a separate single-word
    # round below checks partial feedback deterministically.
    assert client.get(f"/api/sessions/{session['id']}", headers=teacher).status_code == 404
    active = client.get(f"/api/profiles/{profile_id}", headers=admin).json()["active_session"]
    assert active["id"] == session["id"] and active["answered"] == 0
    post(client, f"/sessions/{session['id']}/answers", admin, item_id=items[0]["id"], choices=["ла", "о"])
    result = post(client, f"/sessions/{session['id']}/finish", admin)
    assert result["total"] == 1 and result["correct"] == 0 and len(result["mistakes"]) == 1
    assert not result["complete"]
    assert client.get(f"/api/profiles/{profile_id}", headers=admin).json()["active_session"] is None
    assert client.post(f"/api/sessions/{session['id']}/answers", headers=admin,
                       json={"item_id": items[1]["id"], "choices": [""]}).status_code == 409
    post(client, f"/profiles/{profile_id}/sessions", admin, list_id=list_id, item_ids=[items[1]["id"]])


def test_resume_cursor_choices_and_feedback(client, admin):
    _, list_id, profile_id, items = setup_training(client, admin, raw="с(ло,ла)в(о,а)\nграм(,м)ота")
    session = post(client, f"/profiles/{profile_id}/sessions", admin, list_id=list_id, item_ids=[i["id"] for i in items])
    # Answer in server order, then advance to the second task.
    first_id = session["items"][0]["id"]
    answers = ["ло", "о"] if first_id == items[0]["id"] else [""]
    post(client, f"/sessions/{session['id']}/answers", admin, item_id=first_id, choices=answers)
    saved = client.get(f"/api/sessions/{session['id']}", headers=admin).json()
    assert saved["choices"] == answers and saved["feedback"]["complete"] and saved["index"] == 0
    saved = post(client, f"/sessions/{session['id']}/advance", admin, item_id=first_id)
    assert saved["index"] == 1 and not saved["choices"] and saved["answered"] == 1
    if saved["items"][1]["id"] == items[0]["id"]:
        post(client, f"/sessions/{session['id']}/answers", admin, item_id=items[0]["id"], choices=["ла"])
        saved = client.get(f"/api/sessions/{session['id']}", headers=admin).json()
        assert saved["choices"] == ["ла"]
        assert saved["feedback"] == {"complete": False, "correct": False, "results": [False], "correct_answers": ["ло"]}
    assert client.post(f"/api/sessions/{session['id']}/advance", headers=admin,
                       json={"item_id": saved["items"][1]["id"]}).status_code == 409


def test_combined_lists_and_category_validation(client, admin):
    folder_id, list_id, profile_id, items = setup_training(client, admin, raw="[без удвоения] грам(,м)ота")
    other = post(client, f"/folders/{folder_id}/lists", admin, name="Слитно или раздельно", raw="По( ,)этому")
    post(client, f"/profiles/{profile_id}/lists", admin, list_id=other["id"])
    other_items = client.get(f"/api/lists/{other['id']}", headers=admin).json()["items"]
    session = post(client, f"/profiles/{profile_id}/sessions", admin, list_ids=[list_id, other["id"]],
                   item_ids=[items[0]["id"], other_items[0]["id"]])
    assert len(session["items"]) == 2 and session["list_ids"] == [list_id, other["id"]]
    assert next(i for i in session["items"] if i["id"] == items[0]["id"])["explanation"] == "без удвоения"
    post(client, f"/sessions/{session['id']}/answers", admin, item_id=items[0]["id"], choices=[""])
    post(client, f"/sessions/{session['id']}/answers", admin, item_id=other_items[0]["id"], choices=[" "])
    result = post(client, f"/sessions/{session['id']}/finish", admin)
    assert result["correct"] == 2 and result["category"] == "spelling"
    profile = client.get(f"/api/profiles/{profile_id}", headers=admin).json()
    assert [l["correct"] for l in profile["lists"]] == [1, 1]
    folder = post(client, "/folders", admin, name="Ударения", category="stress")
    stress = post(client, f"/folders/{folder['id']}/lists", admin, name="Ударения", raw="тОрт")
    post(client, f"/profiles/{profile_id}/lists", admin, list_id=stress["id"])
    assert client.post(f"/api/profiles/{profile_id}/sessions", headers=admin,
                       json={"list_ids": [list_id, stress["id"]], "item_ids": [items[0]["id"]]}).status_code == 422


def test_empty_early_finish(client, admin):
    _, list_id, profile_id, items = setup_training(client, admin)
    session = post(client, f"/profiles/{profile_id}/sessions", admin, list_id=list_id, item_ids=[items[0]["id"]])
    result = post(client, f"/sessions/{session['id']}/finish", admin)
    assert result["total"] == result["correct"] == 0 and result["mistakes"] == []


def test_partial_feedback_is_restored_and_unfinished_word_not_counted(client, admin):
    _, list_id, profile_id, items = setup_training(client, admin, raw="с(ло,ла)в(о,а)")
    session = post(client, f"/profiles/{profile_id}/sessions", admin, list_id=list_id, item_ids=[items[0]["id"]])
    post(client, f"/sessions/{session['id']}/answers", admin, item_id=items[0]["id"], choices=["ла"])
    saved = client.get(f"/api/sessions/{session['id']}", headers=admin).json()
    assert saved["index"] == 0 and saved["choices"] == ["ла"]
    assert saved["feedback"] == {"correct": False, "complete": False, "results": [False], "correct_answers": ["ло"]}
    result = post(client, f"/sessions/{session['id']}/finish", admin)
    assert result["total"] == 0 and result["mistakes"] == []
