# Model evaluation on simulated learner data

**These results measure performance on an artificial simulation. They are not proven real-world predictive accuracy, improved learner outcomes, or intervention effectiveness.**

The validation-selected candidate flags 95.8% of test snapshots. Its recall is 99.5%, but precision is only 45.0%: 466 of its 848 flags are false positives. The low threshold provides little prioritisation because almost every snapshot is flagged.

At module level it detects 128 of 128 eligible missed deadlines, but also warns on 247 on-time modules and reaches 90 unique students. High module detection therefore should not be interpreted as efficient support targeting or intervention success. Thresholds remain frozen as specified; these findings have not been used to tune them.

## Frozen selection

Candidate: **logistic_regression**, chosen using validation F2, then precision, then logistic regression for a model tie. Each model's threshold maximises validation F2 over 0.05–0.95 in steps of 0.01; threshold ties prefer precision then the higher threshold. Numeric ties use absolute tolerance 1e-12. F2 places four times as much weight on false negatives as false positives in its count-based formula. This is a prototype choice, not an established optimal staff policy or a measured staffing budget.

`models/selection.json` was saved at 2026-10-14T10:25:30.588866+00:00 before test probabilities or test metrics were calculated. The same fitted pipelines and thresholds were then reloaded for evaluation. No refit on validation, test, or combined datasets occurred. Test findings did not change the selection.

## Models and data

One pooled model per algorithm uses all 15 allowlisted predictors, including snapshot_day. Student IDs, module IDs, timestamps, split labels, outcomes, and hidden traits are excluded. The corrected source data and 420/90/90 student assignments were preserved; hashes are saved with the models. No simulation regeneration or tuning occurred during model training.

Both pipelines use training-only median imputation with missingness indicators and preserve entirely empty features. Indicators are learned for columns missing in training. Logistic regression adds standard scaling and uses C=1, lbfgs, max_iter=3000, random_state=42. Gradient boosting uses 100 trees, learning_rate=0.05, max_depth=2, min_samples_leaf=20, subsample=1, random_state=42. Shallow trees and a minimum leaf size restrict complexity. No hyperparameter search or class rebalancing was used. Every snapshot has equal training weight.

Training warnings: {"logistic_regression": [], "gradient_boosting": []}. A convergence warning aborts the run instead of silently treating the fit as successful.

## Validation performance

| model | threshold_type | cohort | threshold | n_snapshots | prevalence | precision | recall | f1 | f2 | average_precision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | fixed_0.5 | overall | 0.5000 | 822 | 0.5036 | 0.6971 | 0.5169 | 0.5936 | 0.5451 | 0.7003 |
| logistic_regression | validation_f2 | overall | 0.0800 | 822 | 0.5036 | 0.5209 | 0.9952 | 0.6838 | 0.8418 | 0.7003 |
| gradient_boosting | fixed_0.5 | overall | 0.5000 | 822 | 0.5036 | 0.7059 | 0.4348 | 0.5381 | 0.4710 | 0.6910 |
| gradient_boosting | validation_f2 | overall | 0.1600 | 822 | 0.5036 | 0.5306 | 0.9831 | 0.6892 | 0.8399 | 0.6910 |

The complete 91-row threshold table for each model includes precision, recall, F2 and flag counts. Average precision summarises probability ranking across thresholds and is not the precision of one chosen threshold.

## Test performance at frozen validation thresholds

| model | cohort | threshold | n_snapshots | prevalence | precision | recall | f1 | f2 | average_precision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | overall | 0.0800 | 885 | 0.4339 | 0.4505 | 0.9948 | 0.6201 | 0.8012 | 0.6406 |
| logistic_regression | 3 | 0.0800 | 392 | 0.3265 | 0.3518 | 0.9922 | 0.5194 | 0.7274 | 0.4385 |
| logistic_regression | 7 | 0.0800 | 291 | 0.4399 | 0.4456 | 0.9922 | 0.6150 | 0.7967 | 0.5882 |
| logistic_regression | 10 | 0.0800 | 202 | 0.6337 | 0.6337 | 1.0000 | 0.7758 | 0.8964 | 0.7758 |
| gradient_boosting | overall | 0.1600 | 885 | 0.4339 | 0.4620 | 0.9818 | 0.6283 | 0.8014 | 0.6172 |
| gradient_boosting | 3 | 0.1600 | 392 | 0.3265 | 0.3518 | 0.9922 | 0.5194 | 0.7274 | 0.4083 |
| gradient_boosting | 7 | 0.1600 | 291 | 0.4399 | 0.4822 | 0.9531 | 0.6404 | 0.7974 | 0.5543 |
| gradient_boosting | 10 | 0.1600 | 202 | 0.6337 | 0.6337 | 1.0000 | 0.7758 | 0.8964 | 0.7324 |

| model | cohort | tp | fp | tn | fn | flag_count | flagged_percent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | overall | 382 | 466 | 35 | 2 | 848 | 95.8192 |
| logistic_regression | 3 | 127 | 234 | 30 | 1 | 361 | 92.0918 |
| logistic_regression | 7 | 127 | 158 | 5 | 1 | 285 | 97.9381 |
| logistic_regression | 10 | 128 | 74 | 0 | 0 | 202 | 100.0000 |
| gradient_boosting | overall | 377 | 439 | 62 | 7 | 816 | 92.2034 |
| gradient_boosting | 3 | 127 | 234 | 30 | 1 | 361 | 92.0918 |
| gradient_boosting | 7 | 122 | 131 | 32 | 6 | 253 | 86.9416 |
| gradient_boosting | 10 | 128 | 74 | 0 | 0 | 202 | 100.0000 |

## Test reference at threshold 0.5

| model | cohort | threshold | n_snapshots | prevalence | precision | recall | f1 | f2 | average_precision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | overall | 0.5000 | 885 | 0.4339 | 0.6134 | 0.5000 | 0.5509 | 0.5192 | 0.6406 |
| gradient_boosting | overall | 0.5000 | 885 | 0.4339 | 0.6583 | 0.4115 | 0.5064 | 0.4448 | 0.6172 |

Full day-specific metrics at both threshold settings are in `snapshot_metrics.csv`. All fractions are 0–1 except flagged_percent and warned_missed_percent, which are 0–100.

gradient_boosting has the higher observed overall test F2 at its frozen threshold. This descriptive comparison does not establish superiority outside this simulation and does not change the validation-selected candidate.

Precision is the fraction of flags that actually miss the deadline; recall is the fraction of missed-deadline snapshots flagged. False positives represent warnings on on-time modules, not evidence of a barrier. Flag volume shows the simulated review burden and should be considered alongside recall.

## First warning per student-module on test

| measure | logistic_regression | gradient_boosting |
| --- | --- | --- |
| eligible_modules | 392.0000 | 392.0000 |
| eligible_missed_modules | 128.0000 | 128.0000 |
| warned_missed_modules | 128.0000 | 128.0000 |
| warned_missed_percent | 100.0000 | 100.0000 |
| missed_by_all_checks | 0.0000 | 0.0000 |
| median_lead_days | 11.0000 | 11.0000 |
| mean_lead_days | 10.9453 | 10.9453 |
| first_detected_11_days | 127.0000 | 127.0000 |
| first_detected_7_days | 0.0000 | 0.0000 |
| first_detected_4_days | 1.0000 | 1.0000 |
| first_detected_other_lead | 0.0000 | 0.0000 |
| on_time_modules_false_warning | 247.0000 | 240.0000 |
| unique_students_warned | 90.0000 | 90.0000 |
| known_missed_modules_no_snapshots | 0.0000 | 0.0000 |

Only the first positive prediction across available days 3, 7, and 10 counts. Warning lead time is actual deadline minus first-warning timestamp. Mean and median include detected missed-deadline modules only; undetected modules retain blank lead times, never zero. Counts at 11, 7, or 4 days are mutually exclusive first detections. On-time modules with any warning count once; unique warned students are counted across modules. `first_warnings_<model>.csv` retains every eligible module, including unflagged modules with blank first-warning time/lead. Known missed modules with no eligible labelled snapshots are reported separately in `missed_modules_without_snapshots.csv` and excluded from the eligible-module detection denominator.

## Undefined metrics, dependence, and limitations

CSV blank metrics and the word `undefined` mean a missing denominator: precision when no flags, recall when no positives, F1/F2 when there are neither positives nor flags, average precision when there are no positives, and lead-time mean/median when no missed modules are detected. A zero score with a nonzero denominator is a meaningful zero. Counts remain zero when no records qualify.

Snapshots from the same student or module are correlated. Student separation prevents cross-split learner leakage but does not make individual snapshots independent. Later-day cohorts differ as completed modules leave; day-specific metrics are not a controlled comparison of warning timing. No independence-based confidence intervals or significance claims are made.

The synthetic behavioural rules may make patterns easier or different from real learning. Confirmed barriers are not inferred from scores or session lengths. Outcomes with deadlines beyond observation remain excluded under the existing conservative policy, including already-completed modules excluded solely by that policy. Results do not establish calibration, fairness, intervention benefit, or deployment suitability. No dashboard or messaging was implemented.

## Reproduction and tests

Latest full test output:

```text
...........................                                              [100%]
27 passed in 9.50s
```

Run `.\.venv\Scripts\python.exe -m src.modeling` for a new run; existing frozen artifacts are protected against overwrite. Use `--model-dir models/review_run --report-dir reports/review_run` for a separate rerun on unchanged data. Use `--evaluate-only` to evaluate the already-frozen models; source hashes must still match. Run `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` for simulation and model tests. Final test output is saved in `reports/model_test_results.txt`.

Execution note: the initial Windows sandbox blocked a SciPy extension and later prevented pytest temporary-directory creation. Approved outside-sandbox execution completed fitting and all tests without changing Windows security settings. The dependency check found no broken requirements.

## Validation-only workload diagnostic addendum


All results below are **validation-only simulated diagnostics**, distinct from the original test results above. The original report is preserved byte-for-byte in `model_evaluation_before_workload_review.md`; the existing report body and original result files are unchanged.

“Flag every eligible snapshot” is a diagnostic reference, not a newly selected model. It flags 822 validation snapshots, giving precision equal to prevalence (0.5036), recall 1.0000, and F2 0.8354. Original model thresholds remain logistic regression 0.08 and gradient boosting 0.16.

| model | cohort | threshold | n_snapshots | precision | recall | f2 | flag_count | flagged_percent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | overall | 0.0800 | 822 | 0.5209 | 0.9952 | 0.8418 | 791 | 96.2287 |
| gradient_boosting | overall | 0.1600 | 822 | 0.5306 | 0.9831 | 0.8399 | 767 | 93.3090 |
| flag_all_diagnostic | overall | undefined | 822 | 0.5036 | 1.0000 | 0.8354 | 822 | 100.0000 |

First-warning comparison, counting each eligible validation student-module once:

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

Flag-all demonstrates how high recall can arise from broadly warning everyone. It is not evidence of effective prioritisation or improved learner outcomes. Lead times use actual deadline minus the first flag timestamp and include detected missed modules only; blank lead times are never converted to zero. See `workload_review.md` for the checkpoint capacity scenarios and definitions.

**The test set has already been inspected. Any later policy revision is exploratory and must not be presented as a fresh untouched-test evaluation. This review uses validation predictions only, with no test-based tuning, new policy selection, fitting, or data regeneration.**
