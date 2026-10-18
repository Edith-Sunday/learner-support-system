"""Run tests and write a validation report for the exported simulated CSV files."""
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.simulate import FEATURES, ROOT


def table(frame):
    # Markdown without an optional tabulate dependency.
    return '\n'.join(['| ' + ' | '.join(map(str, frame.columns)) + ' |',
                      '| ' + ' | '.join(['---'] * len(frame.columns)) + ' |'] +
                     ['| ' + ' | '.join(map(str, row)) + ' |' for row in frame.itertuples(index=False, name=None)])


def exclusions(outcomes, snapshots):
    """Separate unresolved outcomes from completed-but-policy-excluded modules."""
    excluded = outcomes[outcomes.missed_deadline.isna()].copy()
    excluded['reason'] = excluded.completion_time.notna().map({
        False: 'Future deadline; completion unobserved',
        True: 'Already completed; future deadline (conservative policy only)',
    })
    joined = snapshots.merge(excluded[['student_id', 'module_id', 'reason']],
                             on=['student_id', 'module_id'], validate='many_to_one')
    reasons = ['Future deadline; completion unobserved',
               'Already completed; future deadline (conservative policy only)']
    return pd.DataFrame([dict(reason=r, modules=int((excluded.reason == r).sum()),
                              excluded_snapshots=int((joined.reason == r).sum())) for r in reasons])


def main():
    data = ROOT / 'data'
    reports = ROOT / 'reports'
    reports.mkdir(exist_ok=True)
    run = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider'],
                         cwd=ROOT, capture_output=True, text=True)
    (reports / 'test_results.txt').write_text(run.stdout + run.stderr, encoding='utf-8')
    frames = {p.stem: pd.read_csv(p, low_memory=False) for p in sorted(data.glob('*.csv'))}
    snapshots = frames['prediction_snapshots']
    outcomes = frames['module_outcomes']
    labelled = pd.concat([frames[f'labelled_{s}'] for s in ('train', 'validation', 'test')])
    missing = pd.DataFrame({'feature': FEATURES,
                            'missing_count': [int(snapshots[f].isna().sum()) for f in FEATURES],
                            'missing_percent': [round(snapshots[f].isna().mean() * 100, 2) for f in FEATURES]})
    rates = labelled.groupby(['snapshot_day', 'split']).missed_deadline.agg(['count', 'mean']).reset_index()
    rates.columns = ['snapshot_day', 'split', 'labelled_snapshots', 'missed_deadline_rate']
    rates['missed_deadline_rate'] = rates.missed_deadline_rate.round(4)
    status = outcomes.module_status.value_counts().rename_axis('status').reset_index(name='count')
    metadata = json.loads((data / 'simulation_metadata.json').read_text())
    report = f'''# Simulated data validation report

All records and findings are simulated. No real students or intervention effects are represented.

Seed: {metadata['seed']}. Activity observation: {metadata['observation_start']} through {metadata['observation_end']} (inclusive).
Offline recording closes by {metadata['recording_close']}. Rates below describe eligible snapshots, not independent students.

## Record counts

{table(pd.DataFrame([(k, len(v)) for k, v in frames.items()], columns=['table', 'rows']))}

Events are counted once in `events.csv`; the event-specific CSVs are views of those same events.
Modules count only unlocked student-module pairs, not 600 times eight.
Module outcomes with blank export targets: {int(outcomes.missed_deadline.isna().sum())}.
Unlabelled snapshots excluded from labelled exports: {len(snapshots) - len(labelled)}.

## Why outcomes are excluded

{table(exclusions(outcomes, snapshots))}

The first group is unresolved: its deadline lies beyond the observation window and completion is unobserved even after recording reconciliation. The second group already has an observed on-time completion, but its target remains blank solely because the conservative policy excludes every module whose deadline is beyond the activity window. These are policy exclusions, not uncertainty about whether those modules were completed. Both groups remain excluded from labelled exports. Completion here means occurrence within the activity window established by the final recording reconciliation.

## Offline progression correction

Previous-module timeliness still uses completion occurrence. The next module now unlocks at first system recognition of BOTH requirements; its deadline and day-3/7/10 snapshots use that actual unlock. The clock is established once and is never backdated by delayed occurrence records. Event-time and recorded-at filtering continues to preserve historical snapshots.

## Completion status at activity observation end

{table(status)}

## Feature missingness (all prediction snapshots)

{table(missing)}

## Simulated missed-deadline rates

{table(rates)}

These rates use only known labels and exclude modules whose original deadline exceeds the observation end.
Several snapshots may refer to the same module. Completed modules leave later snapshot cohorts, so rates across days are not directly comparable intervention effects.

## Tests

Exit code: {run.returncode}.

```text
{run.stdout.strip()}
```

Full output: `test_results.txt`. Tests include the Monday-completion/Wednesday-unlock regression, no backdating after delayed records, exclusion-reason counts, threshold and deadline boundaries, grant exhaustion, offline availability, historical counts, all-cohort progression, all-snapshot as-of checks, censoring, split membership, and reproducibility.

## Remaining limitations

Artificial behavioural distributions have not been calibrated against real learners. Confirmed barriers are also simulated reports. No efficacy, fairness, predictive accuracy, or causal claim follows from these data.
The simulation provides at most one late-attempt grant per module, of one or two attempts; a failed learner may remain overdue. Pre-deadline attempts have no policy cap.
Offline events have at most two days of recording delay and are reconciled after the activity window; provisional operational outcomes could differ before reconciliation.
No preprocessing or models were fitted, and no communications were sent.
'''
    (reports / 'validation_report.md').write_text(report, encoding='utf-8')
    print(run.stdout)
    print(f'Report: {reports / "validation_report.md"}')
    raise SystemExit(run.returncode)


if __name__ == '__main__':
    main()
