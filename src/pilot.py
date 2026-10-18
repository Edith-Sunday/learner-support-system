"""Isolated pilot workflow; no real pilot has occurred and no causal claim is made."""
from pathlib import Path
import hashlib
import io
import pandas as pd
import numpy as np
from src.simulate import ROOT

LABEL='Illustrative synthetic example'
FIELDS=['participant_id','group','dataset_kind','enrolled_at','deadline','completion_at','outcome',
        'dispatch_at','delivery_status','response_at','observed_through']
PROTOCOL='''Future pilot protocol (predefined prototype workflow; no real pilot has occurred)

Eligible participants: consenting SS1 chemistry learners beginning the authored Module 1.
Assign learners randomly 1:1 to usual-support baseline or personalised-support group before Module 1 starts; keep each learner in one group. Record assignment separately from outcomes and retain every assigned learner in denominator accounting. Plan sample size and consent before a real pilot.

Intervention: staff review at days 3, 7 and 10, confirmed-need support drafts, and documented follow-up. Usual-support learners retain access to learning materials and help. For comparable response metrics, both groups receive the same neutral check-in at day 3; additional targeted support occurs only in the support group. If baseline receives no check-in, its response rate is Not applicable.

Observation: Module 1's original unlock/enrolment plus 14 days; completion requires practice and a valid quiz pass ≥80%. Use completion occurrence for timeliness, not recording date. Freeze outcome extraction after recording reconciliation, with observed-through timestamps and unresolved outcomes labelled missing. Extensions/extra attempts do not move the original deadline.

Primary outcome: completion by the original 14-day deadline. Only mature, known outcomes enter the rate denominator; report pending and missing separately alongside all assigned participant counts. Missingness may bias the comparison and requires a prespecified real-pilot analysis.

Response: first learner response within 48 hours after the comparable check-in, using the same fixed follow-up interval in both groups. Only dispatches with a full observed 48-hour window and verified real delivery enter real response denominators. For synthetic examples, explicitly simulated dispatches may enter a separate illustrative denominator. Late responses do not count; pending follow-up and unverified delivery are separate. No dispatch means response rate Not applicable, not zero.

Report support minus baseline in percentage points and relative change divided by baseline. Zero baseline means relative change Not defined. Observational baseline comparisons cannot establish causality; even a randomised pilot requires adequate sample size, adherence, consent, and uncertainty analysis. Simulated dispatch is not verified real delivery. Never pool these records with historical simulation or interactive demonstration records.
'''

def validate(frame):
    if set(frame)!=set(FIELDS): raise ValueError('CSV must contain exactly the documented pilot columns.')
    f=frame.copy()
    if f.empty or f.participant_id.isna().any() or f.participant_id.astype(str).str.strip().eq('').any() or f.participant_id.duplicated().any():
        raise ValueError('Participants must be unique and nonempty; repeated or inconsistent group assignments are rejected.')
    if not f.group.isin(['baseline','support']).all() or not f.dataset_kind.isin(['synthetic','real']).all() or f.dataset_kind.nunique()!=1:
        raise ValueError('Invalid group or mixed dataset kinds.')
    if not f.outcome.isin(['on_time','late','not_completed','missing','pending']).all(): raise ValueError('Invalid outcome.')
    if not f.delivery_status.isin(['none','simulated','verified','unverified']).all(): raise ValueError('Invalid delivery status.')
    if f.dataset_kind.iloc[0]=='real' and f.delivery_status.eq('simulated').any(): raise ValueError('Simulated dispatch cannot be imported as real delivery.')
    for c in ['enrolled_at','deadline','completion_at','dispatch_at','response_at','observed_through']:
        raw=f[c]
        parsed=[]
        for value in raw:
            if pd.isna(value) or str(value).strip()=='': parsed.append(pd.NaT); continue
            try: t=pd.Timestamp(value)
            except Exception as e: raise ValueError('Invalid timestamp: '+c) from e
            if t.tzinfo is None: raise ValueError('Timestamps require an explicit UTC offset.')
            parsed.append(t.tz_convert('UTC'))
        f[c]=pd.to_datetime(parsed,utc=True)
    if f[['enrolled_at','deadline','observed_through']].isna().any().any(): raise ValueError('Required timestamps missing.')
    if not (f.deadline-f.enrolled_at).eq(pd.Timedelta(days=14)).all(): raise ValueError('Original deadline must be enrolment +14 days.')
    if f.observed_through.lt(f.enrolled_at).any(): raise ValueError('Observation before enrolment.')
    for c in ('completion_at','dispatch_at','response_at'):
        if (f[c].notna() & (f[c].lt(f.enrolled_at)|f[c].gt(f.observed_through))).any(): raise ValueError('Impossible timestamp: '+c)
    if not f.dispatch_at.isna().eq(f.delivery_status.eq('none')).all(): raise ValueError('Dispatch/status mismatch.')
    if (f.response_at.notna() & (f.dispatch_at.isna()|f.response_at.lt(f.dispatch_at))).any(): raise ValueError('Response must follow dispatch.')
    if not f.completion_at.notna().eq(f.outcome.isin(['on_time','late'])).all(): raise ValueError('Completion/outcome mismatch.')
    if (f.outcome.eq('on_time') & f.completion_at.gt(f.deadline)).any() or (f.outcome.eq('late') & f.completion_at.le(f.deadline)).any(): raise ValueError('Timeliness contradicts original deadline.')
    if (f.outcome.isin(['not_completed','missing']) & f.deadline.gt(f.observed_through)).any() or (f.outcome.eq('pending') & f.deadline.le(f.observed_through)).any(): raise ValueError('Outcome maturity inconsistent with observed-through time.')
    return f

def difference(baseline,support):
    if baseline is None or support is None: return dict(percentage_points=None,relative_percent=None)
    return dict(percentage_points=100*(support-baseline),relative_percent=100*(support-baseline)/baseline if baseline else None)

def summarize(frame):
    f=validate(frame); rows=[]
    for group in ('baseline','support'):
        g=f.loc[f.group.eq(group)]
        mature=g.deadline.le(g.observed_through)
        eligible=mature & g.outcome.isin(['on_time','late','not_completed'])
        dispatch=g.dispatch_at.notna()
        verified=g.delivery_status.eq('simulated' if f.dataset_kind.iloc[0]=='synthetic' else 'verified')
        followed=dispatch & (g.observed_through-g.dispatch_at).ge(pd.Timedelta(hours=48))
        response_eligible=followed & verified
        responded=response_eligible & g.response_at.notna() & (g.response_at-g.dispatch_at).le(pd.Timedelta(hours=48))
        n=int(eligible.sum()); nr=int(response_eligible.sum())
        rows.append(dict(group=group,participants=len(g),eligible_outcomes=n,on_time=int((eligible & g.outcome.eq('on_time')).sum()),
            completion_rate=float((eligible & g.outcome.eq('on_time')).sum()/n) if n else None,
            pending_outcomes=int((~mature).sum()),missing_outcomes=int((mature & g.outcome.eq('missing')).sum()),
            dispatched=int(dispatch.sum()),eligible_response_followup=nr,responses=int(responded.sum()),
            response_rate=float(responded.sum()/nr) if nr else None,pending_response_followup=int((dispatch & ~followed).sum()),
            unverified_delivery=int((dispatch & ~verified).sum()),no_message=int((~dispatch).sum())))
    diffs={metric:difference(rows[0][metric],rows[1][metric]) for metric in ('completion_rate','response_rate')}
    return rows,diffs

def example():
    """Fixed illustrative cases, not optimised for intervention benefit."""
    start=pd.Timestamp('2026-01-01T08:00Z'); records=[]
    for group in ('baseline','support'):
        for i in range(12):
            # Deliberately the same outcome pattern in both groups; no impact claim.
            enrolled=start+pd.Timedelta(days=20 if i==10 else 0)
            deadline=enrolled+pd.Timedelta(days=14)
            outcome='on_time' if i<4 else 'late' if i==4 else 'pending' if i==10 else 'missing' if i==11 else 'not_completed'
            completion=enrolled+pd.Timedelta(days=10 if i<4 else 16) if outcome in ('on_time','late') else None
            dispatch=enrolled+pd.Timedelta(days=3) if i!=9 else None
            observed=start+pd.Timedelta(days=24)
            records.append(dict(participant_id=f'PILOT-EXAMPLE-{group}-{i+1:02}',group=group,dataset_kind='synthetic',
                enrolled_at=enrolled.isoformat(),deadline=deadline.isoformat(),completion_at=completion.isoformat() if completion else None,
                outcome=outcome,dispatch_at=dispatch.isoformat() if dispatch else None,delivery_status='simulated' if dispatch else 'none',
                response_at=(dispatch+pd.Timedelta(hours=24 if i<3 else 60)).isoformat() if dispatch and i<5 else None,
                observed_through=observed.isoformat()))
    return pd.DataFrame(records,columns=FIELDS)

def render():
    import streamlit as st
    st.subheader('Pilot evaluation')
    st.caption('Illustrative example uses synthetic records. No real pilot has occurred.')
    with st.expander('Predefined pilot protocol',expanded=False): st.markdown(PROTOCOL)
    mode=st.radio('Pilot dataset',['Illustrative synthetic example','Validate future pilot CSV'],format_func=lambda value:'Illustrative example' if value==LABEL else value)
    f=example(); label=LABEL
    if mode!='Illustrative synthetic example':
        st.caption('Imports stay in a separate pilot folder and never create operational learners. Use pseudonymous participant IDs.')
        uploaded=st.file_uploader('Pilot CSV',type='csv')
        st.download_button('Download input template',pd.DataFrame(columns=FIELDS).to_csv(index=False),'pilot_input_template.csv')
        if uploaded is None: return
        try:
            f=validate(pd.read_csv(io.BytesIO(uploaded.getvalue())))
        except (ValueError,TypeError) as e: st.error(str(e)); return
        label=LABEL if f.dataset_kind.iloc[0]=='synthetic' else 'Imported pilot records — delivery and study provenance require verification'
        if st.button('Save validated pilot copy separately'):
            dest=ROOT/'pilot'/'imports'; dest.mkdir(parents=True,exist_ok=True)
            digest=hashlib.sha256(uploaded.getvalue()).hexdigest()
            target=dest/(digest+'.csv')
            if not target.exists(): target.write_bytes(uploaded.getvalue())
            st.success('Validated copy saved only in pilot/imports/'+target.name)
    rows,diffs=summarize(f)
    st.subheader('Illustrative example' if label==LABEL else label)
    st.caption('Data origin: '+label)
    st.caption('On-time completion uses mature known outcomes. Pending and missing are excluded from rates and reported separately. Response uses comparable check-ins and a full 48-hour follow-up; no message means Not applicable.')
    display=pd.DataFrame(rows)
    for row in rows:
        rate='Not applicable' if row['response_rate'] is None else f"{row['response_rate']:.1%}"
        st.write(f"{row['group'].capitalize()}: {row['on_time']}/{row['eligible_outcomes']} mature known outcomes completed on time; "
                 f"{row['pending_outcomes']} pending and {row['missing_outcomes']} missing. "
                 f"Responses: {row['responses']}/{row['eligible_response_followup']} eligible check-ins ({rate}); "
                 f"{row['pending_response_followup']} awaiting full follow-up, {row['no_message']} without a message.")
    display.insert(0,'result_label',label)
    for c in ('completion_rate','response_rate'):
        display[c]=display[c].map(lambda x:'Not applicable' if pd.isna(x) else f'{x:.1%}')
    display.columns=[c.replace('_',' ').capitalize() for c in display]
    st.dataframe(display,hide_index=True,width='stretch')
    for metric,d in diffs.items():
        pp='Not defined' if d['percentage_points'] is None else f"{d['percentage_points']:+.1f} percentage points"
        relative='Not defined' if d['relative_percent'] is None else f"{d['relative_percent']:+.1f}% relative change"
        st.write(metric.replace('_',' ').capitalize()+': '+pp+'; '+relative)
    st.info('Arithmetic example only: 40% to 50% = +10 percentage points and +25% relative change. This is not a pilot finding.')
    st.caption('The illustrative groups use the same fixed outcome pattern; the example was not generated to prove that support works. Observational comparisons cannot establish causality.')
    export=pd.DataFrame(rows); export.insert(0,'result_label',label)
    st.download_button('Download labelled pilot metrics',export.to_csv(index=False),'pilot_metrics.csv')
    source=f.copy(); source.insert(0,'result_label',label)
    st.download_button('Download labelled demonstration records',source.to_csv(index=False),'pilot_records_labelled.csv')
    with st.expander('Input format and validation'):
        st.write('Required CSV columns: '+', '.join(FIELDS))
        st.write('UTC-offset timestamps; optional completion/dispatch/response fields may be blank. Outcomes: on_time, late, not_completed, missing, pending. Groups: baseline/support. dataset_kind: synthetic or real, never mixed. delivery_status: none, simulated (synthetic only), verified, unverified. One comparable check-in and its first response per participant. observed_through is the last reliable observation, not the upload time. A labelled export includes result_label for disclosure; remove that extra column to use the strict input template.')
        st.write('Duplicate IDs, inconsistent assignments, invalid outcomes, changed deadlines, impossible or naive timestamps and mixed cohort types are rejected. Real delivery provenance must be verified outside this demonstration.')
