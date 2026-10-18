# Pilot workflow

Future pilot protocol (predefined prototype workflow; no real pilot has occurred)

Eligible participants: consenting SS1 chemistry learners beginning the authored Module 1.
Assign learners randomly 1:1 to usual-support baseline or personalised-support group before Module 1 starts; keep each learner in one group. Record assignment separately from outcomes and retain every assigned learner in denominator accounting. Plan sample size and consent before a real pilot.

Intervention: staff review at days 3, 7 and 10, confirmed-need support drafts, and documented follow-up. Usual-support learners retain access to learning materials and help. For comparable response metrics, both groups receive the same neutral check-in at day 3; additional targeted support occurs only in the support group. If baseline receives no check-in, its response rate is Not applicable.

Observation: Module 1's original unlock/enrolment plus 14 days; completion requires practice and a valid quiz pass ≥80%. Use completion occurrence for timeliness, not recording date. Freeze outcome extraction after recording reconciliation, with observed-through timestamps and unresolved outcomes labelled missing. Extensions/extra attempts do not move the original deadline.

Primary outcome: completion by the original 14-day deadline. Only mature, known outcomes enter the rate denominator; report pending and missing separately alongside all assigned participant counts. Missingness may bias the comparison and requires a prespecified real-pilot analysis.

Response: first learner response within 48 hours after the comparable check-in, using the same fixed follow-up interval in both groups. Only dispatches with a full observed 48-hour window and verified real delivery enter real response denominators. For synthetic examples, explicitly simulated dispatches may enter a separate illustrative denominator. Late responses do not count; pending follow-up and unverified delivery are separate. No dispatch means response rate Not applicable, not zero.

Report support minus baseline in percentage points and relative change divided by baseline. Zero baseline means relative change Not defined. Observational baseline comparisons cannot establish causality; even a randomised pilot requires adequate sample size, adherence, consent, and uncertainty analysis. Simulated dispatch is not verified real delivery. Never pool these records with historical simulation or interactive demonstration records.


Input columns: participant_id, group, dataset_kind, enrolled_at, deadline, completion_at, outcome, dispatch_at, delivery_status, response_at, observed_through