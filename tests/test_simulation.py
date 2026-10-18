"""Business-rule fixtures and full-cohort checks for simulated data."""
from io import StringIO

import pandas as pd
import pytest

from src.simulate import (DAY, FEATURES, ROOT, START, completion, features_at, known,
                          next_module_clock, outcome, simulate, snapshot_times, validate_attempts)
from src.validate import exclusions


def event(kind, day, *, recorded_day=None, **kwargs):
    return dict(event_id=f'{kind}-{day}', student_id='S1', module_id=1,
                event_type=kind, event_time=START + day * DAY,
                recorded_at=START + (day if recorded_day is None else recorded_day) * DAY,
                source='online', **kwargs)


@pytest.fixture(scope='session')
def cohort():
    return simulate()


@pytest.mark.parametrize('score,passes', [(0, False), (70, False), (80, True), (100, True)])
def test_pass_threshold_and_both_requirements(score, passes):
    quiz = event('quiz', 4, score_pct=score, valid=1)
    assert completion([quiz])[0] is None
    practice = event('practice', 5, accuracy_pct=0)
    assert completion([practice])[0] is None
    assert (completion([practice, quiz])[0] is not None) == passes
    if passes:
        assert completion([practice, quiz])[0] == START + 5 * DAY


def test_invalid_quiz_does_not_pass():
    assert completion([event('practice', 1), event('quiz', 2, score_pct=100, valid=0)])[0] is None


@pytest.mark.parametrize('offset,missed', [(0, 0), (1 / 86400, 1)])
def test_deadline_boundary_and_late_completion(offset, missed):
    events = [event('practice', 1), event('quiz', 14 + offset, score_pct=80, valid=1)]
    result = outcome(events, START + 14 * DAY, START + 30 * DAY)
    assert result['missed_deadline'] == missed
    assert result['module_status'] == ('completed_late' if missed else 'completed_on_time')


def test_grants_boundary_and_exhaustion():
    deadline = START + 14 * DAY
    # Unlimited attempts at or before the inclusive deadline.
    validate_attempts([event('quiz', 14, score_pct=70, valid=1) for _ in range(20)], deadline)
    q = event('quiz', 15, score_pct=80, valid=1, grant_id='g')
    with pytest.raises(AssertionError, match='without grant'):
        validate_attempts([q], deadline)
    g = event('grant', 14.5, additional_attempts=1)
    g['event_id'] = 'g'
    validate_attempts([g, q], deadline)
    q2 = event('quiz', 16, score_pct=90, valid=1, grant_id='g')
    with pytest.raises(AssertionError, match='exhausted'):
        validate_attempts([g, q, q2], deadline)
    g['additional_attempts'] = 2
    validate_attempts([g, q, q2], deadline)
    g['recorded_at'] = START + 16 * DAY
    with pytest.raises(AssertionError):
        validate_attempts([g, q], deadline)


def test_offline_recording_and_historical_snapshot_immutability():
    p = event('practice', 2, recorded_day=5, accuracy_pct=0)
    q = event('quiz', 2, recorded_day=5, score_pct=80, valid=1)
    p['source'] = q['source'] = 'teacher_offline'
    records = [p, q]
    assert completion(records) == (START + 2 * DAY, START + 5 * DAY)
    assert completion(known(records, START + 3 * DAY))[0] is None
    f = features_at(records, [], 1, START + 3 * DAY, 3)
    assert f['activities_completed'] == 0
    assert f['no_login'] == 1 and f['days_since_login'] is None
    assert f['quiz_score_trend'] is None and f['session_length'] is None
    later = event('quiz', 20, score_pct=100, valid=1)
    assert features_at(records + [later], [], 1, START + 3 * DAY, 3) == f
    assert features_at(records, [], 1, START + 7 * DAY, 7)['activities_completed'] == 2
    # Recorded after the deadline but performed before it is on time.
    q['event_time'] = START + 14 * DAY
    q['recorded_at'] = START + 16 * DAY
    assert outcome(records, START + 14 * DAY, START + 30 * DAY)['missed_deadline'] == 0


def test_historical_counts_and_feature_arithmetic():
    m = [dict(module_id=1, deadline=START + 14 * DAY)]
    records = [event('practice', 15, recorded_day=18),
               event('quiz', 16, score_pct=80, valid=1)]
    f = features_at(records, m, 2, START + 17 * DAY, 3)
    assert f['past_late_submissions'] == f['previous_modules_completed_late'] == 0
    f = features_at(records, m, 2, START + 19 * DAY, 3)
    assert f['past_late_submissions'] == f['previous_modules_completed_late'] == 1
    records = [event('practice', 1), event('quiz', 2, score_pct=70, valid=1),
               event('quiz', 3, score_pct=50, valid=1),
               event('session', 2, duration_minutes=20, idle_minutes=8, active_minutes=12, interrupted=1),
               event('session', 3, duration_minutes=40, idle_minutes=10, active_minutes=30, interrupted=0),
               event('login', 1)]
    f = features_at(records, [], 1, START + 7 * DAY, 7)
    assert f['quiz_score_trend'] == -20
    assert f['current_quiz_score'] == 50 and f['quiz_attempt_count'] == 2
    assert f['session_length'] == 30 and f['time_on_task'] == 42
    assert f['days_since_login'] == 6 and f['failed_or_dropped_sessions'] == 1
    assert f['activities_completed'] == 1


def test_offline_monday_completion_unlocks_next_module_on_wednesday():
    monday = pd.Timestamp('2026-01-05T12:00:00Z')
    wednesday = monday + 2 * DAY
    practice = event('practice', 0, accuracy_pct=0)
    quiz = event('quiz', 0, score_pct=80, valid=1)
    for e in (practice, quiz):
        e.update(event_time=monday, recorded_at=wednesday, source='teacher_offline')
    records = [practice, quiz]
    # Tuesday's original deadline: Monday is on time even though recognition is late.
    result = outcome(records, monday + DAY, monday + 30 * DAY)
    assert result['completion_time'] == monday
    assert result['completion_known_at'] == wednesday
    assert result['missed_deadline'] == 0
    assert result['module_status'] == 'completed_on_time'
    with pytest.raises(ValueError):
        next_module_clock(known(records, wednesday - pd.Timedelta(seconds=1)))
    clock = next_module_clock(known(records, wednesday))
    assert clock['unlock_time'] == clock['unlock_known_at'] == wednesday
    assert clock['deadline'] == pd.Timestamp('2026-01-21T12:00:00Z')
    assert snapshot_times(clock) == [(d, wednesday + d * DAY) for d in (3, 7, 10)]
    assert snapshot_times(clock)[0][1] == pd.Timestamp('2026-01-10T12:00:00Z')
    # A still earlier occurrence arriving Friday can revise retrospective completion,
    # but cannot backdate the established access clock or Wednesday's snapshot facts.
    old_snapshot = features_at(records, [], 1, monday + DAY, 3)
    delayed = [dict(e, event_id=e['event_id'] + '-delayed',
                    event_time=monday - DAY, recorded_at=wednesday + 2 * DAY) for e in records]
    assert completion(records + delayed)[0] == monday - DAY
    assert next_module_clock(records + delayed) == clock
    assert features_at(records + delayed, [], 1, monday + DAY, 3) == old_snapshot


def test_unknown_outcome_even_if_already_completed():
    records = [event('practice', 1), event('quiz', 2, score_pct=80, valid=1)]
    assert outcome(records, START + 14 * DAY, START + 10 * DAY)['missed_deadline'] is None
    assert outcome([], START + 14 * DAY, START + 10 * DAY)['module_status'] == 'in_progress'
    assert outcome([], START + 14 * DAY, START + 20 * DAY)['module_status'] == 'overdue'


def test_exclusion_report_distinguishes_unresolved_and_completed():
    outcomes = pd.DataFrame([
        dict(student_id='S1', module_id=1, missed_deadline=None, completion_time=None),
        dict(student_id='S2', module_id=1, missed_deadline=None, completion_time=START),
        dict(student_id='S3', module_id=1, missed_deadline=0, completion_time=START),
    ])
    snapshots = pd.DataFrame([dict(student_id=s, module_id=1) for s in ('S1', 'S1', 'S2', 'S3')])
    report = exclusions(outcomes, snapshots)
    assert report.modules.tolist() == [1, 1]
    assert report.excluded_snapshots.tolist() == [2, 1]
    assert 'unobserved' in report.reason.iloc[0]
    assert 'conservative policy only' in report.reason.iloc[1]


def test_full_cohort_progression_and_grants(cohort):
    outcomes = cohort['module_outcomes']
    events = cohort['events']
    groups = {k: g.to_dict('records') for k, g in events.groupby(['student_id', 'module_id'])}
    enrolment = cohort['students'].set_index('student_id').enrolment_time
    for sid, modules in outcomes.groupby('student_id'):
        previous = None
        assert list(modules.module_id) == list(range(1, len(modules) + 1))
        for m in modules.to_dict('records'):
            if previous is not None:
                assert pd.notna(previous['completion_time']), 'Cannot progress past an unfinished module'
            assert m['unlock_time'] == (enrolment[sid] if previous is None else previous['completion_known_at'])
            assert m['unlock_time'] == m['unlock_known_at']
            assert m['unlock_time'] <= START + 120 * DAY
            assert m['deadline'] == m['unlock_time'] + 14 * DAY
            records = groups.get((sid, m['module_id']), [])
            for e in records:
                assert e['event_time'] >= m['unlock_time']
                assert e['event_time'] >= m['unlock_known_at']
                assert e['recorded_at'] >= e['event_time']
            validate_attempts(records, m['deadline'])
            completed, _ = completion(records)
            if completed is None:
                assert pd.isna(m['completion_time'])
            else:
                assert m['completion_time'] == completed
            previous = m
    assert outcomes.module_id.max() == 8
    assert (outcomes.groupby('student_id').size() < 8).any()
    assert set(outcomes.module_status) == {'in_progress', 'overdue', 'completed_on_time', 'completed_late'}
    late = outcomes[outcomes.module_status == 'completed_late'].dropna(subset=['missed_deadline'])
    assert (late.missed_deadline == 1).all()


def test_every_snapshot_is_asof_and_incomplete(cohort):
    by_student = {s: g.to_dict('records') for s, g in cohort['events'].groupby('student_id')}
    modules = {s: g.to_dict('records') for s, g in cohort['module_outcomes'].groupby('student_id')}
    for row in cohort['prediction_snapshots'].to_dict('records'):
        at = row['snapshot_time']
        records = by_student[row['student_id']]
        # Independently truncate first; future record changes cannot enter features.
        truncated = [e for e in records if e['recorded_at'] <= at and e['event_time'] <= at]
        expected = features_at(truncated, modules[row['student_id']], row['module_id'], at, row['snapshot_day'])
        for key in FEATURES:
            assert (pd.isna(row[key]) and pd.isna(expected[key])) or row[key] == pytest.approx(expected[key])
        assert completion([e for e in truncated if e['module_id'] == row['module_id']])[0] is None
        assert at == row['unlock_time'] + row['snapshot_day'] * DAY
    assert 'missed_deadline' not in cohort['prediction_snapshots']
    assert not set(FEATURES) & {'student_id', 'module_id', 'split', 'completion_time', 'missed_deadline', 'latent_skill'}


def test_splits_and_labelled_exports(cohort):
    assignment = cohort['student_splits'].set_index('student_id').split
    assert assignment.value_counts().to_dict() == {'train': 420, 'test': 90, 'validation': 90}
    assert assignment.index.is_unique
    for name, frame in cohort.items():
        if 'split' in frame:
            assert (frame.student_id.map(assignment) == frame.split).all(), name
    for label in ('train', 'validation', 'test'):
        data = cohort[f'labelled_{label}']
        assert data.missed_deadline.notna().all()
        assert (data.deadline <= START + 120 * DAY).all()
        assert (data.split == label).all()
    assert cohort['module_outcomes'].missed_deadline.isna().any()
    joined = cohort['prediction_snapshots'].merge(
        cohort['module_outcomes'][['student_id', 'module_id', 'missed_deadline']],
        on=['student_id', 'module_id'])
    assert joined.missed_deadline.notna().sum() == sum(
        len(cohort[f'labelled_{s}']) for s in ('train', 'validation', 'test'))


def test_reproducibility_and_seed_variation(cohort):
    again = simulate()
    for name in cohort:
        pd.testing.assert_frame_equal(cohort[name], again[name])
    different = simulate(seed=43, observation_days=10)
    assert not different['students'].equals(cohort['students'])


def test_default_csv_exports_match_generated_records(cohort):
    # Verifies actual delivered CSVs, including timestamp/blank serialization.
    # Generate the default seed-42/120-day outputs before running the suite.
    for name, frame in cohort.items():
        path = ROOT / 'data' / f'{name}.csv'
        assert path.exists(), f'Run the default generator first: missing {path}'
        expected = pd.read_csv(StringIO(frame.to_csv(index=False, date_format='%Y-%m-%dT%H:%M:%S.%fZ')), low_memory=False)
        actual = pd.read_csv(path, low_memory=False)
        pd.testing.assert_frame_equal(actual, expected)
        assert (actual.is_simulated == 1).all()
