"""Clean-export startup and seed persistence checks (no training or simulation)."""
import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from streamlit.testing.v1 import AppTest
from src.cloud_demo import SEED, initialize_demo
from src.simulate import ROOT

def test_seed_initialization_is_consistent_and_never_resets(tmp_path):
    before=hashlib.sha256(SEED.read_bytes()).hexdigest()
    target=tmp_path/'demo.sqlite3'
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: initialize_demo(target),range(8)))
    with sqlite3.connect(target) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert db.execute('SELECT COUNT(*) FROM learners').fetchone()[0]==7
        db.execute("UPDATE demo_clock SET effective_at='2026-10-23T08:00:00+00:00'")
    initialize_demo(target)
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT effective_at FROM demo_clock').fetchone()[0].startswith('2026-10-23')
    assert hashlib.sha256(SEED.read_bytes()).hexdigest()==before

def test_clean_export_all_workflows(monkeypatch):
    # Intended to run in a clean export with no pre-existing runtime directory.
    monkeypatch.delenv('INTERACTIVE_DEMO_DB',raising=False)
    monkeypatch.delenv('LEARNER_DEMO_DB',raising=False)
    from src.cloud_demo import demo_database
    path=demo_database()
    app=AppTest.from_file(str(ROOT/'dashboard.py'),default_timeout=60).run()
    assert not app.exception
    assert app.title[0].value=='All learners'
    app.sidebar.radio[0].set_value('Needs attention').run()
    assert not app.exception
    assert len([b for b in app.button if b.label=='Review and support'])==4
    app.button(key='review-support-DEMO004').click().run()
    assert app.selectbox(key='staff_profile_learner').value=='DEMO004'
    assert any(t.label=='Quiz results' for t in app.tabs)
    assert any(b.label=='Save follow-up' for b in app.button)
    for page in ['Support messages','Model evaluation']:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception
    assert any(e.label=='Saved assessments and selection policy' for e in app.expander)
    app.segmented_control[0].set_value('Learner').run()
    for page in ['Lesson','Practice','Quiz and results','My support']:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM assessment_results').fetchone()[0]==4
        assert db.execute('SELECT COUNT(*) FROM demo_outbox').fetchone()[0]==2
