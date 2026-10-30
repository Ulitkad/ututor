"""Idempotent upgrades for databases created before format v2."""
import re

from sqlalchemy import inspect, select, text

from . import models as m


def migrate(engine, db):
    columns = {c["name"] for c in inspect(engine).get_columns("training_sessions")}
    with engine.begin() as conn:
        # Legacy sessions could not be resumed: they must not block new rounds.
        for name, declaration in {
            "status": "VARCHAR NOT NULL DEFAULT 'finished'",
            "context": "JSON NOT NULL DEFAULT '{}'",
            "cursor": "INTEGER NOT NULL DEFAULT 0",
        }.items():
            if name not in columns:
                conn.execute(text(f"ALTER TABLE training_sessions ADD COLUMN {name} {declaration}"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS one_active_training_per_profile "
                          "ON training_sessions (profile_id) WHERE status = 'active'"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_versions (name VARCHAR PRIMARY KEY)"))
        if conn.scalar(text("SELECT name FROM schema_versions WHERE name = 'literal_spaces_v2'")):
            return
    # Rewrite old source only. Keep structured answers, IDs and Progress intact.
    for item in db.scalars(select(m.Item).join(m.TaskList).join(m.Folder).where(m.Folder.category == "spelling")):
        item.source = re.sub(r"\(([^()]*)\)", lambda match: "(" + ",".join(v.strip() for v in match[1].split(",")) + ")", item.source)
    db.execute(text("INSERT INTO schema_versions (name) VALUES ('literal_spaces_v2')"))
    db.commit()
