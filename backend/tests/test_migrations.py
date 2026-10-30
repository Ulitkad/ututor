from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app import models as m
from app.database import Base
from app.migrations import migrate


def test_legacy_spaces_migrate_once_without_losing_progress(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(m.User(id=1, username="teacher", name="Учитель", password_hash="unused"))
        db.add(m.Folder(id=1, owner_id=1, category="spelling", name="Папка"))
        db.add(m.TaskList(id=1, folder_id=1, name="Старый список"))
        db.add(m.Profile(id=1, owner_id=1, name="Ученик"))
        data = {"parts": [{"text": "опас"}, {"hint": "", "options": ["", "т"], "correct": ""}, {"text": "ный"}]}
        db.add(m.Item(id=1, list_id=1, position=0, source="опас( ,т)ный", data=data))
        db.add(m.Progress(profile_id=1, item_id=1, correct=True, attempts=4))
        db.commit()
        migrate(engine, db)
        db.expire_all()
        item = db.get(m.Item, 1)
        assert item.source == "опас(,т)ный" and item.data == data
        progress = db.scalar(select(m.Progress))
        assert progress.item_id == 1 and progress.correct and progress.attempts == 4
        item.source = "По( ,)этому"  # New format must never be migrated again.
        db.commit()
        migrate(engine, db)
        db.expire_all()
        assert db.get(m.Item, 1).source == "По( ,)этому"
    engine.dispose()


def test_old_session_schema_upgrade(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE training_sessions (id VARCHAR PRIMARY KEY, profile_id INTEGER)"))
        conn.execute(text("INSERT INTO training_sessions VALUES ('legacy', 1)"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        migrate(engine, db)
        row = db.execute(text("SELECT status, context, cursor FROM training_sessions")).one()
        assert row == ("finished", "{}", 0)
        migrate(engine, db)
    engine.dispose()


def test_active_session_locks_migrated_from_profile_to_lists(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'active.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(m.TrainingSession(id="saved", profile_id=1, list_id=10, items=[], answers={},
                                 context={"list_ids": [10, 20]}, status="active"))
        db.commit()
        with engine.begin() as conn:
            conn.execute(text("CREATE UNIQUE INDEX one_active_training_per_profile ON training_sessions (profile_id) WHERE status = 'active'"))
        migrate(engine, db)
        locks = list(db.scalars(select(m.TrainingListLock).order_by(m.TrainingListLock.list_id)))
        assert [(lock.profile_id, lock.list_id, lock.session_id) for lock in locks] == [(1, 10, "saved"), (1, 20, "saved")]
        assert db.get(m.TrainingSession, "saved").status == "active"
        # The old unique index is gone: a disjoint session can coexist.
        db.add(m.TrainingSession(id="other", profile_id=1, list_id=30, items=[], answers={}, context={"list_ids": [30]}))
        db.commit()
        migrate(engine, db)
        assert len(list(db.scalars(select(m.TrainingListLock)))) == 2  # Backfill is one-time.
    engine.dispose()
