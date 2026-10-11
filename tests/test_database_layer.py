import os
import sys
import unittest
import uuid
from pathlib import Path

from dotenv import load_dotenv
from integration_support import require_integration_database


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
load_dotenv(ROOT / ".env")


class DatabaseIntegrationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_integration_database()

        from app.db import get_connection

        cls.get_connection = staticmethod(get_connection)

    def test_database_tables_and_seed_data(self):
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                for table in ("profiles", "categories", "venues", "events", "registrations", "notifications"):
                    cursor.execute("select to_regclass(%s)", (f"public.{table}",))
                    self.assertEqual(cursor.fetchone()[0], table)

                cursor.execute("select count(*) from profiles")
                self.assertGreaterEqual(cursor.fetchone()[0], 5)

                cursor.execute("select count(*) from events")
                self.assertGreaterEqual(cursor.fetchone()[0], 3)

    def test_duplicate_registration_is_rejected(self):
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("select event_id, student_id from registrations limit 1")
                event_id, student_id = cursor.fetchone()
                with self.assertRaises(Exception):
                    cursor.execute(
                        "insert into registrations (event_id, student_id) values (%s, %s)",
                        (event_id, student_id),
                    )
                connection.rollback()

    def test_basic_crud_round_trip(self):
        category_id = uuid.uuid4()
        name = f"CRUD Category {category_id}"
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "insert into categories (id, name, description) values (%s, %s, %s)",
                    (category_id, name, "Temporary CRUD record"),
                )
                cursor.execute("select name from categories where id = %s", (category_id,))
                self.assertEqual(cursor.fetchone()[0], name)
                cursor.execute("update categories set description = %s where id = %s", ("Updated CRUD record", category_id))
                cursor.execute("select description from categories where id = %s", (category_id,))
                self.assertEqual(cursor.fetchone()[0], "Updated CRUD record")
                cursor.execute("delete from categories where id = %s", (category_id,))
                self.assertEqual(cursor.rowcount, 1)


if __name__ == "__main__":
    unittest.main()
