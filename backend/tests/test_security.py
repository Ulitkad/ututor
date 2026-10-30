import pytest

from app import auth
from test_api import post, setup_training


def test_cannot_train_foreign_or_unattached_items(client, admin, teacher):
    _, list_id, profile_id, items = setup_training(client, admin)
    own = post(client, "/profiles", teacher, name="Своя группа", kind="group")
    assert client.post(f"/api/profiles/{own['id']}/lists", headers=teacher, json={"list_id": list_id}).status_code == 404
    assert client.post(f"/api/profiles/{profile_id}/sessions", headers=teacher, json={"list_id": list_id, "item_ids": [items[0]["id"]]}).status_code == 404
    assert client.post(f"/api/profiles/{profile_id}/sessions", headers=admin, json={"list_id": list_id, "item_ids": [999999]}).status_code == 422
    session = post(client, f"/profiles/{profile_id}/sessions", admin, list_id=list_id, item_ids=[items[0]["id"]])
    assert client.get(f"/api/sessions/{session['id']}/results", headers=teacher).status_code == 404
    assert client.post(f"/api/sessions/{session['id']}/answers", headers=admin, json={"item_id": items[0]["id"], "choices": ["not-an-option"]}).status_code == 422


def test_same_origin_cookie_endpoints(client, admin):
    assert client.post("/api/auth/refresh", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.post("/api/auth/logout", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403


def test_login_rate_limit(client):
    auth.login_attempts.clear()
    try:
        for _ in range(20):
            assert client.post("/api/auth/login", json={"username": "missing", "password": "wrong"}).status_code == 401
        assert client.post("/api/auth/login", json={"username": "missing", "password": "wrong"}).status_code == 429
    finally:
        auth.login_attempts.clear()


def test_duplicate_username_and_blank_name(client, admin):
    assert client.post("/api/teachers", headers=admin, json={"username": "admin", "name": "Admin"}).status_code == 409
    assert client.post("/api/teachers", headers=admin, json={"username": "blank", "name": " "}).status_code == 422
