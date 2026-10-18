import json
import hashlib
import numpy as np
import pandas as pd
import pytest
from src.interactive_store import InteractiveStore
from src.interactive_assessment import AssessmentService
from src.interactive_support import SupportService,CATEGORIES
from src.seed_final_demo import answers
from src.chemistry_content import PRACTICE,QUIZ
from src.pilot import example,validate,summarize,difference
from src.interactive_model import FEATURES,ROOT

START=pd.Timestamp('2026-10-01T08:00Z'); STAFF='Demo staff — Amina'

def setup(tmp_path):
    store=InteractiveStore(tmp_path/'isolated.sqlite3',START)
    sid=store.enrol('WhatsApp')
    return store,sid,AssessmentService(store)

def test_candidate_identity_missing_versioned_cutoff(tmp_path):
    store,sid,s=setup(tmp_path)
    assert s.candidate_order==FEATURES
    assert s.identity.endswith(hashlib.sha256((ROOT/'models/interactive_module1/logistic_regression.joblib').read_bytes()).hexdigest())
    store.advance(START+pd.Timedelta(days=3),STAFF,'checkpoint')
    s.run_due(); before=store.read('SELECT * FROM assessments'); result=s.latest(sid)
    assert result['score'] is not None and result['retrospective']==0
    assert json.loads(result['features'])['current_quiz_score'] is None
    s.run_due(); assert len(store.read('SELECT * FROM assessment_results'))==1
    assert before==store.read('SELECT * FROM assessments')
    store.advance(START+pd.Timedelta(days=8),STAFF,'late recording')
    store.submit(sid,'quiz',None,'offline',score=7,occurrence=START+pd.Timedelta(days=2),staff=STAFF,reason='Delayed paper')
    s.run_due(); later=s.latest(sid)
    assert later['retrospective']==1 and json.loads(later['features'])['quiz_attempt_count']==0
    assert store.read('SELECT * FROM assessment_results WHERE checkpoint=3')[0]==result

def test_old_attempt_preserved_and_current_exclusions(tmp_path):
    store,sid,s=setup(tmp_path)
    store.advance(START+pd.Timedelta(days=3),STAFF,'checkpoint')
    values=s.feature_values(sid,store.clock(),3)
    at=store.clock().isoformat()
    with store.transaction() as db:
        db.execute('INSERT INTO assessments VALUES(?,?,?,?,?,?,?,?,?,?)',(sid,1,3,at,at,'old',json.dumps(values),'old-version',None,'legacy'))
    old=store.read('SELECT * FROM assessments')
    s.run_due(); assert s.latest(sid)['retrospective']==1
    assert store.read('SELECT * FROM assessments')==old
    second=store.enrol(); s2=AssessmentService(store)
    store.advance(START+pd.Timedelta(days=6),STAFF,'second checkpoint'); s2.run_due()
    # Identical checkpoint inputs receive exactly equal scores and priority groups.
    rows=s2.review_rows(); assert len(rows)==2
    assert rows[0]['score']==rows[1]['score'] and rows[0]['priority_group']==rows[1]['priority_group']
    store.submit(sid,'practice',answers(PRACTICE),'p'); store.submit(sid,'quiz',answers(QUIZ),'q')
    assert sid not in [r['student_id'] for r in s2.review_rows()]
    store.advance(START+pd.Timedelta(days=30),STAFF,'overdue')
    assert not s2.review_rows()
    s2.run_due(); assert not store.read('SELECT * FROM assessment_results WHERE module_id=2')
    assert all(r['module_id']==1 for r in store.overdue())

def test_support_neutral_categories_dispatch_response(tmp_path):
    store,sid,s=setup(tmp_path); service=SupportService(store)
    assert 'What help' in service.suggested(sid)
    for i,category in enumerate(CATEGORIES[:3]):
        service.confirm(sid,category,'student','Confirmed directly',STAFF,'barrier'+str(i))
        message=service.suggested(sid)
        assert ['Practice P1','Original deadline','Download'][i] in message
    did=service.draft(sid,message,STAFF,'draft')
    mid=service.dispatch(did,STAFF,'send')
    assert service.dispatch(did,STAFF,'send')==mid
    assert service.dispatch(did,STAFF,'another-click')==mid
    assert len(service.messages(sid))==1 and service.messages(sid)[0]['channel']=='WhatsApp'
    service.respond(sid,mid,'Please help with P2',True,'response')
    service.respond(sid,mid,'Please help with P2',True,'response')
    assert len(store.read('SELECT * FROM demo_responses'))==1
    other=store.enrol()
    with pytest.raises(ValueError): service.respond(other,mid,'Wrong learner',False,'bad')
    did2=service.draft(sid,'Another draft',STAFF,'d2'); store.preference(sid,'email')
    with pytest.raises(ValueError,match='Preference changed'): service.dispatch(did2,STAFF,'s2')
    assert len(store.read('SELECT * FROM support_drafts'))==2

def test_support_grants_and_feedback(tmp_path):
    store,sid,s=setup(tmp_path); service=SupportService(store)
    store.submit(sid,'quiz',answers(QUIZ,False),'failed')
    service.confirm(sid,CATEGORIES[0],'teacher','Discussed mistakes',STAFF,'b')
    assert 'recorded quiz feedback' in service.suggested(sid)
    store.advance(START+pd.Timedelta(days=15),STAFF,'overdue')
    assert 'grants no extension' in service.suggested(sid)
    store.grant(sid,1,STAFF,'Confirmed support','g')
    assert '1 authorised' in service.suggested(sid)
    store.submit(sid,'practice',answers(PRACTICE),'p');store.submit(sid,'quiz',answers(QUIZ),'q')
    assert 'waiting for content' in service.suggested(sid)

def test_pilot_denominators_missing_pending_and_no_message():
    f=example(); rows,diffs=summarize(f)
    for r in rows:
        assert r['participants']==12 and r['eligible_outcomes']==10
        assert r['on_time']==4 and r['completion_rate']==.4
        assert r['pending_outcomes']==1 and r['missing_outcomes']==1
        assert r['eligible_response_followup']==10 and r['responses']==3 and r['pending_response_followup']==1
    assert diffs['completion_rate']['percentage_points']==0
    f.loc[f.group.eq('baseline'),['dispatch_at','response_at']]=None
    f.loc[f.group.eq('baseline'),'delivery_status']='none'
    rows,_=summarize(f)
    assert rows[0]['response_rate'] is None and rows[0]['no_message']==12
    assert difference(.4,.5)['percentage_points']==pytest.approx(10)
    assert difference(.4,.5)['relative_percent']==pytest.approx(25)
    assert difference(0,.5)['relative_percent'] is None

@pytest.mark.parametrize('change',['duplicate','group','timestamp','outcome','real_simulated','deadline'])
def test_pilot_rejects_bad_records(change):
    f=example()
    if change=='duplicate': f=pd.concat([f,f.iloc[:1]],ignore_index=True)
    elif change=='group': f.loc[0,'group']='both'
    elif change=='timestamp': f.loc[0,'response_at']='2025-01-01T00:00Z'
    elif change=='outcome': f.loc[0,'outcome']='success'
    elif change=='real_simulated': f['dataset_kind']='real'
    else: f.loc[0,'deadline']='2026-01-17T08:00Z'
    with pytest.raises(ValueError): validate(f)

def test_pilot_unverified_and_late_response():
    f=example(); f['dataset_kind']='real'; f.loc[f.delivery_status.eq('simulated'),'delivery_status']='unverified'
    rows,_=summarize(f); assert all(r['response_rate'] is None and r['unverified_delivery']==11 for r in rows)
    f.loc[f.delivery_status.eq('unverified'),'delivery_status']='verified'
    rows,_=summarize(f); assert rows[0]['responses']==3  # 60-hour replies excluded
    assert not set(f.participant_id)&set(pd.read_csv(ROOT/'data/students.csv').student_id)
