import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
import pytest


@pytest.fixture
def runtime_copy(tmp_path):
    (tmp_path/"infra").mkdir();(tmp_path/"backend").mkdir();(tmp_path/".runtime").mkdir()
    script=tmp_path/"infra"/"local.py"
    shutil.copy2(Path(__file__).resolve().parents[2]/"infra"/"local.py",script)
    config={"host":"127.0.0.1","port":55432,"dbname":"DEMO_db","user":"DEMO_user","password":"DEMO-private-sentinel","django_secret":"DEMO-secret-sentinel","web_hosts":["127.0.0.1"]}
    path=tmp_path/".runtime"/"postgresql-connection.json";path.write_text(json.dumps(config),encoding="utf-8")
    def run(*args):
        return subprocess.run([sys.executable,str(script),*args],capture_output=True,text=True,encoding="utf-8",env={**os.environ,"PYTHONUTF8":"1"},timeout=10)
    return run,path,config


def test_source_runtime_command_preserves_credentials_and_forwards_only_configured_source(runtime_copy):
    run,path,original=runtime_copy
    result=run("journal-source","DEMO_sheet_123","0","Лист1")
    assert result.returncode==0
    assert "DEMO-private-sentinel" not in result.stdout+result.stderr
    assert json.loads(path.read_text(encoding="utf-8"))=={**original,"journal_source":{"spreadsheet_id":"DEMO_sheet_123","gid":"0","sheet_name":"Лист1"}}
    probe=run("backend","-c","import json,os; print(json.dumps([os.getenv('AIS_JOURNAL_GOOGLE_ID'),os.getenv('AIS_JOURNAL_GOOGLE_GID'),os.getenv('AIS_JOURNAL_GOOGLE_SHEET_NAME')]))")
    assert probe.returncode==0 and json.loads(probe.stdout)==["DEMO_sheet_123","0","Лист1"]


@pytest.mark.parametrize("args",[("https://other.invalid","0","Лист1"),("DEMO_sheet_123","0&bad=1","Лист1"),("DEMO_sheet_123","0",""),()])
def test_invalid_source_runtime_command_leaves_existing_configuration_intact(runtime_copy,args):
    run,path,original=runtime_copy
    assert run("journal-source","DEMO_sheet_123","0","Лист1").returncode==0
    before=path.read_bytes()
    result=run("journal-source",*args)
    assert result.returncode!=0 and path.read_bytes()==before


def test_unconfigured_source_is_not_inherited_from_unrelated_environment(runtime_copy,monkeypatch):
    run,_,_=runtime_copy
    monkeypatch.setenv("AIS_JOURNAL_GOOGLE_ID","UNRELATED_sheet_123")
    probe=run("backend","-c","import os; print(repr(os.getenv('AIS_JOURNAL_GOOGLE_ID')))")
    assert probe.returncode==0 and probe.stdout.strip()=="''"
