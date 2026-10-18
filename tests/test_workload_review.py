"""Workload-only tests: do not fit models or evaluate test data."""
import json

import numpy as np
import pandas as pd

from src.modeling import snapshot_metrics
from src.simulate import ROOT
from src.workload_review import capacity_scenarios, digest


def test_capacity_ceiling_ties_and_target_independence():
    rows = pd.DataFrame([dict(model='m', snapshot_day=day, student_id=f'S{i:02}',
                              module_id=1, probability=.5, missed_deadline=i % 2)
                         for day in (3, 7, 10) for i in range(11)])
    summary, ranked = capacity_scenarios(rows.sample(frac=1, random_state=42))
    assert summary.reviewed.tolist() == [2, 3, 4] * 3
    for day in (3, 7, 10):
        selected = ranked[(ranked.snapshot_day == day) & ranked.reviewed_10pct.eq(1)]
        assert selected.student_id.tolist() == ['S00', 'S01']
    assert summary.boundary_tied_total.eq(11).all()
    assert summary.lowest_selected_score.eq(.5).all()
    flipped = rows.copy()
    flipped['missed_deadline'] = 1 - flipped.missed_deadline
    _, changed = capacity_scenarios(flipped)
    cols = ['student_id', 'module_id', 'snapshot_day', 'risk_rank', 'reviewed_10pct', 'reviewed_20pct', 'reviewed_30pct']
    pd.testing.assert_frame_equal(ranked[cols].reset_index(drop=True), changed[cols].reset_index(drop=True))


def test_flag_all_reference_arithmetic():
    result = snapshot_metrics([1, 0, 0, 1], np.ones(4), .5)
    assert result['precision'] == .5 and result['recall'] == 1
    assert result['f2'] == 10 / 12
    assert result['flag_count'] == 4 and result['flagged_percent'] == 100


def test_workload_exports_and_preservation():
    reports = ROOT / 'reports'
    audit = json.loads((reports / 'workload_review_audit.json').read_text())
    assert not audit['test_data_evaluated'] and not audit['retrained']
    for filename, before in audit['original_artifact_hashes'].items():
        if filename.replace('\\', '/') == 'reports/model_evaluation.md':
            continue
        artifact=ROOT / filename.replace('\\','/')
        if artifact.suffix=='.txt' and not artifact.exists():
            continue  # Local execution logs are not deployment artifacts.
        assert digest(artifact) == before
    original = (reports / 'model_evaluation_before_workload_review.md').read_bytes()
    assert (reports / 'model_evaluation.md').read_bytes().startswith(original)
    summary = pd.read_csv(reports / 'workload_validation_capacity.csv')
    rankings = pd.read_csv(reports / 'workload_validation_rankings.csv')
    assert len(summary) == 18
    assert rankings.split.eq('validation').all()
    for row in summary.to_dict('records'):
        cohort = rankings[(rankings.model == row['model']) & (rankings.snapshot_day == row['snapshot_day'])]
        reviewed = cohort[cohort[f"reviewed_{row['review_percent']}pct"].eq(1)]
        assert len(reviewed) == row['reviewed'] == (len(cohort) * row['review_percent'] + 99) // 100
        assert reviewed.missed_deadline.sum() == row['tp']
        assert row['tp'] + row['fp'] == row['reviewed']
        assert np.isclose(reviewed.probability.min(), row['lowest_selected_score'])
