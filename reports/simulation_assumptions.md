# Simulation assumptions and limitations

All records, learner characteristics, barriers, and findings are simulated. They do not represent real students and cannot demonstrate intervention effectiveness.

## Timeline and completion

The default activity observation window is 2026-01-01 00:00:00 UTC through 2026-05-01 00:00:00 UTC, inclusive (120 elapsed days). Enrolment is spread across the first seven days. There are 600 SS1 chemistry students and at most eight sequential modules. Modules have numeric IDs only; chemistry content is not implemented.

Module 1 unlocks at enrolment. Each later module unlocks when the system first knows that the preceding module's practice and passing quiz requirements are both satisfied (`completion_known_at`). Every original deadline is exactly 14 elapsed days after this actual access time, with no extensions. Events exactly at the deadline are on time; events strictly after it are late. A valid quiz score of 80, 90, or 100 passes. Completion occurrence is the later of the first practice-submission occurrence and first passing valid quiz occurrence, and determines the previous module's timeliness. Practice accuracy is irrelevant. Passing remains satisfied even if a subsequent quiz score declines. Late completion unlocks the next module when recognized and retains its original missed-deadline label.

Pre-deadline quiz attempts have no policy limit. The generator samples opportunities to attempt quizzes, so realised attempts remain finite and vary. After a deadline, a recorded teacher grant must already exist at the attempt time, including for offline attempts. Each grant permits exactly one or two additional attempts. This generator offers at most one grant per student-module; it can leave students permanently overdue. The validator supports multiple grants and tracks each grant independently. All simulated submitted quiz records are valid; invalid-result handling is tested separately.

## Offline work and historical availability

Each event has its occurrence (`event_time`) and availability (`recorded_at`) timestamps. Online work and grants are recorded immediately. Teacher-recorded offline sessions, practice, and quiz results have independently sampled recording delays of 0.1 to 2 days. Offline work has the same completion and late-attempt rules. Offline session records are teacher-recorded estimates of duration and active time, not device telemetry.

Completion timeliness uses occurrence times. Recognition is the earliest time the records establish both requirements. The next module's `unlock_time` and `unlock_known_at` both equal that recognition time. Its deadline is 14 days later, and its day-3, day-7, and day-10 snapshots are scheduled from this actual unlock. Unlock and deadline are established once; subsequently arriving records with earlier occurrence times never backdate them. No next-module activity occurs before access. A module can be complete retrospectively but still have an earlier snapshot if completion was not yet known then.

For example, offline completion on Monday January 5 at 12:00 UTC, recorded on Wednesday January 7 at 12:00 UTC, uses Monday for the preceding module's timeliness. The next module unlocks Wednesday, is due January 21 at 12:00 UTC, and has its first snapshot on Saturday January 10 at 12:00 UTC. Recognition after the activity observation end does not create a next-module row within the observation window.

Activity stops at the observation end. Recording reconciliation remains open for two further days (through 2026-05-03 for the defaults), so all generated activity is eventually recorded. Final outcome rows describe activity through May 1 using that reconciliation; events occurring after May 1 are not simulated. Completion is only eventual within this window, not a lifetime outcome. The conservative export policy leaves the target blank whenever the original deadline exceeds the activity observation end. The report separates genuinely unresolved modules (completion unobserved and deadline still ahead) from already-completed modules excluded solely by this policy. For the latter, completion and its on-time status are observed, but the target is withheld for export consistency. Neither group enters a labelled export.

Snapshots include only events with BOTH occurrence and recorded-at times at or before the snapshot. Appending a delayed offline record cannot change any earlier snapshot. Most recent quiz/login means most recent occurrence among the available records, with event ID breaking ties. Historical practice lateness counts first submissions; completion lateness is a separate count. Completion in a historical snapshot is recomputed from available source records, never taken from the final outcome table.

Session event time denotes the availability point at the end of a simulated session. Duration, idle time, and active time are summaries at that point. Login is represented at the same activity opportunity. This simplifies within-session timing; no partially observed session durations enter features.

## Generating variation

NumPy's seeded generator (default seed 42) draws continuous learner skill, connectivity-failure propensity, engagement, and initial engagement delay. Drivers overlap: steady progress can coexist with connection problems, difficult modules, or delayed engagement. They are not exclusive assigned categories. Hidden traits are exported separately solely for simulator auditing and are excluded from model inputs.

Skill follows Beta(7,3), connectivity propensity Beta(1.5,5), engagement Beta(5,2), and initial delay Gamma(shape=1.3, scale=2.3 days). Module difficulty offsets are [0, .07, .13, .03, .16, .09, .12, .05]. Activity opportunities recur every Uniform(0.35,1.8) days, with reduced participation before the initial delay. Each opportunity can include a login, session, practice, quiz, and teacher grant. Quiz scores are Binomial(10, success probability) times ten. The probability combines skill, module difficulty, attempt experience, and fresh noise; scores can improve or decline. These are uncalibrated design assumptions, not findings about learners.

Preference is sampled from SMS, WhatsApp, and email. Barrier reports are separately sampled student/teacher-confirmed statements with timestamps. They are not inferred from low scores or short sessions, and need not match hidden traits. No inferred risk labels or recommendations are produced at this stage. Communication preferences and confirmed barriers are excluded from the default predictor allowlist. No messages are sent.

## Splits, missingness, and interpretation

A separate generator with seed + 1 permutes student IDs into exactly 420 train, 90 validation, and 90 test students. Split membership is assigned before outcomes and carried into every operational record. No student crosses splits. Some students may contribute no eligible labelled snapshots. CSV exports retain IDs for auditing; future modelling must select only `data/model_features.json` as inputs and `missed_deadline` separately as the target.

Missing login history, insufficient quiz history, or absent sessions remain blank, not imputed. Counts and indicators use zero when no applicable event is known. Several snapshots can belong to the same student-module; they are correlated. Cohorts at days 3, 7, and 10 differ because known completed modules exit. No preprocessing is fitted and no model is trained. The data are not tuned against predictive performance and cannot support real-world effectiveness, fairness, or causal claims.

Reproduction requires the pinned direct dependencies, seed, observation period, and code. Run into a separate output directory to compare variants without replacing the default datasets. The generator rewrites only its named outputs; all unrelated project files are preserved.
