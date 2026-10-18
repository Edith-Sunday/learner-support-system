r"""Separate, exploratory Module 1 ranking experiment. Never used by the dashboard.

Run: .venv\Scripts\python.exe -m src.interactive_model
The design is saved before fitting; selection is saved before test evaluation.
"""
from pathlib import Path
import hashlib
import json
import math
import platform
import warnings
from importlib.metadata import version

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.simulate import ROOT, features_at

FEATURES = ['practice_submitted', 'quiz_passed', 'current_quiz_score',
            'quiz_score_trend', 'quiz_attempt_count', 'snapshot_day']
TARGET = 'missed_deadline'
DAYS = (3, 7, 10)
DESIGN = {
    'features': FEATURES,
    'eligibility': 'Original labelled exports only; Module 1; days 3/7/10; fewer than two known completed requirements. Original censoring and student assignments.',
    'budget': 'ceil(0.20 * eligible snapshots) independently per checkpoint; one learner per checkpoint',
    'ties': 'Descending model score then ascending student_id; IDs are administrative tie-breakers, never predictors. Rule: fewer requirements, missing score first, lower latest score, student_id.',
    'selection': 'Highest validation mean recall across days 3/7/10; absolute tolerance 1e-12 ties favour logistic regression. No test-based changes.',
    'random': '1000 independent repeated draws, numpy default_rng(42); uniform permutations within each checkpoint, same ceil review volume. Report mean, SD, 2.5th/97.5th percentiles; descriptive variation, not confidence intervals.',
    'logistic_regression': {'C': 1.0, 'max_iter': 3000, 'random_state': 42},
    'gradient_boosting': {'n_estimators': 80, 'learning_rate': 0.05, 'max_depth': 2, 'min_samples_leaf': 15, 'random_state': 42},
    'preprocessing': 'Training-only median imputation with missing indicators and keep_empty_features; standard scaling for logistic regression only.',
    'exclusions': {
        'activities_completed': 'Exactly practice_submitted + quiz_passed; redundant. Retained for eligibility and progress rule.',
        'offline_participation': 'Not equivalent: original includes any teacher_offline event, including sessions. Interactive records cover practice/quiz only. Excluded rather than silently redefining.',
        'past_late_submissions / previous_modules_completed_late': 'Structural zero for Module 1.',
        'login / interruptions / session length / active time': 'Measurement not equivalent. Existing timer and original full model remain unchanged.'},
    'status': 'Exploratory simulated-data evaluation; test set already inspected in previous work. No numeric interactive integration or backfill.'}


def save(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def predictors(frame):
    """Strict subset selection: additional input columns can never become predictors."""
    x = frame.loc[:, FEATURES].apply(pd.to_numeric, errors='raise')
    if np.isinf(x.to_numpy(float)).any():
        raise ValueError('Infinite feature')
    return x


def eligible(frame, split, assignments, outcomes, end):
    if assignments.student_id.duplicated().any():
        raise ValueError('Duplicate student assignment')
    if not frame.student_id.map(assignments.set_index('student_id').split).eq(split).all() or not frame.split.eq(split).all():
        raise ValueError('Student split violation')
    f = frame.loc[frame.module_id.eq(1) & frame.snapshot_day.isin(DAYS) & frame.activities_completed.lt(2)].copy()
    if f.empty or f.duplicated(['student_id', 'snapshot_day']).any():
        raise ValueError('Empty or duplicate eligible cohort')
    if not f[TARGET].isin([0, 1]).all() or not f.is_simulated.eq(1).all():
        raise ValueError('Invalid target / source')
    if not f.activities_completed.eq(f.practice_submitted+f.quiz_passed).all():
        raise ValueError('Invalid requirement count')
    for col in ('unlock_time', 'deadline', 'snapshot_time'):
        f[col] = pd.to_datetime(f[col], utc=True)
    if not ((f.deadline-f.unlock_time).eq(pd.Timedelta(days=14)) & (f.snapshot_time-f.unlock_time).eq(pd.to_timedelta(f.snapshot_day, unit='D')) & f.deadline.le(end)).all():
        raise ValueError('Timing or censoring violation')
    o = outcomes.loc[outcomes.module_id.eq(1)].set_index('student_id')
    if not f[TARGET].eq(f.student_id.map(o[TARGET])).all():
        raise ValueError('Outcome changed')
    recognized = pd.to_datetime(f.student_id.map(o.completion_known_at), utc=True)
    if (recognized.notna() & recognized.le(f.snapshot_time)).any():
        raise ValueError('Completed module eligible')
    x = predictors(f)
    if not x[['practice_submitted','quiz_passed']].isin([0,1]).all().all():
        raise ValueError('Invalid progress indicator')
    if x.drop(columns=['current_quiz_score','quiz_score_trend']).isna().any().any():
        raise ValueError('Missing required observation')
    if not x.current_quiz_score.isna().eq(x.quiz_attempt_count.eq(0)).all() or not x.quiz_score_trend.isna().eq(x.quiz_attempt_count.lt(2)).all():
        raise ValueError('Missingness semantics violated')
    if not x.current_quiz_score.dropna().isin(range(0,101,10)).all():
        raise ValueError('Invalid quiz percentage')
    return f.sort_values(['snapshot_day','student_id']).reset_index(drop=True)


def verify_event_mapping(frame, events):
    """Reconstruct every eligible snapshot from occurrence AND availability cutoffs."""
    groups = {sid: rows.to_dict('records') for sid, rows in events.groupby('student_id')}
    offline_difference = 0
    for row in frame.to_dict('records'):
        records = groups.get(row['student_id'], [])
        actual = features_at(records, [], 1, row['snapshot_time'], row['snapshot_day'])
        for name in FEATURES+['activities_completed']:
            a, b = actual[name], row[name]
            if not ((pd.isna(a) and pd.isna(b)) or a == b):
                raise ValueError(f'Feature reconstruction differs: {name}')
        submissions = [r for r in records if r['event_type'] in ('practice','quiz')]
        offline_difference += actual['offline_participation'] != features_at(submissions, [], 1, row['snapshot_time'], row['snapshot_day'])['offline_participation']
    return offline_difference


def pipeline(name):
    steps = [SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True)]
    if name == 'logistic_regression':
        steps += [StandardScaler(), LogisticRegression(**DESIGN[name])]
    elif name == 'gradient_boosting':
        steps += [GradientBoostingClassifier(**DESIGN[name])]
    else:
        raise ValueError(name)
    return make_pipeline(*steps)


def rule_scores(f):
    # 102-point separation ensures requirement count dominates every quiz value.
    return (2-f.activities_completed)*102-f.current_quiz_score.fillna(-1)


def select(f, scores):
    result = np.zeros(len(f), dtype=bool)
    for day in DAYS:
        part = f.loc[f.snapshot_day.eq(day)].copy()
        part['rank_score'] = np.asarray(scores)[part.index]
        chosen = part.sort_values(['rank_score','student_id'], ascending=[False,True]).head(math.ceil(len(part)*.2))
        result[chosen.index] = True
    return result


def metrics(f, scores, flags, name):
    records=[]
    for day in (*DAYS, 'pooled'):
        mask=np.ones(len(f),bool) if day=='pooled' else f.snapshot_day.eq(day).to_numpy()
        y=f.loc[mask,TARGET].to_numpy(int); s=np.asarray(scores)[mask]; z=np.asarray(flags)[mask]
        tp=int((y*z).sum()); reviewed=int(z.sum()); positive=int(y.sum())
        selected_scores=s[z]
        cutoff=float(selected_scores.min()) if len(selected_scores) else None
        _,counts=np.unique(s,return_counts=True)
        records.append(dict(method=name,checkpoint=day,eligible=len(y),positives=positive,prevalence=float(y.mean()) if len(y) else None,
            reviewed=reviewed,true_positives=tp,false_warnings=reviewed-tp,precision=tp/reviewed if reviewed else None,
            recall=tp/positive if positive else None,average_precision=float(average_precision_score(y,s)) if positive else None,
            lowest_selected_score=cutoff,unique_scores=len(counts),learners_in_tied_groups=int(counts[counts>1].sum()),
            largest_tie=int(counts.max()) if len(counts) else 0,
            boundary_tie_size=int((s==cutoff).sum()) if cutoff is not None and day!='pooled' else None,
            selected_from_boundary_tie=int(((s==cutoff)&z).sum()) if cutoff is not None and day!='pooled' else None))
    return records


def warnings_summary(f, flags, outcomes, split):
    first=f.loc[flags].sort_values('snapshot_time').drop_duplicates('student_id')
    missed=f.loc[f[TARGET].eq(1),'student_id'].nunique()
    detected=first.loc[first[TARGET].eq(1)]
    lead=(detected.deadline-detected.snapshot_time).dt.total_seconds()/86400
    known=outcomes.loc[outcomes.split.eq(split)&outcomes.module_id.eq(1)&outcomes[TARGET].eq(1)]
    return dict(eligible_modules=f.student_id.nunique(),eligible_missed_modules=missed,
        detected_missed_modules=len(detected),recall=len(detected)/missed if missed else None,
        missed_all_checks=missed-len(detected),mean_lead_days=float(lead.mean()) if len(lead) else None,
        median_lead_days=float(lead.median()) if len(lead) else None,
        first_detected_11_days=int(lead.eq(11).sum()),first_detected_7_days=int(lead.eq(7).sum()),first_detected_4_days=int(lead.eq(4).sum()),
        on_time_modules_warned=int(first[TARGET].eq(0).sum()),unique_students_warned=len(first),
        known_missed_without_snapshots=int((~known.student_id.isin(f.student_id)).sum()))


def choose(rows):
    means={n:float(np.mean([r['recall'] for r in rows if r['method']==n and r['checkpoint'] in DAYS])) for n in ('logistic_regression','gradient_boosting')}
    return ('gradient_boosting' if means['gradient_boosting']>means['logistic_regression']+1e-12 else 'logistic_regression'), means


def evaluate(f, fitted, outcomes, split, destination):
    all_metrics=[]; modules=[]
    audit=f[['student_id','module_id','snapshot_day','snapshot_time','deadline',TARGET]].copy()
    for name in (*fitted, 'progress_rule'):
        scores=fitted[name].predict_proba(predictors(f))[:,1] if name in fitted else rule_scores(f).to_numpy()
        flags=select(f,scores)
        all_metrics.extend(metrics(f,scores,flags,name))
        modules.append(dict(method=name,**warnings_summary(f,flags,outcomes,split)))
        audit[name+'_score']=scores; audit[name+'_review']=flags.astype(int)
    audit.to_csv(destination/f'{split}_predictions.csv',index=False)
    rng=np.random.default_rng(42)
    random_metrics=[]; random_modules=[]
    for draw in range(1000):
        scores=rng.random(len(f))
        flags=select(f,scores)
        random_metrics.extend(dict(draw=draw,**r) for r in metrics(f,scores,flags,'random'))
        random_modules.append(dict(draw=draw,**warnings_summary(f,flags,outcomes,split)))
    pd.DataFrame(all_metrics).to_csv(destination/f'{split}_metrics.csv',index=False)
    pd.DataFrame(modules).to_csv(destination/f'{split}_warnings.csv',index=False)
    pd.DataFrame(random_metrics).to_csv(destination/f'{split}_random_draws.csv',index=False)
    pd.DataFrame(random_modules).to_csv(destination/f'{split}_random_warnings.csv',index=False)
    stats=[]
    for day,g in pd.DataFrame(random_metrics).groupby('checkpoint'):
        for col in ['reviewed','true_positives','false_warnings','precision','recall','average_precision']:
            stats.append(dict(checkpoint=day,metric=col,mean=g[col].mean(),sd=g[col].std(),p025=g[col].quantile(.025),p975=g[col].quantile(.975)))
    pd.DataFrame(stats).to_csv(destination/f'{split}_random_summary.csv',index=False)
    pd.DataFrame(random_modules).drop(columns='draw').agg(['mean','std',lambda x:x.quantile(.025),lambda x:x.quantile(.975)]).to_csv(destination/f'{split}_random_warning_summary.csv')
    return all_metrics,modules,stats


def table(rows, columns):
    def val(x):
        if x is None or (isinstance(x,float) and np.isnan(x)): return 'Undefined'
        return f'{x:.3f}' if isinstance(x,(float,np.floating)) else str(x)
    return '| '+' | '.join(columns)+' |\n| '+' | '.join(['---']*len(columns))+' |\n'+'\n'.join('| '+' | '.join(val(r[c]) for c in columns)+' |' for r in rows)+'\n'


def run():
    output=ROOT/'models'/'interactive_module1'
    output.mkdir(exist_ok=True)
    if (output/'selection.json').exists():
        raise RuntimeError('Refusing to overwrite the frozen experiment; archive separately for an authorised new run.')
    save(output/'design.json',DESIGN)  # Persisted before any fitting or performance computation.
    data=ROOT/'data'
    assignments=pd.read_csv(data/'student_splits.csv')
    outcomes=pd.read_csv(data/'module_outcomes.csv')
    end=pd.Timestamp(json.loads((data/'simulation_metadata.json').read_text())['observation_end'])
    frames={s:eligible(pd.read_csv(data/f'labelled_{s}.csv'),s,assignments,outcomes,end) for s in ('train','validation','test')}
    events=pd.read_csv(data/'events.csv',low_memory=False); events=events.loc[events.module_id.eq(1)].copy()
    for c in ('event_time','recorded_at'): events[c]=pd.to_datetime(events[c],utc=True)
    mismatch={s:verify_event_mapping(f,events) for s,f in frames.items()}
    counts=[dict(split=s,students=f.student_id.nunique(),snapshots=len(f),positive_snapshots=int(f[TARGET].sum()),missed_modules=f.loc[f[TARGET].eq(1),'student_id'].nunique()) for s,f in frames.items()]
    pd.DataFrame(counts).to_csv(output/'cohort_counts.csv',index=False)
    if frames['train'][TARGET].nunique()!=2 or any(frames['validation'].loc[frames['validation'].snapshot_day.eq(d),TARGET].sum()==0 for d in DAYS):
        raise ValueError('Insufficient classes for predeclared comparison; scope will not expand')
    fitted={}; caught=[]; reproducibility={}
    x=predictors(frames['train']); y=frames['train'][TARGET]
    for name in ('logistic_regression','gradient_boosting'):
        with warnings.catch_warnings(record=True) as ws:
            warnings.simplefilter('always')
            model=pipeline(name).fit(x,y)
        caught.extend(str(w.message) for w in ws)
        repeated=pipeline(name).fit(x,y)
        vx=predictors(frames['validation'])
        if not np.array_equal(model.predict_proba(vx),repeated.predict_proba(vx)):
            raise AssertionError('Training is not reproducible')
        joblib.dump(model,output/f'{name}.joblib')
        if not np.array_equal(model.predict_proba(vx),joblib.load(output/f'{name}.joblib').predict_proba(vx)):
            raise AssertionError('Reload prediction changed')
        fitted[name]=model; reproducibility[name]=True
    validation=evaluate(frames['validation'],fitted,outcomes,'validation',output)
    selected,means=choose(validation[0])
    selection=dict(selected=selected,validation_mean_recall=means,criterion=DESIGN['selection'],test_previously_inspected=True,
        frozen_before_this_run_test_evaluation=True,pipeline_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*.joblib')})
    save(output/'selection.json',selection)  # Hard boundary: test performance is computed only below.
    test=evaluate(frames['test'],fitted,outcomes,'test',output)
    metadata=dict(dataset_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in data.iterdir() if p.is_file()},
        feature_order=FEATURES,versions={n:version(n) for n in ('pandas','numpy','scikit-learn','joblib')},python=platform.python_version(),
        warnings=caught,reproducibility=reproducibility,offline_definition_disagreements=mismatch,
        training_unique_values={c:int(x[c].nunique(dropna=False)) for c in FEATURES},
        training_missing_counts=x.isna().sum().to_dict(),design_hash=hashlib.sha256((output/'design.json').read_bytes()).hexdigest())
    save(output/'metadata.json',metadata)
    report=['# Additional Module 1 model: exploratory evaluation\n',
        '**Artificial simulation only: no proven real-world predictive accuracy or improved learner outcomes. The test set was already examined in earlier project work; these are exploratory results, not an untouched-test evaluation. Numeric interactive scoring remains disabled.**\n',
        '## Predeclared design and mappings\n',
        'The machine-readable design was saved before fitting (`models/interactive_module1/design.json`). Selection was written before this run computed test performance. One pooled model per algorithm includes checkpoint day; no search or simulation changes. Training-only median imputation with indicators preserves raw missing quiz scores (no attempt) and trends (fewer than two attempts). Logistic regression uses scaling, C=1, max_iter=3000, seed 42; boosting uses 80 trees, learning rate .05, depth 2, minimum leaf 15, seed 42.\n',
        'Included: practice submitted (any accepted submission, correctness irrelevant); quiz passed (any valid score ≥80%, never undone by a later lower score); latest quiz score (percent); latest minus previous score (percentage points); count of valid attempts; scheduled checkpoint day. Interactive quiz points are multiplied by ten. Both routes use the same `features_at` implementation, occurrence/record-ID order, and BOTH event_time and recorded_at ≤ checkpoint. Online and delayed-offline mapping cases are tested. All eligible historical rows were independently reconstructed from events.\n',
        'Activities completed is the exact sum of the two progress indicators, so is redundant and used only for eligibility/rule. Earlier-module counts are structural zero. Offline participation is excluded: original teacher-offline sessions are not available in interactive records. Observed snapshot disagreements with a submission-only definition: '+str(mismatch)+'. Login, interruptions, session duration and active time are excluded for measurement incompatibility; existing tracking remains intact. Constant counts and missingness are recorded in metadata; no data-dependent feature dropping.\n',
        'Eligible rows are original conservatively labelled, incomplete Module 1 snapshots at days 3/7/10. Completion known by the checkpoint excludes a row. Timeliness still uses completion occurrence, and deadlines beyond the original observation window remain censored. Original student assignments are checked. No other module or synthetic learner was added.\n',table(counts,['split','students','snapshots','positive_snapshots','missed_modules']),
        '## Comparison and frozen selection\n',
        'Each checkpoint reviews ceil(20% × its cohort size). This illustrative review budget is neither agreed staffing capacity nor a daily caseload. Models rank descending probability. The progress rule ranks fewer completed requirements, then missing latest score before observed scores, then lower score. Missing first is a declared conservative review choice, not evidence of low ability. Exact ties use ascending learner ID, with no target information. Identical inputs receive identical model scores; the ID ordering is administrative, not personalised differentiation.\n',
        'Random reference: 1,000 seeded draws at the same review volumes, seed 42, fresh uniform rankings at each checkpoint. Tables report mean, standard deviation and central 95% draw range (not uncertainty intervals for real-world performance).\n',
        f'Selected candidate: **{selected}**. Validation mean recall across checkpoints: {means}. Ties within 1e-12 favour logistic regression. No decision changes after test evaluation.\n',
        '## Results\n']
    for split,result in [('validation',validation),('test',test)]:
        report += [f'### {split.title()}\n',table(result[0],['method','checkpoint','eligible','positives','reviewed','true_positives','false_warnings','precision','recall','average_precision']),
            'Module-level first warning (each learner-module counted once):\n',table(result[1],['method','eligible_missed_modules','detected_missed_modules','missed_all_checks','mean_lead_days','median_lead_days','first_detected_11_days','first_detected_7_days','first_detected_4_days','on_time_modules_warned','unique_students_warned','known_missed_without_snapshots']),
            'Random reference variation:\n',table(result[2],['checkpoint','metric','mean','sd','p025','p975']),
            'Exact score ties (pooled rows combine multiple snapshots per learner):\n',table(result[0],['method','checkpoint','unique_scores','learners_in_tied_groups','largest_tie','boundary_tie_size','selected_from_boundary_tie'])]
    report += ['## Interpretation and recommendation\n']
    for split,result in [('validation',validation),('test',test)]:
        for day in DAYS:
            r=next(r for r in result[0] if r['method']==selected and r['checkpoint']==day)
            rule=next(r for r in result[0] if r['method']=='progress_rule' and r['checkpoint']==day)
            random=next(r for r in result[2] if r['metric']=='recall' and r['checkpoint']==day)
            report.append(f"- {split.title()} day {day}: candidate recall {r['recall']:.3f}, rule {rule['recall']:.3f}, random mean {random['mean']:.3f} (draw range {random['p025']:.3f}–{random['p975']:.3f}); candidate {'exceeds' if r['recall']>rule['recall'] else 'does not exceed'} the rule at the same review volume.\n")
    report += ['\nDo not enable numeric scoring on this evidence alone. A transparent progress-based review list is the more defensible interim option for staff review: there is no demonstrated real-world benefit and small checkpoint cohorts plus tied scores make rankings unstable. This is a recommendation for review, not a newly implemented policy. Even favourable differences in this simulation require independent prospective evidence and a workload policy agreed with staff.\n',
        'Snapshot rows within a learner/module are correlated; later cohorts differ because completed modules leave. Module 1 alone limits sample size, coverage and transfer to other modules. AP uses untie-broken scores (rule score preserves the declared ordering); arbitrary ID order is not credited as predictive information. Pooled rule/random AP is descriptive across changing cohorts, not a selected policy. Undefined metrics are blank in CSV/“Undefined” here (no positives or no detected warning); genuine zero detection remains zero. Lead time is actual deadline minus first selected snapshot timestamp, averaged only over detected missed modules, never zero-filled for undetected cases. Random module-level variation and all individual draws are in separate CSVs.\n',
        'A fixed probability threshold allows workload to vary; this fixed review fraction chooses the top ranks regardless of absolute scores. Neither constitutes a calibrated probability or validated staff decision rule. The original frozen thresholds and results remain unchanged. No checkpoint history is overwritten or backfilled.\n',
        f'Fit warnings: {caught or "None"}. Both repeated fits and saved/reloaded predictions matched exactly. Dataset hashes, versions, feature order, settings, validation/test predictions, metric tables, random draws and module summaries are saved under `models/interactive_module1/`.\n',
        'Reproduce in a separate copy with no existing `models/interactive_module1/selection.json`: `.\\.venv\\Scripts\\python.exe -m src.interactive_model`. The script refuses to overwrite its frozen output.\n']
    (ROOT/'reports'/'interactive_model_evaluation.md').write_text('\n'.join(report),encoding='utf-8')
    print(json.dumps(dict(selection=selection,counts=counts,warnings=caught),indent=2))


if __name__ == '__main__':
    run()
