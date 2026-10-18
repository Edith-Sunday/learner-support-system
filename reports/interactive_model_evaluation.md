# Additional Module 1 model: exploratory evaluation

**Artificial simulation only: no proven real-world predictive accuracy or improved learner outcomes. The test set was already examined in earlier project work; these are exploratory results, not an untouched-test evaluation. Numeric interactive scoring remains disabled.**

## Predeclared design and mappings

The machine-readable design was saved before fitting (`models/interactive_module1/design.json`). Selection was written before this run computed test performance. One pooled model per algorithm includes checkpoint day; no search or simulation changes. Training-only median imputation with indicators preserves raw missing quiz scores (no attempt) and trends (fewer than two attempts). Logistic regression uses scaling, C=1, max_iter=3000, seed 42; boosting uses 80 trees, learning rate .05, depth 2, minimum leaf 15, seed 42.

Included: practice submitted (any accepted submission, correctness irrelevant); quiz passed (any valid score ≥80%, never undone by a later lower score); latest quiz score (percent); latest minus previous score (percentage points); count of valid attempts; scheduled checkpoint day. Interactive quiz points are multiplied by ten. Both routes use the same `features_at` implementation, occurrence/record-ID order, and BOTH event_time and recorded_at ≤ checkpoint. Online and delayed-offline mapping cases are tested. All eligible historical rows were independently reconstructed from events.

Activities completed is the exact sum of the two progress indicators, so is redundant and used only for eligibility/rule. Earlier-module counts are structural zero. Offline participation is excluded: original teacher-offline sessions are not available in interactive records. Observed snapshot disagreements with a submission-only definition: {'train': 67, 'validation': 19, 'test': 11}. Login, interruptions, session duration and active time are excluded for measurement incompatibility; existing tracking remains intact. Constant counts and missingness are recorded in metadata; no data-dependent feature dropping.

Eligible rows are original conservatively labelled, incomplete Module 1 snapshots at days 3/7/10. Completion known by the checkpoint excludes a row. Timeliness still uses completion occurrence, and deadlines beyond the original observation window remain censored. Original student assignments are checked. No other module or synthetic learner was added.

| split | students | snapshots | positive_snapshots | missed_modules |
| --- | --- | --- | --- | --- |
| train | 402 | 926 | 381 | 127 |
| validation | 86 | 198 | 102 | 34 |
| test | 85 | 197 | 81 | 27 |

## Comparison and frozen selection

Each checkpoint reviews ceil(20% × its cohort size). This illustrative review budget is neither agreed staffing capacity nor a daily caseload. Models rank descending probability. The progress rule ranks fewer completed requirements, then missing latest score before observed scores, then lower score. Missing first is a declared conservative review choice, not evidence of low ability. Exact ties use ascending learner ID, with no target information. Identical inputs receive identical model scores; the ID ordering is administrative, not personalised differentiation.

Random reference: 1,000 seeded draws at the same review volumes, seed 42, fresh uniform rankings at each checkpoint. Tables report mean, standard deviation and central 95% draw range (not uncertainty intervals for real-world performance).

Selected candidate: **logistic_regression**. Validation mean recall across checkpoints: {'logistic_regression': 0.2843137254901961, 'gradient_boosting': 0.2647058823529412}. Ties within 1e-12 favour logistic regression. No decision changes after test evaluation.

## Results

### Validation

| method | checkpoint | eligible | positives | reviewed | true_positives | false_warnings | precision | recall | average_precision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | 3 | 86 | 34 | 18 | 12 | 6 | 0.667 | 0.353 | 0.519 |
| logistic_regression | 7 | 63 | 34 | 13 | 8 | 5 | 0.615 | 0.235 | 0.580 |
| logistic_regression | 10 | 49 | 34 | 10 | 9 | 1 | 0.900 | 0.265 | 0.865 |
| logistic_regression | pooled | 198 | 102 | 41 | 29 | 12 | 0.707 | 0.284 | 0.691 |
| gradient_boosting | 3 | 86 | 34 | 18 | 11 | 7 | 0.611 | 0.324 | 0.487 |
| gradient_boosting | 7 | 63 | 34 | 13 | 7 | 6 | 0.538 | 0.206 | 0.562 |
| gradient_boosting | 10 | 49 | 34 | 10 | 9 | 1 | 0.900 | 0.265 | 0.808 |
| gradient_boosting | pooled | 198 | 102 | 41 | 27 | 14 | 0.659 | 0.265 | 0.672 |
| progress_rule | 3 | 86 | 34 | 18 | 8 | 10 | 0.444 | 0.235 | 0.419 |
| progress_rule | 7 | 63 | 34 | 13 | 8 | 5 | 0.615 | 0.235 | 0.605 |
| progress_rule | 10 | 49 | 34 | 10 | 9 | 1 | 0.900 | 0.265 | 0.828 |
| progress_rule | pooled | 198 | 102 | 41 | 25 | 16 | 0.610 | 0.245 | 0.523 |

Module-level first warning (each learner-module counted once):

| method | eligible_missed_modules | detected_missed_modules | missed_all_checks | mean_lead_days | median_lead_days | first_detected_11_days | first_detected_7_days | first_detected_4_days | on_time_modules_warned | unique_students_warned | known_missed_without_snapshots |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | 34 | 17 | 17 | 9.471 | 11.000 | 12 | 3 | 2 | 10 | 27 | 0 |
| gradient_boosting | 34 | 15 | 19 | 9.733 | 11.000 | 11 | 3 | 1 | 11 | 26 | 0 |
| progress_rule | 34 | 15 | 19 | 8.533 | 11.000 | 8 | 4 | 3 | 11 | 26 | 0 |

Random reference variation:

| checkpoint | metric | mean | sd | p025 | p975 |
| --- | --- | --- | --- | --- | --- |
| 3 | reviewed | 18.000 | 0.000 | 18.000 | 18.000 |
| 3 | true_positives | 7.187 | 1.914 | 3.000 | 11.000 |
| 3 | false_warnings | 10.813 | 1.914 | 7.000 | 15.000 |
| 3 | precision | 0.399 | 0.106 | 0.167 | 0.611 |
| 3 | recall | 0.211 | 0.056 | 0.088 | 0.324 |
| 3 | average_precision | 0.427 | 0.056 | 0.332 | 0.552 |
| 7 | reviewed | 13.000 | 0.000 | 13.000 | 13.000 |
| 7 | true_positives | 6.962 | 1.534 | 4.000 | 10.000 |
| 7 | false_warnings | 6.038 | 1.534 | 3.000 | 9.000 |
| 7 | precision | 0.536 | 0.118 | 0.308 | 0.769 |
| 7 | recall | 0.205 | 0.045 | 0.118 | 0.294 |
| 7 | average_precision | 0.565 | 0.057 | 0.467 | 0.685 |
| 10 | reviewed | 10.000 | 0.000 | 10.000 | 10.000 |
| 10 | true_positives | 6.943 | 1.327 | 4.000 | 9.000 |
| 10 | false_warnings | 3.057 | 1.327 | 1.000 | 6.000 |
| 10 | precision | 0.694 | 0.133 | 0.400 | 0.900 |
| 10 | recall | 0.204 | 0.039 | 0.118 | 0.265 |
| 10 | average_precision | 0.718 | 0.059 | 0.604 | 0.836 |
| pooled | reviewed | 41.000 | 0.000 | 41.000 | 41.000 |
| pooled | true_positives | 21.092 | 2.808 | 15.975 | 27.000 |
| pooled | false_warnings | 19.908 | 2.808 | 14.000 | 25.025 |
| pooled | precision | 0.514 | 0.068 | 0.390 | 0.659 |
| pooled | recall | 0.207 | 0.028 | 0.157 | 0.265 |
| pooled | average_precision | 0.528 | 0.035 | 0.463 | 0.595 |

Exact score ties (pooled rows combine multiple snapshots per learner):

| method | checkpoint | unique_scores | learners_in_tied_groups | largest_tie | boundary_tie_size | selected_from_boundary_tie |
| --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | 3 | 20 | 74 | 53 | 53 | 5 |
| logistic_regression | 7 | 32 | 39 | 17 | 2 | 2 |
| logistic_regression | 10 | 30 | 26 | 9 | 6 | 2 |
| logistic_regression | pooled | 82 | 139 | 53 | Undefined | Undefined |
| gradient_boosting | 3 | 14 | 81 | 56 | 56 | 7 |
| gradient_boosting | 7 | 21 | 49 | 21 | 1 | 1 |
| gradient_boosting | 10 | 18 | 38 | 21 | 1 | 1 |
| gradient_boosting | pooled | 53 | 168 | 56 | Undefined | Undefined |
| progress_rule | 3 | 15 | 81 | 53 | 53 | 18 |
| progress_rule | 7 | 16 | 59 | 17 | 17 | 13 |
| progress_rule | 10 | 14 | 46 | 9 | 3 | 1 |
| progress_rule | pooled | 17 | 196 | 76 | Undefined | Undefined |

### Test

| method | checkpoint | eligible | positives | reviewed | true_positives | false_warnings | precision | recall | average_precision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | 3 | 85 | 27 | 17 | 7 | 10 | 0.412 | 0.259 | 0.403 |
| logistic_regression | 7 | 66 | 27 | 14 | 10 | 4 | 0.714 | 0.370 | 0.647 |
| logistic_regression | 10 | 46 | 27 | 10 | 7 | 3 | 0.700 | 0.259 | 0.726 |
| logistic_regression | pooled | 197 | 81 | 41 | 24 | 17 | 0.585 | 0.296 | 0.622 |
| gradient_boosting | 3 | 85 | 27 | 17 | 6 | 11 | 0.353 | 0.222 | 0.377 |
| gradient_boosting | 7 | 66 | 27 | 14 | 9 | 5 | 0.643 | 0.333 | 0.552 |
| gradient_boosting | 10 | 46 | 27 | 10 | 7 | 3 | 0.700 | 0.259 | 0.655 |
| gradient_boosting | pooled | 197 | 81 | 41 | 22 | 19 | 0.537 | 0.272 | 0.574 |
| progress_rule | 3 | 85 | 27 | 17 | 6 | 11 | 0.353 | 0.222 | 0.353 |
| progress_rule | 7 | 66 | 27 | 14 | 7 | 7 | 0.500 | 0.259 | 0.458 |
| progress_rule | 10 | 46 | 27 | 10 | 7 | 3 | 0.700 | 0.259 | 0.771 |
| progress_rule | pooled | 197 | 81 | 41 | 20 | 21 | 0.488 | 0.247 | 0.426 |

Module-level first warning (each learner-module counted once):

| method | eligible_missed_modules | detected_missed_modules | missed_all_checks | mean_lead_days | median_lead_days | first_detected_11_days | first_detected_7_days | first_detected_4_days | on_time_modules_warned | unique_students_warned | known_missed_without_snapshots |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | 27 | 16 | 11 | 8.375 | 7.000 | 7 | 7 | 2 | 15 | 31 | 0 |
| gradient_boosting | 27 | 13 | 14 | 8.615 | 7.000 | 6 | 6 | 1 | 14 | 27 | 0 |
| progress_rule | 27 | 14 | 13 | 8.071 | 7.000 | 6 | 5 | 3 | 18 | 32 | 0 |

Random reference variation:

| checkpoint | metric | mean | sd | p025 | p975 |
| --- | --- | --- | --- | --- | --- |
| 3 | reviewed | 17.000 | 0.000 | 17.000 | 17.000 |
| 3 | true_positives | 5.388 | 1.799 | 2.000 | 9.000 |
| 3 | false_warnings | 11.612 | 1.799 | 8.000 | 15.000 |
| 3 | precision | 0.317 | 0.106 | 0.118 | 0.529 |
| 3 | recall | 0.200 | 0.067 | 0.074 | 0.333 |
| 3 | average_precision | 0.351 | 0.057 | 0.263 | 0.473 |
| 7 | reviewed | 14.000 | 0.000 | 14.000 | 14.000 |
| 7 | true_positives | 5.764 | 1.652 | 3.000 | 9.000 |
| 7 | false_warnings | 8.236 | 1.652 | 5.000 | 11.000 |
| 7 | precision | 0.412 | 0.118 | 0.214 | 0.643 |
| 7 | recall | 0.213 | 0.061 | 0.111 | 0.333 |
| 7 | average_precision | 0.444 | 0.062 | 0.341 | 0.577 |
| 10 | reviewed | 10.000 | 0.000 | 10.000 | 10.000 |
| 10 | true_positives | 5.835 | 1.393 | 3.000 | 8.025 |
| 10 | false_warnings | 4.165 | 1.393 | 1.975 | 7.000 |
| 10 | precision | 0.584 | 0.139 | 0.300 | 0.802 |
| 10 | recall | 0.216 | 0.052 | 0.111 | 0.297 |
| 10 | average_precision | 0.617 | 0.067 | 0.497 | 0.755 |
| pooled | reviewed | 41.000 | 0.000 | 41.000 | 41.000 |
| pooled | true_positives | 16.987 | 2.772 | 12.000 | 23.000 |
| pooled | false_warnings | 24.013 | 2.772 | 18.000 | 29.000 |
| pooled | precision | 0.414 | 0.068 | 0.293 | 0.561 |
| pooled | recall | 0.210 | 0.034 | 0.148 | 0.284 |
| pooled | average_precision | 0.425 | 0.035 | 0.365 | 0.503 |

Exact score ties (pooled rows combine multiple snapshots per learner):

| method | checkpoint | unique_scores | learners_in_tied_groups | largest_tie | boundary_tie_size | selected_from_boundary_tie |
| --- | --- | --- | --- | --- | --- | --- |
| logistic_regression | 3 | 15 | 78 | 60 | 60 | 5 |
| logistic_regression | 7 | 28 | 48 | 19 | 1 | 1 |
| logistic_regression | 10 | 31 | 23 | 4 | 1 | 1 |
| logistic_regression | pooled | 74 | 149 | 60 | Undefined | Undefined |
| gradient_boosting | 3 | 11 | 81 | 63 | 63 | 8 |
| gradient_boosting | 7 | 21 | 52 | 23 | 1 | 1 |
| gradient_boosting | 10 | 23 | 30 | 14 | 1 | 1 |
| gradient_boosting | pooled | 55 | 163 | 63 | Undefined | Undefined |
| progress_rule | 3 | 14 | 80 | 60 | 60 | 17 |
| progress_rule | 7 | 17 | 63 | 19 | 19 | 14 |
| progress_rule | 10 | 15 | 43 | 7 | 2 | 2 |
| progress_rule | pooled | 17 | 196 | 83 | Undefined | Undefined |

## Interpretation and recommendation

- Validation day 3: candidate recall 0.353, rule 0.235, random mean 0.211 (draw range 0.088–0.324); candidate exceeds the rule at the same review volume.

- Validation day 7: candidate recall 0.235, rule 0.235, random mean 0.205 (draw range 0.118–0.294); candidate does not exceed the rule at the same review volume.

- Validation day 10: candidate recall 0.265, rule 0.265, random mean 0.204 (draw range 0.118–0.265); candidate does not exceed the rule at the same review volume.

- Test day 3: candidate recall 0.259, rule 0.222, random mean 0.200 (draw range 0.074–0.333); candidate exceeds the rule at the same review volume.

- Test day 7: candidate recall 0.370, rule 0.259, random mean 0.213 (draw range 0.111–0.333); candidate exceeds the rule at the same review volume.

- Test day 10: candidate recall 0.259, rule 0.259, random mean 0.216 (draw range 0.111–0.297); candidate does not exceed the rule at the same review volume.


Do not enable numeric scoring on this evidence alone. A transparent progress-based review list is the more defensible interim option for staff review: there is no demonstrated real-world benefit and small checkpoint cohorts plus tied scores make rankings unstable. This is a recommendation for review, not a newly implemented policy. Even favourable differences in this simulation require independent prospective evidence and a workload policy agreed with staff.

Snapshot rows within a learner/module are correlated; later cohorts differ because completed modules leave. Module 1 alone limits sample size, coverage and transfer to other modules. AP uses untie-broken scores (rule score preserves the declared ordering); arbitrary ID order is not credited as predictive information. Pooled rule/random AP is descriptive across changing cohorts, not a selected policy. Undefined metrics are blank in CSV/“Undefined” here (no positives or no detected warning); genuine zero detection remains zero. Lead time is actual deadline minus first selected snapshot timestamp, averaged only over detected missed modules, never zero-filled for undetected cases. Random module-level variation and all individual draws are in separate CSVs.

A fixed probability threshold allows workload to vary; this fixed review fraction chooses the top ranks regardless of absolute scores. Neither constitutes a calibrated probability or validated staff decision rule. The original frozen thresholds and results remain unchanged. No checkpoint history is overwritten or backfilled.

Fit warnings: None. Both repeated fits and saved/reloaded predictions matched exactly. Dataset hashes, versions, feature order, settings, validation/test predictions, metric tables, random draws and module summaries are saved under `models/interactive_module1/`.

Reproduce in a separate copy with no existing `models/interactive_module1/selection.json`: `.\.venv\Scripts\python.exe -m src.interactive_model`. The script refuses to overwrite its frozen output.

## Random module-level warning variation

Each draw deduplicates first warnings before calculating detected-only lead time. SD and the central draw range describe random review variability, not real-world confidence.

### Validation random first-warning reference

| metric | mean | sd | p025 | p975 |
| --- | --- | --- | --- | --- |
| detected_missed_modules | 17.079 | 2.236 | 13.000 | 21.000 |
| recall | 0.502 | 0.066 | 0.382 | 0.618 |
| mean_lead_days | 7.914 | 0.557 | 6.789 | 9.000 |
| median_lead_days | 7.803 | 1.516 | 7.000 | 11.000 |
| on_time_modules_warned | 17.552 | 2.412 | 13.000 | 22.000 |
| unique_students_warned | 34.631 | 1.848 | 31.000 | 38.000 |

### Test random first-warning reference

| metric | mean | sd | p025 | p975 |
| --- | --- | --- | --- | --- |
| detected_missed_modules | 13.694 | 2.167 | 10.000 | 18.000 |
| recall | 0.507 | 0.080 | 0.370 | 0.667 |
| mean_lead_days | 7.764 | 0.643 | 6.537 | 9.000 |
| median_lead_days | 7.632 | 1.419 | 7.000 | 11.000 |
| on_time_modules_warned | 20.833 | 2.354 | 16.000 | 25.000 |
| unique_students_warned | 34.527 | 1.797 | 31.000 | 38.000 |

## Practical reading of the evidence

Validation contained only 34 missed-deadline modules; test contained 27. Later checkpoints have only 49 and 46 eligible learners respectively. At day 3, 53 of 86 validation learners share one logistic-regression score, and 60 of 85 test learners share one score. These large groups cannot be meaningfully personalised using these inputs. All six selected predictors vary in training; 486 of 926 training quiz scores and 771 trends are genuinely missing.

Logistic regression exceeds the random mean recall at each checkpoint in both subsets, but these are small descriptive differences, not proof of statistically reliable superiority. Its validation day-7 and day-10 review results equal the progress rule; test day 10 also ties. Test day-10 average precision is actually higher for the progress rule (0.771 versus 0.726). This mixed evidence does not justify replacing a transparent review list with numeric model scores now. No such list or score policy was enabled in this task.
