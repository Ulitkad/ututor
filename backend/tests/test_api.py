import base64
import os
from pathlib import Path

import jwt

from app import auth


def post(client, path, headers, **data):
    response = client.post(f"/api{path}", headers=headers, json=data)
    assert response.status_code in (200, 201), response.text
    return response.json()


def setup_training(client, headers, category="spelling", raw="мыш(ь, )\nопас( ,т)ный\nс(ло,ла)в(о,а,и,е)"):
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
    response = client.post("/api/import?category=spelling", headers=admin, files={"file": ("test.txt", "мыш(ь, )".encode())})
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
    response = client.put(f"/api/lists/{task_list}", headers=admin, json={"name": "Новое имя", "raw": "мыш(ь, )\nнов(ы,а)й"})
    assert response.status_code == 200
    updated = client.get(f"/api/lists/{task_list}", headers=admin).json()
    assert updated["items"][0]["id"] == items[0]["id"]
    assert client.delete(f"/api/folders/{folder}", headers=admin).status_code == 204
    assert client.get(f"/api/lists/{task_list}", headers=admin).status_code == 404
    assert client.get(f"/api/profiles/{profile}", headers=admin).json()["lists"] == []
