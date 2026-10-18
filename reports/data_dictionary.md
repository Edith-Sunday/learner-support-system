# Simulated data dictionary

All CSV records have `is_simulated=1`. UTF-8 CSVs use an empty field for missing/not-applicable values. Timestamps are ISO 8601 UTC with microsecond precision. Internal calculations retain nanoseconds; CSV timestamp rounding can differ by less than one microsecond. Numbers are unscaled: a score of 80 means 80%, not 0.8. No missing-value imputation is performed.

## Tables and row units

| File in data | One row represents | Columns |
| --- | --- | --- |
| students.csv | One simulated student | student_id, enrolment_time, communication_preference, split, is_simulated |
| student_splits.csv | One student's split assignment | student_id, split, is_simulated |
| hidden_traits.csv | One student's private simulation drivers | student_id, latent_skill, latent_connectivity_failure, latent_delay_days, latent_engagement, is_simulated |
| events.csv | One source event, sorted by occurrence and ID | All common event columns and all event payload columns below; irrelevant payload cells are blank |
| logins.csv | One online login | Common event columns |
| sessions.csv | One online or offline session summary | Common event columns, duration_minutes, idle_minutes, active_minutes, interrupted |
| practice_submissions.csv | One submitted practice | Common event columns, accuracy_pct |
| quiz_attempts.csv | One submitted quiz | Common event columns, score_pct, valid, grant_id |
| teacher_grants.csv | One teacher authorisation | Common event columns, additional_attempts |
| support_information.csv | One simulated confirmed barrier report | student_id, module_id, event_time, recorded_at, confirmed_by, barrier, split, is_simulated |
| module_outcomes.csv | One unlocked student-module | student_id, module_id, unlock_time, unlock_known_at, deadline, split, completion_time, completion_known_at, missed_deadline, module_status, is_simulated |
| prediction_snapshots.csv | One eligible day-3, day-7, or day-10 snapshot | student_id, module_id, unlock_time, unlock_known_at, deadline, split, snapshot_time, all 15 predictors below, is_simulated |
| labelled_train.csv / labelled_validation.csv / labelled_test.csv | One eligible snapshot with a known label in the specified split | All snapshot columns plus missed_deadline |

Event-specific tables are views of `events.csv`; do not concatenate them with the full event table or events will be duplicated. `student_id` joins students and splits; `(student_id,module_id)` joins outcomes and snapshots. `(student_id,module_id,snapshot_day)` uniquely identifies snapshots. `grant_id` references the grant's `event_id`. Hidden traits have no split column because they are not modelling records; their assignment can only be audited via student_splits.

## Identifiers, support, audit, and source-event columns

Common event columns are event_id, student_id, module_id, event_time, recorded_at, source, split, and is_simulated. `event_type` is additionally present in the combined events table. Source-event fields are inputs to feature derivation, not automatic model predictors.

| Column | Role | Units / meaning | Missing values |
| --- | --- | --- | --- |
| student_id | Identifier | Artificial S0001 to S0600 | Never |
| module_id | Identifier | Sequential integer 1–8 | Never |
| event_id | Identifier | Unique source event ID; generation-order sequence | Never |
| split | Audit | train, validation, test; student-level membership | Never |
| is_simulated | Audit | Integer 1 on every row | Never |
| enrolment_time | Audit | UTC enrolment instant; module 1 unlock | Never |
| communication_preference | Support | SMS, WhatsApp, email | Never |
| event_type | Source event | login, session, practice, quiz, grant | Never |
| event_time | Source event / support | UTC occurrence instant | Never |
| recorded_at | Source event / support | UTC instant record becomes available | Never |
| source | Source event | online, teacher_offline, teacher (grants) | Never |
| duration_minutes | Source event | Session total minutes including idle time | Non-session rows only |
| idle_minutes | Source event | Session minutes excluded from active work | Non-session rows only |
| active_minutes | Source event | duration_minutes minus idle_minutes | Non-session rows only |
| interrupted | Source event | 1 for a dropped/failed online session, else 0; counted once | Non-session rows only |
| accuracy_pct | Source event | Practice accuracy, 0–100%; irrelevant to completion | Non-practice rows only |
| score_pct | Source event | Ten-question quiz score, 0–100 in steps of 10 percentage points | Non-quiz rows only |
| valid | Source event | 1 for valid result; only valid results can pass | Non-quiz rows only |
| grant_id | Identifier | Authorising teacher grant event_id for post-deadline quiz | Pre-deadline quiz or non-quiz |
| additional_attempts | Source event | Granted post-deadline count, 1 or 2 | Non-grant rows only |
| confirmed_by | Support | student or teacher, simulated confirming party | Never |
| barrier | Support | connectivity, content_difficulty, time_constraints, none_reported; confirmed statement, not inferred risk | Never |
| unlock_time | Audit | UTC actual access time; previous completion_known_at or enrolment; established once, never backdated | Never |
| unlock_known_at | Audit | UTC availability of unlock; equals unlock_time, retained for schema compatibility | Never |
| deadline | Audit | Original unlock_time + 14 days, inclusive boundary | Never |
| snapshot_time | Audit | unlock_time + snapshot_day, UTC | Never |

## Explicit model predictors

Only these 15 fields appear in `model_features.json`. Aggregates for current module use recorded information available by snapshot_time; login history spans all modules for that student. Counts of previous modules use only earlier module IDs and information known at the snapshot.

| Column | Role | Units / definition | Missing values |
| --- | --- | --- | --- |
| days_since_login | Predictor | Fractional elapsed days since latest known online login | No known login |
| no_login | Predictor | 1 if no known online login, otherwise 0 | Never |
| quiz_score_trend | Predictor | Latest minus previous known valid quiz score, percentage points | Fewer than two attempts |
| past_late_submissions | Predictor | Number of earlier modules whose first known practice submission occurred after its deadline | Never; zero when none |
| session_length | Predictor | Mean recorded duration_minutes for current module, includes idle | No known sessions |
| failed_or_dropped_sessions | Predictor | Count of current-module interrupted sessions | Never; zero when none |
| time_on_task | Predictor | Sum of current-module active_minutes, excludes idle | Never; zero when none |
| activities_completed | Predictor | practice_submitted + quiz_passed, 0–2 | Never |
| practice_submitted | Predictor | 1 if any current-module practice submission is known | Never |
| quiz_passed | Predictor | 1 if any known valid current-module score is at least 80% | Never |
| current_quiz_score | Predictor | Most recent known valid current-module quiz score in percent | No known attempt |
| quiz_attempt_count | Predictor | Number of known valid current-module quiz attempts | Never; zero when none |
| offline_participation | Predictor | 1 if teacher_offline activity in current module is known | Never |
| previous_modules_completed_late | Predictor | Earlier modules whose completion is known and effective completion is after original deadline | Never; zero when none |
| snapshot_day | Predictor | Integer elapsed-day horizon: 3, 7, or 10 | Never |

## Outcomes (never predictors)

| Column | Role | Units / meaning | Missing values |
| --- | --- | --- | --- |
| completion_time | Outcome | UTC first completion occurrence during observation; determines this module's timeliness, not next-module unlock | Requirements not both met |
| completion_known_at | Outcome | UTC earliest recognition of both requirements from recorded times; actual unlock of next module if within observation | Requirements not both recorded |
| missed_deadline | Outcome / target | 0 if both met by original inclusive deadline; 1 otherwise, including late completion | Deadline after activity observation end: either unresolved completion or already completed but conservatively excluded |
| module_status | Outcome | in_progress, completed_on_time, overdue, completed_late, as of observation end with final recording reconciliation | Never |

Blank targets for future deadlines have two distinct meanings in the validation report: completion remains unobserved, or completion is observed but the conservative export policy withholds the label. Both are excluded from labelled exports. The latter retains its observed completion timestamp and completed_on_time status. These report categories are not added as model predictors.

## Private simulation drivers (never predictors)

| Column | Role | Units / meaning | Missing values |
| --- | --- | --- | --- |
| latent_skill | Hidden simulation trait | Baseline success propensity, 0–1 | Never |
| latent_connectivity_failure | Hidden simulation trait | Connection failure propensity, 0–1 | Never |
| latent_delay_days | Hidden simulation trait | Initial engagement delay in elapsed days | Never |
| latent_engagement | Hidden simulation trait | Activity propensity, 0–1 | Never |

`simulation_metadata.json` records is_simulated, seed (integer), students (count), observation_start, observation_end, recording_close (UTC timestamps), and module_difficulty (eight probability offsets). `model_features.json` is an ordered JSON list of the predictor names above. Neither JSON file contains training records.
