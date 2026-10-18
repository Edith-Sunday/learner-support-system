"""Local Streamlit staff demonstration. Run with the explicit project interpreter."""
from datetime import datetime, time
import os
from pathlib import Path
import uuid

import pandas as pd
import streamlit as st

from src.dashboard_data import (DEFAULT_TIME, SIX_INPUTS, active_queues, available,
                                current_inputs, historical_modules, load_ranker, load_sources)
from src.staff_store import CHALLENGES, STAFF, STATUSES, StaffStore, message_draft
from src.simulate import ROOT

import altair as alt
from src.dashboard_ui import current_learners, status_counts, filter_cases, date_label, duration_label, input_groups, evaluation_table, last_assessed_label

st.set_page_config(page_title='Chemistry learner support', page_icon='🧪', layout='wide')
st.markdown("""<style>
.block-container {padding-top:3.8rem; max-width:1600px; padding-bottom:2rem;}
h1 {font-size:1.7rem !important;} h2 {font-size:1.3rem !important;} h3 {font-size:1.1rem !important;}
h1,h2,h3 {color:#253238;}
[data-testid="stMetric"] {background:#EFF5F5; padding:.65rem .9rem; border-radius:8px;}
[data-testid="stMetricValue"] {font-size:1.6rem;}
[data-testid="stSidebar"] {min-width:240px; max-width:260px;}
.demo-badge {background:#E1F2EF; color:#125E58; padding:4px 9px; border-radius:5px; font-size:.85rem;}
</style>""", unsafe_allow_html=True)
@st.cache_resource
def sources_and_model():
    sources = load_sources()
    pipeline, features = load_ranker()
    return sources, pipeline, features


@st.cache_data(show_spinner=False)
def historical_view(at_iso):
    sources, pipeline, features = sources_and_model()
    at = pd.Timestamp(at_iso)
    modules = historical_modules(sources['students'], sources['events'], at)
    early, overdue = active_queues(modules, sources['prediction_snapshots'], at, pipeline, features)
    return modules, early, overdue



def show_table(frame, height='auto'):
    labels = {'student_id':'Learner ID', 'module_id':'Module', 'deadline':'Deadline',
              'learning_status':'Learning status', 'remaining_requirements':'Remaining requirements',
              'unlock_time':'Unlocked', 'completion_time':'Completed', 'completion_known_at':'Completion recognised',
              'event_time':'Occurred', 'recorded_at':'Recorded', 'score_pct':'Score (%)',
              'valid':'Valid attempt', 'source':'Route', 'grant_id':'Grant reference',
              'confirmed_by':'Confirmed by', 'barrier':'Challenge', 'effective_at':'Effective time',
              'created_at':'Saved at (audit)', 'referral_time':'Referral time'}
    display = frame.copy()
    for col in display:
        if pd.api.types.is_datetime64_any_dtype(display[col]):
            display[col] = display[col].map(date_label)
    display = display.rename(columns=labels)
    # Accessible HTML cells wrap long text; retain sorting/download tools separately.
    table_height = height if isinstance(height, int) else 390
    html = display.to_html(index=False, escape=True, na_rep='Not recorded', border=0)
    st.html(f'''<style>
    .readable-table {{overflow:auto; border:1px solid #D8E2E2; border-radius:6px;}}
    .readable-table table {{border-collapse:collapse; width:100%; table-layout:fixed; font-size:14px; color:#253238;}}
    .readable-table th,.readable-table td {{padding:9px 10px; text-align:left; white-space:normal; overflow-wrap:anywhere; border-bottom:1px solid #E2E8E8; vertical-align:top;}}
    .readable-table th {{background:#EFF5F5; position:sticky; top:0; font-weight:600;}}
    </style><div class="readable-table" style="max-height:{table_height}px" role="region" aria-label="Scrollable data table" tabindex="0">{html}</div>''')
    with st.expander('Table tools: sort or download'):
        st.dataframe(display, hide_index=True, width='stretch', height=height)


workspace = st.sidebar.segmented_control('Role workspace', ['Staff', 'Learner'], default='Staff', key='role_workspace')
from src.interactive_ui import render
render(workspace)
st.stop()

sources, pipeline, features = sources_and_model()
start = pd.Timestamp(sources['metadata']['observation_start'])
end = pd.Timestamp(sources['metadata']['observation_end'])
st.sidebar.subheader('Chemistry support')
page = st.sidebar.radio('Workspace', ['All learners', 'Early review', 'Overdue referrals', 'Model evaluation'], key='page')
with st.sidebar.expander('Demo settings'):
    selected_date = st.date_input('As of date (UTC)', DEFAULT_TIME.date(), min_value=start.date(), max_value=end.date(), key='asof_date')
    selected_time = st.time_input('As of time (UTC)', time(12, 0), step=60, key='asof_time')
    st.caption('Historical demonstration: only information that occurred and was recorded by this time is shown. Default: a fixed mid-window date, not chosen using model results.')
at = pd.Timestamp(datetime.combine(selected_date, selected_time), tz='UTC')
if not start <= at <= end:
    st.error('Choose a time between 1 Jan 2026, 00:00 UTC and 1 May 2026, 00:00 UTC.')
    st.stop()
st.sidebar.caption('As of ' + date_label(at))
st.sidebar.caption('Support is available to every learner.')
if not st.session_state.get('profile') or st.session_state['profile'][0] != page:
    st.title(page)
st.markdown('<span class="demo-badge">Simulated-data prototype</span> &nbsp; As of ' + date_label(at), unsafe_allow_html=True)
st.caption('Model scores are experimental.')
store = StaffStore(Path(os.environ.get('LEARNER_DEMO_DB', ROOT / 'runtime' / 'staff_demo.sqlite3')))
modules, early, overdue = historical_view(at.isoformat())
store.ensure_referrals(overdue)


def with_support(frame):
    frame = frame.copy()
    states = [store.state(at, r.student_id, r.module_id) for r in frame.itertuples()]
    frame['Assigned staff'] = [s['staff'] for s in states]
    frame['Support status'] = [s['status'] for s in states]
    return frame


def open_profile(sid):
    st.session_state['profile'] = (page, sid)


def back_to_list():
    st.session_state.pop('profile', None)


def learner_picker(frame):
    if frame.empty:
        st.info('No learners match this view. Change the filters or demonstration time.')
        return
    left, right = st.columns([3, 1], vertical_alignment='bottom')
    sid = left.selectbox('Learner to open', frame.student_id.tolist(), key=f'pick-{page}')
    right.button('Open learner', on_click=open_profile, args=(sid,), type='primary')


def filter_controls(frame, prefix, overdue_only=False):
    defaults = {'query':'', 'status':'All', 'module':'All', 'staff':'All', 'review':'All'}
    # Separate durable keys survive Streamlit's cleanup of hidden list widgets.
    for name, value in defaults.items():
        st.session_state.setdefault(f'{prefix}-{name}', value)
        st.session_state[f'widget-{prefix}-{name}'] = st.session_state[f'{prefix}-{name}']
    def remember(name):
        st.session_state[f'{prefix}-{name}'] = st.session_state[f'widget-{prefix}-{name}']
    def clear():
        for name, value in defaults.items():
            st.session_state[f'{prefix}-{name}'] = value
    cols = st.columns([2, 2, 1, 2] if not overdue_only else [2, 2, 2])
    query = cols[0].text_input('Search learner ID', key=f'widget-{prefix}-query', on_change=remember, args=('query',))
    if overdue_only:
        staff = cols[1].selectbox('Assigned staff', ['All'] + STAFF, key=f'widget-{prefix}-staff', on_change=remember, args=('staff',))
        review = cols[2].selectbox('Review status', ['All'] + STATUSES, key=f'widget-{prefix}-review', on_change=remember, args=('review',))
        status, module = 'All', 'All'
    else:
        status = cols[1].selectbox('Learning status', ['All', 'In progress', 'Overdue', 'Completed all eight modules'], key=f'widget-{prefix}-status', on_change=remember, args=('status',))
        module = cols[2].selectbox('Module', ['All'] + list(range(1, 9)), key=f'widget-{prefix}-module', on_change=remember, args=('module',))
        staff = cols[3].selectbox('Assigned staff', ['All'] + STAFF, key=f'widget-{prefix}-staff', on_change=remember, args=('staff',))
        review = 'All'
    st.button('Clear filters', on_click=clear, key=f'clear-{prefix}')
    filtered = filter_cases(frame, query, status, module, staff, review)
    st.caption(f'Showing {len(filtered)} of {len(frame)} learners')
    return filtered


def support_actions(sid, mid, case, learner, actions, state):
    st.caption('Demonstration actions take effect at ' + date_label(at) + '. Drafts are not sent.')
    token_key = f'action-token-{sid}-{mid}'
    st.session_state.setdefault(token_key, str(uuid.uuid4()))
    def save(kind, payload):
        store.record(sid, mid, kind, at, payload, st.session_state[token_key])
        st.session_state[token_key] = str(uuid.uuid4())
        st.session_state['saved_notice'] = 'Demonstration record saved locally. No message was sent.'
        st.rerun()
    if st.session_state.get('saved_notice'):
        st.success(st.session_state.pop('saved_notice'))
    with st.expander('Update review'):
        with st.form(f'review-{sid}-{mid}-{at.isoformat()}'):
            staff = st.selectbox('Assign demonstration staff', STAFF, index=STAFF.index(state['staff']))
            status = st.selectbox('Review status', STATUSES, index=STATUSES.index(state['status']))
            notes = st.text_area('Review notes', value=state['notes'])
            follow = st.date_input('Follow-up date (optional)', value=pd.Timestamp(state['follow_up']).date() if state.get('follow_up') else None)
            if st.form_submit_button('Save review'):
                save('review', dict(staff=staff, status=status, notes=notes, follow_up=str(follow) if follow else None))
    with st.expander('Record confirmed challenge'):
        with st.form(f'challenge-{sid}-{mid}'):
            category = st.selectbox('Confirmed challenge', CHALLENGES)
            confirmed_by = st.selectbox('Confirmed by', ['student', 'teacher'])
            need = st.text_area('Confirmed details / skill need')
            confirmed = st.checkbox('A student or teacher has confirmed this demonstration record')
            if st.form_submit_button('Save confirmed challenge'):
                if not confirmed:
                    st.warning('Confirm the source before saving a challenge.')
                else:
                    save('challenge', dict(category=category, confirmed_by=confirmed_by, details=need))
    with st.expander('Preview support draft'):
        category = st.selectbox('Draft category', ['Content difficulty', 'Deadline difficulty', 'Connectivity difficulty', 'Unclear or mixed difficulty', 'Overdue'])
        confirmed_needs = [a['payload']['details'] for a in actions if a['kind'] == 'challenge' and a['module_id'] == mid and a['payload']['category'] == 'Content difficulty']
        draft = message_draft(case, category, at, confirmed_needs[-1] if confirmed_needs else '')
        st.caption(f'Channel: {learner.communication_preference} · Preview only; no messaging service is connected.')
        st.text(draft)
        if st.button('Save draft locally'):
            save('draft', dict(category=category, channel=learner.communication_preference, text=draft, delivery_status='Draft only — not sent'))


def details(sid):
    st.button('← Back to list', on_click=back_to_list)
    history = modules[modules.student_id.eq(sid)]
    if history.empty:
        st.info('This learner is not yet enrolled at the selected time.')
        return
    learner = sources['students'].set_index('student_id').loc[sid]
    case = history.iloc[-1].to_dict()
    mid = int(case['module_id'])
    state = store.state(at, sid, mid)
    actions = store.actions(at, sid)
    st.title(f'{sid} · Module {mid}')
    st.markdown(f"**{case['learning_status']}** · {state['staff']} · Preferred channel: **{learner.communication_preference}**")
    overview, activity, support, audit = st.tabs(['Overview', 'Learning activity', 'Support', 'History'])
    with overview:
        complete = int(history.learning_status.str.startswith('Completed').sum())
        st.subheader(f'Module progress · {complete} of 8 completed')
        st.progress(complete / 8)
        left, right = st.columns(2, gap='large')
        with left:
            st.subheader('Completion checklist')
            st.write(('✓' if case['practice_submitted'] else '○') + ' Practice submitted — ' + ('Yes' if case['practice_submitted'] else 'Not yet'))
            st.write(('✓' if case['quiz_passed'] else '○') + ' Quiz passed at ≥80% — ' + ('Yes' if case['quiz_passed'] else 'Not yet'))
            st.write('Latest quiz score: ' + (f"{case['latest_quiz_score']:.0f}%" if pd.notna(case['latest_quiz_score']) else 'No quiz attempt recorded'))
        with right:
            st.subheader('Deadline')
            st.write('Original deadline: ' + date_label(case['deadline']))
            if case['learning_status'].startswith('Completed'):
                st.write('Completed: ' + date_label(case['completion_time']))
            elif at > case['deadline']:
                st.write('Overdue by: ' + duration_label(at - case['deadline']))
            else:
                st.write('Time remaining: ' + duration_label(case['deadline'] - at))
            st.write('Remaining requirements: ' + case['remaining_requirements'])
        st.caption('Staff review status: ' + state['status'] + '. Review status does not change learning completion.')
    with activity:
        visible = available(sources['events'], at)
        quizzes = visible[visible.student_id.eq(sid) & visible.module_id.eq(mid) & visible.event_type.eq('quiz')].sort_values(['event_time', 'event_id']).copy()
        st.subheader('Quiz attempts in this module')
        if quizzes.empty:
            st.info('No quiz attempt recorded at this time.')
        else:
            quizzes['Attempt'] = range(1, len(quizzes) + 1)
            quizzes['Route'] = quizzes.source.map({'teacher_offline':'Offline (teacher recorded)', 'online':'Online'})
            quizzes['Result'] = quizzes.valid.map({1:'Valid', 0:'Invalid'})
            points = alt.Chart(quizzes).mark_point(filled=True, size=100).encode(
                x=alt.X('Attempt:O', title='Attempt number'), y=alt.Y('score_pct:Q', title='Quiz score (%)', scale=alt.Scale(domain=[0,100])),
                color=alt.Color('Route:N', scale=alt.Scale(range=['#087F8C','#A65A00'])), shape='Result:N',
                tooltip=['Attempt','score_pct','Route','Result'])
            rule = alt.Chart(pd.DataFrame({'Pass requirement':[80]})).mark_rule(strokeDash=[5,4], color='#666666').encode(y='Pass requirement:Q')
            st.altair_chart((points + rule).properties(height=210), width='stretch')
            st.caption('Dashed line: 80% pass requirement. Only valid attempts can satisfy completion. Offline attempts are labelled in the legend and table.')
            if len(quizzes) == 1:
                st.caption('One attempt recorded; there is no trend to display.')
            show_table(quizzes[['Attempt','score_pct','Route','Result','event_time']], height=140)
        st.subheader('Current recorded observations')
        st.caption('As of ' + date_label(at) + '. These observations do not establish the reason for a model score.')
        groups = input_groups(current_inputs(sources, modules, sid, mid, at))
        for group, rows in groups.items():
            st.markdown('**' + group + '**')
            for label, value, help_text in rows:
                st.write(f'{label}: **{value}**')
                if help_text:
                    st.caption(help_text)
        st.write('Offline participation: ' + ('Recorded' if case['offline_participation'] else 'Not recorded'))
        scores = early[early.student_id.eq(sid)]
        if len(scores) and pd.notna(scores.iloc[0].model_risk_score):
            score = scores.iloc[0]
            st.info(f'Model risk score: {score.model_risk_score:.3f} · Day {int(score.checkpoint_day)} · Snapshot: {date_label(score.score_timestamp)} · Last assessed: {last_assessed_label(score.score_timestamp, at)}. This older snapshot is separate from current observations.')
        else:
            st.caption('No eligible score for the current active early-review view. This does not mean low risk.')
    with support:
        st.subheader('Staff support')
        st.write(f"Assigned staff: {state['staff']} · Review status: {state['status']}")
        st.markdown('**Confirmed challenges**')
        barriers = available(sources['support_information'], at)
        barriers = barriers[barriers.student_id.eq(sid)].copy()
        challenges = [dict(Module=a['module_id'], Challenge=a['payload']['category'], **{'Confirmed by':a['payload']['confirmed_by'], 'Details':a['payload']['details']}) for a in actions if a['kind']=='challenge']
        if barriers.empty and not challenges:
            st.caption('No student- or teacher-confirmed challenge recorded at this time.')
        if len(barriers):
            barriers['barrier'] = barriers.barrier.str.replace('_',' ').str.capitalize()
            show_table(barriers[['module_id','barrier','confirmed_by']])
        if challenges:
            show_table(pd.DataFrame(challenges))
        st.caption('Progress observations alone do not prove a challenge.')
        support_actions(sid, mid, case, learner, actions, state)
        st.caption('Quiz-attempt grants and offline-result entry are the next workflow step; they are not available here.')
    with audit:
        st.subheader('Module history')
        show_table(history[['module_id','learning_status','unlock_time','deadline','completion_time','completion_known_at']])
        st.subheader('Support actions')
        if actions:
            show_table(pd.DataFrame([{'Action':a['kind'].capitalize(), 'Module':a['module_id'], 'Effective time':date_label(a['effective_at']), 'Saved at (audit)':date_label(a['created_at']), 'Details':str(a['payload'])} for a in actions]))
        else:
            st.caption('No support actions recorded at this time.')
        if len(barriers):
            st.markdown('**Source confirmation history**')
            show_table(barriers[['module_id','barrier','confirmed_by','event_time','recorded_at']])
        st.subheader('Referral history')
        referrals = pd.DataFrame(store.referrals(at, sid))
        if referrals.empty:
            st.caption('No referral history recorded at this time.')
        else:
            referrals['referral_time'] = pd.to_datetime(referrals.referral_time, utc=True)
            show_table(referrals)
        with st.expander('Quiz recording audit'):
            show_table(quizzes[['event_time','recorded_at','score_pct','valid','source','grant_id']])
        st.caption('Full timestamp precision is retained in the underlying records. Completed cases retain history; staff review never resolves learning requirements.')


# Page navigation closes the profile; returning to a list preserves its durable filters.
profile = st.session_state.get('profile')
if profile and profile[0] != page:
    back_to_list()
    profile = None
if profile:
    details(profile[1])
    st.stop()
if page == 'All learners':
    current = with_support(current_learners(modules))
    counts = status_counts(current)
    enrolled_count = int(sources['students'].enrolment_time.le(at).sum())
    assert len(current) == enrolled_count
    cols = st.columns(4)
    for col, label, count in zip(cols, ['Enrolled learners', 'Active before deadline', 'Overdue', 'Completed all 8'], [len(current), *counts.tolist()]):
        col.metric(label, count)
    chart_data = counts.rename_axis('Current status').reset_index(name='Learners')
    chart = alt.Chart(chart_data).mark_bar(color='#087F8C', size=17).encode(
        y=alt.Y('Current status:N', sort=counts.index.tolist(), title=None, axis=alt.Axis(labelLimit=240)),
        x=alt.X('Learners:Q', title='Number of learners', axis=alt.Axis(tickMinStep=1, tickCount=6)), tooltip=['Current status','Learners'])
    labels = chart.mark_text(align='left', dx=5, color='#253238').encode(text='Learners:Q')
    st.altair_chart((chart + labels).properties(height=170), width='stretch')
    table = filter_controls(current, 'learners')
    display = table[['student_id','module_id','learning_status','latest_quiz_score','deadline','Assigned staff']].copy()
    display['latest_quiz_score'] = display.latest_quiz_score.map(lambda x: f'{x:.0f}%' if pd.notna(x) else 'No quiz attempt recorded')
    show_table(display.rename(columns={'module_id':'Current module','latest_quiz_score':'Latest quiz (%)'}), height=245)
    learner_picker(table)
elif page == 'Early review':
    st.caption('Model risk score: experimental 0–1 ranking, not a verified probability. Support remains available to everyone.')
    a, b, c = st.columns([1,1,2], vertical_alignment='bottom')
    # Retain display limit across profile navigation, too.
    st.session_state.setdefault('early-all-value', True)
    st.session_state.setdefault('early-top-value', 25)
    st.session_state['early-all'] = st.session_state['early-all-value']
    st.session_state['early-top'] = min(st.session_state['early-top-value'], max(1,len(early)))
    def keep_limit():
        st.session_state['early-all-value'] = st.session_state['early-all']
        st.session_state['early-top-value'] = st.session_state['early-top']
    show_all = a.checkbox('Show all', key='early-all', on_change=keep_limit)
    top = b.number_input('Top cases to review', min_value=1, max_value=max(1,len(early)), key='early-top', disabled=show_all, on_change=keep_limit)
    c.caption('The limit changes this view only, not eligibility for help.')
    shown = early if show_all else early.head(int(top))
    st.caption(f'Showing {len(shown)} of {len(early)} cases · {early.model_risk_score.notna().sum()} scored · {early.model_risk_score.isna().sum()} not yet scored')
    table = shown[['student_id','module_id','model_risk_score','score_status','checkpoint_day','score_timestamp']].copy()
    table['Last assessed'] = table.score_timestamp.map(lambda t: last_assessed_label(t, at))
    table['model_risk_score'] = table.model_risk_score.map(lambda x: f'{x:.3f}' if pd.notna(x) else 'Not yet scored')
    table['checkpoint_day'] = table.checkpoint_day.map(lambda x: f'Day {int(x)}' if pd.notna(x) else 'No snapshot yet')
    show_table(table.rename(columns={'model_risk_score':'Model risk score','score_status':'Score status','checkpoint_day':'Checkpoint','score_timestamp':'Score timestamp'}), height=360)
    learner_picker(shown)
elif page == 'Overdue referrals':
    st.caption('All known unresolved overdue cases, regardless of score. Staff review does not complete learning.')
    table = filter_controls(with_support(overdue), 'overdue', overdue_only=True)
    display = table[['student_id','module_id','deadline','remaining_requirements','Assigned staff','Support status']].copy()
    display.insert(3, 'Overdue by', table.deadline.map(lambda t: duration_label(at-t)))
    show_table(display, height=360)
    learner_picker(table)
else:
    st.warning('Frozen evaluation on artificial data. The test set has already been inspected. The exploratory ranked workflow is not a newly validated policy or a fresh untouched-test evaluation.')
    metrics = pd.read_csv(ROOT / 'reports' / 'snapshot_metrics.csv')
    selected = metrics[metrics.split.eq('test') & metrics.cohort.eq('overall') & metrics.threshold_type.eq('validation_f2')]
    st.subheader('Original frozen test evaluation')
    show_table(evaluation_table(selected, [
        ('threshold','Frozen probability threshold','.2f'), ('precision','Precision','.1%'),
        ('recall','Recall','.1%'), ('f2','F2 score (0–1)','.3f'),
        ('fp','False-warning snapshots',',.0f'), ('flag_count','Snapshots flagged',',.0f'),
        ('flagged_percent','Snapshots flagged (%)','.1f')]))
    st.write('The original logistic-regression threshold flags almost everyone: 95.8% of test snapshots. High recall comes with substantial false-warning volume. That threshold is kept in the evaluation record, not used for automatic referrals here.')
    warnings = pd.read_csv(ROOT / 'reports' / 'module_warning_summary.csv')
    st.subheader('First warning per learner-module')
    show_table(evaluation_table(warnings, [
        ('eligible_missed_modules','Eligible missed-deadline modules',',.0f'),
        ('warned_missed_modules','Missed-deadline modules warned',',.0f'),
        ('mean_lead_days','Mean warning lead time (days)','.2f'),
        ('median_lead_days','Median warning lead time (days)','.2f'),
        ('on_time_modules_false_warning','On-time modules with a false warning',',.0f'),
        ('unique_students_warned','Unique learners warned',',.0f')]))
    st.caption('Lead time includes detected missed-deadline modules only. Snapshots within learners/modules are correlated and later-day cohorts differ as completed modules leave.')
    st.subheader('Exploratory operations')
    st.write('Early review ranks saved logistic-regression scores; a top-case limit changes the view only. Overdue referrals are driven solely by recorded incompletion after the deadline. All learners can receive support. No new policy performance is claimed.')
    with st.expander('Validation workload diagnostic'):
        workload = pd.read_csv(ROOT / 'reports' / 'workload_validation_snapshot_reference.csv')
        show_table(evaluation_table(workload[workload.cohort.eq('overall')], [
            ('precision','Precision','.1%'), ('recall','Recall','.1%'),
            ('f2','F2 score (0–1)','.3f'), ('flag_count','Snapshots flagged',',.0f')]))
        st.caption('Flag-all is a diagnostic reference. Workload fractions are illustrative checkpoint-cohort scenarios, not daily teacher caseloads.')
    with st.expander('Methodology and limitations'):
        st.write('Early review uses the latest available day-3, day-7 or day-10 snapshot, with only frozen allowlisted predictors. Scores rank descending, then learner ID and module for ties. Unscored learners follow scored learners; no new risk bands or thresholds are introduced. The frozen 0.08 threshold does not trigger dashboard referrals.')
        st.write('Only events whose occurrence and recording timestamps are available at the selected time contribute. Completion recognition unlocks the next module. Deadline equality remains on time. Staff actions have separate effective and real audit times.')
        st.write('This local prototype has no production authentication. Simulation accuracy does not establish real-world accuracy or improved learner outcomes. Quiz grants and offline-result entry remain future work.')
