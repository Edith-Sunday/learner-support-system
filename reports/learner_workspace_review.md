# Learner chemistry workspace review

Completed 15 October 2026 in `C:\Users\hp\Documents\ChatGPT\Learner support system`.

## Implemented

- Separate Learner and Staff workspaces, with historical and interactive staff cohorts. Interactive DEMO learners and their records persist in a separate SQLite database.
- A persisted, shared UTC demonstration clock with forward-only staff advancement and a separate actual save timestamp. Refreshes do not reset the clock or enrolment.
- Module 1, Chemical Equations—From Formulae to Balancing: worked lesson, atom-count examples, hints, three practice questions, ten quiz questions, explicit choices, server-side grading, question feedback and skill labels. Smallest positive integer coefficients are required. Invalid/incomplete answers do not create attempts. Draft answers persist after leaving a field.
- Practice submission counts even when incorrect. Quiz pass is 8/10; both requirements are necessary. Earlier valid passes remain valid. Unlimited quiz submissions are permitted through the original deadline, including equality. Later submissions require an unused teacher grant, checked at submission and consumed atomically. Duplicate requests cannot consume extra grants.
- Teacher grants of one or two attempts with staff identity, reason and timestamps. Offline practice/quiz entry validates occurrence bounds, integer scores, and grant availability at occurrence for late quizzes. Aggregate offline scores do not invent question feedback.
- Previous-module timeliness uses completion occurrence. Module 2 unlock and its 14-day deadline use recognition and are never backdated. Module 2 explicitly has no content or assessments in this prototype.
- Downloadable lesson, practice and quiz materials; learner quiz download excludes the key. Teacher key is exposed only in the staff demonstration workspace. The role switch provides no security boundary.
- Communication preferences, support requests, attempt history, staff assignment/review/support actions and overdue referrals. Review status cannot complete learning requirements. Interactive learners are labelled “Not yet assessed — interactive scoring not connected”; no synthetic risk or activity measurements are assigned.

Implementation: `src/interactive_store.py`, `src/interactive_ui.py`, `src/chemistry_content.py`, `content/chemical_equations.md`, and integration in `dashboard.py`. Regression coverage is in `tests/test_interactive_workspace.py`.

## Checks actually performed

### Automated

The full suite passed **54 tests in 40.23 seconds**. After the final offline timestamp input and teacher-control caption adjustment, the focused suite passed **14 tests in 11.17 seconds**. See `learner_workspace_full_tests.txt` and `learner_workspace_tests.txt`. The full suite was not rerun after that final UI adjustment.

Coverage includes enrolment/deadlines; incorrect practice counting; 7/10 failure and exact 8/10 pass; pass without practice; one-time progression; deadline equality and stale-form submission checks; one/two-grant exhaustion; concurrent/duplicate submission protection; offline Monday occurrence with Wednesday recognition; delayed on-time completion and late referral closure; invalid scores/times; preserved earlier passes; preferences/support persistence; independent staff review; content chemistry/keys; and Streamlit AppTest learner/staff agreement.

An initial form-key collision was corrected. A later restricted test invocation could not access pytest temporary directories; the authorised rerun passed. These failed invocations are not described as passing tests.

### Actual browser inspection

Used the local Streamlit app in the in-app browser. Checked the historical cohort still displayed 600 learners, 288 active cases, 308 overdue cases and four learners completing all eight simulated modules.

Enrolled interactive DEMO001 with SMS preference. Viewed the lesson and blank quiz (multiple-choice answers were unselected). Submitted incorrect answers to all three practice questions: the resulting 0/3 submission counted towards completion. Submitted an exact 8/10 quiz and inspected the pass and question feedback. The connected staff Overview showed Module 1 completed on time and Module 2 active with unavailable content. Opened the staff grant/offline controls and saved a one-attempt teacher grant; the visible success receipt confirmed the original deadline was unchanged.

Saved and visually inspected screenshots of lesson, practice, quiz, results and teacher controls in `learner_workspace_screenshots/`. The teacher screenshot shows controls before the grant was submitted. Offline submission, clock advancement, post-deadline exhaustion and support persistence were tested automatically, not claimed as separately exercised browser journeys. No mobile-browser or multi-user deployment testing was performed.

## Preservation and retained demonstration state

All **66 pre-existing data/model/report files** matched their pre-change SHA-256 hashes; see `learner_workspace_integrity.json`. Frozen datasets, student splits, pipelines, model selection, simulation settings and earlier reports were not regenerated or changed. Existing historical staff records were compared with the pre-change database backup. New interactive records use a separate database. README now documents the new workflow without removing the earlier reproduction instructions.

Browser QA leaves DEMO001 available for review, with incorrect practice, a valid 8/10 pass and one unused additional Module 1 attempt. The shared demo clock remains at 15 October 2026, 15:40:22.128388 UTC; enrolment and recognised completion occurred at that demonstration instant. Its Module 2 deadline is 29 October 2026 at the same time. Actual save timestamps separately capture wall-clock saves. Enrol another learner for a fresh journey; no existing records were cleared.

## Reproduce

From the project folder:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Open http://127.0.0.1:8501. Select Learner to enrol and study. Select Staff → Interactive demonstration for the corresponding profile and Support controls. `INTERACTIVE_DEMO_DB` optionally selects a separate interactive database; `LEARNER_DEMO_DB` continues to select the historical staff database. Tests use temporary databases. The local preview is left running for review.

## Limits and remaining scope

This is a local demonstration, not authenticated staff/learner access. Only Module 1 content is implemented. The fixed quiz is not a validated mastery instrument; a pass does not establish mastery of every skill. Question randomisation, secure identity, production operation and interactive model scoring remain future work. Existing model results measure artificial simulation performance, not proven real-world accuracy or improved outcomes. The test set has already been inspected, so later policy changes remain exploratory.

No messages were sent, models retrained, simulation regenerated or external deployment performed. No additional learner-workspace implementation is started after this review.
