# Dashboard redesign review

Review date: 15 October 2026 (Africa/Kigali).

This is an interface redesign of the existing simulated-data prototype. The learning rules, frozen models, source datasets and staff storage implementation were retained. No learner quiz system, attempt grants or offline-result entry was implemented.

## Completed implementation

- All learners is the default page, followed by Early review, Overdue referrals and Model evaluation. Demo settings are collapsed; the selected UTC time remains visible.
- All learners has four summary cards, a mutually exclusive historical status chart, learner-ID search, status/module/staff filters, Clear filters, filtered/total counts and a bounded table with six essential columns.
- A dedicated learner profile has Back to list and Overview, Learning activity, Support and History tabs. Filter values are held separately from temporary widgets so they survive profile navigation.
- Overview shows completed modules out of eight, the practice/valid-quiz checklist, latest quiz, original deadline and readable time remaining/overdue. Learning completion remains separate from staff review.
- Learning activity uses historically available quiz attempts with an 80% reference line and offline labels. The original six inputs are grouped into Engagement, Assessment and Submission history. Current observations are distinguished from older model snapshots; missing data has explicit text.
- Support retains confirmed challenges and the original SQLite save/confirmation behaviour. Review, challenge and draft actions are behind collapsed expanders. Drafts remain unsent.
- History retains module, support, confirmation, referral and quiz-recording information. Dates are displayed in UTC with full precision retained in underlying records.
- Early review retains the original ranking, ties, unscored cases and Show all/top-case display limit. Overdue retains every unresolved case regardless of score, with staff/review filters.
- Tables now wrap text in bounded, keyboard-focusable regions. Optional table tools preserve interactive sorting and CSV download. Model evaluation compares readable metric names across models, formats percentages/counts/lead time and retains the original limitations and saved results.
- Duration text now uses singular/plural correctly, including `1 hour` and `1 day`. Session duration and active study time use `min`; quiz results use `%` or a `%` column/axis label; quiz change uses `percentage points`.

## Checks and evidence

The final complete automated run passed **39 tests in 33.19 seconds**, recorded in `reports/dashboard_redesign_tests.txt`. It used `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`. The run included default-page, filter/Back restoration, summary reconciliation, unit/missing-state and singular-duration checks, Streamlit AppTest, and existing historical, simulation, model and persistence tests. Existing model unit tests use temporary fixtures; saved models were not retrained. Tests save support records only into temporary test databases.

Browser inspection confirmed All learners and all four learner-profile tabs at **1366×768 and 1920×1080**. At 15 Feb 2026, 12:00 UTC, totals reconcile: **600 enrolled = 288 in progress + 308 overdue + 4 completed all eight**. Early review, Overdue referrals and Model evaluation were also inspected at 1366×768. Main table headers and cells wrap instead of truncating; bounded regions scroll vertically for further rows. At the smaller height, scrolling is needed to reach controls below the table; the page does not attempt to squeeze all details onto one screen.

The browser checks actually performed were:

- Opened S0001 Overview: practice submitted, quiz not yet passed, latest result **70%**, original deadline, **26 days 1 hour** overdue.
- Opened Learning activity: three historically available attempts, an 80% line, online/offline labels, **36.0 min** average session duration, **608.1 min** total active study time, **2.4 days** since login, **3** interrupted sessions, **+10.0 percentage points** quiz change and **0** previous late practice submissions. The score table and chart explicitly label scores with `%`.
- Opened Support and expanded each of Update review, Record confirmed challenge and Preview support draft. Confirming party/confirmation checkbox and the unsent WhatsApp draft were visible. No live staff action was saved during this inspection.
- Opened History: original module dates and retained referral date were visible, with explicit empty support-history text. Raw timestamp precision remains stored even though display is to the minute.
- Checked the Early review list: 288 total, 195 scored and 93 unscored. Checked the Overdue list: all 308 cases before filtering, independent of score.
- Inspected Model evaluation: readable model names, precision/recall percentages, integer flag/false-warning counts, F2 on its original 0–1 scale and lead time labelled in days. Display rounding does not alter saved values or frozen selection.
- Searched for a nonexistent learner and verified the zero-match explanation. Opened S0005 Learning activity and verified **No quiz attempt recorded**, **No sessions recorded** and **Needs two attempts to calculate change**, rather than replacing missing values with zeros.

SHA-256 audit confirms **all 53 pre-existing data/model/report files unchanged** (`reports/dashboard_redesign_integrity.json`). A row-level SQLite comparison against the pre-redesign copy confirms every existing record retained: **308 referrals before and after; 0 action rows before and after**. Persistence of newly saved actions is exercised in temporary-database tests. Source historical/scoring and staff-store implementations were not changed.

The preview required a restart because the old Streamlit process retained an earlier imported presentation helper. It was restarted successfully and browser inspection then passed. This was a preview-process issue, not a data migration. No formal screen-reader audit, mobile-device test or production usability study was performed.

## Screenshots

Screenshots are saved under `reports/dashboard_redesign_screenshots/`. The six requested views are included here, with additional History, unit-detail, evaluation and laptop-landing captures in that folder.

### All learners (1920×1080)

![All learners](dashboard_redesign_screenshots/all_learners.jpg)

### Learner Overview (1920×1080)

![Overview](dashboard_redesign_screenshots/overview.jpg)

### Learning activity (1920×1080)

![Learning activity](dashboard_redesign_screenshots/learning_activity.jpg)

### Support (1920×1080)

![Support](dashboard_redesign_screenshots/support.jpg)

### Early review (1366×768)

![Early review](dashboard_redesign_screenshots/early_review.jpg)

### Overdue referrals (1366×768)

![Overdue referrals](dashboard_redesign_screenshots/overdue_referrals.jpg)

## Remaining scope

The requested redesign and targeted follow-up fixes are implemented. User acceptance review remains. No production authentication, external deployment, real-world model validation, learner quiz workflow, quiz grants, offline-result entry or messaging delivery is included. These remain future work. Model scores are experimental and the test set was already inspected; this interface does not establish a newly validated policy.

Local review URL: http://127.0.0.1:8501/.
