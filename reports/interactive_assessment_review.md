# Interactive assessment review — 17 October 2026

The usability and content-availability changes are implemented. Checkpoint collection and audit integration use the existing frozen logistic regression pipeline, but **interactive scores are deliberately withheld** because three required measurements are unsupported. This is not evidence of real-world predictive accuracy or improved learner outcomes.

## Changes

- Practice and quiz now have one blank input per chemical formula, proper subscripts/arrows, and accessible formula-specific labels. The original question order, exact keys, server grading, feedback and transactional submission protections remain. Drafts persist after a field is committed (Tab/Enter or leaving the field); values are stored in the existing draft format for compatibility.
- Teachers see “Allow extra attempts” and “When did the learner complete this?” with separate UTC date/time controls. The explanation distinguishes completion from recording. The unchanged default preserves the exact demo instant, including seconds; edited times select a minute. Occurrence validation, grants, original deadlines and audit timestamps remain unchanged.
- Explicit `content_availability` records mark Module 1 available and Module 2 unavailable. Module 2 shows “Waiting for content”, is excluded from early review, overdue queues and deadline reminders, and remains incomplete. Original unlock/deadline records remain in History. Existing unavailable-content referrals are retained and displayed with the exclusion reason. Publishing future content requires an explicit deadline policy; an expired stored deadline must not silently become actionable.
- An explicit study timer stores actual wall-clock session duration separately from an interaction-based active-time estimate. Completed-session mean duration can populate the original session-length input. Incomplete sessions are excluded. Active estimates are not silently substituted for the original active-study predictor.
- Immutable day-3/7/10 assessment-attempt records store scheduled time, processing time, actual save time, all 15 feature values, pipeline identity, nullable score and reason. Staff can inspect inputs, current progress and processing notes. Assessed-list size/full-list controls and deterministic descending-score/learner-ID ordering are implemented; currently no interactive learner receives a numeric score.

No automatic 0.08 referral, risk categories, messages, retraining, historical data regeneration or Module 2 content were added.

## Original model compatibility

Inspected `data/model_features.json`, `models/feature_order.json`, `models/selection.json`, the fitted pipeline, `src/simulate.py:features_at`, and the original dictionary. The frozen pipeline is median imputation with indicators, scaling and logistic regression. Its fitted missingness indicators cover only `days_since_login`, `quiz_score_trend`, `session_length` and `current_quiz_score`. SHA-256 identity is checked against the saved selection before loading predictions; feature order must exactly match the allowlist.

The app has no authenticated login, reliable dropped-session instrumentation or complete active-study measurement. Therefore `no_login`, `failed_or_dropped_sessions` and `time_on_task` are missing. These were never missing in training and have no fitted missingness indicators. Although the imputer could mechanically replace them, doing so would silently imply observations the app does not have. The conservative compatibility gate withholds predictions and records the precise reason. Completing the supported integration does **not** make numeric interactive scoring operational. Reliable measurements and an explicitly reviewed compatibility policy are required before that can change; no frozen model or policy was altered here.

## Feature-by-feature mapping

All submission features use the unchanged original derivation, filtering both event occurrence and recording time at the scheduled checkpoint. Offline aggregate scores remain aggregate observations, without invented question answers. Zeros below mean no qualifying record known at that checkpoint, not proof that no unrecorded offline work occurred.

| Predictor | Original definition / units | Interactive source and limitation |
|---|---|---|
| days_since_login | Fractional days since latest known online login | Missing: selecting a role/learner or starting study is not authentication. |
| no_login | 1 if no known online login; otherwise 0 | Missing, not 1: login instrumentation itself is absent. Blocks scoring. |
| quiz_score_trend | Latest minus previous known valid current-module score, percentage points | Submission scores ×10, ordered by occurrence and record ID; missing with fewer than two known attempts. |
| past_late_submissions | Count of earlier modules whose first known practice occurred after their deadline | Observed structural zero for Module 1, which has no earlier modules. Future modules require extending the mapping. |
| session_length | Mean known current-module session duration including idle, minutes | Explicitly started/ended Module 1 study sessions, actual elapsed minutes, known by cutoff. Missing if none ended; unclosed sessions excluded. Covers recorded sessions only, not offline/uninstrumented study. |
| failed_or_dropped_sessions | Count of interrupted current-module sessions | Missing: no reliable failure/interruption telemetry. Browser closure and role switches prove neither a login nor connectivity failure. Blocks scoring. |
| time_on_task | Sum of current-module active minutes excluding idle | Missing: interaction gaps provide only an estimate and cannot faithfully measure all active work. That estimate is displayed separately, never substituted. Blocks scoring. |
| activities_completed | practice_submitted + quiz_passed, 0–2 | Known valid practice and quiz records; zero when neither is known. |
| practice_submitted | Any known current-module practice, 0/1 | Online submission or teacher-recorded offline practice, including incorrect practice. |
| quiz_passed | Any known valid score ≥80%, 0/1 | At least one accepted score ≥8/10; later lower scores do not undo it. |
| current_quiz_score | Most recent known valid score, percent | Accepted online/offline score ×10, occurrence/record-ID ordering; missing before an attempt is known. |
| quiz_attempt_count | Known valid current-module attempts, count | Accepted submission records only; invalid submissions and duplicate requests add nothing. Zero is genuine absence of known accepted attempts. |
| offline_participation | Any known teacher-offline current-module activity, 0/1 | Accepted offline practice/quiz records mapped to original teacher_offline route; zero means none recorded. No fabricated offline sessions. |
| previous_modules_completed_late | Earlier modules with known late completion, count | Structural zero for Module 1. No unavailable Module 2 prediction is produced. |
| snapshot_day | Checkpoint horizon, 3/7/10 days | Scheduled checkpoint from original unlock; never replaced by an arbitrary elapsed day after a jump. |

## Timer and time semantics

The timer begins only on “Start study session” and ends only on “End study session”. Reruns while that learner is selected update observed intervals. Actual UTC wall timestamps determine elapsed minutes; demo-clock advancement does not add time. A consecutive interaction gap of at most 60 seconds contributes to the **estimated** active minutes; a longer gap contributes no active minutes. This is an explicit conservative interaction heuristic, not measured attention. Long idle periods still belong to an explicitly closed session's total elapsed duration. An abandoned/unclosed session stays unfinished and is excluded from model aggregation. No browser-close detector, background heartbeat or connectivity inference is claimed.

The session row stores its demo occurrence/recording times as well as actual start/end times. Only completed sessions recorded by a checkpoint can enter its mean. If the actual system clock moves backwards, an update is rejected. The demonstration clock remains forward-only and independent.

## Assessment triggering and clock jumps

`AssessmentService.run_due()` executes when the interactive app renders, including reruns after staff clock advancement. There is no background scheduler. It examines due day-3/7/10 checkpoints for available modules that were not already recognised complete at that checkpoint. The primary key `(student_id,module_id,checkpoint)` makes repeated runs idempotent. Existing rows are never updated after delayed evidence arrives.

For a forward jump, each missed checkpoint is recorded with features known by its original scheduled time and the actual processing demo time plus real save time. Later-recorded submissions are excluded even if their occurrence was earlier. Late processing is explicitly recorded; no historical warning or score is fabricated. Already-completed or now-overdue modules cannot enter the active early-review list. Such missed checkpoints can remain as unscored audit records. Overdue referrals for available unfinished modules remain independent of model score. Module 2 is excluded before checkpoint processing.

“Last assessed” is relative to the selected shared demo time and describes the processing attempt, which may have produced no score; the assessment note explains that result. Current progress is shown separately from frozen checkpoint inputs. Confirmed challenges continue to require student/teacher confirmation. Neither inactivity nor a score is described as proof of a barrier.

## Validation

The full suite after the final code changes passed **60 tests in 26.90 seconds**, recorded in `interactive_assessment_tests.txt`. The earlier focused suite passed 20 tests. A restricted sandbox run stalled during Streamlit testing and was interrupted; the authorised run outside that restriction passed. That stalled invocation is not counted as a pass.

New coverage checks blank coefficient fields, draft navigation, invalid/incomplete late submissions without grant consumption, actual session/active distinctions, idle handling, unchanged elapsed minutes after a demo jump, genuinely missing measurements, pre-checkpoint eligibility, completion exclusion, duplicate checkpoint protection, delayed offline recording cutoffs, immutable earlier records, teacher date/time controls, and waiting-for-content exclusion after a 40-day jump. Existing completion/grant/offline/progression, simulation, frozen-model and dashboard tests remain in the full suite.

Browser checks use the original app read-only for the retained learner's waiting status and an isolated `runtime/assessment_browser_qa.sqlite3` on port 8502 for changed workflows. The original demo clock was not advanced. Historical All learners still showed 600 learners, 288 active-before-deadline, 308 overdue and four completed-all-eight learners. Screenshots are saved in `interactive_assessment_screenshots/`; the coefficient layout was inspected at 390×844 and the viewport then restored. Browser checks are detailed in the completion notes below; automated time-jump/concurrency checks are not represented as browser actions.

## Preservation

All **75 pre-existing files** under data, models and reports matched the hashes captured before this task. Original table rows in both the interactive database and historical staff database matched their backups exactly, including the existing learner, two submissions, one grant, original module dates, drafts and all 308 historical referrals. New schema is additive. Evidence: `interactive_assessment_integrity.json`. Existing reports remain unchanged; this report supersedes only their statements about the current interactive UI.

## Reproduce and limits

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

The main app is http://127.0.0.1:8501. For isolated exploration, set `INTERACTIVE_DEMO_DB` to a separate SQLite path before launching on another port. The browser-check preview on http://127.0.0.1:8502 uses only isolated interactive records. Do not advance the main demonstration clock for destructive checks.

Remaining gaps: authenticated login and reliable activity/failure instrumentation; numerical interactive predictions withheld; no background scheduling; no validated real-world score interpretation; no production authentication; Module 2 remains unavailable. Existing test data have already been inspected, so future policy changes are exploratory and cannot be called a fresh untouched-test evaluation. Local preview is left running for review; nothing is deployed externally.


## Final browser completion notes

After fixing draft restoration, committed P1 coefficient 2 in the isolated browser, navigated to Lesson and back to Practice, and verified the input still contained 2. The fix saves only the changed field and gives a new page entry fresh widget identities with database-backed defaults; earlier blank inputs cannot erase other saved answers. Full tests were rerun after this fix and the final readable review-table change.

Inspected the teacher completion-date/time controls and successfully recorded an offline practice submission in the isolated database; the browser displayed the saved receipt. Early review then showed current practice submitted as Yes, while its persisted day-3 input record remained unchanged. Inspected the unassessed explanation, checkpoint, Last assessed, list-size/full-list controls, and the All learners Waiting for content status. The original learner's waiting screen was checked without advancing its clock or creating new records.

Visually inspected all four requested screenshots plus the narrow-screen coefficient screenshot. Files: coefficient_entry.jpg, teacher_date_time.jpg, waiting_for_content.jpg, interactive_early_review.jpg and coefficient_narrow.jpg under interactive_assessment_screenshots. The final early-review explanation uses readable labels outside the table to avoid a narrow, excessively tall note column. Browser checks did not include simulated network failures, authentication, or a claimed numeric prediction. Those measurements remain unsupported.
