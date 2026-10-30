from sqlalchemy import select

from app import models as m
from app.database import SessionLocal
from test_api import post, setup_training


def test_existing_items_and_saved_sessions_get_layout_without_changing_answers(client, admin):
    raw = "Установка [тест] оборудования (сберечь|сбережёт,сберегёт) здоровье. [конец]"
    _, list_id, profile_id, items = setup_training(client, admin, category="grammar", raw=raw)
    item_id = items[0]["id"]
    session = post(client, f"/profiles/{profile_id}/sessions", admin, list_id=list_id, item_ids=[item_id])
    expected = items[0]["layout"]
    assert session["items"][0]["layout"] == expected
    # Emulate persisted items and a session created before positional rendering.
    with SessionLocal() as db:
        saved = db.get(m.TrainingSession, session["id"])
        context = dict(saved.context)
        context["public_items"] = [{k: v for k, v in item.items() if k != "layout"} for item in context["public_items"]]
        saved.context = context
        before_data = dict(db.get(m.Item, item_id).data)
        before_snapshot = saved.items
        db.commit()
    loaded = client.get(f"/api/lists/{list_id}", headers=admin).json()["items"][0]
    assert loaded["id"] == item_id and loaded["data"] == before_data
    assert loaded["layout"] == expected
    resumed = client.get(f"/api/sessions/{session['id']}", headers=admin).json()
    assert resumed["items"][0]["layout"] == expected
    assert resumed["items"][0]["parts"] == session["items"][0]["parts"]  # Same shuffled options.
    post(client, f"/sessions/{session['id']}/answers", admin, item_id=item_id, choices=["сбережёт"])
    with SessionLocal() as db:
        assert db.get(m.TrainingSession, session["id"]).items == before_snapshot
        assert db.scalar(select(m.Progress).where(m.Progress.item_id == item_id)).correct


def test_mistake_results_preserve_annotation_position(client, admin):
    _, list_id, profile_id, items = setup_training(client, admin, raw="грам[тест](,м)ота [конец]")
    session = post(client, f"/profiles/{profile_id}/sessions", admin, list_id=list_id, item_ids=[items[0]["id"]])
    post(client, f"/sessions/{session['id']}/answers", admin, item_id=items[0]["id"], choices=["м"])
    result = post(client, f"/sessions/{session['id']}/finish", admin)
    mistake = result["mistakes"][0]
    assert mistake["layout"] == items[0]["layout"]
    assert mistake["solution"] == "грамота"
