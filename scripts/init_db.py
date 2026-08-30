"""
Apply schema.sql to the database named in .env.

Does the same job as `mysql < schema.sql` but through mysql-connector, so
no MySQL command-line client needs to be installed.

    python scripts/init_db.py           # create tables, keep existing ones
    python scripts/init_db.py --drop    # DROP every table first, then recreate

Aiven, PlanetScale and most hosted MySQL providers require TLS. This
connects with TLS enabled and no CA pinning, which is what those
providers expect out of the box.
"""

import argparse
import os
import re
import sys

from dotenv import load_dotenv

import mysql.connector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(ROOT, "schema.sql")

load_dotenv(os.path.join(ROOT, ".env"))


def connect():
    cfg = dict(
        host=os.environ.get("MYSQL_HOST"),
        user=os.environ.get("MYSQL_USER"),
        password=os.environ.get("MYSQL_PASSWORD"),
        database=os.environ.get("MYSQL_DATABASE"),
        port=int(os.environ.get("MYSQL_PORT", 3306)),
        connection_timeout=30,
    )
    missing = [k for k in ("host", "user", "database") if not cfg[k]]
    if missing:
        sys.exit(f"Missing in .env: {', '.join(m.upper() for m in missing)}")

    print(f"Connecting to {cfg['host']}:{cfg['port']}/{cfg['database']} ...")
    try:
        # ssl_disabled defaults to False, so TLS is negotiated when the
        # server offers it. Hosted providers require this.
        return mysql.connector.connect(**cfg)
    except mysql.connector.Error as exc:
        sys.exit(
            f"\nCould not connect: {exc}\n\n"
            "Check that MYSQL_HOST / PORT / USER / PASSWORD / DATABASE in .env\n"
            "match the connection details from your provider, and that the\n"
            "service has finished starting up."
        )


def split_statements(sql):
    """Strip -- comments and split on semicolons."""
    lines = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or not stripped:
            continue
        lines.append(line)
    body = "\n".join(lines)
    return [s.strip() for s in body.split(";") if s.strip()]


def existing_tables(cur):
    cur.execute("SHOW TABLES")
    return [r[0] for r in cur.fetchall()]


def drop_all(cur):
    tables = existing_tables(cur)
    if not tables:
        print("Nothing to drop.")
        return
    print(f"Dropping {len(tables)} existing tables ...")
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for t in tables:
        cur.execute(f"DROP TABLE IF EXISTS `{t}`")
        print(f"  dropped {t}")
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")


def main():
    parser = argparse.ArgumentParser(description="Apply schema.sql to the configured database.")
    parser.add_argument("--drop", action="store_true",
                        help="DROP all existing tables before applying the schema.")
    args = parser.parse_args()

    if not os.path.exists(SCHEMA_PATH):
        sys.exit(f"schema.sql not found at {SCHEMA_PATH}")

    with open(SCHEMA_PATH, encoding="utf-8") as f:
        statements = split_statements(f.read())

    cn = connect()
    cur = cn.cursor()

    try:
        if args.drop:
            drop_all(cur)

        print(f"\nApplying {len(statements)} statements from schema.sql ...")
        created = 0
        for stmt in statements:
            cur.execute(stmt)
            # Drain any result so the connection stays usable.
            try:
                cur.fetchall()
            except mysql.connector.Error:
                pass
            match = re.search(r"CREATE TABLE IF NOT EXISTS `?(\w+)`?", stmt)
            if match:
                created += 1
                print(f"  {match.group(1)}")
        cn.commit()

        tables = existing_tables(cur)
        print(f"\nDone. {created} CREATE statements applied; "
              f"{len(tables)} tables now in the database.")
        if len(tables) != 21:
            print(f"WARNING: expected 21 tables, found {len(tables)}.")
        print("\nNext:  python scripts/seed_demo.py")
    except mysql.connector.Error as exc:
        cn.rollback()
        sys.exit(f"\nFailed while applying schema: {exc}")
    finally:
        cur.close()
        cn.close()


if __name__ == "__main__":
    main()
