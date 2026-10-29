"""Isolate potentially blocking SMB IO in a short-lived, bounded child process."""
import os
from pathlib import Path
import subprocess
import sys


def probe_directory(path):
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name('_storage_probe_worker.py')), path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            timeout=5, creationflags=flags,
        )
    except subprocess.TimeoutExpired:
        # subprocess.run kills and reaps the child before re-raising.
        return 'timeout'
    except OSError:
        return 'unavailable'
    return 'available' if result.returncode == 0 and result.stdout == 'available' else 'unavailable'
