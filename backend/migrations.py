"""Additive schema migrations.

New tables are created by ``Base.metadata.create_all``. Columns added to tables that
already exist in a deployed database are applied here as nullable or defaulted
``ALTER TABLE ... ADD COLUMN`` statements, so existing rows are kept. Each step is
idempotent and recorded in ``schema_migrations``.
"""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

# (migration id, table, column, column DDL)
COLUMN_MIGRATIONS = [
    ("r3_001", "content_items", "created_by_user_id", "VARCHAR(36)"),
    ("r3_002", "content_items", "media_kind", "VARCHAR(10) NOT NULL DEFAULT 'text'"),
    ("r3_003", "content_items", "approved_version_id", "VARCHAR(36)"),
    ("r3_004", "review_decisions", "reviewer_user_id", "VARCHAR(36)"),
    ("r3_005", "review_decisions", "evidence_confirmed", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("r3_006", "findings", "region_json", "TEXT"),
    ("r3_007", "brands", "palette_json", "TEXT"),
]


def run_migrations(engine: Engine) -> list:
    applied = []
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (id VARCHAR(40) PRIMARY KEY)"))
        done = {row[0] for row in conn.execute(text("SELECT id FROM schema_migrations"))}
        insp = inspect(conn)
        for mig_id, table, column, ddl in COLUMN_MIGRATIONS:
            if mig_id in done:
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            if column not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
            conn.execute(text("INSERT INTO schema_migrations (id) VALUES (:id)"), {"id": mig_id})
            applied.append(mig_id)
    return applied
