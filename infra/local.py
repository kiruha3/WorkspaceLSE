"""Project-local development runtime; never touches existing databases or services.

Run with backend/.venv/Scripts/python.exe. PostgreSQL binaries belong in
.runtime/postgresql (Windows portable distribution); all state stays ignored.
"""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
DATA = RUNTIME / "postgresql-data"
CONNECTION = RUNTIME / "postgresql-connection.json"
BIN = RUNTIME / "postgresql" / "bin"


def connection():
    if not CONNECTION.exists():
        raise SystemExit("Run db-start first; project connection settings are missing.")
    return json.loads(CONNECTION.read_text(encoding="utf-8"))


def run_pg(program, *args, check=True):
    executable = BIN / (program + (".exe" if os.name == "nt" else ""))
    return subprocess.run(
        [str(executable), *map(str, args)], check=check,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def db_start():
    import psycopg
    from psycopg import sql

    RUNTIME.mkdir(exist_ok=True)
    if not (DATA / "PG_VERSION").exists():
        if DATA.exists() and any(DATA.iterdir()):
            raise SystemExit("Data directory is not empty; refusing to overwrite it.")
        if not CONNECTION.exists():
            CONNECTION.write_text(json.dumps({
                "host": "127.0.0.1", "port": 55432, "dbname": "ais_lse",
                "user": "ais_lse", "password": secrets.token_urlsafe(32),
                "django_secret": secrets.token_urlsafe(64),
            }), encoding="utf-8")
        config = connection()
        password_file = RUNTIME / "initdb-password"
        password_file.write_text(config["password"], encoding="utf-8")
        try:
            run_pg("initdb", "-D", DATA, "-U", config["user"], "--encoding=UTF8",
                   "--locale=C", "--auth-host=scram-sha-256", "--auth-local=scram-sha-256",
                   f"--pwfile={password_file}")
        finally:
            password_file.unlink(missing_ok=True)
    config = connection()
    if run_pg("pg_ctl", "-D", DATA, "status", check=False).returncode:
        run_pg("pg_ctl", "-D", DATA, "-l", RUNTIME / "postgresql.log", "-o",
               f"-h 127.0.0.1 -p {config['port']} -c shared_buffers=32MB -c max_connections=30",
               "start", "-w", "-t", "30")
    credentials = {key: value for key, value in config.items() if key != "django_secret"}
    credentials["dbname"] = "postgres"
    with psycopg.connect(**credentials, autocommit=True, connect_timeout=3) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (config["dbname"],)).fetchone():
            conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(config["dbname"])))
    print(f"Project PostgreSQL ready on 127.0.0.1:{config['port']}; database {config['dbname']}.")


def backend(args):
    config = connection()
    env = os.environ.copy()
    env.update({"PGHOST": config["host"], "PGPORT": str(config["port"]),
                "PGDATABASE": config["dbname"], "PGUSER": config["user"],
                "PGPASSWORD": config["password"], "DJANGO_SECRET_KEY": config["django_secret"],
                "DJANGO_DEBUG": "1"})
    return subprocess.call([sys.executable, *args], cwd=ROOT / "backend", env=env)


if __name__ == "__main__":
    command, *arguments = sys.argv[1:]
    if command == "db-start":
        db_start()
    elif command == "db-status":
        sys.exit(run_pg("pg_ctl", "-D", DATA, "status", check=False).returncode)
    elif command == "db-stop":
        run_pg("pg_ctl", "-D", DATA, "stop", "-m", "fast", "-w", "-t", "30")
    elif command == "backend":
        sys.exit(backend(arguments))
    else:
        raise SystemExit("Commands: db-start, db-status, db-stop, backend <python arguments>")
