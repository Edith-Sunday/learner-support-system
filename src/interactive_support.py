"""Local-only support threads. No transport or external messaging client."""
import json
from src.interactive_store import saved_now
from src.staff_store import StaffStore, STAFF, STATUSES

CATEGORIES=['Difficulty understanding the chemistry','Difficulty managing time or meeting deadlines',
            'Connectivity or offline-access difficulties','Other / needs discussion']
LEGACY={'Content difficulty':CATEGORIES[0],'Deadline difficulty':CATEGORIES[1],'Connectivity difficulty':CATEGORIES[2]}

class SupportService:
    def __init__(self,store):
        self.store=store
        self.staff=StaffStore(store.path)
        with store.transaction() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS support_barriers(id INTEGER PRIMARY KEY,student_id TEXT,module_id INTEGER,
              category TEXT,source TEXT,details TEXT,staff TEXT,effective_at TEXT,created_at TEXT,request_key TEXT UNIQUE);
            CREATE TABLE IF NOT EXISTS support_drafts(id INTEGER PRIMARY KEY,student_id TEXT,module_id INTEGER,
              channel TEXT,message TEXT,staff TEXT,effective_at TEXT,created_at TEXT,request_key TEXT UNIQUE);
            CREATE TABLE IF NOT EXISTS demo_outbox(id INTEGER PRIMARY KEY,draft_id INTEGER UNIQUE,student_id TEXT,module_id INTEGER,
              channel TEXT,message TEXT,staff TEXT,dispatched_at TEXT,created_at TEXT,request_key TEXT UNIQUE);
            CREATE TABLE IF NOT EXISTS demo_responses(id INTEGER PRIMARY KEY,message_id INTEGER,student_id TEXT,
              response TEXT,help_requested INTEGER,effective_at TEXT,created_at TEXT,request_key TEXT UNIQUE);
            ''')

    def barrier(self,sid):
        rows=self.store.read('SELECT * FROM support_barriers WHERE student_id=? AND module_id=1 ORDER BY id DESC',(sid,))
        if rows: return rows[0]
        old=[a for a in self.staff.actions(self.store.clock(),sid,1) if a['kind']=='challenge']
        if old:
            p=old[-1]['payload']
            return dict(category=LEGACY.get(p['category'],CATEGORIES[3]),source=p['confirmed_by'],details=p.get('details',''))
        return None

    def confirm(self,sid,category,source,details,staff,key):
        self.store.state(sid); self.store._staff(staff,details)
        if category not in CATEGORIES or source not in ('student','teacher'): raise ValueError('Choose a category and confirmation source.')
        with self.store.transaction() as db:
            old=db.execute('SELECT student_id,category,source,details FROM support_barriers WHERE request_key=?',(key,)).fetchone()
            if old:
                if tuple(old)!=(sid,category,source,details): raise ValueError('Request already used for another confirmation.')
                return
            db.execute('INSERT INTO support_barriers(student_id,module_id,category,source,details,staff,effective_at,created_at,request_key) VALUES(?,1,?,?,?,?,?,?,?)',
                       (sid,category,source,details,staff,self.store._clock(db).isoformat(),saved_now(),key))

    def suggested(self,sid):
        state=self.store.state(sid); barrier=self.barrier(sid)
        opening=f"Hello {sid}, "
        if state['current_module']==2:
            return opening+'your Module 1 work is complete. Module 2 is waiting for content; no action is due for it. Would you like help revising Module 1?'
        remaining=[]
        if not state['practice_submitted']: remaining.append('submit practice')
        if not state['quiz_passed']: remaining.append('pass the quiz with at least 8/10')
        category=barrier['category'] if barrier else None
        if category==CATEGORIES[0]:
            text='Review Module 1 Lesson: formulae and atom counting, coefficients versus subscripts, and the worked balancing examples. Practice P1 covers diatomic elements, P2 atom counting and P3 combustion.'
            quizzes=[r for r in state['attempts'] if r['kind']=='quiz' and r['source']=='online']
            if quizzes:
                skills=sorted({r['skill'] for r in json.loads(quizzes[-1]['answers']) if not r['correct']})
                if skills: text+=' Your latest recorded quiz feedback identifies questions to revisit on: '+', '.join(skills)+'. This is question feedback, not a diagnosis.'
        elif category==CATEGORIES[1]:
            text='Remaining work: '+', then '.join(remaining)+'. Original deadline: '+state['deadline']+'. Agree a manageable study plan with your teacher.'
        elif category==CATEGORIES[2]:
            text='Download the Module 1 lesson, practice worksheet and learner quiz from your workspace. Your teacher can record offline completion, including when it occurred. The same practice and 80% quiz requirements apply.'
        else:
            text='What help would you find useful with Module 1? Please tell your teacher whether you need an explanation, help planning study time, offline materials, or something else.'
        if state['available_grants']:
            text+=f" You currently have {state['available_grants']} authorised additional quiz attempt(s). Your original deadline is unchanged."
        elif state['learning_status']=='Overdue':
            text+=' A further quiz attempt needs teacher authorisation; this message grants no extension or attempt.'
        return opening+text

    def draft(self,sid,message,staff,key):
        state=self.store.state(sid); self.store._staff(staff,message)
        with self.store.transaction() as db:
            old=db.execute('SELECT id,student_id,message FROM support_drafts WHERE request_key=?',(key,)).fetchone()
            if old:
                if old['student_id']!=sid or old['message']!=message: raise ValueError('Draft key already used.')
                return old['id']
            cur=db.execute('INSERT INTO support_drafts(student_id,module_id,channel,message,staff,effective_at,created_at,request_key) VALUES(?,1,?,?,?,?,?,?)',
                (sid,state['preference'],message,staff,self.store._clock(db).isoformat(),saved_now(),key))
            return cur.lastrowid

    def dispatch(self,draft_id,staff,key):
        self.store._staff(staff,'Simulate sending')
        with self.store.transaction() as db:
            d=db.execute('SELECT * FROM support_drafts WHERE id=?',(draft_id,)).fetchone()
            if d is None: raise ValueError('Save a draft first.')
            old=db.execute('SELECT * FROM demo_outbox WHERE request_key=? OR draft_id=?',(key,draft_id)).fetchone()
            if old:
                if old['draft_id']!=draft_id: raise ValueError('Dispatch key already used.')
                return old['id']
            channel=db.execute('SELECT preference FROM learners WHERE student_id=?',(d['student_id'],)).fetchone()[0]
            if channel!=d['channel']: raise ValueError('Preference changed. Save a new draft using the current preferred channel.')
            cur=db.execute('INSERT INTO demo_outbox(draft_id,student_id,module_id,channel,message,staff,dispatched_at,created_at,request_key) VALUES(?,?,?,?,?,?,?,?,?)',
                (draft_id,d['student_id'],d['module_id'],d['channel'],d['message'],staff,self.store._clock(db).isoformat(),saved_now(),key))
            return cur.lastrowid

    def respond(self,sid,mid,text,help_requested,key):
        if not text.strip(): raise ValueError('Enter a response.')
        with self.store.transaction() as db:
            message=db.execute('SELECT * FROM demo_outbox WHERE id=? AND student_id=?',(mid,sid)).fetchone()
            if message is None: raise ValueError('Message does not belong to this learner.')
            old=db.execute('SELECT message_id,student_id,response,help_requested FROM demo_responses WHERE request_key=?',(key,)).fetchone()
            if old:
                if tuple(old)!=(mid,sid,text,int(help_requested)): raise ValueError('Response key already used.')
                return
            db.execute('INSERT INTO demo_responses(message_id,student_id,response,help_requested,effective_at,created_at,request_key) VALUES(?,?,?,?,?,?,?)',
                (mid,sid,text,int(help_requested),self.store._clock(db).isoformat(),saved_now(),key))

    def messages(self,sid):
        return self.store.read('SELECT * FROM demo_outbox WHERE student_id=? ORDER BY id',(sid,))


def conversation(store,sid):
    import streamlit as st
    from src.dashboard_ui import date_label
    service=SupportService(store)
    messages=service.messages(sid)
    if not messages: st.caption('No messages yet.')
    for message in messages:
        with st.container(border=True):
            st.caption(message['staff']+' · '+date_label(message['dispatched_at']))
            st.write(message['message'])
            for response in store.read('SELECT response,help_requested,effective_at FROM demo_responses WHERE message_id=? ORDER BY id',(message['id'],)):
                st.markdown('**Learner reply**')
                st.write(response['response'])
                if response['help_requested']: st.caption('More help requested')
    return messages


def staff_support_ui(store,sid,staff):
    import streamlit as st
    import pandas as pd
    from src.interactive_ui import action_token,successful,request_text,demo_name,action_staff
    service=SupportService(store); state=store.state(sid); barrier=service.barrier(sid)
    st.subheader('Support conversation')
    conversation(store,sid)
    st.write('Confirmed need: '+(barrier['category'] if barrier else 'Not confirmed — start with a check-in'))
    for request in store.read('SELECT message FROM requests WHERE student_id=? ORDER BY id DESC LIMIT 1',(sid,)):
        st.info('Help requested: '+request_text(request['message']))
    with st.expander('1. Review need'):
        with st.form('barrier-'+sid):
            staff=action_staff('need-'+sid)
            category=st.selectbox('Support category',CATEGORIES)
            source=st.selectbox('Confirmed by',['student','teacher'])
            details=st.text_area('What help is needed?')
            confirmed=st.checkbox('The learner or teacher confirmed this need')
            if st.form_submit_button('Save support need'):
                try:
                    if not confirmed: raise ValueError('Please confirm the need with the learner or teacher.')
                    service.confirm(sid,category,source,details,staff,action_token('barrier-'+sid))
                    successful('Support need saved.','barrier-'+sid)
                except ValueError as e: st.error(str(e))
    with st.expander('2. Prepare message'):
        staff=action_staff('draft-'+sid)
        st.caption('Preferred channel: '+state['preference'])
        context=str(barrier)+str(state['available_grants'])+state['learning_status']
        suggested=service.suggested(sid).replace('Hello '+sid+',','Hello '+demo_name(sid)+',')
        text=st.text_area('Review and edit draft',suggested,key='support-compose-'+sid+context)
        if st.button('Save draft'):
            try:
                service.draft(sid,text,staff,action_token('support-draft-'+sid))
                successful('Draft saved — not sent.','support-draft-'+sid)
            except ValueError as e: st.error(str(e))
    drafts=store.read('SELECT * FROM support_drafts WHERE student_id=? ORDER BY id DESC',(sid,))
    with st.expander('3. Review and send'):
        if not drafts: st.caption('Prepare and save a draft first.')
        else:
            did=st.selectbox('Saved draft',[d['id'] for d in drafts],format_func=lambda n:'Draft '+str(n))
            d=next(d for d in drafts if d['id']==did)
            st.write(d['message']); st.caption('Preferred channel: '+d['channel'])
            already=store.read('SELECT id FROM demo_outbox WHERE draft_id=?',(did,))
            if already: st.info('This draft has been sent inside the demo.')
            else:
                staff=action_staff('send-'+sid)
                st.caption('Nothing is sent by SMS, WhatsApp or email')
                if st.button('Send demo message',type='primary'):
                    try:
                        service.dispatch(did,staff,action_token('dispatch-'+str(did)))
                        successful('Demo message sent to the learner workspace.')
                    except ValueError as e: st.error(str(e))
    review=service.staff.state(store.clock(),sid,1)
    with st.expander('4. Follow up'):
        with st.form('thread-followup-'+sid):
            actor=action_staff('followup-'+sid)
            assigned=st.selectbox('Assigned teacher',STAFF,index=STAFF.index(review['staff']),key='followup-staff-'+sid)
            status=st.selectbox('Follow-up status',STATUSES,index=STATUSES.index(review['status']))
            follow=st.date_input('Follow-up date',value=pd.Timestamp(review['follow_up']).date() if review.get('follow_up') else None)
            notes=st.text_area('Follow-up notes',review.get('notes',''))
            if st.form_submit_button('Save follow-up'):
                if not actor:
                    st.error('Choose your name to record this action.')
                else:
                    service.staff.record(sid,1,'review',store.clock(),dict(staff=assigned,status=status,notes=notes,follow_up=str(follow) if follow else None,recorded_by=actor),action_token('thread-follow-'+sid))
                    successful('Follow-up saved.','thread-follow-'+sid)


def learner_messages_ui(store,sid):
    import streamlit as st
    from src.interactive_ui import action_token,successful
    service=SupportService(store)
    st.caption('Demo messages stay inside this app.')
    messages=conversation(store,sid)
    if not messages: return
    mid=st.selectbox('Reply to',[m['id'] for m in messages],format_func=lambda n:'Message '+str(n))
    with st.form('response-'+sid+'-'+str(mid)):
        response=st.text_area('Your reply')
        help_requested=st.checkbox('I would like more help')
        if st.form_submit_button('Send reply'):
            try:
                service.respond(sid,mid,response,help_requested,action_token('reply-'+sid+'-'+str(mid)))
                successful('Reply saved for your teacher.','reply-'+sid+'-'+str(mid))
            except ValueError as e: st.error(str(e))
