"""Idempotent upgrades for databases created before format v2."""
import json
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
        conn.execute(text("DROP INDEX IF EXISTS one_active_training_per_profile"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_versions (name VARCHAR PRIMARY KEY)"))
        if not conn.scalar(text("SELECT name FROM schema_versions WHERE name = 'per_list_training_locks'")):
            # Existing active sessions keep their answers and now lock their own
            # source lists instead of the entire profile. Old schema fixtures may
            # have no context until the column upgrade above.
            for session_id, profile_id, context in conn.execute(text("SELECT id, profile_id, context FROM training_sessions WHERE status = 'active'")):
                for list_id in json.loads(context).get("list_ids", []):
                    conn.execute(text("INSERT INTO training_list_locks (profile_id, list_id, session_id) VALUES (:profile, :list, :session)"),
                                 {"profile": profile_id, "list": list_id, "session": session_id})
            conn.execute(text("INSERT INTO schema_versions (name) VALUES ('per_list_training_locks')"))
        if conn.scalar(text("SELECT name FROM schema_versions WHERE name = 'literal_spaces_v2'")):
            return
    # Rewrite old source only. Keep structured answers, IDs and Progress intact.
    for item in db.scalars(select(m.Item).join(m.TaskList).join(m.Folder).where(m.Folder.category == "spelling")):
        item.source = re.sub(r"\(([^()]*)\)", lambda match: "(" + ",".join(v.strip() for v in match[1].split(",")) + ")", item.source)
    db.execute(text("INSERT INTO schema_versions (name) VALUES ('literal_spaces_v2')"))
    db.commit()
