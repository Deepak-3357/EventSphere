"""Apply the checked-in Phase 2 migration and seed data."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import get_connection  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "supabase" / "migrations"
SEED = PROJECT_ROOT / "database" / "seed.sql"


def main():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
                cursor.execute(migration.read_text(encoding="utf-8"))
            cursor.execute(SEED.read_text(encoding="utf-8"))
    print("EventSphere database migration and seed completed.")


if __name__ == "__main__":
    main()
