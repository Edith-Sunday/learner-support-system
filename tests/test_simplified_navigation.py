"""Focused checks for the simplified navigation and read-only evaluation surface."""
from streamlit.testing.v1 import AppTest
from src.interactive_store import InteractiveStore
from src.seed_final_demo import answers
from src.chemistry_content import PRACTICE, QUIZ
from src.simulate import ROOT


def test_navigation_waiting_and_readonly_samples(tmp_path,monkeypatch):
    store=InteractiveStore(tmp_path/'ui.sqlite3','2026-10-01T08:00Z')
    sid=store.enrol()
    store.submit(sid,'practice',answers(PRACTICE),'p')
    store.submit(sid,'quiz',answers(QUIZ),'q')
    monkeypatch.setenv('INTERACTIVE_DEMO_DB',str(store.path))
    app=AppTest.from_file(str(ROOT/'dashboard.py'),default_timeout=60).run()
    assert app.sidebar.radio[0].options==['All learners','Needs attention','Support messages','Model evaluation']
    assert not any(s.label=='Cohort' for s in app.selectbox)
    app.sidebar.radio[0].set_value('Model evaluation').run()
    assert not app.exception
    assert any(e.label=='Sample learner data' for e in app.expander)
    assert any(e.label=='Pilot evaluation' for e in app.expander)
    assert not any(b.label in ['Send demo message','Allow extra attempts','Save follow-up'] for b in app.button)
    assert len(store.learners())==1
    app.segmented_control[0].set_value('Learner').run()
    assert app.sidebar.radio[0].options==['My learning','Lesson','Practice','Quiz and results','My support']
    assert any('Module 1 complete. Module 2 is not available yet.' in x.value for x in app.info)
    visible=' '.join(x.value for x in app.caption)
    assert 'assessment' not in visible.lower() and 'seeded' not in visible.lower()
    app.sidebar.radio[0].set_value('My support').run()
    assert any(e.label=='Request help' for e in app.expander)
    assert any(e.label=='Communication preference' for e in app.expander)
    assert not app.exception
