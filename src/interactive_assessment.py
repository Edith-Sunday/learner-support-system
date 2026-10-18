"""Audited checkpoint integration; unavailable measurements never become observations."""
import hashlib
import json
import uuid

import joblib
import pandas as pd

from src.interactive_store import utc, saved_now
from src.simulate import ROOT, features_at


class AssessmentService:
    def __init__(self, store):
        self.store = store
        self.order = json.loads((ROOT/'data/model_features.json').read_text())
        from src.interactive_model import FEATURES
        folder=ROOT/'models/interactive_module1'
        path = folder/'logistic_regression.joblib'
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        selection=json.loads((folder/'selection.json').read_text())
        metadata=json.loads((folder/'metadata.json').read_text())
        if selection['selected']!='logistic_regression' or digest!=selection['pipeline_hashes'][path.name]:
            raise ValueError('Module 1 candidate checksum/selection mismatch.')
        self.candidate_order=metadata['feature_order']
        if self.candidate_order!=FEATURES:
            raise ValueError('Module 1 feature order mismatch.')
        self.identity = 'interactive_module1/logistic_regression:sha256:' + digest
        self.pipeline = joblib.load(path)
        if list(self.pipeline.feature_names_in_) != self.candidate_order:
            raise ValueError('Candidate pipeline feature order mismatch.')
        imputer=self.pipeline.named_steps['simpleimputer']
        if imputer.strategy!='median' or not imputer.add_indicator or not imputer.keep_empty_features or list(self.pipeline.named_steps)!=['simpleimputer','standardscaler','logisticregression']:
            raise ValueError('Candidate preprocessing mismatch.')
        with store.transaction() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS study_sessions(
              id TEXT PRIMARY KEY, student_id TEXT, started_at TEXT, ended_at TEXT,
              last_seen TEXT, duration_minutes REAL, active_minutes REAL DEFAULT 0,
              event_time TEXT, recorded_at TEXT, end_reason TEXT);
            CREATE TABLE IF NOT EXISTS assessments(
              student_id TEXT, module_id INTEGER, checkpoint INTEGER, scheduled_at TEXT,
              assessed_at TEXT, saved_at TEXT, features TEXT, model_identity TEXT,
              score REAL, reason TEXT, PRIMARY KEY(student_id,module_id,checkpoint));
            CREATE TABLE IF NOT EXISTS assessment_results(
              student_id TEXT, module_id INTEGER, checkpoint INTEGER, model_identity TEXT,
              scheduled_at TEXT, assessed_at TEXT, saved_at TEXT, features TEXT,
              score REAL, retrospective INTEGER, reason TEXT,
              PRIMARY KEY(student_id,module_id,checkpoint,model_identity));
            ''')

    def start_session(self, sid, wall=None):
        """Explicit study session, never an authenticated login."""
        wall=utc(wall or saved_now()).isoformat()
        with self.store.transaction() as db:
            self.store._module(db,sid)
            if db.execute('SELECT 1 FROM study_sessions WHERE student_id=? AND ended_at IS NULL',(sid,)).fetchone():
                return
            db.execute('INSERT INTO study_sessions(id,student_id,started_at,last_seen,event_time,recorded_at) VALUES(?,?,?,?,?,?)',
                       (str(uuid.uuid4()),sid,wall,wall,self.store._clock(db).isoformat(),self.store._clock(db).isoformat()))

    def touch_session(self, sid, *, end=False, wall=None):
        """A UI interaction confirms presence, not continuous study or connectivity."""
        wall=utc(wall or saved_now())
        with self.store.transaction() as db:
            row=db.execute('SELECT * FROM study_sessions WHERE student_id=? AND ended_at IS NULL',(sid,)).fetchone()
            if row is None:
                return
            gap=(wall-utc(row['last_seen'])).total_seconds()
            if gap < 0:
                raise ValueError('Actual activity time cannot move backwards.')
            # Only short, bounded interaction intervals count towards the observed estimate.
            active=row['active_minutes']+(gap/60 if gap<=60 else 0)
            duration=(wall-utc(row['started_at'])).total_seconds()/60
            db.execute('UPDATE study_sessions SET last_seen=?,active_minutes=?,duration_minutes=?,ended_at=?,recorded_at=?,end_reason=? WHERE id=?',
                       (wall.isoformat(),active,duration,wall.isoformat() if end else None,
                        self.store._clock(db).isoformat(),'Learner ended session' if end else None,row['id']))

    def feature_values(self, sid, at, day):
        at=utc(at)
        records=self.store.read('SELECT * FROM submissions WHERE student_id=?',(sid,))
        events=[dict(event_id=r['id'],module_id=1,event_type=r['kind'],valid=1,
                     event_time=utc(r['event_time']),recorded_at=utc(r['recorded_at']),
                     score_pct=(r['score'] or 0)*10,source='teacher_offline' if r['source']=='offline' else 'online') for r in records]
        values=features_at(events,[],1,at,day)
        # No authenticated login and no reliable interruption instrumentation.
        values.update(days_since_login=None,no_login=None,failed_or_dropped_sessions=None)
        # Mean of known, explicitly closed sessions. Unclosed sessions are not fabricated.
        # Interaction-based active minutes are an estimate, not the original measured active time.
        sessions=self.store.read('SELECT * FROM study_sessions WHERE student_id=? AND ended_at IS NOT NULL',(sid,))
        durations=[r['duration_minutes'] for r in sessions if utc(r['recorded_at'])<=at and utc(r['event_time'])<=at]
        values.update(session_length=sum(durations)/len(durations) if durations else None,time_on_task=None)
        return {name:values[name] for name in self.order}

    def unsupported(self, values):
        # Legacy availability audit; the original full-feature pipeline is not loaded.
        unexpected=[name for name in ('no_login','failed_or_dropped_sessions','time_on_task') if values[name] is None]
        return ('Unavailable measurements never missing in training: '+', '.join(unexpected)+
                '. No authenticated login, reliable interruption telemetry, or complete active-time coverage.') if unexpected else ''

    def run_due(self):
        """Runs on app use, not in the background. Each checkpoint is immutable."""
        at=self.store.clock()
        for learner in self.store.learners():
            sid=learner['student_id']
            state=self.store.state(sid)
            for module in self.store.module_history(sid):
                if not self.store.content_available(module['module_id']):
                    continue
                for day in (3,7,10):
                    due=utc(module['unlock_time'])+pd.Timedelta(days=day)
                    if due>at or (module['recognized_at'] and utc(module['recognized_at'])<=due):
                        continue
                    values=self.feature_values(sid,due,day)
                    reason=self.unsupported(values)
                    if at>due:
                        reason='Checkpoint processed late on app use; no warning was delivered at the scheduled time. '+reason
                    if state['completion_time'] or at>utc(module['deadline']):
                        reason='No longer eligible for early review. '+reason
                    old=self.store.read('SELECT * FROM assessments WHERE student_id=? AND module_id=? AND checkpoint=?',(sid,module['module_id'],day))
                    with self.store.transaction() as db:
                        db.execute('INSERT OR IGNORE INTO assessments VALUES(?,?,?,?,?,?,?,?,?,?)',
                                   (sid,module['module_id'],day,due.isoformat(),at.isoformat(),saved_now(),
                                    json.dumps(values),'observation-v1',None,reason))
                    if module['module_id']!=1 or not self.eligible(sid):
                        continue
                    captured=json.loads(old[0]['features']) if old else values
                    candidate={name:captured[name] for name in self.candidate_order}
                    if candidate['practice_submitted']+candidate['quiz_passed']>=2:
                        continue
                    frame=pd.DataFrame([candidate],columns=self.candidate_order).astype(float)
                    score=float(self.pipeline.predict_proba(frame)[0,1])
                    retro=bool(old) or at>due
                    note=('Calculated later from checkpoint inputs; not an earlier delivered warning.' if retro else
                          'Calculated at checkpoint on app use; assessment is not message delivery.')
                    with self.store.transaction() as db:
                        db.execute('INSERT OR IGNORE INTO assessment_results VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                            (sid,1,day,self.identity,due.isoformat(),at.isoformat(),saved_now(),json.dumps(candidate),score,int(retro),note))

    def eligible(self,sid):
        state=self.store.state(sid)
        return self.store.content_available(1) and state['current_module']==1 and not state['completion_time'] and self.store.clock()<=utc(state['deadline'])

    def latest(self, sid):
        rows=self.store.read('SELECT * FROM assessment_results WHERE student_id=? AND model_identity=? ORDER BY checkpoint DESC LIMIT 1',(sid,self.identity))
        if rows:
            return rows[0]
        rows=self.store.read('SELECT * FROM assessments WHERE student_id=? ORDER BY checkpoint DESC LIMIT 1',(sid,))
        return rows[0] if rows else None

    def review_rows(self,ordering='Model ordering'):
        rows=[]
        for learner in self.store.learners():
            state=self.store.state(learner['student_id'])
            if not self.eligible(state['student_id']):
                continue
            latest=self.latest(state['student_id'])
            values=json.loads(latest['features']) if latest else self.feature_values(state['student_id'],self.store.clock(),3)
            rows.append(dict(student_id=state['student_id'],score=latest['score'] if latest else None,
                             assessed_at=latest['assessed_at'] if latest else None,
                             scheduled_at=latest['scheduled_at'] if latest else None,
                             checkpoint=latest['checkpoint'] if latest else None,
                             reason=latest['reason'] if latest else 'First checkpoint has not been processed yet.',
                             practice_submitted=state['practice_submitted'],quiz_passed=state['quiz_passed'],
                             progress_count=values['practice_submitted']+values['quiz_passed'],current_quiz_score=values['current_quiz_score']))
        def priority(row):
            if ordering=='Progress ordering':
                return (row['progress_count'],row['current_quiz_score'] if row['current_quiz_score'] is not None else -1)
            return (row['score'] is None,-row['score'] if row['score'] is not None else 0)
        rows.sort(key=lambda row:(priority(row),row['student_id']))
        groups={}
        for row in rows:
            key=priority(row)
            groups.setdefault(key,len(groups)+1)
            row['priority_group']=groups[key]
        return rows
