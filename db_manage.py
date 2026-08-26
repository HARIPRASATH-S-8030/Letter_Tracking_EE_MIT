"""Create or migrate the configured PostgreSQL database without embedded secrets."""

import os

import psycopg2

from letterbox import create_app
from letterbox.extensions import db


def main() -> None:
    app = create_app()
    with app.app_context():
        db.create_all()
        print("Configured database tables are ready.")

    render_url = os.environ.get("RENDER_DATABASE_URL")
    supabase_url = os.environ.get("SUPABASE_DATABASE_URL")
    if not render_url or not supabase_url:
        print("Set RENDER_DATABASE_URL and SUPABASE_DATABASE_URL to migrate between databases.")
        return

    with psycopg2.connect(render_url) as render, psycopg2.connect(supabase_url) as supabase:
        with render.cursor() as source, supabase.cursor() as destination:
            for table in ("users", "letters"):
                source.execute(f"SELECT * FROM {table}")
                rows = source.fetchall()
                if not rows:
                    print(f"{table}: empty")
                    continue
                placeholders = ",".join(["%s"] * len(rows[0]))
                destination.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
                print(f"{table}: {len(rows)} rows migrated")


if __name__ == "__main__":
    main()
