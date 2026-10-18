"""Learner and connected teacher demonstration views. No synthetic model predictions."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

import pandas as pd
import streamlit as st

from src.chemistry_content import TITLE, LESSON, PRACTICE, QUIZ, worksheet
from src.dashboard_ui import date_label, duration_label, last_assessed_label
from src.interactive_store import InteractiveStore, utc
from src.interactive_assessment import AssessmentService
from src.staff_store import StaffStore, STAFF, STATUSES, CHALLENGES
from src.simulate import ROOT

UNSCORED = 'Experimental checkpoint assessment is available to staff at days 3, 7 and 10; processing runs when the app is used.'
NO_ASSESSMENT = 'No assessment due — waiting for content.'
WAITING = 'Module 1 complete. Module 2 is not available yet.'


def display(frame):
    if not len(frame):
        st.caption('No records yet.')
        return
    frame=pd.DataFrame(frame)
    labels={'student_id':'Learner ID','module_id':'Module','enrolled_at':'Enrolled','preference':'Preferred channel',
            'event_time':'Occurred (UTC)','recorded_at':'Recorded (demo UTC)','created_at':'Saved (actual UTC)',
            'effective_at':'Effective (demo UTC)','unlock_time':'Unlocked','deadline':'Original deadline',
            'completion_time':'Completion occurrence','recognized_at':'Completion recognised', 'score':'Score / 10',
            'kind':'Record type','source':'Route','grant_id':'Grant','quantity':'Authorised attempts','used':'Used attempts',
            'staff':'Teacher','reason':'Reason','message':'Support request','learning_status':'Learning status',
            'duration_minutes':'Session duration (minutes)','active_minutes':'Estimated active time (minutes)',
            'started_at':'Started (actual UTC)','ended_at':'Ended (actual UTC)','end_reason':'Session ending',
            'checkpoint':'Checkpoint day','scheduled_at':'Scheduled checkpoint','assessed_at':'Processed (demo UTC)',
            'content_status':'Content / queue status'}
    labels.update(message_id='Message ID',response='Learner response',help_requested='More help requested',
                  experimental_score='Experimental score',retrospective='Calculated later',model_identity='Model version')
    for col in frame:
        if col in ('duration_minutes','active_minutes'):
            frame[col]=frame[col].map(lambda x:f'{x:.2f}' if pd.notna(x) else 'Not recorded')
        if col.endswith('_at') or col in ('event_time','deadline','unlock_time','completion_time'):
            frame[col]=frame[col].map(lambda t: date_label(t) if t else 'Not recorded')
    # Wrapped HTML preserves long reasons/requests rather than clipping them.
    st.html('<style>.demo-table{max-height:350px;overflow:auto}.demo-table table{width:100%;border-collapse:collapse;table-layout:auto;min-width:560px;font-size:14px}.demo-table th,.demo-table td{padding:9px;border-bottom:1px solid #dce5e5;text-align:left;overflow-wrap:break-word}.demo-table th{background:#eff5f5}</style><div class="demo-table" tabindex="0">'+frame.rename(columns=labels).to_html(index=False,escape=True,na_rep='Not recorded')+'</div>')


def action_token(key):
    key='token-'+key
    st.session_state.setdefault(key,str(uuid.uuid4()))
    return st.session_state[key]


def successful(message, key=None):
    if key:
        st.session_state.pop('token-'+key,None)
    st.session_state['interactive_notice']=message
    st.rerun()


def go(section):
    st.session_state['learning_section']=section


def feedback(record,kind):
    questions=PRACTICE if kind=='practice' else QUIZ
    st.subheader('Results and feedback')
    if record['source']=='offline':
        st.write(f"Teacher-recorded score: {record['score']}/10" if kind=='quiz' else 'Teacher-recorded practice submitted.')
        st.info('Only an aggregate result was recorded. No question-level answers or skill diagnoses are available.')
        return
    results=json.loads(record['answers'])
    score=record['score']
    notice=st.warning if kind=='quiz' and score<8 else st.success
    notice(f"Score: {score}/{len(questions)}" + (f" ({score*10}%) — {'Passed' if score>=8 else 'Not yet passed'}" if kind=='quiz' else ' — practice submission recorded'))
    if kind=='quiz':
        st.caption('Pass mark: 8/10 (80%). Review the questions below to see what to practise.')
    for q,r in zip(questions,results):
        with st.expander(f"{q['id']} · {'Correct' if r['correct'] else 'Incorrect'} · {q['skill']}",expanded=not r['correct']):
            st.write(q['prompt'])
            st.write('Your answer: '+str(r['answer']))
            st.write('Correct answer: '+(', '.join(map(str,q['answer'])) if isinstance(q['answer'],tuple) else q['answer']))
            st.write(q['explanation'])
            if kind=='practice':
                st.caption('Hint: '+q['hint'])
    st.caption('Review formulae and atom counting in Lesson. Practise diatomic elements in P1, atom counting in P2, and combustion in P3; the iron worked example explains odd/even counts.')
    a,b=st.columns(2)
    a.button('Review the lesson',on_click=go,args=('Lesson',),key=f'lesson-{kind}')
    b.button('Go to practice',on_click=go,args=('Practice',),key=f'practice-{kind}')


def assessment(store,sid,kind):
    state=store.state(sid)
    questions=PRACTICE if kind=='practice' else QUIZ
    draft=store.draft(sid,kind)
    submitted=store.read('SELECT * FROM submissions WHERE request_key=?',(draft['token'],))
    if submitted:
        feedback(submitted[0],kind)
        if st.button('Start another practice' if kind=='practice' else 'Start another quiz',key=f'new-{kind}'):
            store.draft(sid,kind,new=True)
            st.rerun()
        return
    st.caption('Enter the smallest positive whole numbers below each formula, including 1. Start with your own answers; every box must be filled.')
    if kind=='quiz':
        st.write('10 questions · 1 mark each · Pass: 8/10 (80%)')
        st.caption('Your answers save as you work.')
        if not state['quiz_allowed']:
            st.warning('You need an extra attempt from your teacher. You can still practise.')
            st.button('Request help',on_click=go,args=('My support',),key='quiz-help')
    saved=json.loads(draft['answers'])
    entry=st.session_state.get('assessment_entry','initial')
    keys={q['id']:f"answer-{draft['token']}-{entry}-{q['id']}" for q in questions}
    def current_answers():
        return {q['id']:(','.join(st.session_state.get(keys[q['id']]+f'-{i}','') for i in range(len(q['answer'])))
                         if q['type']=='coefficients' else st.session_state.get(keys[q['id']])) for q in questions}
    def persist(qid,index=None):
        # Save only the changed field. Navigation can remove other widget keys;
        # treating those absent widgets as blank would erase an existing draft.
        key=keys[qid]+(f'-{index}' if index is not None else '')
        if key not in st.session_state:
            return
        previous=json.loads(store.draft(sid,kind)['answers'])
        if index is None:
            previous[qid]=st.session_state[key]
        else:
            question=next(q for q in questions if q['id']==qid)
            parts=str(previous.get(qid) or '').split(',')
            parts=(parts+['']*len(question['answer']))[:len(question['answer'])]
            parts[index]=st.session_state[key]
            previous[qid]=','.join(parts)
        store.save_draft(sid,kind,draft['token'],previous)
    for q in questions:
        with st.container(border=True):
            st.markdown(f"**{q['id']}. {q['prompt']}**")
            if q['type']=='coefficients':
                # One formula per row remains readable without horizontal scrolling on phones.
                i=0
                for side,label in zip(q['prompt'].split('→'),('Reactants','Products →')):
                    st.caption(label)
                    for formula in side.split('+'):
                        st.markdown('**'+formula.strip()+'**')
                        parts=str(saved.get(q['id']) or '').split(',')
                        st.text_input(f"{q['id']} coefficient {i+1} for {formula.strip()}",value=parts[i] if i<len(parts) else '',key=keys[q['id']]+f'-{i}',on_change=persist,args=(q['id'],i),placeholder='Whole number',label_visibility='collapsed')
                        i+=1
            else:
                st.radio(f"{q['id']} answer",['A','B','C','D'],index='ABCD'.index(saved[q['id']]) if saved.get(q['id']) in ('A','B','C','D') else None,format_func=lambda option,q=q:q['options'][ord(option)-65],key=keys[q['id']],on_change=persist,args=(q['id'],))
            if kind=='practice':
                with st.expander('Hint'):
                    st.write(q['hint'])
    if st.button('Submit practice' if kind=='practice' else 'Submit quiz',type='primary'):
        answers=current_answers()
        try:
            store.submit(sid,kind,answers,draft['token'])
            successful('Submission recorded once. Your results are ready.')
        except ValueError as error:
            st.error(str(error))


def demo_name(sid):
    names={'DEMO001':'Alex','DEMO002':'Bella','DEMO003':'Chris','DEMO004':'Dara',
           'DEMO005':'Emeka','DEMO006':'Farah','DEMO007':'Grace'}
    return names.get(sid,'Learner '+sid.removeprefix('DEMO'))+' (demo)'


def request_text(text):
    for prefix in ('Browser demonstration: ', 'Seeded demonstration request: '):
        if text.startswith(prefix): return text[len(prefix):]
    return text


def remaining_work(state):
    parts=[]
    if not state['practice_submitted']: parts.append('Submit practice')
    if not state['quiz_passed']: parts.append('Pass the quiz at 80%')
    return ' · '.join(parts) if parts else 'All Module 1 requirements complete'


def learner_view(store):
    st.title('My learning' if st.session_state.get('learning_section','My learning')=='My learning' else 'Chemistry workspace')
    learners=store.learners()
    with st.expander('Choose a demo learner',expanded=not learners):
        if learners:
            sid=st.selectbox('Learner',[r['student_id'] for r in learners],format_func=demo_name,key='interactive_learner')
        channel=st.selectbox('Preferred contact channel',['SMS','WhatsApp','email'],key='enrol-channel')
        if st.button('Enrol new demo learner'):
            sid=store.enrol(channel)
            st.session_state['interactive_learner']=sid
            successful('Learner enrolled.')
    if not learners:
        st.info('Choose Enrol new demo learner to begin.'); return
    state=store.state(sid)
    section=st.sidebar.radio('Learning sections',['My learning','Lesson','Practice','Quiz and results','My support'],key='learning_section')
    if st.session_state.get('assessment_page')!=(sid,section):
        st.session_state['assessment_page']=(sid,section)
        st.session_state['assessment_entry']=str(uuid.uuid4())
    st.caption(demo_name(sid)+' · Module 1 · '+TITLE)
    if section=='My learning':
        st.subheader('Module 1 · '+state['learning_status'])
        if state['current_module']==2:
            st.info(WAITING)
        else:
            st.write('Deadline: **'+date_label(state['deadline'])+'**')
        for label,value in [('Practice submitted',state['practice_submitted']),('Quiz passed',state['quiz_passed'])]:
            st.write(('✓ ' if value else '○ ')+label+(' — Yes' if value else ' — Not yet'))
        if state['current_module']==2:
            target,label='My support','View support'
        elif not state['quiz_allowed']:
            target,label='My support','View support'
        elif not state['practice_submitted']:
            target,label='Lesson','Continue lesson'
        else:
            target,label='Quiz and results','Take quiz'
        st.button(label,on_click=go,args=(target,),type='primary')
    elif section=='Lesson':
        st.markdown(LESSON)
        st.download_button('Download lesson',LESSON,'chemistry_lesson.md',mime='text/markdown')
        st.button('Complete practice',on_click=go,args=('Practice',),type='primary')
    elif section=='Practice':
        st.subheader('Practice')
        st.write('Submit all three answers. Practice does not use a quiz attempt.')
        st.download_button('Download practice worksheet',worksheet(PRACTICE),'chemistry_practice.txt')
        assessment(store,sid,'practice')
    elif section=='Quiz and results':
        st.subheader('Quiz and results')
        st.write('To complete Module 1: '+remaining_work(state))
        if state['current_module']==1:
            st.caption('Deadline: '+date_label(state['deadline'])+f" · Extra attempts available: {state['available_grants']}")
        st.download_button('Download quiz',worksheet(QUIZ),'chemistry_quiz.txt')
        assessment(store,sid,'quiz')
        with st.expander('Previous results'):
            for record in [r for r in state['attempts'] if r['kind']=='quiz']:
                st.write(f"{record['score']*10}% · {date_label(record['event_time'])} · {'Passed' if record['score']>=8 else 'Not yet passed'}")
    else:
        from src.interactive_support import learner_messages_ui
        st.subheader('My support')
        learner_messages_ui(store,sid)
        with st.expander('Request help'):
            message=st.text_area('What would you like help with?')
            if st.button('Send help request'):
                try:
                    store.request_help(sid,message,action_token(f'help-{sid}'))
                    successful('Your teacher can now see your request.',f'help-{sid}')
                except ValueError as error: st.error(str(error))
            display(store.read('SELECT message,effective_at FROM requests WHERE student_id=?',(sid,)))
        with st.expander('Communication preference'):
            channel=st.selectbox('Preferred channel',['SMS','WhatsApp','email'],index=['SMS','WhatsApp','email'].index(state['preference']))
            if st.button('Save preference'):
                store.preference(sid,channel); successful('Preference saved.')
    with st.expander('Study timer'):
        st.caption('Session time includes breaks. Select End session when you finish.')
        service=AssessmentService(store)
        if st.button('Start session'): service.start_session(sid)
        service.touch_session(sid)
        if st.button('End session'): service.touch_session(sid,end=True)
        display(store.read('SELECT started_at,ended_at,duration_minutes,active_minutes FROM study_sessions WHERE student_id=? ORDER BY started_at DESC',(sid,)))


def action_staff(key):
    return st.selectbox('Your name',STAFF[1:],index=None,placeholder='Choose your name to record this action',key='actor-'+key)


def selected_support_rows(service,limit=10):
    """Existing top-N model ordering with boundary ties; only saved numeric results."""
    ranked=[r for r in service.review_rows('Model ordering') if r['score'] is not None]
    if len(ranked)<=limit: return ranked
    boundary=ranked[int(limit)-1]['priority_group']
    return [r for r in ranked if r['priority_group']<=boundary]


def open_support_learner(sid):
    st.session_state['staff_profile_learner']=sid


def teacher_controls(store,sid,state,staff):
    st.caption('Module 1 quiz and offline work')
    with st.expander('Authorise additional quiz attempts'):
        token=action_token('grant-'+sid)
        recorded=store.read('SELECT id,quantity FROM quiz_grants WHERE request_key=?',(token,))
        if recorded:
            st.success(f"Grant {recorded[0]['id']} recorded once: {recorded[0]['quantity']} additional attempts.")
            if st.button('Prepare another grant'):
                successful('Ready for a new authorisation.','grant-'+sid)
        else:
            with st.form('grant-'+sid):
                staff=action_staff('grant-'+sid)
                quantity=st.selectbox('Additional attempts',[1,2])
                reason=st.text_input('Reason for authorisation')
                if st.form_submit_button('Allow extra attempts'):
                    try:
                        store.grant(sid,quantity,staff,reason,token)
                        successful('Additional attempts authorised. Original deadline unchanged.')
                    except ValueError as error:
                        st.error(str(error))
    with st.expander('Record offline practice or quiz'):
        st.caption('Enter when the work was completed, in UTC. A late quiz needs an extra attempt authorised before that time.')
        token=action_token('offline-'+sid)
        recorded=store.read('SELECT id FROM submissions WHERE request_key=?',(token,))
        if recorded:
            st.success(f"Offline record {recorded[0]['id']} saved once.")
            if st.button('Prepare another offline record'):
                successful('Ready for another offline record.','offline-'+sid)
        else:
            # A fresh role/learner entry must not revive a stale hidden widget
            # whose browser label and server-side selection have diverged.
            context=(sid,st.session_state.get('interactive_role_entry'))
            if st.session_state.get('offline_context')!=context:
                st.session_state['offline_context']=context
                st.session_state['offline_entry']=str(uuid.uuid4())
            kind=st.selectbox('Offline record type',['practice','quiz'],key='offline-kind-'+st.session_state['offline_entry'])
            with st.form('offline-'+sid+'-'+kind):
                staff=action_staff('offline-'+sid)
                at=store.clock()
                st.write('When did the learner complete this?')
                completed_date=st.date_input('Completion date (UTC)',at.date())
                completed_time=st.time_input('Completion time (UTC)',at.time(),step=60)
                score=st.number_input('Quiz score out of 10',min_value=0,max_value=10,step=1) if kind=='quiz' else None
                reason=st.text_input('Offline evidence / teacher note')
                if st.form_submit_button('Record offline result'):
                    try:
                        occurrence=utc(datetime.combine(completed_date,completed_time).replace(tzinfo=timezone.utc))
                        if completed_date==at.date() and (completed_time.hour,completed_time.minute)==(at.hour,at.minute):
                            occurrence=at
                        store.submit(sid,kind,None,token,score=int(score) if kind=='quiz' else None,occurrence=occurrence,staff=staff,reason=reason)
                        successful('Offline record saved; progression refreshed.')
                    except ValueError as error:
                        st.error(str(error))
    with st.expander('Teacher answer key · Module 1'):
        st.caption('Teacher demonstration access only. Role switching is not authentication.')
        st.text(worksheet(PRACTICE,True)+'\n'+worksheet(QUIZ,True))
        st.download_button('Download teacher answer key',worksheet(PRACTICE,True)+'\n'+worksheet(QUIZ,True),'teacher_answer_key.txt')


def demo_controls(store,staff):
    with st.sidebar.expander('Demo controls'):
        st.caption('Use this to demonstrate check-ins and missed deadlines without waiting.')
        st.write('Demo date: '+date_label(store.clock()))
        days=st.number_input('Days forward',min_value=0,max_value=365,step=1)
        minutes=st.number_input('Additional minutes',min_value=0,max_value=1439,step=1)
        staff=action_staff('date-change')
        reason=st.text_input('Reason for date change')
        st.caption('This changes the demo date for all learners in this demonstration.')
        if st.button('Move demo date forward'):
            try:
                store.advance(store.clock()+pd.Timedelta(days=int(days),minutes=int(minutes)),staff,reason)
                successful('Demo date moved forward.')
            except ValueError as error: st.error(str(error))
        st.markdown('**Demo guide**')
        for person in store.learners():
            state=store.state(person['student_id'])
            summary=('Completed Module 1' if state['current_module']==2 else 'Missed a deadline' if state['learning_status']=='Overdue' else 'Ready to take a quiz' if state['practice_submitted'] else 'Working through Module 1')
            if person['student_id']=='DEMO007': summary='Needs help with balancing equations'
            st.caption(demo_name(person['student_id'])+' — '+summary)


def staff_view(store):
    page=st.sidebar.radio('Staff pages',['All learners','Needs attention','Support messages','Model evaluation'])
    staff=None
    demo_controls(store,staff)
    st.title(page)
    if page=='Model evaluation':
        from src.evaluation_ui import render_evaluation
        render_evaluation(store); return
    people=store.learners()
    if not people: st.info('No learners yet. Enrol a learner in the learner workspace.'); return
    service=AssessmentService(store); support_store=StaffStore(store.path)
    states={p['student_id']:store.state(p['student_id']) for p in people}
    chosen=list(states)
    if page=='Needs attention':
        period=st.radio('View',['Before the deadline','Deadline missed'],horizontal=True)
        if period=='Deadline missed':
            st.subheader('Deadline missed')
            chosen=[r['student_id'] for r in store.overdue()]
        else:
            st.subheader('May need support')
            st.caption('Check in with these learners before their deadline.')
            chosen=[r['student_id'] for r in selected_support_rows(service,st.session_state.get('review_limit',10))]
        assigned=st.selectbox('Assigned teacher',['All']+STAFF,key='attention-assigned')
        chosen=[sid for sid in chosen if assigned=='All' or support_store.state(store.clock(),sid,1)['staff']==assigned]
    if page=='Support messages':
        requests=store.read('SELECT student_id,message,effective_at FROM requests ORDER BY id DESC')
        with st.expander('Help requests',expanded=True):
            display([{'Learner':demo_name(r['student_id']),'Request':request_text(r['message']),'Received':date_label(r['effective_at'])} for r in requests])
    else:
        if page=='All learners':
            search=st.text_input('Search learners',placeholder='Name or learner ID')
            a,b=st.columns(2)
            status=a.selectbox('Progress',['All','In progress','Overdue','Completed on time','Completed late'])
            assigned=b.selectbox('Assigned teacher',['All']+STAFF)
            chosen=[sid for sid in chosen if (not search or search.lower() in (demo_name(sid)+' '+sid).lower())
                    and (status=='All' or states[sid]['learning_status']==status)
                    and (assigned=='All' or support_store.state(store.clock(),sid,1)['staff']==assigned)]
        rows=[]
        for sid in chosen:
            state=states[sid]; review=support_store.state(store.clock(),sid,1)
            row={'Learner':demo_name(sid),'Module':state['current_module'],
                 'Progress':remaining_work(state),'Deadline / status':date_label(state['deadline']) if state['current_module']==1 else 'Waiting for content','Assigned teacher':review['staff']}
            rows.append(row)
        if page=='Needs attention':
            st.html('<style>[class*="st-key-review-support-"] button * {white-space:normal!important;overflow:visible!important;text-overflow:clip!important;-webkit-line-clamp:unset!important}</style>')
            labels=['Learner','Module','Deadline / days remaining','Practice submitted','Latest quiz result','Assigned teacher','Review and support']
            widths=[1.2,.55,1.5,.8,.8,1.1,1.2]
            for col,label in zip(st.columns(widths),labels): col.markdown('**'+label+'**')
            for sid in chosen:
                state=states[sid]; review=support_store.state(store.clock(),sid,1)
                quiz=[r for r in state['attempts'] if r['kind']=='quiz']
                days=(utc(state['deadline'])-store.clock()).total_seconds()/86400
                timing=f'{days:.1f} days remaining' if days>=0 else f'{abs(days):.1f} days overdue'
                cols=st.columns(widths,vertical_alignment='center')
                values=[demo_name(sid),str(state['current_module']),date_label(state['deadline'])+' · '+timing,
                        'Yes' if state['practice_submitted'] else 'Not yet',str(quiz[-1]['score']*10)+'%' if quiz else 'No result yet',review['staff']]
                for col,value in zip(cols,values): col.write(value)
                cols[-1].button('Review and support',key='review-support-'+sid,on_click=open_support_learner,args=(sid,))
        else:
            display(rows)
    if not chosen:
        st.info('No learners match this view.'); return
    sid=st.selectbox('Open learner',chosen,format_func=demo_name,key='staff_profile_learner')
    state=states[sid]
    st.subheader(demo_name(sid))
    st.caption('Learner ID: '+sid)
    if page=='Support messages':
        from src.interactive_support import staff_support_ui
        staff_support_ui(store,sid,staff)
        return
    progress,quiz,support,history=st.tabs(['Progress','Quiz results','Support','History'])
    with progress:
        if state['current_module']==2: st.info(WAITING)
        else:
            st.write('**'+state['learning_status']+'** · Deadline: '+date_label(state['deadline']))
        st.write('Practice submitted: **'+('Yes' if state['practice_submitted'] else 'Not yet')+'**')
        st.write('Quiz passed: **'+('Yes' if state['quiz_passed'] else 'Not yet')+'**')
        st.write('Next: '+remaining_work(state))
        review=support_store.state(store.clock(),sid,1)
        st.caption('Following up: '+review['staff']+' · '+review['status'])
        for r in store.read('SELECT message FROM requests WHERE student_id=? ORDER BY id DESC LIMIT 1',(sid,)):
            st.info('Help requested: '+request_text(r['message']))
    with quiz:
        quizzes=[r for r in state['attempts'] if r['kind']=='quiz']
        if quizzes:
            latest=quizzes[-1]
            st.subheader(f"Latest quiz: {latest['score']*10}%")
            st.caption('Pass mark: 80% · '+('Passed' if latest['score']>=8 else 'Not yet passed'))
            if latest['source']=='online':
                for q,r in zip(QUIZ,json.loads(latest['answers'])):
                    with st.expander(q['id']+' · '+('Correct' if r['correct'] else 'Review')+' · '+q['skill']):
                        st.write(q['prompt']); st.write('Learner answer: '+str(r['answer'])); st.write(q['explanation'])
            else: st.caption('Teacher-recorded result; individual answers were not recorded.')
        else: st.info('No quiz result yet.')
        teacher_controls(store,sid,state,staff)
        with st.expander('Earlier results and study sessions'):
            display([{'Result':str(r['score']*10)+'%' if r['kind']=='quiz' else 'Practice submitted','Completed':date_label(r['event_time'])} for r in state['attempts']])
            display(store.read('SELECT started_at,ended_at,duration_minutes,active_minutes FROM study_sessions WHERE student_id=?',(sid,)))
    with support:
        from src.interactive_support import staff_support_ui
        staff_support_ui(store,sid,staff)
    with history:
        with st.expander('Learning and extra attempts'):
            display(store.module_history(sid))
            display(store.read('SELECT quantity,used,effective_at,staff,reason FROM quiz_grants WHERE student_id=?',(sid,)))
        with st.expander('Support and earlier drafts'):
            display([{k:a[k] for k in ['kind','module_id','effective_at','payload']} for a in support_store.actions(store.clock(),sid)])
        with st.expander('Date changes'):
            display(store.read('SELECT effective_at,staff,reason FROM clock_history'))


def render(workspace):
    if st.session_state.get('interactive_role')!=workspace:
        st.session_state['interactive_role']=workspace
        st.session_state['interactive_role_entry']=str(uuid.uuid4())
    from src.cloud_demo import demo_database
    store=InteractiveStore(demo_database())
    from src.interactive_support import SupportService
    SupportService(store); AssessmentService(store).run_due()
    st.markdown('<span class="demo-badge">Demo</span>',unsafe_allow_html=True)
    if 'interactive_notice' in st.session_state: st.success(st.session_state.pop('interactive_notice'))
    if workspace=='Learner': learner_view(store)
    else: staff_view(store)


def review_display(row, at):
    assessed=row.get('assessed_at')
    scored=row.get('score') is not None
    elapsed=last_assessed_label(assessed,at) if assessed else 'Never'
    if not scored and elapsed=='Just assessed':
        elapsed='Checked just now'
    return {'Learner ID':row['student_id'],'Experimental score':f"{row['score']:.3f}" if row.get('score') is not None else 'Not yet assessed',
            ('Last assessed' if scored else 'Last checked'):elapsed,
            'Inputs captured':date_label(row['scheduled_at']) if row.get('scheduled_at') else 'No checkpoint yet',
            'Equal priority group':row.get('priority_group','Profile'),
            'Checkpoint':f"Day {row['checkpoint']}" if row.get('checkpoint') else 'Pending',
            'Practice submitted':('Yes' if row['practice_submitted'] else 'Not yet') if 'practice_submitted' in row else 'See current progress below',
            'Quiz passed':('Yes' if row['quiz_passed'] else 'Not yet') if 'quiz_passed' in row else 'See current progress below',
            'Assessment note':row.get('reason') or 'Experimental score; not a confirmed barrier'}


def show_review(rows, at):
    formatted=[review_display(row,at) for row in rows]
    display([{key:value for key,value in row.items() if key!='Assessment note'} for row in formatted])
    for row in formatted:
        note=row['Assessment note']
        for internal,label in [('no_login','login status'),('failed_or_dropped_sessions','failed or interrupted session count'),('time_on_task','total active study time')]:
            note=note.replace(internal,label)
        st.caption(row['Learner ID']+' — '+note)



