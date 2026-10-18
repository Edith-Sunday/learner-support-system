"""Simulated SS1 chemistry event histories; no real learner records or fitted models."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
START = pd.Timestamp('2026-01-01T00:00:00Z')
DAY = pd.Timedelta(days=1)
FEATURES = [
    'days_since_login', 'no_login', 'quiz_score_trend', 'past_late_submissions',
    'session_length', 'failed_or_dropped_sessions', 'time_on_task',
    'activities_completed', 'practice_submitted', 'quiz_passed',
    'current_quiz_score', 'quiz_attempt_count', 'offline_participation',
    'previous_modules_completed_late', 'snapshot_day',
]
EVENT_COLUMNS = ['event_id', 'student_id', 'module_id', 'event_type', 'event_time',
                 'recorded_at', 'source', 'duration_minutes', 'idle_minutes',
                 'active_minutes', 'interrupted', 'accuracy_pct', 'score_pct',
                 'valid', 'grant_id', 'additional_attempts']


def known(events, at):
    """Occurrence and availability are both bounded; never backfill snapshots."""
    return [e for e in events if e['event_time'] <= at and e['recorded_at'] <= at]


def completion(events):
    """Return occurrence-based timeliness and first system recognition separately."""
    practice = [e for e in events if e['event_type'] == 'practice']
    passes = [e for e in events if e['event_type'] == 'quiz'
              and e['valid'] and e['score_pct'] >= 80]
    if not practice or not passes:
        return None, None
    effective = max(min(e['event_time'] for e in practice),
                    min(e['event_time'] for e in passes))
    recognized = max(min(e['recorded_at'] for e in practice),
                     min(e['recorded_at'] for e in passes))
    return effective, recognized


def module_clock(unlock):
    """Establish a module's clock once; delayed occurrence records cannot move it."""
    return dict(unlock_time=unlock, unlock_known_at=unlock, deadline=unlock + 14 * DAY)


def next_module_clock(previous_events):
    """Access begins when records first establish BOTH completion requirements."""
    _, recognized = completion(previous_events)
    if recognized is None:
        raise ValueError('Previous module is not known to be complete')
    return module_clock(recognized)


def snapshot_times(module):
    return [(day, module['unlock_time'] + day * DAY) for day in (3, 7, 10)]


def outcome(events, deadline, end):
    completed, recognized = completion([e for e in events if e['event_time'] <= end])
    missed = None if deadline > end else int(completed is None or completed > deadline)
    status = ('completed_on_time' if completed <= deadline else 'completed_late') if completed is not None else ('overdue' if end > deadline else 'in_progress')
    return dict(completion_time=completed, completion_known_at=recognized,
                missed_deadline=missed, module_status=status)


def validate_attempts(events, deadline):
    grants = {e['event_id']: e for e in events if e['event_type'] == 'grant'}
    usage = {}
    for e in sorted(events, key=lambda x: (x['event_time'], x['event_id'])):
        if e['event_type'] != 'quiz':
            continue
        assert e['score_pct'] in range(0, 101, 10)
        if e['event_time'] > deadline:
            g = grants.get(e.get('grant_id'))
            assert g is not None, 'Late quiz without grant'
            assert g['student_id'] == e['student_id'] and g['module_id'] == e['module_id']
            assert g['event_time'] <= e['event_time'] and g['recorded_at'] <= e['event_time']
            assert g['additional_attempts'] in (1, 2)
            usage[g['event_id']] = usage.get(g['event_id'], 0) + 1
            assert usage[g['event_id']] <= g['additional_attempts'], 'Grant exhausted'


def features_at(events, modules, module_id, at, day):
    available = known(events, at)
    current = [e for e in available if e['module_id'] == module_id]
    logins = [e for e in available if e['event_type'] == 'login']
    quizzes = sorted([e for e in current if e['event_type'] == 'quiz' and e['valid']],
                     key=lambda e: (e['event_time'], e['event_id']))
    sessions = [e for e in current if e['event_type'] == 'session']
    practice = int(any(e['event_type'] == 'practice' for e in current))
    passed = int(any(e['score_pct'] >= 80 for e in quizzes))
    late_practice = late_completion = 0
    for m in modules:
        if m['module_id'] >= module_id:
            continue
        history = [e for e in available if e['module_id'] == m['module_id']]
        submissions = [e for e in history if e['event_type'] == 'practice']
        late_practice += int(bool(submissions) and min(e['event_time'] for e in submissions) > m['deadline'])
        finished, _ = completion(history)
        late_completion += int(finished is not None and finished > m['deadline'])
    return dict(
        days_since_login=(at - max(e['event_time'] for e in logins)) / DAY if logins else None,
        no_login=int(not logins),
        quiz_score_trend=quizzes[-1]['score_pct'] - quizzes[-2]['score_pct'] if len(quizzes) >= 2 else None,
        past_late_submissions=late_practice,
        session_length=float(np.mean([e['duration_minutes'] for e in sessions])) if sessions else None,
        failed_or_dropped_sessions=sum(e['interrupted'] for e in sessions),
        time_on_task=sum(e['active_minutes'] for e in sessions),
        activities_completed=practice + passed, practice_submitted=practice,
        quiz_passed=passed, current_quiz_score=quizzes[-1]['score_pct'] if quizzes else None,
        quiz_attempt_count=len(quizzes),
        offline_participation=int(any(e['source'] == 'teacher_offline' for e in current)),
        previous_modules_completed_late=late_completion, snapshot_day=day,
    )


def simulate(seed=42, n_students=600, observation_days=120):
    """Generate events first, using independent latent drivers rather than labels."""
    if n_students != 600:
        raise ValueError('This study requires 600 students and a 420/90/90 split.')
    if observation_days < 1:
        raise ValueError('observation_days must be positive')
    rng = np.random.default_rng(seed)
    end = START + observation_days * DAY
    ids = [f'S{i:04d}' for i in range(1, n_students + 1)]
    shuffled = np.random.default_rng(seed + 1).permutation(ids)
    split = {s: ('train' if i < 420 else 'validation' if i < 510 else 'test')
             for i, s in enumerate(shuffled)}
    students, traits, support, all_events, all_modules, snapshots = [], [], [], [], [], []
    difficulty = np.array([0.0, .07, .13, .03, .16, .09, .12, .05])

    def add(events, sid, mid, kind, time, source='online', **values):
        delay = float(rng.uniform(.1, 2)) if source == 'teacher_offline' else 0
        record = dict.fromkeys(EVENT_COLUMNS)
        record.update(event_id=f'E{len(all_events) + 1:07d}', student_id=sid,
                      module_id=mid, event_type=kind, event_time=time,
                      recorded_at=time + delay * DAY, source=source, **values)
        events.append(record)
        all_events.append(record)
        return record

    for sid in ids:
        enrolled = START + float(rng.uniform(0, 7)) * DAY
        students.append(dict(student_id=sid, enrolment_time=enrolled,
                             communication_preference=rng.choice(['SMS', 'WhatsApp', 'email']),
                             split=split[sid]))
        # Continuous, overlapping drivers, not mutually exclusive learner categories.
        skill = float(rng.beta(7, 3))
        connectivity = float(rng.beta(1.5, 5))
        delay = float(rng.gamma(1.3, 2.3))
        engagement = float(rng.beta(5, 2))
        traits.append(dict(student_id=sid, latent_skill=skill,
                           latent_connectivity_failure=connectivity,
                           latent_delay_days=delay, latent_engagement=engagement))
        student_events, modules = [], []
        clock = module_clock(enrolled)
        for mid in range(1, 9):
            unlock = clock['unlock_time']
            if unlock > end:
                break
            deadline = clock['deadline']
            module = dict(student_id=sid, module_id=mid, **clock, split=split[sid])
            modules.append(module)
            events = []
            time = unlock + float(rng.uniform(.15, 1.5)) * DAY
            practice_done = False
            grant = None
            used = 0
            attempts = 0
            finished = recognized = None
            while time <= end:
                elapsed = float((time - unlock) / DAY)
                # Sparse participation continues after deadline; no forced completion.
                probability = engagement * (.18 if elapsed < delay else .8)
                if rng.random() < probability:
                    offline = rng.random() < connectivity * .7
                    source = 'teacher_offline' if offline else 'online'
                    failed = int(not offline and rng.random() < connectivity)
                    if not offline:
                        add(events, sid, mid, 'login', time)
                    duration = float(np.round(rng.uniform(5, 65), 2))
                    idle = float(np.round(duration * rng.uniform(.02, .45), 2))
                    add(events, sid, mid, 'session', time, source,
                        duration_minutes=duration, idle_minutes=idle,
                        active_minutes=round(duration - idle, 2), interrupted=failed)
                    if not failed:
                        if not practice_done and rng.random() < min(.85, .18 + elapsed * .04):
                            add(events, sid, mid, 'practice', time, source,
                                accuracy_pct=int(rng.integers(0, 11) * 10))
                            practice_done = True
                        if time > deadline and grant is None and rng.random() < .25:
                            grant = add(events, sid, mid, 'grant', time, 'teacher',
                                        additional_attempts=int(rng.integers(1, 3)))
                        allowed = time <= deadline or (grant is not None and used < grant['additional_attempts'])
                        if allowed and rng.random() < .6:
                            success = np.clip(skill - difficulty[mid - 1] + .035 * attempts + rng.normal(0, .09), .1, .98)
                            add(events, sid, mid, 'quiz', time, source,
                                score_pct=int(rng.binomial(10, success) * 10), valid=1,
                                grant_id=grant['event_id'] if time > deadline else None)
                            attempts += 1
                            if time > deadline:
                                used += 1
                finished, recognized = completion(events)
                if finished is not None:
                    break
                time += float(rng.uniform(.35, 1.8)) * DAY
            validate_attempts(events, deadline)
            student_events.extend(events)
            all_modules.append({**module, **outcome(events, deadline, end)})
            # Confirmed barriers are separately simulated reports, never inferred from scores.
            if events and rng.random() < .4:
                event = events[int(rng.integers(len(events)))]
                support.append(dict(student_id=sid, module_id=mid,
                                    event_time=event['event_time'], recorded_at=event['recorded_at'],
                                    confirmed_by=rng.choice(['student', 'teacher']),
                                    barrier=rng.choice(['connectivity', 'content_difficulty', 'time_constraints', 'none_reported']),
                                    split=split[sid]))
            if finished is None:
                break
            clock = next_module_clock(events)
        # Feature construction never receives outcome rows or latent traits.
        for m in modules:
            for day, at in snapshot_times(m):
                if at > end:
                    continue
                current = [e for e in known(student_events, at) if e['module_id'] == m['module_id']]
                if completion(current)[0] is not None:
                    continue
                snapshots.append({**m, 'snapshot_time': at,
                                  **features_at(student_events, modules, m['module_id'], at, day)})

    def frame(rows, columns=None):
        df = pd.DataFrame(rows, columns=columns)
        df['is_simulated'] = 1
        return df

    events_df = frame(all_events, EVENT_COLUMNS).sort_values(['event_time', 'event_id']).reset_index(drop=True)
    events_df['split'] = events_df.student_id.map(split)
    outcomes = frame(all_modules)
    outcomes['missed_deadline'] = outcomes.missed_deadline.astype('Int64')
    snap = frame(snapshots)
    joined = snap.merge(outcomes[['student_id', 'module_id', 'missed_deadline']],
                        on=['student_id', 'module_id'], validate='many_to_one')
    labelled = joined[joined.missed_deadline.notna()].copy()
    result = dict(students=frame(students), hidden_traits=frame(traits),
                  support_information=frame(support, ['student_id', 'module_id', 'event_time', 'recorded_at', 'confirmed_by', 'barrier', 'split']),
                  events=events_df, module_outcomes=outcomes, prediction_snapshots=snap,
                  student_splits=frame([dict(student_id=s, split=split[s]) for s in ids]))
    for label in ('train', 'validation', 'test'):
        result[f'labelled_{label}'] = labelled[labelled.split == label].reset_index(drop=True)
    fields = {
        'sessions': ('session', ['duration_minutes', 'idle_minutes', 'active_minutes', 'interrupted']),
        'logins': ('login', []), 'practice_submissions': ('practice', ['accuracy_pct']),
        'quiz_attempts': ('quiz', ['score_pct', 'valid', 'grant_id']),
        'teacher_grants': ('grant', ['additional_attempts']),
    }
    common = ['event_id', 'student_id', 'module_id', 'event_time', 'recorded_at', 'source', 'split', 'is_simulated']
    for table, (kind, columns) in fields.items():
        result[table] = events_df.loc[events_df.event_type == kind, common + columns].reset_index(drop=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--observation-days', type=int, default=120)
    parser.add_argument('--output', type=Path, default=ROOT / 'data')
    args = parser.parse_args()
    tables = simulate(args.seed, observation_days=args.observation_days)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(args.output / f'{name}.csv', index=False, date_format='%Y-%m-%dT%H:%M:%S.%fZ')
    (args.output / 'model_features.json').write_text(json.dumps(FEATURES, indent=2) + '\n', encoding='utf-8')
    metadata = dict(is_simulated=True, seed=args.seed, students=600, observation_start=START.isoformat(),
                    observation_end=(START + args.observation_days * DAY).isoformat(),
                    recording_close=(START + (args.observation_days + 2) * DAY).isoformat(),
                    module_difficulty=[0, .07, .13, .03, .16, .09, .12, .05])
    (args.output / 'simulation_metadata.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({name: len(df) for name, df in tables.items()}, indent=2))


if __name__ == '__main__':
    main()
