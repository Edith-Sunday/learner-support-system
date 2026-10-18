Deployment-ready entry point: **dashboard.py**, Python **3.13**, branch **codex/streamlit-cloud**. No secrets required. See the Streamlit Community Cloud deployment section below and reports/cloud_deployment_review.md. Earlier local-development notes are retained.

## Simplified journey — current launch

Learners now use **My learning, Lesson, Practice, Quiz and results, My support**. Staff use **All learners, Needs attention, Support messages, Model evaluation**. Sample learner data and pilot tools are under Model evaluation; date controls are under Demo controls. Existing learning and model rules remain unchanged.

The verified copy is running at http://127.0.0.1:8505. Launch it with:

```powershell
Set-Location 'C:\Users\hp\Documents\ChatGPT\Learner support system'
$env:INTERACTIVE_DEMO_DB='C:\Users\hp\Documents\ChatGPT\Learner support system\runtime\usability_demo.sqlite3'
$env:LEARNER_DEMO_DB='C:\Users\hp\Documents\ChatGPT\Learner support system\runtime\usability_historical.sqlite3'
.\.venv\Scripts\python.exe -m streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8505 --server.headless true --browser.gatherUsageStats false
```

Without the environment override, the app opens `runtime/final_connected_demo.sqlite3`. Use a copy for record/date-changing demonstrations. Read the [current handover and five-minute walkthrough](reports/final_project_handover.md) and [verified tests](reports/usability_verified_tests.txt). Earlier navigation and port instructions below are historical stage notes.

# Learner Early-Warning and Personalised Support System

## Completed connected prototype — 18 October 2026

All five local components are connected: experimental early-warning assessment, saved model comparison, personalised support with simulated messaging, staff/learner workspaces, and a separate pilot-evaluation workflow. **Artificial simulation results are not proven real-world predictive accuracy or improved learner outcomes. No real pilot has occurred.**

Launch the verified isolated demonstration from PowerShell (the server may already be running):

```powershell
Set-Location 'C:\Users\hp\Documents\ChatGPT\Learner support system'
$env:INTERACTIVE_DEMO_DB='C:\Users\hp\Documents\ChatGPT\Learner support system\runtime\final_connected_demo.sqlite3'
$env:LEARNER_DEMO_DB='C:\Users\hp\Documents\ChatGPT\Learner support system\runtime\final_historical_staff.sqlite3'
.\.venv\Scripts\python.exe -m streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8504 --server.headless true --browser.gatherUsageStats false
```

Open http://127.0.0.1:8504 and select Staff → Interactive demonstration, or Learner. This uses separate databases and preserves the original user records. DEMO007 contains the browser-created support journey; DEMO001 demonstrates a browser-authorised late completion after a seeded overdue start. Module 2 stays Waiting for content. Messages are simulated locally only; the role switch is not authentication.

The frozen six-feature Module 1 logistic regression now supplies experimental numeric ordering at eligible checkpoints. It has not consistently outperformed the progress rule. Scores are not validated probabilities. The original full-feature model is not used for interactive predictions; session tracking remains intact. Processing runs on app use, and later calculations are labelled retrospective. The test set was already inspected; subsequent policy work is exploratory.

Read [final handover and walkthrough](reports/final_project_handover.md), [final tests](reports/final_connected_tests_4.txt), [preservation audit](reports/final_preservation_audit.json), [Module 1 comparison](reports/interactive_model_evaluation.md), and [pilot protocol](pilot/protocol.md). Run the full suite with `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`. The final handover supersedes earlier stage notes below about interactive scoring being disabled; original reports remain unchanged for provenance.

This project is a prototype for SS1 chemistry students. It will use simulated data to predict whether learners will miss a module's 14-day completion deadline and support the development of personalised learner support.

The prototype will be implemented in stages. Simulated data and prototype predictions are intended for development and evaluation, not validated decisions about real learners.

## Planned tools

- Python
- pandas
- scikit-learn
- Streamlit

## Project structure

- `src/`: application and modelling source code.
- `data/`: simulated event histories, prediction snapshots, outcomes, and split exports.
- `content/`: chemistry module content and support resources.
- `reports/`: evaluation results and project reports.
- `tests/`: simulation rules, model boundaries, selection, and evaluation tests.
- `models/`: fitted pipelines and the frozen validation selection, settings, feature order, dependency versions, and source-data hashes.

## Current stage

The corrected data simulation, model evaluation, and first local Streamlit staff dashboard are implemented for 600 simulated SS1 chemistry students and up to eight sequential modules. All data and findings are simulated. Model results measure performance on artificial data, not proven real-world predictive accuracy or improved learner outcomes. The dashboard records demonstration support actions and drafts only; no chemistry assessment interface or message sending is implemented.

## Reproduce on Windows PowerShell

Run from `C:\Users\hp\Documents\ChatGPT\Learner support system`. Use the explicit virtual-environment interpreter because global Python aliases do not work in the current shell.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.simulate --seed 42 --observation-days 120
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m src.validate
```

The first command is only needed to restore dependencies. Direct installed versions of numpy, pandas, pytest, scikit-learn, and joblib are pinned in `requirements.txt`; their required transitive dependencies are installed as well. `src.validate` runs the tests and writes `reports/validation_report.md` and `reports/test_results.txt` for the default CSV export. Python 3.13.16 was used. The sandbox may emit a Python executable-location warning even when commands succeed.

The generator replaces its named outputs in `data/`. To preserve the default generated data while comparing a seed, use `--output data/seed43 --seed 43`. Unrelated files are not touched. Repeated runs with the same versions, seed, and observation period produce the same data. Tests do not replace the CSV files.

## Model training and evaluation

For model work, use the existing corrected datasets. Do not run the generator or change the student splits to improve results. From the project directory:

```powershell
# First model run only: refuses to overwrite an existing model directory.
.\.venv\Scripts\python.exe -m src.modeling

# Re-evaluate the frozen delivered pipelines on unchanged source data.
.\.venv\Scripts\python.exe -m src.modeling --evaluate-only

# Separate reproducibility run, preserving the delivered artifacts.
.\.venv\Scripts\python.exe -m src.modeling --model-dir models/review_run --report-dir reports/review_run

# Run all simulation and model tests after the default model artifacts exist.
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

The simulation tests also generate in-memory fixtures to check rules and reproducibility; they do not regenerate the saved datasets. Tests of saved models expect the default `models/` and `reports/` artifacts. If starting from an empty project, generate the default data first, run the default model command, then run all tests.

Both algorithms use only the ordered 15-column `data/model_features.json` allowlist, with `missed_deadline=1` as the positive class. Median imputation and missingness indicators are fitted on training data only. Logistic regression also uses training-only scaling; gradient boosting uses fixed shallow-tree settings. Each algorithm pools days 3, 7, and 10 and retains snapshot_day. No hyperparameter search is performed.

Validation alone selects thresholds by F2, precision, then higher threshold, and selects the candidate by F2, precision, then logistic regression. The selected thresholds and candidate are durably saved before test evaluation. The test set never changes those decisions. Evaluation-only runs check source-data and pipeline hashes and do not refit models or rewrite the frozen selection.

Review `reports/model_evaluation.md`, `snapshot_metrics.csv`, `module_warning_summary.csv`, the two complete `validation_thresholds_*.csv` files, and the per-model test prediction and first-warning exports. The report explains undefined metrics, correlated snapshots, differing day-specific cohorts, and detected-only warning lead times. `models/selection.json` contains the frozen choices, full classifier settings, preprocessing policy, dependency versions, source hashes, and pipeline hashes. `reports/evaluation_audit.json` records the selection hash and confirms unchanged inputs and decisions. `reports/model_test_results.txt` records the full test run.


## Local staff dashboard

From this project folder, launch with the explicit virtual-environment interpreter:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

Open `http://127.0.0.1:8501`. Stop the server with Ctrl+C in its terminal. It binds only to loopback and is not published. Streamlit's built-in Deploy menu is not part of this local workflow. Streamlit is pinned in `requirements.txt`, alongside the existing dependencies.

Pages: **Early review**, **Overdue referrals**, **All learners**, and **Model evaluation**. The sidebar selects an historical date/time in UTC inside the simulation activity window. The default, 15 February 2026 at 12:00 UTC, is a fixed interior demonstration date allowing multiple module cycles; it was not selected by predictive performance. It shows 288 unfinished not-yet-overdue cases (195 scored, 93 not yet scored), 308 overdue cases, and 600 enrolled learners.

Operational state is reconstructed from events available by the selected time, including both occurrence and recording timestamps. It never uses final reconciled module outcomes. Recognition of both completion requirements unlocks the next module and starts its 14-day clock. Equality with the deadline is still on time. Scores use each active module's latest available day-3/7/10 snapshot and the saved logistic-regression allowlist/pipeline. Score timestamps remain visible. Top-case limits affect display only; all learners can receive support. Every unresolved overdue module appears independently of risk score.

Staff actions persist separately in `runtime/staff_demo.sqlite3`, which is ignored by Git. Assignments, review notes/status, follow-up dates, confirmed challenges, and unsent drafts have an effective simulation timestamp and a separate real save timestamp. Historical views filter by the effective demonstration time. Review status cannot complete a module. Referral records have unique student-module keys; reruns do not duplicate them, and completion removes a case from the active list while retaining history. Tests use separate temporary databases. `LEARNER_DEMO_DB` can explicitly select another demonstration database without touching source data.

This ranked approach is exploratory. The frozen 0.08 threshold stays in evaluation records and never creates automatic referrals. The test set has already been inspected; later policy changes are not fresh untouched-test evaluations. Working quiz grants and offline-result entry are available in the separate interactive cohort described below. Message drafts are previewed and saved locally only. The workspace switch is not authentication; this is a single local demonstration, not a service for real learner records or deployment.

Run checks using `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`. The existing modeling tests fit temporary test fixtures; they do not retrain or overwrite saved production pipelines. Dashboard smoke tests use Streamlit AppTest, temporary SQLite storage, all four pages, and a saved review action. See `reports/dashboard_review.md` and `reports/dashboard_tests.txt` for this stage's results.

## Data use

Read `reports/data_dictionary.md` for every column and `reports/simulation_assumptions.md` for the timeline, event distributions, offline recording policy, and limitations. The default activity window is January 1 through May 1, 2026 UTC, with offline recording reconciled through May 3. A module's original deadline is unlock plus 14 days, inclusive.

Source activity is generated first. Each next module unlocks when the system first recognizes both previous-module completion requirements. Its 14-day deadline and day-3/7/10 snapshots start from that actual access time; delayed records never backdate this clock. Previous-module timeliness still uses completion occurrence. Snapshots use only records available by that instant and omit modules already known to be complete. The six original features are preserved alongside additional predictors. Final outcomes are separate; modules with deadlines beyond the observation window have blank targets and are excluded from labelled exports. The validation report separates unresolved completion from observed completion excluded solely by that conservative policy.

`data/model_features.json` is the sole default model-feature allowlist. IDs, split membership, hidden traits, support reports, timestamps, and outcome fields must not be automatically selected as predictors. Labelled exports include audit IDs and a separate `missed_deadline` target; they are not ready-made numeric feature matrices. Every student belongs to exactly one split: 420 train, 90 validation, and 90 test. Do not fit preprocessing across these splits in future stages.

`data/events.csv` contains the chronological source events. Sessions, logins, practices, quizzes, and grants are also exported separately for inspection; these tables duplicate the corresponding source rows. Communication preferences are in students; timestamped confirmed barriers are in support_information. Hidden traits are kept in hidden_traits and are never passed to feature derivation.

## Interactive learner chemistry workspace

Launch with the same Streamlit command above. Select **Learner** to enrol a demonstration learner and use My learning, Lesson, Practice, Quiz and results, and Get help. Select **Staff**, then **Interactive demonstration**, to inspect the same learner and use Support controls for quiz grants, offline records, assignments, reviews, and unsent drafts. Historical simulation remains a separate cohort.

Module 1 contains a worked chemical-equations lesson, three practice questions and a fixed ten-question quiz. Any valid practice submission counts; at least 8/10 on a valid quiz is also required. Module 2 unlocks at recognition of both requirements with its own 14-day deadline, but its content is explicitly unavailable. Downloads include learner materials without a quiz key; the staff workspace exposes the teacher key.

The separate `runtime/interactive_demo.sqlite3` persists enrolments, answers, drafts, attempts, grants, support requests, preferences and the shared forward-only UTC demonstration clock. `INTERACTIVE_DEMO_DB` can point to a different demo database. Advancing the clock affects all interactive learners and cannot be undone through the app. Actual save timestamps remain distinct from effective demonstration times. Offline completion timeliness uses occurrence; progression uses recognition. Interactive learners have no model score or invented activity measurements.

Run all checks with `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`, or the focused journey with `.\.venv\Scripts\python.exe -m pytest tests/test_interactive_workspace.py -q -p no:cacheprovider`. Tests use temporary databases. See `reports/learner_workspace_review.md`, the test logs and the five screenshots in `reports/learner_workspace_screenshots` for actual verification and limitations. The local browser QA learner DEMO001 is retained for review; enrol another learner for a fresh journey.

## Interactive assessment and unavailable content

Module 2 now remains **Waiting for content**, with its original dates retained only for audit. It cannot create actionable early-review cases, overdue referrals or deadline reminders. Future content publication requires an explicit deadline policy.

Practice/quiz answers use one blank input per formula. Teacher controls use separate UTC date/time inputs and **Allow extra attempts**. The optional study timer uses actual elapsed time; active time is separately labelled as an interaction-based estimate.

Day-3/7/10 checkpoint attempts run on interactive app use, not a background scheduler, and persist immutable input/model/time records. Late processing never pretends a warning was delivered earlier. Numeric interactive scores are currently withheld: authenticated login status, reliable session interruption counts and faithful active-study totals are missing, while those predictors were always observed during training. No values are invented to bypass this check. See `reports/interactive_assessment_review.md` for every feature mapping, test results, browser checks and limitations.


## Separate Module 1 experiment (17 October 2026)

See `reports/interactive_model_evaluation.md` for the additional six-feature, Module-1-only ranking comparison and `reports/interactive_ui_followup.md` for UI verification. Outputs live in `models/interactive_module1/`; original models and results are unchanged. This experiment is not connected to interactive scoring. The test set was previously inspected; results are exploratory simulation evidence only.

Run tests with `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`. To reproduce the experiment, use a separate project copy without an existing `models/interactive_module1/selection.json`, then run `.\.venv\Scripts\python.exe -m src.interactive_model`. The command deliberately refuses to overwrite frozen experiment outputs. Do not delete the current artifacts just to rerun it.


## Streamlit Community Cloud deployment

Repository: https://github.com/Edith-Sunday/learner-support-system
Branch: `codex/streamlit-cloud`; main file: `dashboard.py`; select **Python 3.13** in Advanced settings. The local tested interpreter is 3.13.16. No Streamlit secrets, environment variables, external messaging credentials or system packages are required. Runtime packages are pinned to the saved models' training environment; do not upgrade scikit-learn independently of model compatibility checks.

A fresh checkout starts from `demo_seed/demo.sqlite3`, a SQLite backup of the latest working fictional demonstration (seven learners, four saved predictions). The app initializes `runtime/cloud_demo.sqlite3` once, atomically, and never resets an existing database on reruns. Existing local databases and the optional local `INTERACTIVE_DEMO_DB` override remain supported. The seed contains sample records only; its provenance, counts and checksum are in `demo_seed/manifest.json`.

**Public/shared demonstration only:** visitors may share and change the same demo state. Cloud-local changes are temporary and may disappear on restart, rebuild or redeployment. Do not enter real learner records, contact details or confidential pilot data. Role switching is not authentication. SMS, email and WhatsApp labels are demonstration channel preferences; all messages remain inside the app and no external delivery service is connected.

Fresh-checkout commands (Linux/macOS):

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run dashboard.py
```

On Windows, use `.venv\Scripts\python.exe` for the same commands. Cloud installs `requirements.txt` automatically. The repository excludes local environments, secrets, logs, backups, uploaded pilot files and mutable databases; only the intentionally reviewed demo seed is included. Do not commit `.streamlit/secrets.toml`.

Deployment checks: `python -m pytest tests/test_cloud_deployment.py -q`. A Linux GitHub Actions check runs this against a fresh checkout. Original model and simulated data artifacts are retained without retraining or regeneration. [Streamlit deployment settings](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).

