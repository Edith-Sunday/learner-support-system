"""Read-only model evidence and isolated pilot tools for the simplified dashboard."""
import pandas as pd
import streamlit as st
from src.simulate import ROOT
from src.dashboard_ui import evaluation_table


def readable_metrics(frame):
    cols=['method','checkpoint','eligible','positives','reviewed','precision','recall','average_precision']
    f=frame[[c for c in cols if c in frame]].copy()
    for col in ['precision','recall','average_precision']:
        if col in f: f[col]=f[col].map(lambda v:'Not defined' if pd.isna(v) else f'{v:.1%}')
    f['method']=f.method.replace({'logistic_regression':'Logistic regression','gradient_boosting':'Gradient boosting','progress_rule':'Simple progress rule'})
    return f.rename(columns={'method':'Method','checkpoint':'Check-in day','eligible':'Eligible snapshots','positives':'Missed-deadline snapshots','reviewed':'Reviewed','precision':'Precision','recall':'Recall','average_precision':'Average precision'})


def render_evaluation(store=None):
    st.write('The system estimates which unfinished Module 1 learners may miss their 14-day deadline, so a teacher can review their progress.')
    st.info('Results use simulated learner data. Performance with real learners has not been established.')
    st.write('Logistic regression and gradient boosting were compared with a simple progress rule. The selected logistic regression model has not consistently outperformed that rule.')
    st.caption('Precision: Of the learners flagged, how many missed the deadline?')
    st.caption('Recall: Of the learners who missed the deadline, how many were flagged?')
    st.caption('Warning time: How many days before the deadline were they identified?')
    st.write('At the illustrative 20% review level, validation recall averaged 28.4% for logistic regression and 26.5% for gradient boosting. These are checkpoint snapshots, not independent learners.')
    with st.expander('Comparison results'):
        for split in ['validation','test']:
            st.subheader(split.title())
            st.dataframe(readable_metrics(pd.read_csv(ROOT/'models/interactive_module1'/f'{split}_metrics.csv')),hide_index=True,width='stretch')
        st.write('Logistic regression identified 17 of 34 missed-deadline modules in validation and 16 of 27 in test. The progress rule identified 15 and 14 respectively. Random ordering averaged about 17.08 validation detections. This does not show consistent superiority.')
        st.caption('The test set was previously inspected. Later policy changes are exploratory, not a fresh untouched-test evaluation. Later check-in cohorts differ as completed modules leave; snapshots from the same learner are correlated.')
    with st.expander('Warning time and full comparison'):
        st.caption('Lead time describes detected missed-deadline modules only. Calculated-later interactive scores are not earlier delivered warnings.')
        for split in ['validation','test']:
            st.write(split.title()+' — first warning per learner-module')
            table=pd.read_csv(ROOT/'models/interactive_module1'/f'{split}_warnings.csv')
            table.columns=[c.replace('_',' ').capitalize() for c in table.columns]
            st.dataframe(table,hide_index=True,width='stretch')
        st.caption('Large tied groups limit individual differentiation. Test day-10 average precision was higher for the progress rule (77.1%) than logistic regression (72.6%).')
    with st.expander('How assessments and ordering work'):
        st.write('Check-ins use inputs from days 3, 7 and 10 after unlock. Both the activity time and the time it was recorded must be within the checkpoint. Processing occurs when the app is used; later calculations are labelled in the saved assessment records below. Completed, overdue and unavailable modules leave the active review list. Missed deadlines are followed up independently of scores.')
        st.write('Model review order sorts by the latest eligible experimental score. Learning progress sorts by fewer completed requirements, then missing or lower latest quiz score. Equal priorities remain tied; learner ID only orders their display. The visible limit includes an entire tied group. The frozen comparison used an administrative ID tie-break at a fixed review volume; the screen does not redefine that evaluation.')
        st.write('Predictors: practice submitted, quiz passed, latest quiz percentage, score change in percentage points, valid quiz attempt count and checkpoint day. Missing scores and trends remain missing until the fitted training-only imputer handles them. Progress and model scores do not confirm a learner barrier.')
    with st.expander('Saved assessments and selection policy'):
        st.write('May need support uses saved predictions from the connected logistic regression model: eligible, incomplete Module 1 learners whose deadline has not passed, with a saved numeric score. The configured review limit is 10 by default. Highest scores come first; the entire boundary tie is included, so the list can exceed the limit. Learner ID orders display within ties. There is no new probability threshold. Learners without saved scores remain in All learners. A small cohort may fit entirely within the limit; unfinished status alone does not select a learner.')
        st.caption('Current configured review limit: '+str(st.session_state.get('review_limit',10))+'. This prototype ranking policy is not a validated staffing capacity. Observed progress and reported difficulties are not explanations of model selection.')
        if store is not None:
            import json
            from src.interactive_ui import demo_name
            records=store.read('SELECT * FROM assessment_results ORDER BY student_id, checkpoint')
            if records:
                display=[]
                for r in records:
                    row={'Learner':demo_name(r['student_id']),'Learner ID':r['student_id'],'Check-in day':r['checkpoint'],'Score':f"{r['score']:.1%}",'Scheduled at':r['scheduled_at'],'Calculated at':r['assessed_at'],'Timing note':r['reason']}
                    row.update({k.replace('_',' ').capitalize():v for k,v in json.loads(r['features']).items()})
                    display.append(row)
                st.dataframe(pd.DataFrame(display),hide_index=True,width='stretch')
            else:
                st.info('No saved assessments yet.')
    with st.expander('Measurement limitations'):
        st.write('Session time includes breaks. Active minutes estimate short intervals between interactions, not all study time. Neither is used by the connected six-feature model. Login and interruption measurements are unavailable, not zero. The quiz uses a fixed question set. Real-world validation, staff capacity decisions, consent and production authentication remain outside this prototype.')
    with st.expander('Earlier full-feature evaluation'):
        f=pd.read_csv(ROOT/'reports/snapshot_metrics.csv')
        selected=f[f.split.eq('test') & f.cohort.eq('overall') & f.threshold_type.eq('validation_f2')]
        st.dataframe(evaluation_table(selected,[('threshold','Frozen threshold','.2f'),('precision','Precision','.1%'),('recall','Recall','.1%'),('f2','F2','.3f'),('flag_count','Snapshots flagged',',.0f')]),width='stretch')
        st.caption('The original model is not used for connected learner predictions. Its frozen threshold flags 95.8% of test snapshots; high recall comes with substantial review volume.')
        with st.expander('Validation workload reference'):
            table=pd.read_csv(ROOT/'reports/workload_validation_snapshot_reference.csv')
            table.columns=[c.replace('_',' ').capitalize() for c in table.columns]
            st.dataframe(table,hide_index=True,width='stretch')
            st.caption('Flag-everyone is a diagnostic reference, not a new policy. Workload fractions refer to checkpoint cohorts, not daily teacher caseloads.')
    with st.expander('Sample learner data'):
        st.caption('These sample records were used to compare the models.')
        students=pd.read_csv(ROOT/'data/students.csv')
        st.dataframe(students,hide_index=True,width='stretch')
        sid=st.selectbox('Sample learner',students.student_id.tolist())
        events=pd.read_csv(ROOT/'data/events.csv',low_memory=False)
        st.dataframe(events.loc[events.student_id.eq(sid)],hide_index=True,width='stretch')
        st.caption('Read-only sample records. Support actions apply only to the connected demonstration learners.')
    with st.expander('Pilot evaluation'):
        from src.pilot import render
        render()
