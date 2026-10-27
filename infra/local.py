"""Project-local development runtime; never touches existing databases or services.

Run with backend/.venv/Scripts/python.exe. PostgreSQL binaries belong in
.runtime/postgresql (Windows portable distribution); all state stays ignored.
"""
import json
import os
from pathlib import Path
import secrets
import re
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


def backend(args, extra_env=None):
    config = connection()
    env = os.environ.copy()
    env.update({"PGHOST": config["host"], "PGPORT": str(config["port"]),
                "PGDATABASE": config["dbname"], "PGUSER": config["user"],
                "PGPASSWORD": config["password"], "DJANGO_SECRET_KEY": config["django_secret"],
                "DJANGO_DEBUG": "1", "PYTHONUTF8":"1"})
    env["CSRF_TRUSTED_ORIGINS"] = ",".join(
        f"http://{host}:5173" for host in config.get("web_hosts",["127.0.0.1","localhost"]))
    journal=config.get("journal_source",{})
    env.update({"AIS_JOURNAL_GOOGLE_ID":journal.get("spreadsheet_id",""),"AIS_JOURNAL_GOOGLE_GID":journal.get("gid","0"),"AIS_JOURNAL_GOOGLE_SHEET_NAME":journal.get("sheet_name","Лист1")})
    env.update(extra_env or {})
    return subprocess.call([sys.executable, *args], cwd=ROOT / "backend", env=env)


def bootstrap(args):
    login_file = RUNTIME / "local-login.json"
    if login_file.exists():
        login = json.loads(login_file.read_text(encoding="utf-8"))
    else:
        login = {"username":"setup","password":secrets.token_urlsafe(24)}
        login_file.write_text(json.dumps(login),encoding="utf-8")
    return backend(["manage.py","bootstrap_access","--username",login["username"],
                    "--full-name","Ответственный за настройку","--no-input",*args],
                   {"AIS_BOOTSTRAP_PASSWORD":login["password"]})


def workflow_demo(args):
    login_file=RUNTIME / "workflow-demo-login.json"
    if login_file.exists():login=json.loads(login_file.read_text(encoding="utf-8"))
    else:
        login={"password":secrets.token_urlsafe(24),"usernames":["demo.clerk","demo.head3","demo.expert","demo.expert2","demo.trainee"]}
        login_file.write_text(json.dumps(login),encoding="utf-8")
    result=backend(["manage.py","bootstrap_workflow_demo",*args],{"AIS_DEMO_PASSWORD":login["password"]})
    if result==0:
        (RUNTIME / "Демо-доступ-к-АИС.txt").write_text(
            "АИС ФГБУ Абаканская ЛСЭ — учебные профили\nhttp://127.0.0.1:5173/\nhttp://185.112.226.84:5173/\n\n"
            "demo.clerk — приёмка и ручная регистрация\ndemo.head3 — назначение/перепоручение отдела 3\n"
            "demo.expert / demo.expert2 — квалифицированные учебные эксперты 1.1\ndemo.trainee — обучение 1.1, назначение запрещено\n\n"
            "Пароль учебных профилей: "+login["password"]+"\n\nНе персональные аккаунты сотрудников, не использовать для реальных дел.\n"
            "Учётная запись setup и её пароль сохранены отдельно в Доступ-к-АИС.txt.\n",encoding="utf-8")
        print("Demo credentials saved to .runtime/Демо-доступ-к-АИС.txt (ignored by Git).")
    return result


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
    elif command == "bootstrap":
        sys.exit(bootstrap(arguments))
    elif command == "workflow-demo":
        sys.exit(workflow_demo(arguments))
    elif command == "web-hosts":
        if not arguments or any(not re.fullmatch(r"[A-Za-z0-9.-]+",host) for host in arguments):
            raise SystemExit("Pass IPv4 addresses or hostnames, without protocol or port.")
        config = connection()
        config["web_hosts"] = list(dict.fromkeys(["127.0.0.1","localhost",*arguments]))
        CONNECTION.write_text(json.dumps(config),encoding="utf-8")
        print("Web origins saved; restart Django to apply. No database credentials changed.")
    elif command == "journal-source":
        if len(arguments)!=3 or not re.fullmatch(r"[A-Za-z0-9_-]{10,200}",arguments[0]) or not re.fullmatch(r"\d{1,10}",arguments[1]) or not arguments[2].strip():
            raise SystemExit("Pass spreadsheet ID, numeric gid and exact sheet name. Google is read-only.")
        config=connection()
        config["journal_source"]={"spreadsheet_id":arguments[0],"gid":arguments[1],"sheet_name":arguments[2].strip()}
        CONNECTION.write_text(json.dumps(config),encoding="utf-8")
        print("Read-only journal source saved; restart Django to apply. No Google or business data changed.")
    else:
        raise SystemExit("Commands: db-start, db-status, db-stop, web-hosts <hosts>, journal-source <id> <gid> <sheet>, bootstrap [options], backend <python arguments>")
