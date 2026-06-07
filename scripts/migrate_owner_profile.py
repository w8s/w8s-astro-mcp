#!/usr/bin/env python3
"""Migration: rename current_profile_id → owner_profile_id in app_settings.

Run once against any existing database created before this change.
Safe to run multiple times — detects if migration is already applied.

Usage:
    python scripts/migrate_owner_profile.py
    python scripts/migrate_owner_profile.py --db-path /path/to/custom.db
"""

import argparse
import sqlite3
import sys
from pathlib import Path


def get_default_db_path() -> Path:
    return Path.home() / ".w8s-astro-mcp" / "astro.db"


def migrate(db_path: Path) -> None:
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        print("Nothing to migrate.")
        return

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        # Check current columns in app_settings
        cursor.execute("PRAGMA table_info(app_settings)")
        columns = {row[1] for row in cursor.fetchall()}

        if "owner_profile_id" in columns:
            print("Migration already applied — owner_profile_id column exists.")
            return

        if "current_profile_id" not in columns:
            print("Neither current_profile_id nor owner_profile_id found.")
            print("app_settings table may not exist yet — no migration needed.")
            return

        print(f"Migrating: {db_path}")
        print("  Renaming current_profile_id → owner_profile_id ...")

        # SQLite doesn't support RENAME COLUMN before 3.25.0.
        # Use the safe table-rebuild approach for compatibility.
        cursor.executescript("""
            BEGIN;

            CREATE TABLE app_settings_new (
                id INTEGER PRIMARY KEY DEFAULT 1,
                owner_profile_id INTEGER REFERENCES profiles(id) ON DELETE SET NULL
            );

            INSERT INTO app_settings_new (id, owner_profile_id)
            SELECT id, current_profile_id FROM app_settings;

            DROP TABLE app_settings;

            ALTER TABLE app_settings_new RENAME TO app_settings;

            CREATE INDEX IF NOT EXISTS ix_app_settings_owner_profile_id
                ON app_settings (owner_profile_id);

            COMMIT;
        """)

        print("  ✓ Migration complete.")

    except Exception as e:
        conn.rollback()
        print(f"  ✗ Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to SQLite database (default: ~/.w8s-astro-mcp/astro.db)"
    )
    args = parser.parse_args()

    db_path = args.db_path or get_default_db_path()
    migrate(db_path)
