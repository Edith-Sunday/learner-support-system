"""Historical and persistent-support rules; no production models fitted."""
import hashlib
import json
import socket

import numpy as np
import pandas as pd
import pytest

from src.dashboard_data import (DEFAULT_TIME, active_queues, available, historical_modules,
                                load_ranker, load_sources)
from src.simulate import DAY, FEATURES, ROOT
from src.staff_store import StaffStore, message_draft


class ScoreSpy:
    def predict_proba(self, frame):
        assert list(frame.columns) == FEATURES
        self.seen = frame.copy()
        return np.array([[.2, .8]] * len(frame))


def fixture_events():
    monday = pd.Timestamp('2026-01-05T12:00:00Z')
    students = pd.DataFrame([dict(student_id='S1', enrolment_time=monday - 13 * DAY, communication_preference='SMS')])
    events = pd.DataFrame([dict(student_id='S1', module_id=1, event_id='p', event_type='practice',
                                event_time=monday, recorded_at=monday + 2 * DAY, source='teacher_offline', score_pct=np.nan, valid=np.nan),
                           dict(student_id='S1', module_id=1, event_id='q', event_type='quiz',
                                event_time=monday, recorded_at=monday + 2 * DAY, source='teacher_offline', score_pct=80, valid=1)])
    return monday, students, events


def test_historical_offline_completion_boundary_and_correct_unlock():
    monday, students, events = fixture_events()
    # Deadline Tuesday: inclusive equality is still not overdue.
    at_deadline = historical_modules(students, events, monday + DAY)
    assert at_deadline.learning_status.tolist() == ['In progress']
    before_recording = historical_modules(students, events, monday + DAY + pd.Timedelta(seconds=1))
    assert before_recording.learning_status.tolist() == ['Overdue']
    assert not before_recording.practice_submitted.any()
    wednesday = monday + 2 * DAY
    recognized = historical_modules(students, events, wednesday)
    assert recognized.learning_status.tolist() == ['Completed on time', 'In progress']
    assert recognized.iloc[0].completion_time == monday
    assert recognized.iloc[1].unlock_time == wednesday
    assert recognized.iloc[1].deadline == wednesday + 14 * DAY
    # Later occurrence with an earlier recorded_at is still excluded.
    future = events.copy()
    future['event_time'] = monday + 10 * DAY
    future['recorded_at'] = monday
    assert available(future, wednesday).empty


def test_latest_snapshot_unscored_and_overdue_no_score_gate():
    unlock = pd.Timestamp('2026-01-01T00:00:00Z')
    modules = pd.DataFrame([dict(student_id=sid, module_id=1, unlock_time=unlock,
                                 deadline=unlock + 14 * DAY, learning_status=status)
                            for sid, status in [('A', 'In progress'), ('B', 'In progress'),
                                                ('C', 'Overdue'), ('D', 'Completed late')]])
    snapshots = pd.DataFrame([dict(**{f: 0 for f in FEATURES}, student_id='A', module_id=1,
                                   unlock_time=unlock, snapshot_time=unlock + day * DAY)
                              for day in (3, 7, 10)])
    snapshots['snapshot_day'] = [3, 7, 10]
    spy = ScoreSpy()
    early, overdue = active_queues(modules, snapshots, unlock + 8 * DAY, spy, FEATURES)
    assert early.student_id.tolist() == ['A', 'B']
    assert spy.seen.snapshot_day.tolist() == [7]
    assert early.checkpoint_day.iloc[0] == 7
    assert early.score_status.iloc[1] == 'Not yet scored'
    assert pd.isna(early.model_risk_score.iloc[1])
    assert overdue.student_id.tolist() == ['C']
    assert not early.duplicated(['student_id', 'module_id']).any()


def test_staff_persistence_history_idempotency_and_learning_independence(tmp_path):
    monday, students, events = fixture_events()
    at = monday + DAY + pd.Timedelta(seconds=1)
    store = StaffStore(tmp_path / 'demo.sqlite3')
    before = historical_modules(students, events, at)
    payload = dict(staff='Demo staff — Amina', status='Reviewed', notes='Demo review', follow_up=None)
    store.record('S1', 1, 'review', at, payload, 'review-1')
    store.record('S1', 1, 'review', at, payload, 'review-1')
    store.record('S1', 1, 'challenge', at + DAY, dict(category='Mixed', confirmed_by='teacher', details='Confirmed later'), 'challenge-1')
    reopened = StaffStore(tmp_path / 'demo.sqlite3')
    assert len(reopened.actions(at, 'S1')) == 1
    assert len(reopened.actions(at + DAY, 'S1')) == 2
    assert reopened.actions(monday, 'S1') == []
    assert reopened.state(at, 'S1', 1)['status'] == 'Reviewed'
    pd.testing.assert_frame_equal(before, historical_modules(students, events, at))
    store.ensure_referrals(before)
    store.ensure_referrals(before)
    assert len(store.referrals(at, 'S1')) == 1
    assert store.referrals(monday, 'S1') == []
    after = historical_modules(students, events, monday + 2 * DAY)
    assert not after.learning_status.eq('Overdue').any()
    assert len(store.referrals(monday + 2 * DAY, 'S1')) == 1


def test_drafts_are_local_only_and_never_negative_days(tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError('Draft must not use a network')
    monkeypatch.setattr(socket, 'create_connection', no_network)
    at = pd.Timestamp('2026-02-01T12:00:00Z')
    case = dict(student_id='S1', module_id=1, deadline=at - DAY,
                learning_status='Overdue', remaining_requirements='Submit practice; pass quiz')
    store = StaffStore(tmp_path / 'drafts.sqlite3')
    for index, category in enumerate(['Content difficulty', 'Deadline difficulty', 'Connectivity difficulty', 'Unclear or mixed difficulty', 'Overdue']):
        text = message_draft(case, category, at, 'balancing equations')
        assert 'overdue' in text.lower() and '-1' not in text and 'http' not in text
        store.record('S1', 1, 'draft', at, dict(channel='SMS', text=text, delivery_status='Draft only — not sent'), str(index))
    assert len(store.actions(at)) == 5
    case['learning_status'] = 'Completed late'
    completed_draft = message_draft(case, 'Overdue', at)
    assert 'complete' in completed_draft and 'authorisation' not in completed_draft


def test_default_demo_full_coverage_and_source_integrity():
    sources = load_sources()
    assert 'module_outcomes' not in sources
    modules = historical_modules(sources['students'], sources['events'], DEFAULT_TIME)
    pipeline, features = load_ranker()
    early, overdue = active_queues(modules, sources['prediction_snapshots'], DEFAULT_TIME, pipeline, features)
    assert len(early) and len(overdue)
    assert not early.duplicated(['student_id', 'module_id']).any()
    assert not overdue.duplicated(['student_id', 'module_id']).any()
    expected = modules[modules.learning_status.eq('Overdue')]
    assert set(zip(overdue.student_id, overdue.module_id)) == set(zip(expected.student_id, expected.module_id))
    assert early.learning_status.eq('In progress').all()
    assert early.loc[early.model_risk_score.isna(), 'score_status'].eq('Not yet scored').all()
    at_start = pd.Timestamp(sources['metadata']['observation_start'])
    empty_modules = historical_modules(sources['students'], sources['events'], at_start)
    empty_early, empty_overdue = active_queues(empty_modules, sources['prediction_snapshots'], at_start, pipeline, features)
    assert empty_early.empty and empty_overdue.empty
    for item in json.loads((ROOT / 'dashboard_original_hashes.json').read_text(encoding='utf-8-sig')):
        original=__import__('pathlib').PureWindowsPath(item['Path'])
        artifact=ROOT / original.relative_to(original.parents[1]).as_posix()
        if artifact.suffix=='.txt' and not artifact.exists():
            continue  # Local execution logs are deliberately excluded from deployment.
        assert hashlib.sha256(artifact.read_bytes()).hexdigest().upper() == item['Hash']


def test_streamlit_smoke_and_demo_action(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    from src.interactive_store import InteractiveStore
    store = InteractiveStore(tmp_path/'app.sqlite3', '2026-10-01T08:00Z')
    sid = store.enrol()
    monkeypatch.setenv('INTERACTIVE_DEMO_DB', str(store.path))
    app = AppTest.from_file(str(ROOT/'dashboard.py'), default_timeout=60).run()
    assert not app.exception and app.title[0].value == 'All learners'
    for page in ('Needs attention','Support messages','Model evaluation','All learners'):
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception
    app.selectbox(key='actor-followup-'+sid).set_value('Demo staff — Amina')
    app.selectbox(key='actor-followup-'+sid).set_value('Demo staff — Amina')
    next(b for b in app.button if b.label=='Save follow-up').click().run()
    assert not app.exception
    assert len(StaffStore(store.path).actions(store.clock(),sid)) == 1
    assert not any(s.label=='Cohort' for s in app.selectbox)

