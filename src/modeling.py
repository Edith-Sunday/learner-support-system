"""Leakage-controlled model training and evaluation of SIMULATED learner data.

This code never generates or changes source datasets. Validation decisions are
written to disk before test prediction/evaluation. No real-world accuracy claim.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import distributions
import json
from pathlib import Path
import platform
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.simulate import FEATURES, ROOT

TARGET = 'missed_deadline'
KEY = ['student_id', 'module_id']
AUDIT = KEY + ['unlock_time', 'deadline', 'snapshot_time', 'snapshot_day', 'split', 'is_simulated']
MODEL_NAMES = ('logistic_regression', 'gradient_boosting')


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def dataset_hashes(data):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(data.iterdir()) if p.is_file()}


def feature_order(data):
    features = json.loads((data / 'model_features.json').read_text())
    if (not isinstance(features, list) or len(features) != len(set(features))
            or set(features) != set(FEATURES)):
        raise ValueError('Feature allowlist must contain exactly the 15 agreed predictors, once each')
    return features


def predictors(frame, features):
    if len(features) != len(set(features)) or set(features) != set(FEATURES):
        raise ValueError('Forbidden or missing predictor in allowlist')
    missing = set(features) - set(frame.columns)
    if missing:
        raise ValueError(f'Missing predictors: {missing}')
    result = frame.loc[:, features].apply(pd.to_numeric, errors='raise')
    if np.isinf(result.to_numpy(dtype=float)).any():
        raise ValueError('Infinite predictor values')
    return result


def verify_data(frames, assignment, outcomes, features):
    """Validate all exports before training; test labels never inform model choice."""
    if assignment.student_id.duplicated().any():
        raise ValueError('Duplicate student split assignment')
    if assignment.split.value_counts().to_dict() != {'train': 420, 'validation': 90, 'test': 90}:
        raise ValueError('Expected the unchanged 420/90/90 student split')
    member = assignment.set_index('student_id').split
    if outcomes.duplicated(KEY).any():
        raise ValueError('Duplicate module outcomes')
    if not outcomes.student_id.map(member).eq(outcomes.split).all():
        raise ValueError('Outcome student split mismatch')
    student_sets = []
    allowed_missing = {'days_since_login', 'quiz_score_trend', 'session_length', 'current_quiz_score'}
    for split, frame in frames.items():
        if frame.empty or not frame.split.eq(split).all():
            raise ValueError(f'Invalid/empty split {split}')
        if not frame.student_id.map(member).eq(split).all():
            raise ValueError('Student split separation violated')
        ids = set(frame.student_id)
        if any(ids & previous for previous in student_sets):
            raise ValueError('Student overlap between splits')
        student_sets.append(ids)
        x = predictors(frame, features)
        if x.drop(columns=list(allowed_missing)).isna().any().any():
            raise ValueError('Missing required count/indicator predictor')
        if frame[TARGET].isna().any() or not frame[TARGET].isin([0, 1]).all():
            raise ValueError('Target must be known binary 0/1')
        if not frame.is_simulated.eq(1).all() or not frame.snapshot_day.isin([3, 7, 10]).all():
            raise ValueError('Expected simulated day-3/7/10 snapshots')
        if frame.duplicated(KEY + ['snapshot_day']).any():
            raise ValueError('Duplicate snapshot key')
        for col in ('no_login', 'practice_submitted', 'quiz_passed', 'offline_participation'):
            if not x[col].isin([0, 1]).all():
                raise ValueError(f'Invalid indicator {col}')
        if not x.activities_completed.eq(x.practice_submitted + x.quiz_passed).all():
            raise ValueError('Inconsistent activities completed')
        if not x.activities_completed.between(0, 1).all():
            raise ValueError('Known completed module in prediction cohort')
        if not x.no_login.eq(x.days_since_login.isna().astype(int)).all():
            raise ValueError('Login missingness indicator inconsistent')
        if not x.current_quiz_score.isna().eq(x.quiz_attempt_count.eq(0)).all():
            raise ValueError('Quiz count/current score inconsistent')
        if not x.quiz_score_trend.isna().eq(x.quiz_attempt_count.lt(2)).all():
            raise ValueError('Quiz trend missingness inconsistent')
        if not x.current_quiz_score.dropna().isin(range(0, 101, 10)).all():
            raise ValueError('Invalid quiz score')
        if not x.quiz_score_trend.dropna().isin(range(-100, 101, 10)).all():
            raise ValueError('Invalid quiz trend')
        counts = ['past_late_submissions', 'failed_or_dropped_sessions', 'quiz_attempt_count',
                  'previous_modules_completed_late']
        if not ((x[counts] >= 0) & (x[counts] % 1 == 0)).all().all():
            raise ValueError('Invalid count predictor')
        if (x[['days_since_login', 'session_length', 'time_on_task']] < 0).any().any():
            raise ValueError('Negative elapsed/active time')
        unlock = pd.to_datetime(frame.unlock_time, utc=True)
        deadline = pd.to_datetime(frame.deadline, utc=True)
        snapshot = pd.to_datetime(frame.snapshot_time, utc=True)
        if not (deadline - unlock).eq(pd.Timedelta(days=14)).all():
            raise ValueError('Deadline clock mismatch')
        if not (snapshot - unlock).eq(pd.to_timedelta(frame.snapshot_day, unit='D')).all():
            raise ValueError('Snapshot clock mismatch')
        merged = frame.merge(outcomes[KEY + [TARGET, 'deadline']], on=KEY,
                             suffixes=('', '_outcome'), how='left', validate='many_to_one')
        if not merged[TARGET].eq(merged[TARGET + '_outcome']).all():
            raise ValueError('Snapshot target differs from module outcome')
        if not merged.deadline.eq(merged.deadline_outcome).all():
            raise ValueError('Snapshot deadline differs from module outcome')
    if set(frames['train'][TARGET]) != {0, 1}:
        raise ValueError('Training requires both target classes')


def build_pipeline(name):
    imputer = SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True)
    if name == 'logistic_regression':
        return Pipeline([('imputer', imputer), ('scaler', StandardScaler()),
                         ('classifier', LogisticRegression(C=1.0, solver='lbfgs',
                                                           max_iter=3000, random_state=42))])
    if name == 'gradient_boosting':
        return Pipeline([('imputer', imputer),
                         ('classifier', GradientBoostingClassifier(
                             n_estimators=100, learning_rate=0.05, max_depth=2,
                             min_samples_leaf=20, subsample=1.0, random_state=42))])
    raise ValueError(f'Unknown model: {name}')


def snapshot_metrics(y, probability, threshold):
    y = np.asarray(y, dtype=int)
    probability = np.asarray(probability, dtype=float)
    if len(y) != len(probability) or not np.isin(y, [0, 1]).all():
        raise ValueError('Invalid labels/probabilities')
    if not np.isfinite(probability).all() or ((probability < 0) | (probability > 1)).any():
        raise ValueError('Probabilities must be finite and between 0 and 1')
    flag = probability >= threshold
    tp = int(((y == 1) & flag).sum())
    fp = int(((y == 0) & flag).sum())
    tn = int(((y == 0) & ~flag).sum())
    fn = int(((y == 1) & ~flag).sum())
    def ratio(a, b):
        return a / b if b else np.nan
    return dict(n_snapshots=len(y), positive_count=int(y.sum()), prevalence=ratio(int(y.sum()), len(y)),
                precision=ratio(tp, tp + fp), recall=ratio(tp, tp + fn),
                f1=ratio(2 * tp, 2 * tp + fp + fn), f2=ratio(5 * tp, 5 * tp + fp + 4 * fn),
                average_precision=float(average_precision_score(y, probability)) if y.sum() else np.nan,
                tp=tp, fp=fp, tn=tn, fn=fn, flag_count=int(flag.sum()),
                flagged_percent=100 * ratio(int(flag.sum()), len(y)))


def threshold_table(y, probability):
    return pd.DataFrame([dict(threshold=i / 100, **snapshot_metrics(y, probability, i / 100))
                         for i in range(5, 96)])


def best_threshold(table):
    candidates = table.copy()
    for field in ('f2', 'precision'):
        scores = candidates[field].fillna(-np.inf)
        candidates = candidates[np.isclose(scores, scores.max(), rtol=0, atol=1e-12)]
    return candidates.sort_values('threshold', ascending=False).iloc[0].to_dict()


def choose_model(choices):
    candidates = list(choices)
    for field in ('f2', 'precision'):
        best = max(choices[name][field] if pd.notna(choices[name][field]) else -np.inf for name in candidates)
        candidates = [name for name in candidates if np.isclose(
            choices[name][field] if pd.notna(choices[name][field]) else -np.inf,
            best, rtol=0, atol=1e-12)]
    return 'logistic_regression' if 'logistic_regression' in candidates else candidates[0]


def fit_and_select(train, validation, features):
    """Intentionally accepts no test data. Fits preprocessing on training only."""
    x_train, x_validation = predictors(train, features), predictors(validation, features)
    models, tables, choices, messages = {}, {}, {}, {}
    for name in MODEL_NAMES:
        pipeline = build_pipeline(name)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            pipeline.fit(x_train, train[TARGET])
        messages[name] = [f'{type(w.message).__name__}: {w.message}' for w in caught]
        if any(issubclass(w.category, ConvergenceWarning) for w in caught):
            raise RuntimeError(f'{name} did not converge: {messages[name]}')
        probabilities = pipeline.predict_proba(x_validation)[:, 1]
        tables[name] = threshold_table(validation[TARGET], probabilities)
        choices[name] = best_threshold(tables[name])
        models[name] = pipeline
    return models, tables, choices, choose_model(choices), messages


def grouped_metrics(frame, probability, name, split, threshold, threshold_type):
    rows = []
    for day in ('overall', 3, 7, 10):
        mask = np.ones(len(frame), dtype=bool) if day == 'overall' else frame.snapshot_day.eq(day).to_numpy()
        rows.append(dict(model=name, split=split, cohort=str(day), threshold=threshold,
                         threshold_type=threshold_type,
                         **snapshot_metrics(frame.loc[mask, TARGET], probability[mask], threshold)))
    return rows


def early_warnings(predictions, outcomes):
    """Count each module once; only detected positives contribute lead times."""
    if predictions.groupby(KEY)[TARGET].nunique().gt(1).any():
        raise ValueError('Conflicting targets within a module')
    modules = predictions.drop_duplicates(KEY)[KEY + [TARGET]].copy()
    flagged = predictions[predictions.flag.eq(1)].copy()
    flagged['snapshot_time'] = pd.to_datetime(flagged.snapshot_time, utc=True)
    flagged['deadline'] = pd.to_datetime(flagged.deadline, utc=True)
    flagged = flagged[flagged.snapshot_time < flagged.deadline]
    first = flagged.sort_values('snapshot_time').drop_duplicates(KEY)
    first = first[KEY + ['snapshot_time', 'deadline']].rename(columns={'snapshot_time': 'first_warning_time'})
    first['lead_days'] = (first.deadline - first.first_warning_time).dt.total_seconds() / 86400
    modules = modules.merge(first[KEY + ['first_warning_time', 'lead_days']], on=KEY, how='left', validate='one_to_one')
    modules['warned'] = modules.first_warning_time.notna().astype(int)
    missed = modules[modules[TARGET].eq(1)]
    detected = missed[missed.warned.eq(1)]
    known_missed = outcomes[outcomes[TARGET].eq(1)][KEY]
    no_checks = known_missed.merge(modules[KEY], on=KEY, how='left', indicator=True)
    no_checks = no_checks[no_checks['_merge'].eq('left_only')][KEY]
    summary = dict(
        eligible_modules=len(modules), eligible_missed_modules=len(missed),
        warned_missed_modules=len(detected),
        warned_missed_percent=100 * len(detected) / len(missed) if len(missed) else np.nan,
        missed_by_all_checks=len(missed) - len(detected),
        median_lead_days=detected.lead_days.median(), mean_lead_days=detected.lead_days.mean(),
        first_detected_11_days=int(np.isclose(detected.lead_days, 11).sum()),
        first_detected_7_days=int(np.isclose(detected.lead_days, 7).sum()),
        first_detected_4_days=int(np.isclose(detected.lead_days, 4).sum()),
        first_detected_other_lead=int((~np.isclose(detected.lead_days, 11)
                                       & ~np.isclose(detected.lead_days, 7)
                                       & ~np.isclose(detected.lead_days, 4)).sum()),
        on_time_modules_false_warning=int((modules[TARGET].eq(0) & modules.warned.eq(1)).sum()),
        unique_students_warned=int(modules.loc[modules.warned.eq(1), 'student_id'].nunique()),
        known_missed_modules_no_snapshots=len(no_checks))
    return summary, modules, no_checks


def markdown_table(frame):
    def cell(value):
        if pd.isna(value):
            return 'undefined'
        return f'{value:.4f}' if isinstance(value, (float, np.floating)) else str(value)
    return '\n'.join(['| ' + ' | '.join(frame.columns) + ' |',
                      '| ' + ' | '.join(['---'] * len(frame.columns)) + ' |'] +
                     ['| ' + ' | '.join(cell(v) for v in row) + ' |' for row in frame.itertuples(index=False, name=None)])


def write_report(report_dir, manifest, metrics, early):
    test_log = report_dir / 'model_test_results.txt'
    test_result = test_log.read_text(encoding='utf-8').strip() if test_log.exists() else 'Full test run pending; see model_test_results.txt when available.'
    selected = manifest['candidate_model']
    validation = metrics[(metrics.split == 'validation') & (metrics.cohort == 'overall')]
    test = metrics[(metrics.split == 'test') & (metrics.threshold_type == 'validation_f2')]
    baseline = metrics[(metrics.split == 'test') & (metrics.threshold_type == 'fixed_0.5') & (metrics.cohort == 'overall')]
    cols = ['model', 'cohort', 'threshold', 'n_snapshots', 'prevalence', 'precision', 'recall', 'f1', 'f2', 'average_precision']
    counts = ['model', 'cohort', 'tp', 'fp', 'tn', 'fn', 'flag_count', 'flagged_percent']
    comparison = test[test.cohort == 'overall'].set_index('model')
    candidate_result = comparison.loc[selected]
    candidate_warning = early.set_index('model').loc[selected]
    winner = comparison.f2.idxmax()
    headline = (f'{winner} has the higher observed overall test F2 at its frozen threshold. '
                'This descriptive comparison does not establish superiority outside this simulation '
                'and does not change the validation-selected candidate.') if comparison.f2.nunique() > 1 else 'The observed overall test F2 values are tied.'
    report = f'''# Model evaluation on simulated learner data

**These results measure performance on an artificial simulation. They are not proven real-world predictive accuracy, improved learner outcomes, or intervention effectiveness.**

The validation-selected candidate flags {candidate_result.flagged_percent:.1f}% of test snapshots. Its recall is {candidate_result.recall:.1%}, but precision is only {candidate_result.precision:.1%}: {int(candidate_result.fp)} of its {int(candidate_result.flag_count)} flags are false positives. The low threshold provides little prioritisation because almost every snapshot is flagged.

At module level it detects {int(candidate_warning.warned_missed_modules)} of {int(candidate_warning.eligible_missed_modules)} eligible missed deadlines, but also warns on {int(candidate_warning.on_time_modules_false_warning)} on-time modules and reaches {int(candidate_warning.unique_students_warned)} unique students. High module detection therefore should not be interpreted as efficient support targeting or intervention success. Thresholds remain frozen as specified; these findings have not been used to tune them.

## Frozen selection

Candidate: **{selected}**, chosen using validation F2, then precision, then logistic regression for a model tie. Each model's threshold maximises validation F2 over 0.05–0.95 in steps of 0.01; threshold ties prefer precision then the higher threshold. Numeric ties use absolute tolerance 1e-12. F2 places four times as much weight on false negatives as false positives in its count-based formula. This is a prototype choice, not an established optimal staff policy or a measured staffing budget.

`models/selection.json` was saved at {manifest['selection_saved_at_utc']} before test probabilities or test metrics were calculated. The same fitted pipelines and thresholds were then reloaded for evaluation. No refit on validation, test, or combined datasets occurred. Test findings did not change the selection.

## Models and data

One pooled model per algorithm uses all 15 allowlisted predictors, including snapshot_day. Student IDs, module IDs, timestamps, split labels, outcomes, and hidden traits are excluded. The corrected source data and 420/90/90 student assignments were preserved; hashes are saved with the models. No simulation regeneration or tuning occurred during model training.

Both pipelines use training-only median imputation with missingness indicators and preserve entirely empty features. Indicators are learned for columns missing in training. Logistic regression adds standard scaling and uses C=1, lbfgs, max_iter=3000, random_state=42. Gradient boosting uses 100 trees, learning_rate=0.05, max_depth=2, min_samples_leaf=20, subsample=1, random_state=42. Shallow trees and a minimum leaf size restrict complexity. No hyperparameter search or class rebalancing was used. Every snapshot has equal training weight.

Training warnings: {json.dumps(manifest['training_warnings'])}. A convergence warning aborts the run instead of silently treating the fit as successful.

## Validation performance

{markdown_table(validation[['model', 'threshold_type'] + cols[1:]])}

The complete 91-row threshold table for each model includes precision, recall, F2 and flag counts. Average precision summarises probability ranking across thresholds and is not the precision of one chosen threshold.

## Test performance at frozen validation thresholds

{markdown_table(test[cols])}

{markdown_table(test[counts])}

## Test reference at threshold 0.5

{markdown_table(baseline[cols])}

Full day-specific metrics at both threshold settings are in `snapshot_metrics.csv`. All fractions are 0–1 except flagged_percent and warned_missed_percent, which are 0–100.

{headline}

Precision is the fraction of flags that actually miss the deadline; recall is the fraction of missed-deadline snapshots flagged. False positives represent warnings on on-time modules, not evidence of a barrier. Flag volume shows the simulated review burden and should be considered alongside recall.

## First warning per student-module on test

{markdown_table(early.set_index('model').T.rename_axis('measure').reset_index())}

Only the first positive prediction across available days 3, 7, and 10 counts. Warning lead time is actual deadline minus first-warning timestamp. Mean and median include detected missed-deadline modules only; undetected modules retain blank lead times, never zero. Counts at 11, 7, or 4 days are mutually exclusive first detections. On-time modules with any warning count once; unique warned students are counted across modules. `first_warnings_<model>.csv` retains every eligible module, including unflagged modules with blank first-warning time/lead. Known missed modules with no eligible labelled snapshots are reported separately in `missed_modules_without_snapshots.csv` and excluded from the eligible-module detection denominator.

## Undefined metrics, dependence, and limitations

CSV blank metrics and the word `undefined` mean a missing denominator: precision when no flags, recall when no positives, F1/F2 when there are neither positives nor flags, average precision when there are no positives, and lead-time mean/median when no missed modules are detected. A zero score with a nonzero denominator is a meaningful zero. Counts remain zero when no records qualify.

Snapshots from the same student or module are correlated. Student separation prevents cross-split learner leakage but does not make individual snapshots independent. Later-day cohorts differ as completed modules leave; day-specific metrics are not a controlled comparison of warning timing. No independence-based confidence intervals or significance claims are made.

The synthetic behavioural rules may make patterns easier or different from real learning. Confirmed barriers are not inferred from scores or session lengths. Outcomes with deadlines beyond observation remain excluded under the existing conservative policy, including already-completed modules excluded solely by that policy. Results do not establish calibration, fairness, intervention benefit, or deployment suitability. No dashboard or messaging was implemented.

## Reproduction and tests

Latest full test output:

```text
{test_result}
```

Run `.\\.venv\\Scripts\\python.exe -m src.modeling` for a new run; existing frozen artifacts are protected against overwrite. Use `--model-dir models/review_run --report-dir reports/review_run` for a separate rerun on unchanged data. Use `--evaluate-only` to evaluate the already-frozen models; source hashes must still match. Run `.\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider` for simulation and model tests. Final test output is saved in `reports/model_test_results.txt`.

Execution note: the initial Windows sandbox blocked a SciPy extension and later prevented pytest temporary-directory creation. Approved outside-sandbox execution completed fitting and all tests without changing Windows security settings. The dependency check found no broken requirements.
'''
    (report_dir / 'model_evaluation.md').write_text(report, encoding='utf-8')


def run(data, model_dir, report_dir, evaluate_only=False):
    before = dataset_hashes(data)
    features = feature_order(data)
    frames = {s: pd.read_csv(data / f'labelled_{s}.csv', low_memory=False) for s in ('train', 'validation', 'test')}
    assignment = pd.read_csv(data / 'student_splits.csv')
    outcomes = pd.read_csv(data / 'module_outcomes.csv')
    verify_data(frames, assignment, outcomes, features)
    model_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = model_dir / 'selection.json'
    if not evaluate_only:
        if any(model_dir.iterdir()):
            raise FileExistsError('Model directory is not empty; use a fresh --model-dir to preserve frozen decisions')
        models, tables, choices, candidate, messages = fit_and_select(frames['train'], frames['validation'], features)
        for name, pipeline in models.items():
            joblib.dump(pipeline, model_dir / f'{name}.joblib')
            tables[name].to_csv(report_dir / f'validation_thresholds_{name}.csv', index=False)
        manifest = dict(is_simulated=True, selection_saved_at_utc=datetime.now(timezone.utc).isoformat(),
                        candidate_model=candidate, features=features, dataset_hashes=before,
                        thresholds={name: float(choices[name]['threshold']) for name in MODEL_NAMES},
                        validation_choices={name: {k: None if pd.isna(v) else v for k, v in choice.items()}
                                            for name, choice in choices.items()},
                        settings={name: pipeline.named_steps['classifier'].get_params() for name, pipeline in models.items()},
                        preprocessing=dict(imputation='training median', add_indicator=True, keep_empty_features=True,
                                           scaling='training-only StandardScaler for logistic regression only'),
                        selection_rule='validation F2, precision, then higher threshold; model tie prefers logistic regression; atol=1e-12',
                        training_warnings=messages, python_version=platform.python_version(),
                        dependency_versions={d.metadata['Name']: d.version for d in distributions()},
                        pipeline_hashes={name: hashlib.sha256((model_dir / f'{name}.joblib').read_bytes()).hexdigest() for name in MODEL_NAMES})
        save_json(model_dir / 'feature_order.json', features)
        # This durable freeze precedes any test prediction or performance calculation.
        save_json(manifest_path, manifest)
    manifest = json.loads(manifest_path.read_text())
    frozen_bytes = manifest_path.read_bytes()
    if manifest['dataset_hashes'] != before or manifest['features'] != features:
        raise ValueError('Data/features differ from frozen training run')
    metric_rows, early_rows = [], []
    for name in MODEL_NAMES:
        path = model_dir / f'{name}.joblib'
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest['pipeline_hashes'][name]:
            raise ValueError('Saved pipeline differs from frozen manifest')
        pipeline = joblib.load(path)
        threshold = manifest['thresholds'][name]
        for split in ('validation', 'test'):
            frame = frames[split]
            probability = pipeline.predict_proba(predictors(frame, features))[:, 1]
            for threshold_type, value in [('fixed_0.5', 0.5), ('validation_f2', threshold)]:
                metric_rows.extend(grouped_metrics(frame, probability, name, split, value, threshold_type))
            if split == 'test':
                prediction = frame[AUDIT + [TARGET]].copy()
                prediction['probability'] = probability
                prediction['flag'] = (probability >= threshold).astype(int)
                prediction['flag_at_0_5'] = (probability >= 0.5).astype(int)
                prediction['threshold'] = threshold
                prediction.to_csv(report_dir / f'test_predictions_{name}.csv', index=False)
                summary, first, no_checks = early_warnings(prediction, outcomes[outcomes.split.eq('test')])
                early_rows.append(dict(model=name, **summary))
                first.to_csv(report_dir / f'first_warnings_{name}.csv', index=False)
                no_checks.to_csv(report_dir / 'missed_modules_without_snapshots.csv', index=False)
    metrics = pd.DataFrame(metric_rows)
    early = pd.DataFrame(early_rows)
    metrics.to_csv(report_dir / 'snapshot_metrics.csv', index=False)
    early.to_csv(report_dir / 'module_warning_summary.csv', index=False)
    if dataset_hashes(data) != before or manifest_path.read_bytes() != frozen_bytes:
        raise RuntimeError('Source data or frozen decisions changed during evaluation')
    save_json(report_dir / 'evaluation_audit.json', dict(
        selection_sha256=hashlib.sha256(frozen_bytes).hexdigest(),
        evaluated_at_utc=datetime.now(timezone.utc).isoformat(),
        source_hashes_unchanged=True, decisions_unchanged=True))
    write_report(report_dir, manifest, metrics, early)
    print(f'Frozen validation candidate: {manifest["candidate_model"]}')
    print(metrics[(metrics.split == 'test') & (metrics.threshold_type == 'validation_f2') & (metrics.cohort == 'overall')].to_string(index=False))
    print(early.to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--model-dir', type=Path, default=ROOT / 'models')
    parser.add_argument('--report-dir', type=Path, default=ROOT / 'reports')
    parser.add_argument('--evaluate-only', action='store_true')
    args = parser.parse_args()
    run(args.data_dir, args.model_dir, args.report_dir, args.evaluate_only)


if __name__ == '__main__':
    main()
