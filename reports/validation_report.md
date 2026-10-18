# Simulated data validation report

All records and findings are simulated. No real students or intervention effects are represented.

Seed: 42. Activity observation: 2026-01-01T00:00:00+00:00 through 2026-05-01T00:00:00+00:00 (inclusive).
Offline recording closes by 2026-05-03T00:00:00+00:00. Rates below describe eligible snapshots, not independent students.

## Record counts

| table | rows |
| --- | --- |
| events | 65560 |
| hidden_traits | 600 |
| labelled_test | 885 |
| labelled_train | 4423 |
| labelled_validation | 822 |
| logins | 24948 |
| module_outcomes | 2835 |
| practice_submissions | 2811 |
| prediction_snapshots | 6187 |
| quiz_attempts | 7122 |
| sessions | 29882 |
| student_splits | 600 |
| students | 600 |
| support_information | 1099 |
| teacher_grants | 797 |

Events are counted once in `events.csv`; the event-specific CSVs are views of those same events.
Modules count only unlocked student-module pairs, not 600 times eight.
Module outcomes with blank export targets: 39.
Unlabelled snapshots excluded from labelled exports: 57.

## Why outcomes are excluded

| reason | modules | excluded_snapshots |
| --- | --- | --- |
| Future deadline; completion unobserved | 31 | 39 |
| Already completed; future deadline (conservative policy only) | 8 | 18 |

The first group is unresolved: its deadline lies beyond the observation window and completion is unobserved even after recording reconciliation. The second group already has an observed on-time completion, but its target remains blank solely because the conservative policy excludes every module whose deadline is beyond the activity window. These are policy exclusions, not uncertainty about whether those modules were completed. Both groups remain excluded from labelled exports. Completion here means occurrence within the activity window established by the final recording reconciliation.

## Offline progression correction

Previous-module timeliness still uses completion occurrence. The next module now unlocks at first system recognition of BOTH requirements; its deadline and day-3/7/10 snapshots use that actual unlock. The clock is established once and is never backdated by delayed occurrence records. Event-time and recorded-at filtering continues to preserve historical snapshots.

## Completion status at activity observation end

| status | count |
| --- | --- |
| completed_on_time | 1922 |
| completed_late | 485 |
| overdue | 397 |
| in_progress | 31 |

## Feature missingness (all prediction snapshots)

| feature | missing_count | missing_percent |
| --- | --- | --- |
| days_since_login | 406 | 6.56 |
| no_login | 0 | 0.0 |
| quiz_score_trend | 4937 | 79.8 |
| past_late_submissions | 0 | 0.0 |
| session_length | 1540 | 24.89 |
| failed_or_dropped_sessions | 0 | 0.0 |
| time_on_task | 0 | 0.0 |
| activities_completed | 0 | 0.0 |
| practice_submitted | 0 | 0.0 |
| quiz_passed | 0 | 0.0 |
| current_quiz_score | 3017 | 48.76 |
| quiz_attempt_count | 0 | 0.0 |
| offline_participation | 0 | 0.0 |
| previous_modules_completed_late | 0 | 0.0 |
| snapshot_day | 0 | 0.0 |

## Simulated missed-deadline rates

| snapshot_day | split | labelled_snapshots | missed_deadline_rate |
| --- | --- | --- | --- |
| 3 | test | 392 | 0.3265 |
| 3 | train | 1917 | 0.3213 |
| 3 | validation | 351 | 0.3932 |
| 7 | test | 291 | 0.4399 |
| 7 | train | 1451 | 0.4245 |
| 7 | validation | 270 | 0.5111 |
| 10 | test | 202 | 0.6337 |
| 10 | train | 1055 | 0.5839 |
| 10 | validation | 201 | 0.6866 |

These rates use only known labels and exclude modules whose original deadline exceeds the observation end.
Several snapshots may refer to the same module. Completed modules leave later snapshot cohorts, so rates across days are not directly comparable intervention effects.

## Tests

Exit code: 0.

```text
..................                                                       [100%]
18 passed in 15.83s
```

Full output: `test_results.txt`. Tests include the Monday-completion/Wednesday-unlock regression, no backdating after delayed records, exclusion-reason counts, threshold and deadline boundaries, grant exhaustion, offline availability, historical counts, all-cohort progression, all-snapshot as-of checks, censoring, split membership, and reproducibility.

## Remaining limitations

Artificial behavioural distributions have not been calibrated against real learners. Confirmed barriers are also simulated reports. No efficacy, fairness, predictive accuracy, or causal claim follows from these data.
The simulation provides at most one late-attempt grant per module, of one or two attempts; a failed learner may remain overdue. Pre-deadline attempts have no policy cap.
Offline events have at most two days of recording delay and are reconciled after the activity window; provisional operational outcomes could differ before reconciliation.
No preprocessing or models were fitted, and no communications were sent.
