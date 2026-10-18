"""Model boundaries, selection rules, persistence, and warning counting."""
import hashlib
import inspect
import json

import joblib
import numpy as np
import pandas as pd
import pytest

from src.modeling import (MODEL_NAMES, TARGET, best_threshold, build_pipeline,
                          choose_model, early_warnings, feature_order, fit_and_select,
                          predictors, snapshot_metrics, threshold_table, verify_data)
from src.simulate import FEATURES, ROOT


@pytest.fixture(scope='module')
def inputs():
    frames = {s: pd.read_csv(ROOT / 'data' / f'labelled_{s}.csv')
              for s in ('train', 'validation', 'test')}
    assignment = pd.read_csv(ROOT / 'data' / 'student_splits.csv')
    outcomes = pd.read_csv(ROOT / 'data' / 'module_outcomes.csv')
    return frames, assignment, outcomes


def test_allowlist_excludes_injected_audit_and_hidden_columns(inputs, tmp_path):
    frame = inputs[0]['train'].copy()
    frame['latent_skill'] = 100
    frame['future_completion_time'] = 'future'
    x = predictors(frame, FEATURES)
    assert list(x.columns) == FEATURES
    assert not {'student_id', TARGET, 'split', 'latent_skill', 'future_completion_time'} & set(x.columns)
    for bad in (FEATURES + [TARGET], FEATURES[:-1], FEATURES + [FEATURES[0]]):
        with pytest.raises(ValueError):
            predictors(frame, bad)
        (tmp_path / 'model_features.json').write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            feature_order(tmp_path)


def test_student_separation_and_invalid_targets(inputs):
    frames, assignment, outcomes = inputs
    verify_data(frames, assignment, outcomes, FEATURES)
    corrupted = {s: f.copy() for s, f in frames.items()}
    corrupted['test'].loc[0, 'student_id'] = frames['train'].student_id.iloc[0]
    with pytest.raises(ValueError, match='split'):
        verify_data(corrupted, assignment, outcomes, FEATURES)
    for value in (np.nan, 2):
        corrupted = {s: f.copy() for s, f in frames.items()}
        corrupted['train'].loc[0, TARGET] = value
        with pytest.raises(ValueError, match='Target'):
            verify_data(corrupted, assignment, outcomes, FEATURES)


@pytest.mark.parametrize('name', MODEL_NAMES)
def test_training_only_preprocessing_and_reload(name, inputs, tmp_path):
    train = inputs[0]['train'].iloc[:300]
    x = predictors(train, FEATURES)
    pipeline = build_pipeline(name).fit(x, train[TARGET])
    imputer = pipeline.named_steps['imputer']
    expected = x.median().fillna(0).to_numpy()
    np.testing.assert_allclose(imputer.statistics_, expected)
    before = imputer.statistics_.copy()
    if name == 'logistic_regression':
        scaler = pipeline.named_steps['scaler']
        np.testing.assert_allclose(scaler.mean_, imputer.transform(x).mean(axis=0))
        assert scaler.n_samples_seen_ == len(train)
        scaler_before = scaler.mean_.copy()
    heldout = predictors(inputs[0]['validation'].iloc[:30], FEATURES).fillna(99999) + 99999
    probability = pipeline.predict_proba(heldout)
    np.testing.assert_array_equal(imputer.statistics_, before)
    if name == 'logistic_regression':
        np.testing.assert_array_equal(scaler.mean_, scaler_before)
    path = tmp_path / 'pipeline.joblib'
    joblib.dump(pipeline, path)
    np.testing.assert_allclose(joblib.load(path).predict_proba(heldout), probability, rtol=0, atol=1e-14)


def test_threshold_and_model_ties_and_grid():
    grid = threshold_table([0, 1, 1], [.1, .6, .9])
    np.testing.assert_allclose(grid.threshold, np.arange(5, 96) / 100)
    assert len(grid) == 91
    # Identical predictions between .11 and .60; select .60, not first encountered.
    assert best_threshold(grid)['threshold'] == .6
    choices = pd.DataFrame([
        dict(threshold=.4, f2=.8, precision=.5),
        dict(threshold=.3, f2=.8, precision=.6),
        dict(threshold=.5, f2=.8, precision=.6)])
    assert best_threshold(choices)['threshold'] == .5
    models = {name: dict(f2=.8, precision=.6) for name in MODEL_NAMES}
    assert choose_model(models) == 'logistic_regression'
    models['gradient_boosting']['precision'] = .7
    assert choose_model(models) == 'gradient_boosting'


def test_selection_has_no_test_input_and_test_labels_cannot_change_decisions(inputs):
    assert list(inspect.signature(fit_and_select).parameters) == ['train', 'validation', 'features']
    models, tables, choices, selected, _ = fit_and_select(
        inputs[0]['train'].iloc[:300], inputs[0]['validation'].iloc[:100], FEATURES)
    frozen = json.dumps(dict(candidate=selected, thresholds={m: c['threshold'] for m, c in choices.items()}), sort_keys=True)
    test = inputs[0]['test'].iloc[:50]
    # Both possible test label vectors produce evaluations without modifying selection.
    for name, pipeline in models.items():
        probability = pipeline.predict_proba(predictors(test, FEATURES))[:, 1]
        for labels in (test[TARGET], 1 - test[TARGET]):
            snapshot_metrics(labels, probability, choices[name]['threshold'])
        assert best_threshold(tables[name])['threshold'] == choices[name]['threshold']
    assert frozen == json.dumps(dict(candidate=choose_model(choices), thresholds={m: c['threshold'] for m, c in choices.items()}), sort_keys=True)


def test_undefined_metrics_are_not_zero():
    no_flags = snapshot_metrics([1, 0], [.1, .1], .5)
    assert np.isnan(no_flags['precision'])
    assert no_flags['recall'] == no_flags['f1'] == no_flags['f2'] == 0
    no_positives = snapshot_metrics([0, 0], [.7, .1], .5)
    assert no_positives['precision'] == no_positives['f2'] == 0
    assert np.isnan(no_positives['recall']) and np.isnan(no_positives['average_precision'])
    empty = snapshot_metrics([], [], .5)
    assert empty['n_snapshots'] == empty['flag_count'] == 0
    assert np.isnan(empty['f2']) and np.isnan(empty['flagged_percent'])


def test_first_warning_deduplication_and_actual_lead_times():
    unlock = pd.Timestamp('2026-01-07T12:00:00Z')
    rows = []
    # One student, several modules: repeated positives count once per module.
    specifications = [(1, 1, [3, 7, 10]), (2, 1, [7, 10]),
                      (3, 1, []), (4, 0, [10]), (5, 1, [10])]
    for module, target, flagged_days in specifications:
        for day in (3, 7, 10):
            rows.append(dict(student_id='S1', module_id=module, missed_deadline=target,
                             snapshot_time=unlock + pd.Timedelta(days=day),
                             deadline=unlock + pd.Timedelta(days=14), flag=int(day in flagged_days)))
    outcomes = pd.DataFrame([dict(student_id='S1', module_id=m, missed_deadline=t)
                             for m, t, _ in specifications] +
                            [dict(student_id='S2', module_id=1, missed_deadline=1)])
    summary, modules, no_checks = early_warnings(pd.DataFrame(rows).sample(frac=1, random_state=42), outcomes)
    assert summary['eligible_missed_modules'] == 4
    assert summary['warned_missed_modules'] == 3
    assert summary['warned_missed_percent'] == 75
    assert summary['missed_by_all_checks'] == 1
    assert summary['mean_lead_days'] == pytest.approx(22 / 3)
    assert summary['median_lead_days'] == 7
    assert [summary[f'first_detected_{d}_days'] for d in (11, 7, 4)] == [1, 1, 1]
    assert summary['on_time_modules_false_warning'] == 1
    assert summary['unique_students_warned'] == 1
    assert summary['known_missed_modules_no_snapshots'] == 1 and len(no_checks) == 1
    assert modules.loc[modules.module_id.eq(3), 'lead_days'].isna().all()
    assert len(modules) == 5
    # Verify actual timestamps, rather than a hardcoded snapshot-day lookup.
    shifted = pd.DataFrame(rows)
    shifted['snapshot_time'] = shifted.snapshot_time + pd.Timedelta(hours=12)
    shifted_summary, _, _ = early_warnings(shifted, outcomes)
    assert shifted_summary['mean_lead_days'] == pytest.approx(22 / 3 - .5)
    assert shifted_summary['first_detected_other_lead'] == 3
    shifted['flag'] = 0
    empty_summary, empty_modules, _ = early_warnings(shifted, outcomes)
    assert empty_summary['warned_missed_modules'] == 0
    assert np.isnan(empty_summary['mean_lead_days']) and np.isnan(empty_summary['median_lead_days'])
    assert empty_modules.lead_days.isna().all()


def test_saved_artifacts_predictions_and_freeze_audit(inputs):
    model_dir = ROOT / 'models'
    manifest = json.loads((model_dir / 'selection.json').read_text())
    audit = json.loads((ROOT / 'reports' / 'evaluation_audit.json').read_text())
    assert audit['selection_sha256'] == hashlib.sha256((model_dir / 'selection.json').read_bytes()).hexdigest()
    assert pd.Timestamp(audit['evaluated_at_utc']) >= pd.Timestamp(manifest['selection_saved_at_utc'])
    assert audit['source_hashes_unchanged'] and audit['decisions_unchanged']
    for name in MODEL_NAMES:
        pipeline = joblib.load(model_dir / f'{name}.joblib')
        prediction = pipeline.predict_proba(predictors(inputs[0]['test'], FEATURES))[:, 1]
        saved = pd.read_csv(ROOT / 'reports' / f'test_predictions_{name}.csv')
        np.testing.assert_allclose(saved.probability, prediction, rtol=0, atol=1e-14)
        np.testing.assert_array_equal(saved.flag, prediction >= manifest['thresholds'][name])
        np.testing.assert_allclose(pipeline.named_steps['imputer'].statistics_,
                                   predictors(inputs[0]['train'], FEATURES).median().fillna(0))
