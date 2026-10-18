"""Interactive learning journey, clock boundaries and concurrent authorisation safety."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from math import gcd
from functools import reduce
from pathlib import Path
import re

import pandas as pd
import pytest

from src.chemistry_content import PRACTICE, QUIZ, grade, worksheet
from src.interactive_store import InteractiveStore, utc
from src.staff_store import StaffStore
from src.simulate import ROOT

START=pd.Timestamp('2026-10-15T08:00:00Z')
TEACHER='Demo staff — Amina'


def answers(questions=QUIZ, score=None):
    result={q['id']: ','.join(map(str,q['answer'])) if isinstance(q['answer'],tuple) else q['answer'] for q in questions}
    if score is not None:
        for q in questions[score:]:
            result[q['id']]='1,'*(len(q['answer'])-1)+'1' if q['type']=='coefficients' else next(x for x in 'ABCD' if x!=q['answer'])
    return result


@pytest.fixture
def store(tmp_path):
    return InteractiveStore(tmp_path/'demo.sqlite3',START)


def test_enrol_clock_persists_and_cannot_reverse(store):
    sid=store.enrol('WhatsApp')
    assert sid=='DEMO001'
    assert utc(store.state(sid)['deadline'])==START+pd.Timedelta(days=14)
    assert InteractiveStore(store.path,START+pd.Timedelta(days=90)).clock()==START
    with pytest.raises(ValueError):
        store.advance(START-pd.Timedelta(seconds=1),TEACHER,'invalid')
    store.advance(START+pd.Timedelta(days=1),TEACHER,'Demonstrate tomorrow')
    assert InteractiveStore(store.path).clock()==START+pd.Timedelta(days=1)
    assert store.read('SELECT * FROM clock_history')[0]['created_at']


def test_practice_fail_then_exact_pass_and_single_unlock(store):
    sid=store.enrol()
    first=store.submit(sid,'quiz',answers(score=7),'fail')
    assert first['score']==7 and not store.state(sid)['quiz_passed']
    passed=store.submit(sid,'quiz',answers(score=8),'pass')
    assert passed['score']==8 and store.state(sid)['quiz_passed']
    assert store.state(sid)['current_module']==1  # no practice yet
    wrong=answers(PRACTICE,score=0)
    assert store.submit(sid,'practice',wrong,'practice')['score']==0
    state=store.state(sid)
    assert state['learning_status']=='Completed on time' and state['current_module']==2
    assert len(store.module_history(sid))==2
    next_module=store.module_history(sid)[1]
    assert utc(next_module['unlock_time'])==START
    assert utc(next_module['deadline'])==START+pd.Timedelta(days=14)
    store.advance(START+pd.Timedelta(hours=1),TEACHER,'Later review')
    store.submit(sid,'quiz',answers(score=0),'later-low')
    store.submit(sid,'practice',wrong,'repeat-practice')
    assert store.state(sid)['quiz_passed']
    assert store.module_history(sid)[1]==next_module


def test_deadline_equality_and_submit_time_check(store):
    sid=store.enrol()
    deadline=START+pd.Timedelta(days=14)
    store.advance(deadline,TEACHER,'Deadline equality')
    assert store.submit(sid,'quiz',answers(score=7),'at-deadline')['grant_id'] is None
    assert store.state(sid)['learning_status']=='In progress'
    draft=store.draft(sid,'quiz')
    store.advance(deadline+pd.Timedelta(seconds=1),TEACHER,'Just late')
    with pytest.raises(ValueError,match='deadline'):
        store.submit(sid,'quiz',answers(),draft['token'])
    assert len(store.state(sid)['attempts'])==1
    assert len(store.overdue())==1


@pytest.mark.parametrize('quantity',[1,2])
def test_grants_exhaustion_duplicates_and_late_completion(store,quantity):
    sid=store.enrol()
    deadline=utc(store.state(sid)['deadline'])
    store.advance(deadline+pd.Timedelta(days=1),TEACHER,'Late')
    grant=store.grant(sid,quantity,TEACHER,'Extra support','grant')
    assert store.grant(sid,quantity,TEACHER,'Extra support','grant')==grant
    for number in range(quantity):
        record=store.submit(sid,'quiz',answers(),f'attempt-{number}')
        assert store.submit(sid,'quiz',answers(),f'attempt-{number}')['id']==record['id']
    assert store.state(sid)['available_grants']==0
    with pytest.raises(ValueError):
        store.submit(sid,'quiz',answers(),'exhausted')
    store.submit(sid,'practice',answers(PRACTICE,0),'practice')
    assert store.state(sid)['learning_status']=='Completed late'
    assert not store.overdue()
    assert len(store.read('SELECT * FROM interactive_referrals'))==1
    assert utc(store.state(sid)['deadline'])==deadline


def test_concurrent_grant_consumption_and_duplicate_token(store):
    sid=store.enrol()
    store.advance(START+pd.Timedelta(days=15),TEACHER,'Late')
    store.grant(sid,1,TEACHER,'One only','grant')
    def submit(token):
        try:
            return store.submit(sid,'quiz',answers(),token)['id']
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(submit,['same','same']))
    assert results[0]==results[1] and results[0] is not None
    assert len(store.read('SELECT * FROM submissions'))==1
    store.grant(sid,1,TEACHER,'One more','grant-2')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(submit,['different-1','different-2']))
    assert sum(r is not None for r in results)==1
    assert store.state(sid)['available_grants']==0


def test_offline_monday_occurrence_wednesday_recognition(store):
    sid=store.enrol()
    monday=pd.Timestamp('2026-10-26T12:00:00Z')
    wednesday=monday+pd.Timedelta(days=2)
    store.advance(wednesday,TEACHER,'Delayed paper record')
    store.submit(sid,'practice',None,'p',occurrence=monday,staff=TEACHER,reason='Paper practice')
    result=store.submit(sid,'quiz',None,'q',score=8,occurrence=monday,staff=TEACHER,reason='Paper quiz')
    assert result['answers']=='null'
    assert utc(store.state(sid)['completion_time'])==monday
    assert store.state(sid)['learning_status']=='Completed on time'
    module=store.module_history(sid)[1]
    assert utc(module['unlock_time'])==wednesday and utc(module['deadline'])==wednesday+pd.Timedelta(days=14)
    # Earlier delayed records do not backdate established Module 2 access.
    store.advance(wednesday+pd.Timedelta(days=1),TEACHER,'Another record')
    store.submit(sid,'quiz',None,'q-earlier',score=9,occurrence=monday-pd.Timedelta(hours=1),staff=TEACHER,reason='Another paper')
    assert store.module_history(sid)[1]==module


def test_offline_recording_after_deadline_is_still_on_time(store):
    sid=store.enrol()
    deadline=utc(store.state(sid)['deadline'])
    store.advance(deadline+pd.Timedelta(days=3),TEACHER,'Delayed upload')
    for kind in ('practice','quiz'):
        store.submit(sid,kind,None,kind,score=8 if kind=='quiz' else None,occurrence=deadline,staff=TEACHER,reason='On-time paper')
    state=store.state(sid)
    assert state['learning_status']=='Completed on time'
    assert utc(store.module_history(sid)[1]['unlock_time'])==store.clock()
    assert not store.overdue()


def test_offline_invalid_time_score_and_grant_timing(store):
    sid=store.enrol()
    for occurrence,score in [(START-pd.Timedelta(seconds=1),8),(START+pd.Timedelta(seconds=1),8),(START,8.5),(START,True),(START,11)]:
        with pytest.raises(ValueError):
            store.submit(sid,'quiz',None,'invalid',score=score,occurrence=occurrence,staff=TEACHER,reason='Paper')
    store.advance(START+pd.Timedelta(days=16),TEACHER,'Late')
    store.grant(sid,1,TEACHER,'Support','g')
    with pytest.raises(ValueError):
        store.submit(sid,'quiz',None,'before-grant',score=8,occurrence=START+pd.Timedelta(days=15),staff=TEACHER,reason='Before grant')
    assert store.state(sid)['available_grants']==1
    store.submit(sid,'quiz',None,'after-grant',score=8,occurrence=store.clock(),staff=TEACHER,reason='After grant')
    assert store.state(sid)['available_grants']==0


def test_validation_and_exact_smallest_tuple(store):
    sid=store.enrol()
    for invalid in ('', '0,1,2', '-2,1,2', '2.0,1,2','2,1','2 1 2'):
        response=answers()
        response['Q1']=invalid
        with pytest.raises(ValueError):
            store.submit(sid,'quiz',response,'bad')
    response=answers(); response['Q8']=None
    with pytest.raises(ValueError):
        store.submit(sid,'quiz',response,'bad')
    assert not store.state(sid)['attempts']
    response=answers(); response['Q1']='4,2,4'
    assert grade(QUIZ,response)[0]==9


def test_persist_preferences_help_drafts_and_staff_independence(store):
    sid=store.enrol()
    store.preference(sid,'email')
    store.request_help(sid,'Please explain coefficients','request')
    store.request_help(sid,'Please explain coefficients','request')
    draft=store.draft(sid,'quiz')
    store.save_draft(sid,'quiz',draft['token'],{'Q1':'2,1,2'})
    reopened=InteractiveStore(store.path)
    assert reopened.state(sid)['preference']=='email'
    assert len(reopened.read('SELECT * FROM requests'))==1
    assert json.loads(reopened.draft(sid,'quiz')['answers'])=={'Q1':'2,1,2'}
    staff=StaffStore(store.path)
    staff.record(sid,1,'review',store.clock(),dict(staff=TEACHER,status='Reviewed',notes='Support',follow_up=None),'r')
    assert store.state(sid)['learning_status']=='In progress'
    assert not store.state(sid)['practice_submitted']


def test_question_keys_balance_and_learner_download_has_no_keys():
    for q in PRACTICE+QUIZ:
        if q['type']!='coefficients':
            continue
        assert reduce(gcd,q['answer'])==1
        equation=q['prompt'].translate(str.maketrans('₀₁₂₃₄₅₆₇₈₉','0123456789'))
        left,right=equation.split('→')
        counts=[]; offset=0
        for side in (left,right):
            atoms={}
            for formula in side.split('+'):
                coeff=q['answer'][offset]; offset+=1
                for element,number in re.findall(r'([A-Z][a-z]?)(\d*)',formula.strip()):
                    atoms[element]=atoms.get(element,0)+coeff*int(number or 1)
            counts.append(atoms)
        assert counts[0]==counts[1]
    text=worksheet(QUIZ)
    assert 'KEY:' not in text and all(q['explanation'] not in text for q in QUIZ)
    assert 'KEY:' in worksheet(QUIZ,True)


def test_original_artifacts_and_staff_rows_unchanged():
    manifest=ROOT/'runtime'/'learner_original_hashes.json'
    if not manifest.exists():
        __import__('pytest').skip('Local-only preservation evidence is deliberately not published')
    for item in json.loads(manifest.read_text(encoding='utf-8-sig')):
        assert hashlib.sha256(Path(item['Path']).read_bytes()).hexdigest().upper()==item['Hash']
    import sqlite3
    with sqlite3.connect(ROOT/'runtime'/'staff_before_learner.sqlite3') as old, sqlite3.connect(ROOT/'runtime'/'staff_demo.sqlite3') as current:
        for table in ('actions','referrals'):
            assert set(old.execute('SELECT * FROM '+table)) <= set(current.execute('SELECT * FROM '+table))


def test_streamlit_interactive_journey(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    path=tmp_path/'interactive.sqlite3'
    store=InteractiveStore(path,START)
    sid=store.enrol()
    monkeypatch.setenv('INTERACTIVE_DEMO_DB',str(path))
    app=AppTest.from_file(str(ROOT/'dashboard.py'),default_timeout=60).run()
    app.segmented_control[0].set_value('Learner').run()
    assert not app.exception
    assert app.title[0].value=='My learning'
    app.sidebar.radio[0].set_value('Practice').run()
    for widget in app.text_input:
        widget.set_value('1')
    next(b for b in app.button if b.label=='Submit practice').click().run()
    assert store.state(sid)['practice_submitted']
    app.sidebar.radio[0].set_value('Quiz and results').run()
    response=answers(score=8)
    for widget,value in zip(app.text_input,[v for q in QUIZ[:7] for v in response[q['id']].split(',')]):
        widget.set_value(value)
    for widget,q in zip([r for r in app.radio if r.label.endswith(' answer')],QUIZ[7:]):
        assert widget.value is None
        widget.set_value(response[q['id']])
    next(b for b in app.button if b.label=='Submit quiz').click().run()
    assert not app.exception
    assert store.state(sid)['current_module']==2
    app.segmented_control[0].set_value('Staff').run()
    assert not app.exception
    assert any('Module 2' in i.value for i in app.info)
    assert len(store.module_history(sid))==2
