"""Portable, one-time demo initialization; never replace an existing database."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import threading
import uuid
from src.simulate import ROOT

_LOCK = threading.Lock()
SEED = ROOT / 'demo_seed' / 'demo.sqlite3'

def initialize_demo(destination, seed=SEED):
    destination = Path(destination)
    with _LOCK:
        if destination.exists():
            return destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            with closing(sqlite3.connect(Path(seed).resolve().as_uri() + '?mode=ro', uri=True)) as source:
                with closing(sqlite3.connect(temporary)) as target:
                    source.backup(target)
                    if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise RuntimeError('Demo seed failed integrity check')
            # Atomic no-overwrite publication, including concurrent processes.
            try:
                os.link(temporary, destination)
            except FileExistsError:
                pass
        finally:
            temporary.unlink(missing_ok=True)
    return destination

def demo_database():
    override = os.environ.get('INTERACTIVE_DEMO_DB')
    if override:
        return Path(override)  # Existing local/test workflows retain their exact semantics.
    legacy = ROOT / 'runtime' / 'final_connected_demo.sqlite3'
    if legacy.exists():
        return legacy  # Never replace an existing local demonstration.
    return initialize_demo(ROOT / 'runtime' / 'cloud_demo.sqlite3')
