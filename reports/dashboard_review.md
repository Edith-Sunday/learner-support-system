# Staff dashboard review

This is a **simulated-data prototype**. Its scores do not establish real-world predictive accuracy or improved learner outcomes. The test set has already been inspected. Ranked review is an exploratory operational approach, not a fresh untouched-test evaluation or an established staffing policy.

## Launch and environment

From the project folder, run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

Local URL: http://127.0.0.1:8501. The local server was launched for review; it is not externally published. Stop it with Ctrl+C in its terminal. Python 3.13.16 and Streamlit 1.66.0 are used. Streamlit was added to requirements.txt while preserving existing pins; pip reported no broken dependencies.

## Implemented workflow

- **Early review:** the saved logistic-regression pipeline scores only the frozen allowlisted features. One unfinished, not-yet-overdue row per student-module uses its latest available day-3, day-7, or day-10 snapshot. Score time and checkpoint are displayed. Descending score ties use student ID then module. Unscored cases are explicitly labelled and follow scored cases. Show all / Top cases changes visibility only; all learners remain eligible for support.
- **Overdue referrals:** every historically known unfinished module strictly past its deadline appears, independently of score or review status. Original deadlines remain visible. Completed cases leave active lists. SQLite uses a unique student-module key to prevent duplicate referral records across reruns. Once recorded, referral history remains available; historical referrals are materialised when an overdue historical view is visited, rather than claiming an exhaustive background referral service.
- **All learners and case details:** enrolled learners remain accessible, including unscored and completed learners. Recorded progress includes practice, most recent quiz, any valid pass, attempt/module history, remaining requirements, offline participation, communication preference, and the six original tracking inputs. Current input values are distinguished from the older snapshot used for scoring. Recorded progress and confirmed challenges are separate; observations are not presented as proven causes of a model score.
- **Staff support:** fictional staff assignments, review status, notes, follow-up dates, and explicitly confirmed challenges persist separately from learning data. Message drafts cover content, deadlines, connectivity, unclear/mixed needs, and overdue support. Drafts use the preferred channel, require no messaging service, invent no resource links, and use overdue wording instead of negative time remaining. Completed-case drafts offer optional support without suggesting unresolved quiz authorisation.
- **Model evaluation:** saved snapshot metrics and first-warning summaries are displayed, including false warnings and lead time. The frozen logistic threshold of 0.08 flagged about 95.8% of test snapshots; its result is retained, not used to generate automatic dashboard referrals. The saved comparison and diagnostic workload review remain unchanged.

## Historical information and persistence

The UTC selector is bounded by the simulation activity window. Operational status is reconstructed from events satisfying both event_time <= selected time and recorded_at <= selected time, without final reconciled outcomes. Practice submission plus a valid quiz score >=80% establishes completion. Completion occurrence determines timeliness, while recognition establishes the next unlock and its 14-day deadline. Completion exactly at the deadline is on time; an unfinished module becomes overdue only after it.

The deterministic default is **15 February 2026 at 12:00 UTC**, a fixed mid-window demonstration chosen to show active workflow, not by model-performance optimisation. It shows **288 early-review cases (195 scored, 93 unscored), 308 overdue cases, and 600 enrolled learners**. The early-review score is explicitly a model risk score, not a verified real-world probability.

Staff actions use `runtime/staff_demo.sqlite3`, excluded from version control. Their effective time is the selected simulation time; actual save time is retained separately for audit. Historical views hide later-effective actions and later-available source confirmations. Idempotency keys protect repeated action submissions, and review status never changes practice or quiz completion. These are demonstration edits, not claims that staff acted in the real world during the simulated period.

## Checks and preservation

The complete suite passed: **36 tests in 26.34 seconds**, including the prior simulation, modelling, and workload tests. Focused dashboard tests exercise delayed offline recognition, inclusive deadlines, future-information filtering, latest checkpoint selection, unique active rows, unscored cases, score-independent overdue inclusion, durable/idempotent support records, hidden future actions, draft-only behaviour, and saved artifact integrity. Streamlit AppTest renders all four pages, saves a review to a temporary database, and verifies an earlier historical view. The beginning-of-window empty queue is also covered.

The saved model pipelines were not retrained. Existing modelling unit tests may fit temporary fixture pipelines in memory; they do not replace saved artifacts. No simulation data was regenerated. SHA-256 verification found **all 49 pre-existing files in data, models, and reports unchanged**; see `dashboard_integrity.json` and the original hash inventory at the project root. Test output is saved separately in `dashboard_tests.txt` and `dashboard_focused_tests.txt`.

Browser checks inspected all four pages and the support draft preview. Visual inspection confirmed the teal/white/charcoal/grey presentation, readable tables, explicit prototype labels, the 288-to-25 Top cases display change, and the separate overdue list. No external message was sent. Desktop browser inspection and automated Streamlit smoke testing were performed; mobile layouts and accessibility assistive-technology testing were not performed.

## Remaining work and limitations

This is a single local demonstration without production authentication, access roles, or deployment hardening. The selected-time editing model is deliberately historical and should not be reused as a production audit policy. Scores can be several days old; later checkpoint cohorts differ as completed modules leave, and snapshots within a learner/module are correlated.

Teacher grants for one or two additional quiz attempts and teacher offline-result entry are the next workflow implementation step. There are no functioning controls claiming to perform either action. Message drafts remain local and unsent. Resource content, operational staffing capacity, policy validation with genuinely new data, and real-world learner impact evaluation remain future work.
