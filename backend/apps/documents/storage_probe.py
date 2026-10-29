"""Isolate potentially blocking SMB IO in a short-lived, bounded child process."""
import os
from pathlib import Path
import subprocess
import sys


def probe_directory(path):
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    # Windows venv executables are redirectors that spawn the base interpreter.
    # The worker uses only stdlib: launch it directly, so timeout kills the
    # actual IO process rather than leaving a blocked grandchild behind.
    interpreter = getattr(sys, '_base_executable', None) or sys.executable
    try:
        result = subprocess.run(
            [interpreter, str(Path(__file__).with_name('_storage_probe_worker.py')), path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            timeout=5, creationflags=flags,
        )
    except subprocess.TimeoutExpired:
        # subprocess.run kills and reaps the child before re-raising.
        return 'timeout'
    except OSError:
        return 'unavailable'
    return 'available' if result.returncode == 0 and result.stdout == 'available' else 'unavailable'
