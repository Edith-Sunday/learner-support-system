"""Validation-only workload diagnostics; never fit or select a model/policy."""
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.modeling import (AUDIT, KEY, MODEL_NAMES, TARGET, early_warnings,
                          feature_order, grouped_metrics, markdown_table, predictors)
from src.simulate import ROOT

FRACTIONS = (10, 20, 30)
REFERENCE = 'flag_all_diagnostic'
MARKER = '\n## Validation-only workload diagnostic addendum\n'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capacity_scenarios(predictions):
    """Rank on scores only. IDs break ties, never target values or row order."""
    summaries, rankings = [], []
    if predictions.duplicated(['model'] + KEY + ['snapshot_day']).any():
        raise ValueError('Duplicate model/student/module/checkpoint')
    if not np.isfinite(predictions.probability).all():
        raise ValueError('Nonfinite scores')
    for (model, day), cohort in predictions.groupby(['model', 'snapshot_day'], sort=True):
        ranked = cohort.sort_values(['probability', 'student_id', 'module_id'],
                                    ascending=[False, True, True], kind='stable').copy()
        ranked['risk_rank'] = np.arange(1, len(ranked) + 1)
        positives = int(ranked[TARGET].sum())
        for percent in FRACTIONS:
            # Integer ceiling avoids floating-point rounding errors.
            count = (len(ranked) * percent + 99) // 100
            selected = ranked.iloc[:count]
            tp = int(selected[TARGET].sum())
            lowest = float(selected.probability.iloc[-1]) if count else np.nan
            ranked[f'reviewed_{percent}pct'] = (ranked.risk_rank <= count).astype(int)
            summaries.append(dict(model=model, snapshot_day=int(day), review_percent=percent,
                                  eligible_snapshots=len(ranked), positive_snapshots=positives,
                                  reviewed=count, tp=tp, fp=count - tp,
                                  precision=tp / count if count else np.nan,
                                  recall=tp / positives if positives else np.nan,
                                  lowest_selected_score=lowest,
                                  boundary_tied_total=int(ranked.probability.eq(lowest).sum()),
                                  boundary_tied_selected=int(selected.probability.eq(lowest).sum())))
        rankings.append(ranked)
    return pd.DataFrame(summaries), pd.concat(rankings, ignore_index=True)


def main():
    data, models, reports = ROOT / 'data', ROOT / 'models', ROOT / 'reports'
    outputs = [reports / name for name in (
        'workload_review.md', 'workload_validation_predictions.csv',
        'workload_validation_capacity.csv', 'workload_validation_rankings.csv',
        'workload_validation_snapshot_reference.csv', 'workload_validation_first_warning_summary.csv',
        'workload_validation_first_warnings.csv', 'workload_review_audit.json',
        'model_evaluation_before_workload_review.md')]
    if any(p.exists() for p in outputs):
        raise FileExistsError('Workload artifacts already exist; preserve them rather than overwrite this review')
    evaluation = reports / 'model_evaluation.md'
    original_report = evaluation.read_bytes()
    # Hash-only integrity checks never parse or evaluate test records/results.
    originals = {p: digest(p) for folder in (data, models, reports)
                 for p in folder.iterdir() if p.is_file()}
    manifest = json.loads((models / 'selection.json').read_text())
    features = feature_order(data)
    if features != manifest['features']:
        raise ValueError('Feature order changed')
    validation_path = data / 'labelled_validation.csv'
    if digest(validation_path) != manifest['dataset_hashes'][validation_path.name]:
        raise ValueError('Validation data changed from frozen model run')
    # This is the ONLY source dataset parsed for the review.
    validation = pd.read_csv(validation_path)
    if not validation.split.eq('validation').all() or not validation[TARGET].isin([0, 1]).all():
        raise ValueError('Expected labelled validation records only')
    x = predictors(validation, features)
    predictions, metrics, warning_summaries, warning_details = [], [], [], []
    eligible_outcomes = validation.drop_duplicates(KEY)[KEY + [TARGET]]
    for name in (*MODEL_NAMES, REFERENCE):
        if name == REFERENCE:
            # Ones implement flag-all; they are not estimated probabilities.
            probability, threshold = np.ones(len(validation)), .5
        else:
            model_path = models / f'{name}.joblib'
            if digest(model_path) != manifest['pipeline_hashes'][name]:
                raise ValueError('Saved pipeline changed')
            pipeline = joblib.load(model_path)
            probability = pipeline.predict_proba(x)[:, 1]
            threshold = manifest['thresholds'][name]
        predicted = validation[AUDIT + [TARGET]].copy()
        predicted['model'] = name
        predicted['probability'] = probability
        predicted['flag'] = (probability >= threshold).astype(int)
        predicted['threshold'] = threshold
        if name != REFERENCE:
            predictions.append(predicted)
        rows = grouped_metrics(validation, probability, name, 'validation', threshold,
                               'diagnostic_flag_all' if name == REFERENCE else 'original_frozen')
        if name == REFERENCE:
            for row in rows:
                row['threshold'] = np.nan
                row['average_precision'] = np.nan
        metrics.extend(rows)
        summary, details, _ = early_warnings(predicted, eligible_outcomes)
        # This analysis deliberately covers only modules with eligible validation snapshots.
        summary.pop('known_missed_modules_no_snapshots')
        warning_summaries.append(dict(model=name, **summary))
        details['model'] = name
        warning_details.append(details)
    predictions = pd.concat(predictions, ignore_index=True)
    scenarios, rankings = capacity_scenarios(predictions)
    metrics = pd.DataFrame(metrics)
    warnings = pd.DataFrame(warning_summaries)
    tables = {
        'workload_validation_predictions.csv': predictions,
        'workload_validation_capacity.csv': scenarios,
        'workload_validation_rankings.csv': rankings,
        'workload_validation_snapshot_reference.csv': metrics,
        'workload_validation_first_warning_summary.csv': warnings,
        'workload_validation_first_warnings.csv': pd.concat(warning_details, ignore_index=True),
    }
    for filename, frame in tables.items():
        frame.to_csv(reports / filename, index=False)
    columns = ['model', 'cohort', 'threshold', 'n_snapshots', 'precision', 'recall', 'f2',
               'flag_count', 'flagged_percent']
    overall = metrics[metrics.cohort.eq('overall')]
    reference = overall[overall.model.eq(REFERENCE)].iloc[0]
    comparison = markdown_table(overall[columns])
    first_warning = markdown_table(warnings.set_index('model').T.rename_axis('measure').reset_index())
    caveat = ('The test set has already been inspected. Any later policy revision is exploratory '
              'and must not be presented as a fresh untouched-test evaluation. This review uses '
              'validation predictions only, with no test-based tuning, new policy selection, fitting, or data regeneration.')
    addendum = f'''{MARKER}

All results below are **validation-only simulated diagnostics**, distinct from the original test results above. The original report is preserved byte-for-byte in `model_evaluation_before_workload_review.md`; the existing report body and original result files are unchanged.

“Flag every eligible snapshot” is a diagnostic reference, not a newly selected model. It flags {int(reference.flag_count)} validation snapshots, giving precision equal to prevalence ({reference.precision:.4f}), recall {reference.recall:.4f}, and F2 {reference.f2:.4f}. Original model thresholds remain logistic regression {manifest['thresholds']['logistic_regression']} and gradient boosting {manifest['thresholds']['gradient_boosting']}.

{comparison}

First-warning comparison, counting each eligible validation student-module once:

{first_warning}

Flag-all demonstrates how high recall can arise from broadly warning everyone. It is not evidence of effective prioritisation or improved learner outcomes. Lead times use actual deadline minus the first flag timestamp and include detected missed modules only; blank lead times are never converted to zero. See `workload_review.md` for the checkpoint capacity scenarios and definitions.

**{caveat}**
'''
    sections = []
    for name in MODEL_NAMES:
        section_columns = ['snapshot_day', 'review_percent', 'eligible_snapshots', 'reviewed',
                           'tp', 'fp', 'precision', 'recall', 'lowest_selected_score']
        sections.append(f'### {name}\n\n' + markdown_table(scenarios[scenarios.model.eq(name)][section_columns]))
    report = f'''# Validation warning workload review

**These are artificial simulated-data results, not established real-world accuracy or improved learner outcomes.**

**{caveat}**

## Scope and preserved decisions

Only `labelled_validation.csv` is parsed as an input dataset. The existing fitted pipelines are loaded for `predict_proba` only. The candidate remains {manifest['candidate_model']}; thresholds remain unchanged. There are {len(validation)} eligible validation snapshots across {len(eligible_outcomes)} student-module pairs. Eligibility follows the existing labelled-export policy, including its exclusions for deadlines beyond observation. This review does not assess modules without eligible validation snapshots.

## Flag-all diagnostic reference versus original frozen thresholds

{comparison}

{markdown_table(metrics[columns])}

The reference flags every eligible snapshot; its precision is simply the cohort prevalence and its recall is 1 when positives exist. It is not a fitted or newly selected model. Its threshold and average precision are blank because it supplies a flagging rule, not a probability-ranking model. Original model scores and thresholds have not been changed.

## First warning across available validation checkpoints

{first_warning}

Each eligible student-module counts once, using its earliest flag across available days 3, 7, and 10. Mean/median lead times use actual deadline minus first-warning timestamp and only detected missed-deadline modules. First-detection counts at 11, 7, and 4 days are mutually exclusive. On-time modules with at least one warning and unique students warned count once at their respective levels. No-snapshot modules are outside this validation-export-only comparison; none are silently assigned zero lead time or treated as detected.

## Illustrative checkpoint review fractions

The 10%, 20%, and 30% scenarios are illustrative workload scenarios, **not agreed staffing capacities**. They select a fraction of each day-3, day-7, or day-10 checkpoint cohort, pooled across its module unlock dates. They are **not a daily teacher caseload**, nor a count of distinct students or teacher-hours. The same student/module may reappear at another checkpoint. No cross-checkpoint suppression is applied to these scenario tables.

Number reviewed = ceiling(eligible snapshot count × review fraction). Within each model and checkpoint, sort by descending full-precision probability, then ascending student_id (lexicographic), then ascending numeric module_id. Duplicate student-module-checkpoint keys are rejected. Targets never break ties. Exactly the requested ceiling count is selected, even if a score tie spans the boundary.

`lowest_selected_score` is a descriptive boundary, **not a newly chosen threshold**. A rule using score >= that value may select additional tied records. The supporting capacity table includes boundary tie counts, and the ranking table records risk_rank and reviewed_10pct/20pct/30pct for reproducibility. Displayed scores are rounded; CSVs retain full available precision.

{chr(10).join(sections)}

Precision = true positives / reviewed; recall = true positives / all positive snapshots in that checkpoint cohort, including unreviewed positives. False positives are reviewed snapshots whose target is 0. Blank/undefined ratios indicate a zero denominator; a zero ratio with a nonzero denominator is a meaningful zero.

## Fixed threshold versus fixed capacity

A fixed probability threshold flags every score at or above that value. The number flagged varies with cohort size and the distribution of scores; the original frozen models illustrate this potentially high workload.

A fixed review capacity ranks scores and takes the highest k. Here k is ceiling(fraction × checkpoint cohort size), so the proportion is bounded within rounding while the score boundary varies. Neither method establishes actual staffing requirements. Capacity scenarios can leave positive cases unreviewed and do not change the models' underlying risk scores.

Snapshots within a student/module are correlated. Later checkpoint cohorts differ because completed modules leave. Differences across days are descriptive, not causal effects of waiting or intervention. No scenario is selected as a replacement policy.

## Files and reproduction

Supporting CSVs: workload_validation_predictions (original scores/flags), workload_validation_snapshot_reference (overall and checkpoint metrics), workload_validation_first_warning_summary, workload_validation_first_warnings (module audit), workload_validation_capacity (18 scenarios), and workload_validation_rankings (deterministic selection audit).

Code: `src/workload_review.py`. Run `.\\.venv\\Scripts\\python.exe -m src.workload_review` once; the command refuses to overwrite an existing review. `workload_review_audit.json` verifies source datasets, pipelines, frozen metadata, and original result files are unchanged; only this explicit addendum is appended to model_evaluation.md. Its original bytes are also preserved separately.
'''
    (reports / 'workload_review.md').write_text(report, encoding='utf-8')
    (reports / 'model_evaluation_before_workload_review.md').write_bytes(original_report)
    evaluation.write_bytes(original_report + addendum.encode('utf-8'))
    preserved = {str(p.relative_to(ROOT)): digest(p) == previous
                 for p, previous in originals.items() if p != evaluation}
    if not all(preserved.values()) or not evaluation.read_bytes().startswith(original_report):
        raise RuntimeError('Original artifact changed')
    audit = dict(analysis_split='validation', test_data_evaluated=False, retrained=False,
                 frozen_selection_changed=False, original_artifacts_unchanged=preserved,
                 original_artifact_hashes={str(p.relative_to(ROOT)): h for p, h in originals.items()},
                 original_report_sha256=hashlib.sha256(original_report).hexdigest(),
                 report_original_body_preserved=True,
                 source_validation_sha256=digest(validation_path),
                 tie_breaker='probability descending, student_id ascending, module_id numeric ascending')
    (reports / 'workload_review_audit.json').write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')
    print(comparison)
    print(first_warning)
    print(scenarios.to_string(index=False))


if __name__ == '__main__':
    main()
