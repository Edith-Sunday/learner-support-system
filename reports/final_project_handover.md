Current focused correction: http://127.0.0.1:8506 uses runtime/teacher_focus_demo.sqlite3. See reports/teacher_focus_review.md for the saved-prediction list, action-level staff identity and verification. Earlier handover entries below are retained.

## Usability handover — 18 October 2026 (current version)

The connected journey has been simplified without changing model training, fitted pipelines, feature calculations, assessment timing, marking, progression, deadlines, grants or support-service rules. This section supersedes the navigation and launch information in the earlier implementation record below.

### Current navigation

- Learner: **My learning, Lesson, Practice, Quiz and results, My support**.
- Staff: **All learners** (default), **Needs attention, Support messages, Model evaluation**.
- Needs attention separates **Before the deadline** from **Deadline missed**. Sort and view contains Model review order / Learning progress; tied priorities and the whole boundary group remain together. Numeric scores are inside profile Assessment details.
- Profiles group **Progress, Quiz results, Support, History**. Extra attempts, offline entry and teacher answer keys are under Quiz results. Support provides four collapsed steps: Review need, Prepare message, Review and send, Follow up. Old actions/drafts remain available in History.
- My support combines received messages, replies, help requests and communication preference. Session timing remains in a secondary Study timer expander.
- Model evaluation starts with a short explanation and actual comparison results. Collapsed sections retain checkpoint rules, feature definitions, measurement limits, tie handling, earlier full-feature results, read-only **Sample learner data**, and **Pilot evaluation**. Sample data cannot receive operational support actions. Pilot exports still disclose synthetic origin and retain the same denominators and validation.
- **Demo controls** contains the forward-only date controls and an ordinary-language guide. Its scope notice says the change affects all learners. No reset was added.

### Run this verified version

The verified server is running at **http://127.0.0.1:8505** using a copy of the final demonstration database:
`C:\Users\hp\Documents\ChatGPT\Learner support system\runtime\usability_demo.sqlite3`.

```powershell
Set-Location 'C:\Users\hp\Documents\ChatGPT\Learner support system'
$env:INTERACTIVE_DEMO_DB='C:\Users\hp\Documents\ChatGPT\Learner support system\runtime\usability_demo.sqlite3'
$env:LEARNER_DEMO_DB='C:\Users\hp\Documents\ChatGPT\Learner support system\runtime\usability_historical.sqlite3'
.\.venv\Scripts\python.exe -m streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8505 --server.headless true --browser.gatherUsageStats false
```

Do not start a second server on the same port. Without `INTERACTIVE_DEMO_DB`, the application now opens the existing `runtime/final_connected_demo.sqlite3` by default, with no cohort selector. Browser verification used only the copy above. The original final connected database, original interactive database and original staff database were not advanced or modified.

### Five-minute connected demonstration

1. **First minute:** Choose Learner, expand Choose a demo learner and select Grace (DEMO007). My learning shows practice complete, quiz not yet passed, the actionable deadline and Take quiz. Open Lesson or Practice to show the learning content.
2. **Second minute:** Open Quiz and results. The verification copy contains the newly submitted 0/10 attempt with a clear 80% pass mark, remaining requirement and expanded incorrect-answer feedback. Use Start another quiz for a new demonstration attempt; this does not alter the earlier result.
3. **Third minute:** Switch to Staff → All learners and open Grace. Progress shows what remains and the request for help. Quiz results shows the latest result/feedback; additional attempts and offline result entry are collapsed here.
4. **Fourth minute:** Open Support messages and select Grace. Review need → Prepare message → Review and send → Follow up. The copied database includes a newly reviewed demo message and its linked reply. The sending button says Send demo message and explicitly states that nothing is sent by SMS, WhatsApp or email.
5. **Fifth minute:** Switch to Learner → Grace → My support to show the received message and reply. Then briefly show Model evaluation and its Pilot evaluation subsection. The model has mixed advantage over the progress rule; no real learner performance or impact is established.

Alex (DEMO001), Bella (DEMO002) and Farah (DEMO006) have completed Module 1 and show “Module 1 complete. Module 2 is not available yet.” Chris (DEMO003) is working through Module 1; Dara (DEMO004) is ready to take a quiz; Emeka (DEMO005) has requested offline access; Grace needs help with balancing equations. These fictional display names do not replace stored learner IDs. To demonstrate a missed deadline, use Demo controls to move the copied demonstration date beyond an unfinished learner's deadline; it affects the whole copied cohort and cannot be reversed. No dates were advanced during this usability verification.

### What was actually checked

- Browser, desktop 1280 × 900: opened the completed/waiting learner; selected Grace; submitted a new quiz using the existing quiz form; confirmed 0/10, not-yet-passed feedback and remaining work; opened the matching staff Progress/Quiz results/Support views.
- Opened extra-attempt and offline-result controls; did not create another grant or offline result in this pass. Their business rules remain covered by existing regression tests.
- Saved a reviewed support draft, deliberately sent it inside the copied demo, selected that message as the learner and saved a linked reply with a more-help request. Verified the reply in the staff conversation. No external message was sent.
- Opened Model evaluation and Pilot evaluation, verifying visible synthetic-origin disclosure, unchanged completion/response denominators and percentage calculations. Sample records remain read-only; no real pilot was imported.
- Browser at 390 × 844: inspected learner support cards/reply controls, collapsible navigation, staff search/filter/list layout and model overview. Long tables scroll horizontally within their container; they do not squeeze every column onto the phone width. This is an emulated viewport check, not physical-device testing.
- Automated: existing learning/model/support tests retained; UI assertions updated for the authorised menus and focused coverage added for waiting states and read-only sample/pilot access. Final full-suite result: **79 passed in 46.44 seconds**. Output: [usability_verified_tests.txt](usability_verified_tests.txt).
- Preservation: [usability_preservation_audit.json](usability_preservation_audit.json) checks 44 source-data/model files and original database files with no changes. The 122-file original artifact baseline was also rechecked with zero changes. Services were not retrained, datasets were not regenerated and no packages were installed.

Prepared scenarios inherited their original provenance. This pass's new browser actions occurred only for Grace in the copied database. Historical raw request prefixes remain stored; test-only prefixes are omitted from ordinary help-request display. Existing message text is preserved verbatim.

### Final screenshots

1. [Learner overview](usability_screenshots/01_learner_overview.jpg)
2. [Quiz results](usability_screenshots/02_quiz_results.jpg)
3. [Staff learner profile](usability_screenshots/03_staff_profile.jpg)
4. [Support conversation](usability_screenshots/04_support_conversation.jpg)
5. [Model evaluation overview](usability_screenshots/05_model_evaluation.jpg)

Additional waiting-state and narrow-screen captures are in the same folder. No blocker remains for this local prototype. Scores still rely on simulated data, the role switch is not authentication, messages remain inside the app and only Module 1 content is authored. This is a usability improvement, not new evidence of predictive accuracy or learner impact.

---

## Earlier implementation record (preserved for context)

# Final project handover

Completed 18 October 2026. This version of the connected local prototype is complete.

**Artificial simulation only. Scores are experimental, not validated real-world probabilities, and no improved learner outcomes or real pilot effects have been established. No external messages are sent.**

## Five-component status

| Component | Operational behaviour |
| --- | --- |
| Early-warning assessment | Frozen six-feature Module 1 logistic regression; day-3/7/10 inputs; both occurrence and recording cutoffs; immutable versioned results and retained older attempts. Current incomplete, available, non-overdue Module 1 only. |
| Model comparison | Saved validation/test comparisons, progress rule and random reference; no refitting or changed selection. Separate historical full-feature evaluation remains available. |
| Personalised support | Learner requests/preferences, staff-confirmed barriers, neutral or category-specific editable drafts, deliberate simulated dispatch, duplicate protection, linked response/help request, assignment and follow-up. |
| Staff dashboard | Connected learner profiles, model/progress ordering with equal-priority ties, latest input timestamps, independent overdue referrals, quiz grants and offline records. |
| Pilot evaluation | Separate protocol, isolated illustrative dataset, validated future CSV workflow, mature-outcome and 48-hour response denominators, pending/missing accounting and labelled exports. |

## Launch the verified demonstration

Run in PowerShell:

```powershell
Set-Location 'C:\Users\hp\Documents\ChatGPT\Learner support system'
$env:INTERACTIVE_DEMO_DB='C:\Users\hp\Documents\ChatGPT\Learner support system\runtime\final_connected_demo.sqlite3'
$env:LEARNER_DEMO_DB='C:\Users\hp\Documents\ChatGPT\Learner support system\runtime\final_historical_staff.sqlite3'
.\.venv\Scripts\python.exe -m streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8504 --server.headless true --browser.gatherUsageStats false
```

Open http://127.0.0.1:8504. The verified server is left running; do not launch a second process on that port. Ctrl+C in its terminal stops it. This is loopback-only, not an external deployment. Select Staff and Interactive demonstration. The interactive database is exactly `C:\Users\hp\Documents\ChatGPT\Learner support system\runtime\final_connected_demo.sqlite3`; historical staff actions use the separate path above. Existing `interactive_demo.sqlite3` and `staff_demo.sqlite3` remain unchanged.

Checkpoint processing occurs when the interactive app is used, not on a production scheduler. The demonstration clock is forward-only and currently reads 22 October 2026 at 08:00 UTC; this is independent of the computer date. Last assessed/checked values use demonstration time. Assessments preserve scheduled input time, processing time, actual save time, features and model SHA256. Retrospective calculations are labelled calculated later and are not earlier delivered warnings or actual warning-lead-time evidence. No logins, interruptions or active-study values are fabricated. Existing session-duration tracking remains.

## Ordered walkthrough and actual browser verification

1. Select Learner. DEMO007 was enrolled through the browser, submitted practice (3/3) and a quiz (0/10), and saw item feedback. Its request asks for help with coefficients and atom counting; preference was changed to email.
2. The shared isolated clock was advanced three days through the staff UI. Early review showed DEMO007's day-3 experimental score 0.676 and captured-input timestamp. Model and Progress ordering were both inspected; exact-score ties shared priority. Display limits include an entire boundary tie group and can therefore exceed the requested count. This display behaviour does not alter the frozen evaluation's administrative tie-break.
3. On DEMO007's Support tab, a neutral check-in was shown before confirmation. Content difficulty was explicitly confirmed with source student. The generated draft referenced relevant Module 1 content/quiz feedback, was edited and saved as unsent, then deliberately simulated as an email. Nothing left the application. The UI showed it already recorded once, with no second dispatch action.
4. In Learner Messages, DEMO007 saw the message and recorded a linked response requesting help counting hydrogen atoms. Staff saw the history, assigned Demo staff — Amina, and saved Follow-up planned for 24 October. Database audit confirms one outbox record, one linked response and the follow-up date.
5. DEMO001 began as a seeded overdue practice-complete case. Through the browser, staff authorised one extra quiz attempt and recorded an offline 10/10 quiz at 22 October 08:00 UTC. Overview showed Completed late; the original 15 October deadline was unchanged. Module 2 showed Waiting for content. Overdue referrals then showed zero unresolved modules, with no Module 2 actions.
6. Model comparison was opened and its preserved evaluation/limitations inspected. The UI distinguishes current experimental integration from the earlier report's historical scoring-disabled wording.
7. Pilot evaluation was opened in the browser: the protocol, synthetic label, denominators, difference calculations and arithmetic example were inspected. Future CSV validation is covered by automated tests; no real participant data was imported and no real pilot was conducted.

Browser-created DEMO007 is separate from the six named seeded scenarios. DEMO001's starting history was seeded; only its grant and final late-completion steps were browser-created. DEMO002/006 demonstrate completed/waiting states; DEMO003 demonstrates an old unscored attempt plus a separate versioned result; DEMO004 has recorded practice/quiz progress; DEMO005 requests connectivity support. These seeded histories are not claimed as browser journeys. Reproduce the original six-scenario fixture in a new path with `.\.venv\Scripts\python.exe -m src.seed_final_demo --database runtime/new_final_demo.sqlite3`; the command refuses to overwrite an existing database. It does not reproduce subsequent manual browser actions.

## Model evidence and limits

The candidate artifact is `models/interactive_module1/logistic_regression.joblib`, SHA256 `c56ed734830bf69b96b5c6251f2a7ad2f27dc56c11570275e4d66cf7c6342b80`. Integration checks the frozen selection, hash, exact feature order and median-imputation/indicator/scaling pipeline. Predictors are practice submitted, quiz passed, current quiz score, score trend, quiz attempt count and snapshot day, using the same feature derivation evaluated previously. Genuine missing quiz values remain missing for fitted imputation. Original full-feature models are not used for interactive predictions.

From the unchanged [Module 1 evaluation](interactive_model_evaluation.md): validation mean checkpoint recall at the illustrative ceil(20%) review volume is 28.43% for logistic regression versus 26.47% for gradient boosting. Logistic regression beats the progress rule on validation day 3 and ties on days 7/10; on test it beats the rule on days 3/7 and ties on day 10. Module-level detected missed-deadline cases are 17/34 validation and 16/27 test, versus 15/34 and 14/27 for the progress rule. The validation random-reference mean is about 17.08 detected modules, so there is no consistent superiority claim. Large equal-score groups limit personal differentiation. Snapshots are correlated and later cohorts differ as completed work leaves.

The test set has already been inspected. These are exploratory simulation results, not a fresh untouched-test evaluation or evidence that staff intervention works. No model was retrained, no simulation tuned, no frozen thresholds/selection changed. The original [model report](model_evaluation.md) and [workload review](workload_review.md) remain preserved. Older reports describe their stage at the time; this handover documents the newly authorised integration.

## Three separate data contexts

- Historical: 600 simulated learners, existing student splits/data, original full-feature models and separate Module 1 experiment, all unchanged.
- Interactive: seven local demonstration learners, four versioned scores at final audit, local actions/messages only. Seeded provenance is shown. Module 1 is the only authored content; Module 2 dates remain audit-only while unavailable.
- Pilot: `pilot/illustrative_synthetic_example.csv`, `pilot/protocol.md`, and `pilot/input_template.csv`; future validated copies go only to `pilot/imports/`. No operational learners or historical evaluation rows are created from pilot input.

The illustrative pilot has 12 participants per group. Each has 10 mature known outcomes, four on-time completions (40%), one pending and one missing outcome. Each has 11 simulated check-ins: 10 have full 48-hour follow-up, three responses within that interval (30%), one pending follow-up, and one participant without a message. Groups intentionally share the same fixed pattern; differences are zero, not evidence of benefit. The separate 40% to 50% example is arithmetic only: +10 percentage points, +25% relative change. A zero baseline makes relative change undefined; no eligible check-in makes response rate Not applicable, not zero. Missing/pending outcomes are never counted as failures. Real records require verified delivery; local simulation is not real delivery. An observational comparison cannot establish causality.

## Verification and preservation

The final full-suite command is:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp runtime/final_connected_full_4
```

Final result: **78 passed in 50.95 seconds**, after the last code changes. See [final test output](final_connected_tests_4.txt). The suite covers existing rules plus candidate compatibility, missingness and timestamp cutoffs, versioned idempotency, exclusions, ties, support categories/neutral drafts, channel/dispatch/response integrity, pilot denominators, validation and data separation. Model tests may fit temporary fixtures; saved pipelines are never refitted. An initial sandbox run could not resolve the installed Python path; verification was rerun outside that sandbox with the same project virtual environment.

[Preservation audit](final_preservation_audit.json): all 122 preexisting baseline artifacts under data/models/reports have identical SHA256 values. All tables in both original operational databases match the pre-pass SQLite backups row-for-row, including clock, original deadlines, attempts, drafts and referrals. Run `.\.venv\Scripts\python.exe -m src.verify_final_preservation` to repeat. [Isolated demo audit](final_demo_audit.json) records the final completion, message, response and assignment evidence. No external messages, package changes, model training or historical dataset regeneration occurred in this pass.

Screenshots captured from the actual browser are in [final_screenshots](final_screenshots): learner quiz feedback, experimental ordering, learner message/response, staff follow-up, late completion and pilot evaluation. Automated checks are separate from the browser actions listed above; no real-device, production deployment or real-pilot verification is claimed.

## Remaining production limitations

No blocker remains for this local demonstration. Production work would require authentication/authorisation, privacy/consent and retention controls, deployment/security review, reliable scheduling and instrumentation, real message delivery and audit, staff capacity agreement, prospective external validation and a properly designed pilot with uncertainty analysis. The fixed quiz is not a secure examination bank. A role switch is not authentication. Module 2 has no authored content. Existing records and local experimental scores must not be used as validated decisions about real learners.

Portfolio wording: “Built a local SS1 chemistry learner-support prototype connecting a learning workspace, audited checkpoint assessments, comparative evaluation on simulated data, staff-confirmed personalised support with simulated messaging, and a separate pilot-evaluation workflow. Preserved temporal cutoffs and historical records, tested the connected journeys, and documented the limits of artificial-data results. No real-world accuracy or learner-impact claim is made.”



