import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database import SpellDatabase


TARGET = "Player's Handbook (2024)"


def normalize_source(value: str) -> str:
    if value is None:
        return ""
    return value.strip().lower().replace("’", "'")


def main():
    db = SpellDatabase()
    db.initialize()

    updated = 0
    unchanged = 0

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, source FROM spells")
        rows = cursor.fetchall()

        for row in rows:
            current = row["source"] or ""
            if normalize_source(current) == "player's handbook":
                cursor.execute(
                    "UPDATE spells SET source = ? WHERE id = ?",
                    (TARGET, row["id"]),
                )
                updated += 1
            else:
                unchanged += 1

    print({
        "updated": updated,
        "unchanged": unchanged,
        "target": TARGET,
    })


if __name__ == "__main__":
    main()
