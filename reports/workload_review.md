# Validation warning workload review

**These are artificial simulated-data results, not established real-world accuracy or improved learner outcomes.**

**The test set has already been inspected. Any later policy revision is exploratory and must not be presented as a fresh untouched-test evaluation. This review uses validation predictions only, with no test-based tuning, new policy selection, fitting, or data regeneration.**

## Scope and preserved decisions

Only `labelled_validation.csv` is parsed as an input dataset. The existing fitted pipelines are loaded for `predict_proba` only. The candidate remains logistic_regression; thresholds remain unchanged. There are 822 eligible validation snapshots across 351 student-module pairs. Eligibility follows the existing labelled-export policy, including its exclusions for deadlines beyond observation. This review does not assess modules without eligible validation snapshots.

## Flag-all diagnostic reference versus original frozen thresholds

| model | cohort | threshold | n_snapshots | precision | recall | f2 | flag_count | flagged_percent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | overall | 0.0800 | 822 | 0.5209 | 0.9952 | 0.8418 | 791 | 96.2287 |
| gradient_boosting | overall | 0.1600 | 822 | 0.5306 | 0.9831 | 0.8399 | 767 | 93.3090 |
| flag_all_diagnostic | overall | undefined | 822 | 0.5036 | 1.0000 | 0.8354 | 822 | 100.0000 |

| model | cohort | threshold | n_snapshots | precision | recall | f2 | flag_count | flagged_percent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | overall | 0.0800 | 822 | 0.5209 | 0.9952 | 0.8418 | 791 | 96.2287 |
| logistic_regression | 3 | 0.0800 | 351 | 0.4233 | 1.0000 | 0.7859 | 326 | 92.8775 |
| logistic_regression | 7 | 0.0800 | 270 | 0.5152 | 0.9855 | 0.8333 | 264 | 97.7778 |
| logistic_regression | 10 | 0.0800 | 201 | 0.6866 | 1.0000 | 0.9163 | 201 | 100.0000 |
| gradient_boosting | overall | 0.1600 | 822 | 0.5306 | 0.9831 | 0.8399 | 767 | 93.3090 |
| gradient_boosting | 3 | 0.1600 | 351 | 0.4215 | 0.9928 | 0.7811 | 325 | 92.5926 |
| gradient_boosting | 7 | 0.1600 | 270 | 0.5477 | 0.9565 | 0.8323 | 241 | 89.2593 |
| gradient_boosting | 10 | 0.1600 | 201 | 0.6866 | 1.0000 | 0.9163 | 201 | 100.0000 |
| flag_all_diagnostic | overall | undefined | 822 | 0.5036 | 1.0000 | 0.8354 | 822 | 100.0000 |
| flag_all_diagnostic | 3 | undefined | 351 | 0.3932 | 1.0000 | 0.7641 | 351 | 100.0000 |
| flag_all_diagnostic | 7 | undefined | 270 | 0.5111 | 1.0000 | 0.8394 | 270 | 100.0000 |
| flag_all_diagnostic | 10 | undefined | 201 | 0.6866 | 1.0000 | 0.9163 | 201 | 100.0000 |

The reference flags every eligible snapshot; its precision is simply the cohort prevalence and its recall is 1 when positives exist. It is not a fitted or newly selected model. Its threshold and average precision are blank because it supplies a flagging rule, not a probability-ranking model. Original model scores and thresholds have not been changed.

## First warning across available validation checkpoints

| measure | logistic_regression | gradient_boosting | flag_all_diagnostic |
| --- | --- | --- | --- |
| eligible_modules | 351.0000 | 351.0000 | 351.0000 |
| eligible_missed_modules | 138.0000 | 138.0000 | 138.0000 |
| warned_missed_modules | 138.0000 | 138.0000 | 138.0000 |
| warned_missed_percent | 100.0000 | 100.0000 | 100.0000 |
| missed_by_all_checks | 0.0000 | 0.0000 | 0.0000 |
| median_lead_days | 11.0000 | 11.0000 | 11.0000 |
| mean_lead_days | 11.0000 | 10.9493 | 11.0000 |
| first_detected_11_days | 138.0000 | 137.0000 | 138.0000 |
| first_detected_7_days | 0.0000 | 0.0000 | 0.0000 |
| first_detected_4_days | 0.0000 | 1.0000 | 0.0000 |
| first_detected_other_lead | 0.0000 | 0.0000 | 0.0000 |
| on_time_modules_false_warning | 195.0000 | 192.0000 | 213.0000 |
| unique_students_warned | 90.0000 | 90.0000 | 90.0000 |

Each eligible student-module counts once, using its earliest flag across available days 3, 7, and 10. Mean/median lead times use actual deadline minus first-warning timestamp and only detected missed-deadline modules. First-detection counts at 11, 7, and 4 days are mutually exclusive. On-time modules with at least one warning and unique students warned count once at their respective levels. No-snapshot modules are outside this validation-export-only comparison; none are silently assigned zero lead time or treated as detected.

## Illustrative checkpoint review fractions

The 10%, 20%, and 30% scenarios are illustrative workload scenarios, **not agreed staffing capacities**. They select a fraction of each day-3, day-7, or day-10 checkpoint cohort, pooled across its module unlock dates. They are **not a daily teacher caseload**, nor a count of distinct students or teacher-hours. The same student/module may reappear at another checkpoint. No cross-checkpoint suppression is applied to these scenario tables.

Number reviewed = ceiling(eligible snapshot count × review fraction). Within each model and checkpoint, sort by descending full-precision probability, then ascending student_id (lexicographic), then ascending numeric module_id. Duplicate student-module-checkpoint keys are rejected. Targets never break ties. Exactly the requested ceiling count is selected, even if a score tie spans the boundary.

`lowest_selected_score` is a descriptive boundary, **not a newly chosen threshold**. A rule using score >= that value may select additional tied records. The supporting capacity table includes boundary tie counts, and the ranking table records risk_rank and reviewed_10pct/20pct/30pct for reproducibility. Displayed scores are rounded; CSVs retain full available precision.

### logistic_regression

| snapshot_day | review_percent | eligible_snapshots | reviewed | tp | fp | precision | recall | lowest_selected_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | 10 | 351 | 36 | 15 | 21 | 0.4167 | 0.1087 | 0.4043 |
| 3 | 20 | 351 | 71 | 32 | 39 | 0.4507 | 0.2319 | 0.3818 |
| 3 | 30 | 351 | 106 | 55 | 51 | 0.5189 | 0.3986 | 0.3680 |
| 7 | 10 | 270 | 27 | 16 | 11 | 0.5926 | 0.1159 | 0.6311 |
| 7 | 20 | 270 | 54 | 38 | 16 | 0.7037 | 0.2754 | 0.6037 |
| 7 | 30 | 270 | 81 | 51 | 30 | 0.6296 | 0.3696 | 0.5471 |
| 10 | 10 | 201 | 21 | 19 | 2 | 0.9048 | 0.1377 | 0.7708 |
| 10 | 20 | 201 | 41 | 35 | 6 | 0.8537 | 0.2536 | 0.7124 |
| 10 | 30 | 201 | 61 | 54 | 7 | 0.8852 | 0.3913 | 0.6800 |
### gradient_boosting

| snapshot_day | review_percent | eligible_snapshots | reviewed | tp | fp | precision | recall | lowest_selected_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | 10 | 351 | 36 | 18 | 18 | 0.5000 | 0.1304 | 0.4193 |
| 3 | 20 | 351 | 71 | 35 | 36 | 0.4930 | 0.2536 | 0.3716 |
| 3 | 30 | 351 | 106 | 57 | 49 | 0.5377 | 0.4130 | 0.3684 |
| 7 | 10 | 270 | 27 | 18 | 9 | 0.6667 | 0.1304 | 0.5678 |
| 7 | 20 | 270 | 54 | 39 | 15 | 0.7222 | 0.2826 | 0.5470 |
| 7 | 30 | 270 | 81 | 54 | 27 | 0.6667 | 0.3913 | 0.5094 |
| 10 | 10 | 201 | 21 | 16 | 5 | 0.7619 | 0.1159 | 0.7422 |
| 10 | 20 | 201 | 41 | 33 | 8 | 0.8049 | 0.2391 | 0.6977 |
| 10 | 30 | 201 | 61 | 51 | 10 | 0.8361 | 0.3696 | 0.6783 |

Precision = true positives / reviewed; recall = true positives / all positive snapshots in that checkpoint cohort, including unreviewed positives. False positives are reviewed snapshots whose target is 0. Blank/undefined ratios indicate a zero denominator; a zero ratio with a nonzero denominator is a meaningful zero.

## Fixed threshold versus fixed capacity

A fixed probability threshold flags every score at or above that value. The number flagged varies with cohort size and the distribution of scores; the original frozen models illustrate this potentially high workload.

A fixed review capacity ranks scores and takes the highest k. Here k is ceiling(fraction × checkpoint cohort size), so the proportion is bounded within rounding while the score boundary varies. Neither method establishes actual staffing requirements. Capacity scenarios can leave positive cases unreviewed and do not change the models' underlying risk scores.

Snapshots within a student/module are correlated. Later checkpoint cohorts differ because completed modules leave. Differences across days are descriptive, not causal effects of waiting or intervention. No scenario is selected as a replacement policy.

## Files and reproduction

Supporting CSVs: workload_validation_predictions (original scores/flags), workload_validation_snapshot_reference (overall and checkpoint metrics), workload_validation_first_warning_summary, workload_validation_first_warnings (module audit), workload_validation_capacity (18 scenarios), and workload_validation_rankings (deterministic selection audit).

Code: `src/workload_review.py`. Run `.\.venv\Scripts\python.exe -m src.workload_review` once; the command refuses to overwrite an existing review. `workload_review_audit.json` verifies source datasets, pipelines, frozen metadata, and original result files are unchanged; only this explicit addendum is appended to model_evaluation.md. Its original bytes are also preserved separately.
