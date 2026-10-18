import json
import joblib
import numpy as np
import pandas as pd
import pytest
from src.interactive_model import (ROOT, FEATURES, predictors, pipeline, eligible,
    choose, select, rule_scores, warnings_summary, verify_event_mapping)
from src.interactive_store import InteractiveStore
from src.interactive_assessment import AssessmentService
from src.interactive_ui import review_display
from src.chemistry_content import PRACTICE, QUIZ

START=pd.Timestamp('2026-10-01T08:00:00Z')
STAFF='Demo staff — Amina'

def answer(questions):
    return {q['id']:','.join(map(str,q['answer'])) if isinstance(q['answer'],tuple) else q['answer'] for q in questions}

def test_checked_label_relative_to_selected_clock():
    row=dict(student_id='DEMO001',score=None,assessed_at=START,checkpoint=3)
    assert review_display(row,START)['Last checked']=='Checked just now'
    assert review_display(row,START+pd.Timedelta(hours=1))['Last checked']=='1 hour ago'
    assert 'Last assessed' not in review_display(row,START)
    row['score']=.2
    assert review_display(row,START)['Last assessed']=='Just assessed'

def test_online_and_delayed_offline_mapping(tmp_path):
    store=InteractiveStore(tmp_path/'mapping.sqlite3',START)
    online=store.enrol(); offline=store.enrol()
    store.submit(online,'practice',answer(PRACTICE),'online-p')
    store.submit(online,'quiz',answer(QUIZ),'online-q')
    service=AssessmentService(store)
    store.advance(START+pd.Timedelta(days=4),STAFF,'Delayed records')
    store.submit(offline,'practice',None,'offline-p',occurrence=START,staff=STAFF,reason='Paper')
    store.submit(offline,'quiz',None,'offline-q',score=10,occurrence=START,staff=STAFF,reason='Paper')
    before=service.feature_values(offline,START+pd.Timedelta(days=3),3)
    assert before['practice_submitted']==0 and before['quiz_attempt_count']==0
    assert before['current_quiz_score'] is None and before['quiz_score_trend'] is None
    a=service.feature_values(online,store.clock(),7); b=service.feature_values(offline,store.clock(),7)
    assert {c:a[c] for c in FEATURES}=={c:b[c] for c in FEATURES}
    assert b['quiz_score_trend'] is None and b['current_quiz_score']==100
    # Explicit future occurrence cannot leak even if recording is already known.
    events=pd.DataFrame([dict(student_id='x',event_id=1,module_id=1,event_type='quiz',valid=1,score_pct=100,
        event_time=START+pd.Timedelta(days=5),recorded_at=START,source='online')])
    expected=pd.DataFrame([dict(student_id='x',snapshot_time=START,snapshot_day=3,practice_submitted=0,
        quiz_passed=0,current_quiz_score=np.nan,quiz_score_trend=np.nan,quiz_attempt_count=0,activities_completed=0)])
    assert verify_event_mapping(expected,events)==0

def test_train_only_imputation_allowlist_reproducibility(tmp_path):
    f=pd.DataFrame({c:[0,1,0,1,0,1] for c in FEATURES})
    f['current_quiz_score']=[np.nan,20,30,50,80,100]
    f['quiz_score_trend']=[np.nan,np.nan,10,20,30,20]
    f['student_id']='forbidden'; f['missed_deadline']=[0,0,1,0,1,1]
    x=predictors(f)
    assert list(x)==FEATURES and x.isna().any().any()
    for name in ('logistic_regression','gradient_boosting'):
        model=pipeline(name).fit(x,f.missed_deadline)
        imputer=model.named_steps['simpleimputer']
        expected=np.nanmedian(x.to_numpy(),axis=0)
        np.testing.assert_array_equal(imputer.statistics_,expected)
        validation=x.copy(); validation['current_quiz_score']=10000
        before=imputer.statistics_.copy(); model.predict_proba(validation)
        np.testing.assert_array_equal(before,imputer.statistics_)
        repeated=pipeline(name).fit(x,f.missed_deadline)
        np.testing.assert_array_equal(model.predict_proba(x),repeated.predict_proba(x))
        joblib.dump(model,tmp_path/'model.joblib')
        np.testing.assert_array_equal(model.predict_proba(x),joblib.load(tmp_path/'model.joblib').predict_proba(x))

def test_real_split_eligibility_and_censoring():
    data=ROOT/'data'; assignments=pd.read_csv(data/'student_splits.csv'); outcomes=pd.read_csv(data/'module_outcomes.csv')
    end=pd.Timestamp(json.loads((data/'simulation_metadata.json').read_text())['observation_end'])
    sets=[]
    for split in ('train','validation','test'):
        raw=pd.read_csv(data/f'labelled_{split}.csv')
        f=eligible(raw,split,assignments,outcomes,end)
        assert f.module_id.eq(1).all() and f.activities_completed.lt(2).all()
        assert not any(set(f.student_id)&s for s in sets)
        sets.append(set(f.student_id))
        corrupt=raw.copy(); corrupt.loc[0,'student_id']='unknown'
        with pytest.raises(ValueError,match='split'): eligible(corrupt,split,assignments,outcomes,end)
    raw=pd.read_csv(data/'labelled_train.csv')
    with pytest.raises(ValueError,match='censoring'): eligible(raw,'train',assignments,outcomes,pd.Timestamp('2026-01-01',tz='UTC'))

def test_budget_ties_selection_and_first_warning():
    f=pd.DataFrame([dict(student_id=s,module_id=1,snapshot_day=d,snapshot_time=START+pd.Timedelta(days=d),
        deadline=START+pd.Timedelta(days=14),missed_deadline=int(s in ('a','b')),activities_completed=0,current_quiz_score=np.nan)
        for d in (3,7,10) for s in ('a','b','c','d','e','f')])
    flags=select(f,np.ones(len(f)))
    assert flags.sum()==6  # ceil(6*.2)=2 at each checkpoint
    assert set(f.loc[flags,'student_id'])=={'a','b'}
    np.testing.assert_array_equal(flags,select(f.assign(missed_deadline=1-f.missed_deadline),np.ones(len(f))))
    outcome=pd.DataFrame([dict(student_id=s,module_id=1,split='test',missed_deadline=1) for s in ('a','b','absent')])
    summary=warnings_summary(f,flags,outcome,'test')
    assert summary['detected_missed_modules']==2 and summary['mean_lead_days']==11
    assert summary['unique_students_warned']==2 and summary['first_detected_11_days']==2
    assert summary['known_missed_without_snapshots']==1
    assert warnings_summary(f,np.zeros(len(f),bool),outcome,'test')['mean_lead_days'] is None
    rows=[dict(method=n,checkpoint=d,recall=.5) for n in ('logistic_regression','gradient_boosting') for d in (3,7,10)]
    assert choose(rows)[0]=='logistic_regression'
    rows[-1]['recall']=.6
    assert choose(rows)[0]=='gradient_boosting'

def test_ui_conditional_score_waiting_history_and_formula(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    store=InteractiveStore(tmp_path/'ui.sqlite3',START); sid=store.enrol()
    store.advance(START+pd.Timedelta(days=3),STAFF,'Checkpoint')
    service=AssessmentService(store); service.run_due()
    original=store.read('SELECT * FROM assessments')
    monkeypatch.setenv('INTERACTIVE_DEMO_DB',str(store.path))
    app=AppTest.from_file(str(ROOT/'dashboard.py'),default_timeout=60).run()
    assert not any('Quiz score' in n.label for n in app.number_input)
    next(s for s in app.selectbox if s.label=='Offline record type').set_value('quiz').run()
    assert any(n.label=='Quiz score out of 10' for n in app.number_input)
    next(s for s in app.selectbox if s.label=='Offline record type').set_value('practice').run()
    assert not any('Quiz score' in n.label for n in app.number_input)
    store.submit(sid,'practice',answer(PRACTICE),'p'); store.submit(sid,'quiz',answer(QUIZ),'q')
    app.run()
    assert any('Module 1 complete. Module 2 is not available yet.' in c.value for c in app.info)
    assert store.read('SELECT * FROM assessments')==original
    app.segmented_control[0].set_value('Learner').run()
    assert any('Module 1 complete. Module 2 is not available yet.' in c.value for c in app.info)
    app.sidebar.radio[0].set_value('Practice').run()
    assert all(w.value=='' for w in app.text_input)
    first_formula=PRACTICE[0]['prompt'].split('→')[0].split('+')[0].strip()
    assert 'for '+first_formula in app.text_input[0].label
    assert any(m.value=='**'+first_formula+'**' for m in app.markdown)
    assert not app.exception
