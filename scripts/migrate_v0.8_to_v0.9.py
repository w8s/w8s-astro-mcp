#!/usr/bin/env python3
"""Migration script: v0.8 -> v0.9

Adds the connection-related tables introduced in v0.9.0 to an existing
~/.w8s-astro-mcp/astro.db database. Safe to run on any v0.8 database —
SQLAlchemy's create_all() skips tables that already exist.

Usage:
    uv run python scripts/migrate_v0.8_to_v0.9.py
    # or
    python scripts/migrate_v0.8_to_v0.9.py
"""

import sys
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from w8s_astro_mcp.database import get_database_path, create_db_engine, create_tables


def main():
    db_path = get_database_path()

    if not db_path.exists():
        print(f"No database found at {db_path}")
        print("Nothing to migrate — run the server once to create a fresh database.")
        sys.exit(0)

    print(f"Migrating {db_path} ...")
    engine = create_db_engine(db_path)
    create_tables(engine)
    print("Done. Connection tables added (existing tables untouched).")


if __name__ == "__main__":
    main()
