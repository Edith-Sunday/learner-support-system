"""Historical operational state from source events, never reconciled outcomes."""
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.simulate import DAY, ROOT, completion, features_at

DEFAULT_TIME = pd.Timestamp('2026-02-15T12:00:00Z')
KEY = ['student_id', 'module_id']
SIX_INPUTS = ['days_since_login', 'quiz_score_trend', 'past_late_submissions',
              'session_length', 'failed_or_dropped_sessions', 'time_on_task']


def load_sources(root=ROOT):
    tables = {}
    for name in ('students', 'events', 'prediction_snapshots', 'support_information'):
        frame = pd.read_csv(root / 'data' / f'{name}.csv', low_memory=False)
        for col in ('enrolment_time', 'event_time', 'recorded_at', 'unlock_time',
                    'unlock_known_at', 'deadline', 'snapshot_time'):
            if col in frame:
                frame[col] = pd.to_datetime(frame[col], utc=True)
        tables[name] = frame
    tables['metadata'] = json.loads((root / 'data' / 'simulation_metadata.json').read_text())
    return tables


def available(frame, at):
    return frame.loc[frame.event_time.le(at) & frame.recorded_at.le(at)].copy()


def historical_modules(students, events, at):
    visible = available(events, at)
    groups = {key: g.to_dict('records') for key, g in visible.groupby(KEY)}
    rows = []
    for student in students.loc[students.enrolment_time.le(at)].itertuples():
        unlock = student.enrolment_time
        for mid in range(1, 9):
            records = groups.get((student.student_id, mid), [])
            records = [e for e in records if e['event_time'] >= unlock]
            finished, recognized = completion(records)
            practice = any(e['event_type'] == 'practice' for e in records)
            quizzes = sorted([e for e in records if e['event_type'] == 'quiz'],
                             key=lambda e: (e['event_time'], e['event_id']))
            passed = any(e['valid'] == 1 and e['score_pct'] >= 80 for e in quizzes)
            deadline = unlock + 14 * DAY
            state = ('Completed on time' if finished <= deadline else 'Completed late') if finished is not None else ('Overdue' if at > deadline else 'In progress')
            remaining = [label for flag, label in ((practice, 'Submit practice'), (passed, 'Pass valid quiz at 80% or above')) if not flag]
            rows.append(dict(student_id=student.student_id, module_id=mid, unlock_time=unlock,
                             deadline=deadline, learning_status=state, practice_submitted=practice,
                             quiz_passed=passed, latest_quiz_score=quizzes[-1]['score_pct'] if quizzes else np.nan,
                             completion_time=finished, completion_known_at=recognized,
                             remaining_requirements='; '.join(remaining) or 'None',
                             days_overdue=max(0., (at - deadline) / DAY),
                             offline_participation=any(e['source'] == 'teacher_offline' for e in records),
                             communication_preference=student.communication_preference))
            if finished is None or mid == 8:
                break
            unlock = recognized
    columns = ['student_id', 'module_id', 'unlock_time', 'deadline', 'learning_status',
               'practice_submitted', 'quiz_passed', 'latest_quiz_score', 'completion_time',
               'completion_known_at', 'remaining_requirements', 'days_overdue',
               'offline_participation', 'communication_preference']
    return pd.DataFrame(rows, columns=columns)


def active_queues(modules, snapshots, at, pipeline, features):
    active = modules[modules.learning_status.isin(['In progress', 'Overdue'])].copy()
    overdue = active[active.learning_status.eq('Overdue')].copy()
    early = active[active.learning_status.eq('In progress')].copy()
    early['model_risk_score'] = np.nan
    early['score_timestamp'] = pd.NaT
    early['checkpoint_day'] = np.nan
    eligible = snapshots[snapshots.snapshot_time.le(at)].sort_values('snapshot_time').drop_duplicates(KEY, keep='last')
    # Matching the actual historical clock prevents accidentally using another module clock.
    matches = (early[KEY + ['unlock_time']].merge(eligible, on=KEY + ['unlock_time'], how='inner', validate='one_to_one')
               if len(early) and len(eligible) else pd.DataFrame())
    if len(matches):
        scores = pipeline.predict_proba(matches[features])[:, 1]
        lookup = {tuple(r[k] for k in KEY): (score, r['snapshot_time'], r['snapshot_day'])
                  for r, score in zip(matches.to_dict('records'), scores)}
        early['model_risk_score'] = [lookup.get(tuple(r[k] for k in KEY), (np.nan, None, np.nan))[0] for r in early.to_dict('records')]
        early['score_timestamp'] = [lookup.get(tuple(r[k] for k in KEY), (np.nan, None, np.nan))[1] for r in early.to_dict('records')]
        early['checkpoint_day'] = [lookup.get(tuple(r[k] for k in KEY), (np.nan, None, np.nan))[2] for r in early.to_dict('records')]
    early['score_status'] = np.where(early.model_risk_score.isna(), 'Not yet scored', 'Scored')
    early = early.sort_values(['model_risk_score', 'student_id', 'module_id'], ascending=[False, True, True], na_position='last')
    return early.reset_index(drop=True), overdue.sort_values(['deadline', 'student_id', 'module_id']).reset_index(drop=True)


def load_ranker(root=ROOT):
    manifest = json.loads((root / 'models' / 'selection.json').read_text())
    features = json.loads((root / 'data' / 'model_features.json').read_text())
    if features != manifest['features']:
        raise ValueError('Feature order differs from frozen model')
    from src.modeling import predictors
    # Reuse strict allowlist enforcement without fitting anything.
    predictors(pd.DataFrame(columns=features), features)
    path = root / 'models' / 'logistic_regression.joblib'
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest['pipeline_hashes']['logistic_regression']:
        raise ValueError('Saved logistic regression has changed')
    return joblib.load(path), features


def current_inputs(sources, modules, sid, mid, at):
    records = available(sources['events'], at)
    return features_at(records[records.student_id.eq(sid)].to_dict('records'),
                       modules[modules.student_id.eq(sid)].to_dict('records'), mid, at, 0)
