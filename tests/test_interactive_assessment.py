import json
import pandas as pd
import pytest
from src.interactive_store import InteractiveStore, utc
from src.interactive_assessment import AssessmentService
from src.chemistry_content import PRACTICE, QUIZ
from src.simulate import ROOT

START=pd.Timestamp('2026-10-16T08:00:00Z')
TEACHER='Demo staff — Amina'

def answers(questions):
    return {q['id']:','.join(map(str,q['answer'])) if isinstance(q['answer'],tuple) else q['answer'] for q in questions}

def setup(tmp_path):
    store=InteractiveStore(tmp_path/'isolated.sqlite3',START)
    sid=store.enrol()
    return store,sid,AssessmentService(store)

def test_unavailable_content_keeps_audit_but_no_actions(tmp_path):
    store,sid,service=setup(tmp_path)
    store.submit(sid,'practice',answers(PRACTICE),'p')
    store.submit(sid,'quiz',answers(QUIZ),'q')
    module=store.module_history(sid)[1]
    with store.transaction() as db:
        db.execute('INSERT INTO interactive_referrals VALUES(?,?,?,?)',(sid,2,module['deadline'],START.isoformat()))
    store.advance(START+pd.Timedelta(days=40),TEACHER,'Isolated unavailable-content test')
    service.run_due()
    assert not store.overdue() and not service.review_rows()
    assert store.module_history(sid)[1]==module
    assert len(store.read('SELECT * FROM interactive_referrals'))==1
    assert not store.read('SELECT * FROM assessments WHERE module_id=2')
    assert not store.content_available(2)

def test_real_timer_idle_and_clock_jump_no_manufactured_minutes(tmp_path):
    store,sid,service=setup(tmp_path)
    service.start_session(sid,wall=START)
    service.touch_session(sid,wall=START+pd.Timedelta(seconds=30))
    store.advance(START+pd.Timedelta(days=7),TEACHER,'Jump only demo time')
    service.touch_session(sid,end=True,wall=START+pd.Timedelta(seconds=150))
    row=store.read('SELECT * FROM study_sessions')[0]
    assert row['duration_minutes']==2.5 and row['active_minutes']==0.5
    assert service.feature_values(sid,START+pd.Timedelta(days=3),3)['session_length'] is None
    values=service.feature_values(sid,store.clock(),7)
    assert values['session_length']==2.5
    assert values['time_on_task'] is None and values['no_login'] is None
    assert values['failed_or_dropped_sessions'] is None
    assert values['quiz_attempt_count']==0 and values['practice_submitted']==0
    assert 'no_login' in service.unsupported(values)

def test_checkpoint_cutoff_offline_and_immutable_assessments(tmp_path):
    store,sid,service=setup(tmp_path)
    service.run_due()
    assert not store.read('SELECT * FROM assessments')
    store.advance(START+pd.Timedelta(days=3),TEACHER,'First checkpoint')
    service.run_due()
    original=store.read('SELECT * FROM assessments')
    assert len(original)==1 and original[0]['score'] is None
    assert json.loads(original[0]['features'])['practice_submitted']==0
    store.advance(START+pd.Timedelta(days=8),TEACHER,'Missed scheduled day seven')
    store.submit(sid,'practice',None,'offline',occurrence=START+pd.Timedelta(days=2),staff=TEACHER,reason='Delayed evidence')
    service.run_due(); service.run_due()
    rows=store.read('SELECT * FROM assessments ORDER BY checkpoint')
    assert len(rows)==2 and rows[0]==original[0]
    assert json.loads(rows[1]['features'])['practice_submitted']==0
    assert rows[1]['assessed_at']==store.clock().isoformat()
    assert 'processed late' in rows[1]['reason']
    store.advance(START+pd.Timedelta(days=10),TEACHER,'Day ten')
    service.run_due()
    latest=service.latest(sid)
    assert json.loads(latest['features'])['practice_submitted']==1
    assert service.feature_values(sid,store.clock(),10)['offline_participation']==1
    assert latest['model_identity'].startswith('interactive_module1/logistic_regression:sha256:')
    assert latest['score'] is not None

def test_completion_before_checkpoint_not_assessed(tmp_path):
    store,sid,service=setup(tmp_path)
    store.submit(sid,'practice',answers(PRACTICE),'p')
    store.submit(sid,'quiz',answers(QUIZ),'q')
    store.advance(START+pd.Timedelta(days=10),TEACHER,'Complete before checkpoints')
    service.run_due()
    assert not store.read('SELECT * FROM assessments')

def test_blank_boxes_draft_navigation_and_invalid_no_grant_consumption(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    store,sid,service=setup(tmp_path)
    store.advance(START+pd.Timedelta(days=15),TEACHER,'Late isolated learner')
    store.grant(sid,1,TEACHER,'One opportunity','g')
    monkeypatch.setenv('INTERACTIVE_DEMO_DB',str(store.path))
    app=AppTest.from_file(str(ROOT/'dashboard.py'),default_timeout=60).run()
    app.segmented_control[0].set_value('Learner').run()
    app.sidebar.radio[0].set_value('Quiz and results').run()
    assert all(w.value=='' for w in app.text_input)
    app.text_input[0].set_value('2').run()
    app.sidebar.radio[0].set_value('Lesson').run()
    app.sidebar.radio[0].set_value('Quiz and results').run()
    assert app.text_input[0].value=='2' and app.text_input[1].value==''
    next(b for b in app.button if b.label=='Submit quiz').click().run()
    assert app.error and not app.exception
    assert not store.state(sid)['attempts'] and store.state(sid)['available_grants']==1

    app.sidebar.radio[0].set_value('Practice').run()
    app.text_input[0].set_value('2').run()
    # Commit another blank field, as browser blur/navigation can do.
    app.text_input[1].set_value('').run()
    app.sidebar.radio[0].set_value('Lesson').run()
    app.sidebar.radio[0].set_value('Practice').run()
    assert app.text_input[0].value=='2'
    assert json.loads(store.draft(sid,'practice')['answers'])['P1']=='2,,'
    app.sidebar.radio[0].set_value('Quiz and results').run()
    app.text_input[1].set_value('0').run()
    next(b for b in app.button if b.label=='Submit quiz').click().run()
    assert not store.state(sid)['attempts'] and store.state(sid)['available_grants']==1

def test_teacher_controls_and_review_ui(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    store,sid,service=setup(tmp_path)
    store.advance(START+pd.Timedelta(days=3),TEACHER,'Eligible checkpoint')
    monkeypatch.setenv('INTERACTIVE_DEMO_DB',str(store.path))
    app=AppTest.from_file(str(ROOT/'dashboard.py'),default_timeout=60).run()
    assert any(b.label=='Allow extra attempts' for b in app.button)
    assert any(d.label=='Completion date (UTC)' for d in app.date_input)
    assert any(t.label=='Completion time (UTC)' for t in app.time_input)
    next(r for r in app.sidebar.radio if r.label=='Staff pages').set_value('Needs attention').run()
    assert not app.exception
    assert service.latest(sid)['score'] is not None
