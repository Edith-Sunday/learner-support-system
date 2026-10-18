# Interactive UI follow-up — 17 October 2026

The four requested corrections are complete. The additional Module 1 model is evaluated separately in [interactive_model_evaluation.md](interactive_model_evaluation.md); numeric interactive scoring remains disabled. No old unscored assessment was overwritten or backfilled.

## Changes

1. A checkpoint that produced no numeric score displays **Last checked** and, within the first minute, **Checked just now**. Successful numeric assessment formatting retains **Last assessed**. Elapsed values use the selected demo time, not the computer clock.
2. Both learner My learning and the staff profile display **No assessment due — waiting for content.** after available work is complete. Earlier processing attempts remain visible in History. Module 2 remains unavailable; learning requirements, stored module dates and progression rules are unchanged.
3. The offline record-type selector now sits outside the form so switching type rerenders immediately. Only quiz entry displays and accepts a quiz score. Practice passes no score. Fresh role/learner entries use a fresh selector identity to prevent an old hidden quiz widget from disagreeing with the displayed practice selection. Date/time semantics and submission idempotency remain unchanged.
4. Every formula appears directly above its coefficient input at desktop and narrow widths, with its formula-specific accessible label. Blank defaults, persisted drafts, exact grading and submission protections are retained.

## Checks actually performed

- Read the previous assessment review and inspected the existing UI, store, feature derivation, frozen model and original datasets before changing code.
- Ran the final complete suite: **66 passed in 28.48 seconds**. Evidence: `interactive_module1_role_final_tests.txt`. This includes all 60 prior tests and six new tests covering labels/relative clocks, conditional UI, waiting/history preservation, formula/blank inputs, online versus delayed-offline feature equivalence, occurrence and recording cutoffs, student isolation, censoring, missing values, predictor selection, training-only preprocessing, reproducibility, reloading, budget ties, selection and first-warning calculations.
- Earlier test runs exposed two mistakes in the new test fixture (assuming an existing draft receipt, then assuming the first formula was hydrogen). Both test assumptions were corrected. One sandbox run stalled and was interrupted; it is not counted as passing. Authorised runs outside that restriction completed.
- Used a new isolated database, `runtime/module1_browser_qa.sqlite3`, with two demonstration learners. No clock or learner data in either original database was changed for browser checks.
- Inspected the actual browser at desktop 1280×720 and narrow 390×844. Confirmed Last checked/Checked just now, waiting status in staff and learner views, a retained unscored History row, practice with no score, quiz with a score field, and formula-before-input placement. Committed coefficient 2, navigated to Lesson and back, and observed the draft value remained 2.
- Browser role switching exposed a stale offline selector after returning from Learner to Staff. Fixed it, restarted the isolated server, selected quiz, switched to Learner and back to Staff, reopened interactive Support, and verified practice was selected with no quiz-score control. The final full-suite result above follows that code change.
- Narrow-screen checks confirm the focused controls work. Existing wide staff tables still wrap words heavily at 390px; a broader mobile table redesign was not part of these four changes. This is a remaining usability limitation, not a claim that the whole dashboard is mobile-optimised.
- The additional experiment reconstructed all 1,321 eligible snapshots from original event cutoffs, repeated both fits, and verified exact saved/reloaded predictions. Neither fit produced convergence warnings. Details, counts and limitations are in the model report.

## Screenshots

Saved under `reports/interactive_ui_followup_screenshots/`:

- `last_checked.jpg`, `last_checked_narrow.jpg`
- `waiting_staff.jpg`, `waiting_learner.jpg`, `waiting_narrow.jpg`
- `offline_practice.jpg`, `offline_quiz.jpg`, `offline_practice_narrow.jpg`
- `coefficients_desktop.jpg`, `coefficients_narrow.jpg`

The screenshots were visually inspected during the checks. Some earlier coefficient captures retain the previous instructional word “beside”; the final caption now correctly says “below”. Formula/input placement is unchanged from those captures.

## Preservation

All **83 pre-existing data, model and report files** matched the pre-task SHA-256 manifest. All rows of every pre-existing table in both `runtime/interactive_demo.sqlite3` and `runtime/staff_demo.sqlite3` matched the SQLite backups, including drafts, assessments, grants, clocks and referrals. See `interactive_module1_preservation.json`. Existing reports are retained as historical records; this report supersedes their current-UI descriptions.

New models and evaluation tables are confined to `models/interactive_module1/`. Original simulation data, original frozen pipelines, feature allowlist, thresholds and evaluation outputs were not changed. README now points to the new reports and safe reproduction instructions. No packages, Module 2 content, messages or external deployment were added.

## Review readiness

The fresh isolated preview remains running at **http://127.0.0.1:8503**. It uses QA records; the original interactive database is preserved. The viewport override has been reset.

Logistic regression won the predeclared validation comparison, but gains over the progress rule are mixed and early score ties are substantial. Recommend keeping numeric scoring disabled and reviewing whether a transparent progress-based list is more useful before any integration. No new operational policy was enabled. Results concern an artificial simulation; the previously inspected test set is exploratory evidence, not an untouched evaluation or proof of improved learner outcomes.
