"""Independent interactive cohort. All attempt/grant changes are atomic SQLite transactions."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid

import pandas as pd
from src.chemistry_content import PRACTICE, QUIZ, grade
from src.simulate import completion


def utc(value):
    value = pd.Timestamp(value)
    if value.tzinfo is None or pd.isna(value):
        raise ValueError('A valid timezone-aware UTC time is required.')
    return value.tz_convert('UTC')


def saved_now():
    return datetime.now(timezone.utc).isoformat()


class InteractiveStore:
    def __init__(self, path, initial_time=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS demo_clock(id INTEGER PRIMARY KEY CHECK(id=1), effective_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS clock_history(id INTEGER PRIMARY KEY, effective_at TEXT, created_at TEXT, staff TEXT, reason TEXT);
            CREATE TABLE IF NOT EXISTS learners(student_id TEXT PRIMARY KEY, enrolled_at TEXT, created_at TEXT, preference TEXT);
            CREATE TABLE IF NOT EXISTS modules(student_id TEXT, module_id INTEGER, unlock_time TEXT, deadline TEXT,
                completion_time TEXT, recognized_at TEXT, PRIMARY KEY(student_id,module_id));
            CREATE TABLE IF NOT EXISTS submissions(id INTEGER PRIMARY KEY, request_key TEXT UNIQUE, student_id TEXT,
                kind TEXT, source TEXT, event_time TEXT, recorded_at TEXT, created_at TEXT, score INTEGER,
                answers TEXT, grant_id INTEGER, staff TEXT, reason TEXT);
            CREATE TABLE IF NOT EXISTS quiz_grants(id INTEGER PRIMARY KEY, request_key TEXT UNIQUE, student_id TEXT,
                quantity INTEGER CHECK(quantity IN (1,2)), used INTEGER DEFAULT 0 CHECK(used>=0 AND used<=quantity),
                effective_at TEXT, created_at TEXT, staff TEXT, reason TEXT);
            CREATE TABLE IF NOT EXISTS preferences(id INTEGER PRIMARY KEY, student_id TEXT, channel TEXT, effective_at TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY, request_key TEXT UNIQUE, student_id TEXT, message TEXT,
                effective_at TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS interactive_referrals(student_id TEXT, module_id INTEGER, deadline TEXT, created_at TEXT,
                PRIMARY KEY(student_id,module_id));
            CREATE TABLE IF NOT EXISTS drafts(student_id TEXT, kind TEXT, token TEXT UNIQUE, answers TEXT,
                effective_at TEXT, created_at TEXT, PRIMARY KEY(student_id,kind));
            CREATE TABLE IF NOT EXISTS content_availability(module_id INTEGER PRIMARY KEY, available INTEGER, reason TEXT);
            INSERT OR IGNORE INTO content_availability VALUES(1,1,'Module 1 published');
            INSERT OR IGNORE INTO content_availability VALUES(2,0,'Content unavailable; excluded from action queues. Publishing requires an explicit deadline policy.');
            ''')
            db.execute('INSERT OR IGNORE INTO demo_clock VALUES(1,?)', (utc(initial_time or saved_now()).isoformat(),))

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def read(self, query, parameters=()):
        with self.transaction() as db:
            return [dict(r) for r in db.execute(query, parameters)]

    def _clock(self, db):
        return utc(db.execute('SELECT effective_at FROM demo_clock WHERE id=1').fetchone()[0])

    def clock(self):
        return utc(self.read('SELECT effective_at FROM demo_clock')[0]['effective_at'])

    def advance(self, new_time, staff, reason):
        self._staff(staff, reason)
        with self.transaction() as db:
            new_time = utc(new_time)
            if new_time <= self._clock(db):
                raise ValueError('The shared clock can only move forward.')
            db.execute('UPDATE demo_clock SET effective_at=? WHERE id=1', (new_time.isoformat(),))
            db.execute('INSERT INTO clock_history(effective_at,created_at,staff,reason) VALUES(?,?,?,?)',
                       (new_time.isoformat(), saved_now(), staff, reason))
            for row in db.execute('SELECT student_id FROM learners').fetchall():
                self._sync(db, row[0])

    def enrol(self, channel='SMS'):
        self._channel(channel)
        with self.transaction() as db:
            at = self._clock(db)
            sid = f"DEMO{db.execute('SELECT COUNT(*) FROM learners').fetchone()[0]+1:03d}"
            db.execute('INSERT INTO learners VALUES(?,?,?,?)', (sid, at.isoformat(), saved_now(), channel))
            db.execute('INSERT INTO modules VALUES(?,?,?,?,NULL,NULL)', (sid, 1, at.isoformat(), (at+pd.Timedelta(days=14)).isoformat()))
            db.execute('INSERT INTO preferences(student_id,channel,effective_at,created_at) VALUES(?,?,?,?)', (sid,channel,at.isoformat(),saved_now()))
            return sid

    @staticmethod
    def _channel(channel):
        if channel not in ('SMS','WhatsApp','email'):
            raise ValueError('Choose SMS, WhatsApp or email.')

    @staticmethod
    def _staff(staff, reason):
        from src.staff_store import STAFF
        if staff not in STAFF[1:] or not reason.strip():
            raise ValueError('Select a demonstration teacher and give a reason.')

    def _module(self, db, sid):
        row = db.execute('SELECT * FROM modules WHERE student_id=? AND module_id=1', (sid,)).fetchone()
        if row is None:
            raise ValueError('Enrol this interactive learner first.')
        return row

    def _sync(self, db, sid):
        module = self._module(db, sid)
        records = db.execute('SELECT * FROM submissions WHERE student_id=?', (sid,)).fetchall()
        events = [dict(event_type=r['kind'], event_time=utc(r['event_time']), recorded_at=utc(r['recorded_at']),
                       valid=1, score_pct=(r['score'] or 0)*10) for r in records]
        occurred, recognized = completion(events)
        if occurred is not None:
            # Reconciled occurrence can improve timeliness; established next-module clocks never move.
            db.execute('UPDATE modules SET completion_time=?, recognized_at=COALESCE(recognized_at,?) WHERE student_id=? AND module_id=1',
                       (occurred.isoformat(),recognized.isoformat(),sid))
            db.execute('INSERT OR IGNORE INTO modules VALUES(?,?,?,?,NULL,NULL)',
                       (sid,2,recognized.isoformat(),(recognized+pd.Timedelta(days=14)).isoformat()))
        for current in db.execute('SELECT * FROM modules WHERE student_id=?',(sid,)).fetchall():
            available = db.execute('SELECT available FROM content_availability WHERE module_id=?',(current['module_id'],)).fetchone()
            if available and available[0] and self._clock(db) > utc(current['deadline']) and (current['completion_time'] is None or utc(current['recognized_at']) > utc(current['deadline'])):
                db.execute('INSERT OR IGNORE INTO interactive_referrals VALUES(?,?,?,?)',
                           (sid,current['module_id'],current['deadline'],saved_now()))

    def state(self, sid):
        with self.transaction() as db:
            self._sync(db, sid)
            at = self._clock(db)
            module = dict(self._module(db,sid))
            learner = dict(db.execute('SELECT * FROM learners WHERE student_id=?',(sid,)).fetchone())
            rows = [dict(r) for r in db.execute('SELECT * FROM submissions WHERE student_id=? ORDER BY event_time,id',(sid,))]
            practice = any(r['kind']=='practice' for r in rows)
            passed = any(r['kind']=='quiz' and r['score']>=8 for r in rows)
            done = utc(module['completion_time']) if module['completion_time'] else None
            status = ('Completed on time' if done<=utc(module['deadline']) else 'Completed late') if done is not None else ('Overdue' if at>utc(module['deadline']) else 'In progress')
            grants = db.execute('SELECT COALESCE(SUM(quantity-used),0) FROM quiz_grants WHERE student_id=?',(sid,)).fetchone()[0]
            return dict(**learner, **{k:v for k,v in module.items() if k!='student_id'}, practice_submitted=practice,
                        quiz_passed=passed, learning_status=status, available_grants=grants, attempts=rows,
                        current_module=2 if done is not None else 1, as_of=at,
                        quiz_allowed=at<=utc(module['deadline']) or grants>0)

    def submit(self, sid, kind, answers, request_key, *, score=None, occurrence=None, staff='', reason=''):
        if kind not in ('practice','quiz') or not request_key:
            raise ValueError('Invalid submission.')
        offline = occurrence is not None
        if offline:
            self._staff(staff, reason)
            if kind=='quiz' and (type(score) is not int or not 0<=score<=10):
                raise ValueError('Offline quiz score must be an integer from 0 to 10.')
            if answers is not None:
                raise ValueError('Aggregate offline records do not contain question answers.')
            details = None
        else:
            score, details = grade(PRACTICE if kind=='practice' else QUIZ, answers)
        payload = json.dumps(details, sort_keys=True)
        with self.transaction() as db:
            previous = db.execute('SELECT * FROM submissions WHERE request_key=?',(request_key,)).fetchone()
            if previous:
                if previous['student_id']!=sid or previous['kind']!=kind or previous['answers']!=payload or previous['score']!=score or previous['source']!=('offline' if offline else 'online') or (offline and utc(previous['event_time'])!=utc(occurrence)):
                    raise ValueError('This submission token was already used for different answers.')
                return dict(previous)
            module = self._module(db,sid)
            at = self._clock(db)
            occurred = utc(occurrence) if offline else at
            if not utc(module['unlock_time']) <= occurred <= at:
                raise ValueError('Occurrence must be between module unlock and the current recording time.')
            grant_id = None
            if kind=='quiz' and occurred>utc(module['deadline']):
                grant = db.execute('SELECT * FROM quiz_grants WHERE student_id=? AND used<quantity AND effective_at<=? ORDER BY effective_at,id LIMIT 1',
                                   (sid,occurred.isoformat())).fetchone()
                if grant is None:
                    raise ValueError('The deadline has passed. An unused teacher grant must exist at the attempt time.')
                grant_id = grant['id']
                db.execute('UPDATE quiz_grants SET used=used+1 WHERE id=? AND used<quantity',(grant_id,))
            cursor = db.execute('INSERT INTO submissions(request_key,student_id,kind,source,event_time,recorded_at,created_at,score,answers,grant_id,staff,reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                                (request_key,sid,kind,'offline' if offline else 'online',occurred.isoformat(),at.isoformat(),saved_now(),score,payload,grant_id,staff,reason))
            self._sync(db,sid)
            return dict(db.execute('SELECT * FROM submissions WHERE id=?',(cursor.lastrowid,)).fetchone())

    def grant(self, sid, quantity, staff, reason, request_key):
        self._staff(staff,reason)
        if type(quantity) is not int or quantity not in (1,2):
            raise ValueError('Grant one or two attempts.')
        with self.transaction() as db:
            self._module(db,sid)
            previous = db.execute('SELECT * FROM quiz_grants WHERE request_key=?',(request_key,)).fetchone()
            if previous:
                if (previous['student_id'],previous['quantity'],previous['staff'],previous['reason']) != (sid,quantity,staff,reason):
                    raise ValueError('Grant token already used for different content.')
                return previous['id']
            return db.execute('INSERT INTO quiz_grants(request_key,student_id,quantity,effective_at,created_at,staff,reason) VALUES(?,?,?,?,?,?,?)',
                              (request_key,sid,quantity,self._clock(db).isoformat(),saved_now(),staff,reason)).lastrowid

    def preference(self, sid, channel):
        self._channel(channel)
        with self.transaction() as db:
            self._module(db,sid)
            db.execute('UPDATE learners SET preference=? WHERE student_id=?',(channel,sid))
            db.execute('INSERT INTO preferences(student_id,channel,effective_at,created_at) VALUES(?,?,?,?)',(sid,channel,self._clock(db).isoformat(),saved_now()))

    def request_help(self, sid, message, request_key):
        if not message.strip():
            raise ValueError('Describe what help you would like.')
        with self.transaction() as db:
            self._module(db,sid)
            previous = db.execute('SELECT * FROM requests WHERE request_key=?',(request_key,)).fetchone()
            if previous and (previous['student_id']!=sid or previous['message']!=message):
                raise ValueError('Request token already used for different content.')
            db.execute('INSERT OR IGNORE INTO requests(request_key,student_id,message,effective_at,created_at) VALUES(?,?,?,?,?)',
                       (request_key,sid,message,self._clock(db).isoformat(),saved_now()))

    def learners(self):
        return self.read('SELECT * FROM learners ORDER BY student_id')

    def draft(self,sid,kind,new=False):
        if kind not in ('practice','quiz'):
            raise ValueError('Unknown question set.')
        with self.transaction() as db:
            self._module(db,sid)
            if new:
                db.execute('DELETE FROM drafts WHERE student_id=? AND kind=?',(sid,kind))
            db.execute('INSERT OR IGNORE INTO drafts VALUES(?,?,?,?,?,?)',
                       (sid,kind,str(uuid.uuid4()),'{}',self._clock(db).isoformat(),saved_now()))
            return dict(db.execute('SELECT * FROM drafts WHERE student_id=? AND kind=?',(sid,kind)).fetchone())

    def save_draft(self,sid,kind,token,answers):
        with self.transaction() as db:
            if db.execute('SELECT 1 FROM submissions WHERE request_key=?',(token,)).fetchone():
                return
            db.execute('UPDATE drafts SET answers=?,effective_at=?,created_at=? WHERE student_id=? AND kind=? AND token=?',
                       (json.dumps(answers),self._clock(db).isoformat(),saved_now(),sid,kind,token))

    def module_history(self,sid):
        return self.read('SELECT * FROM modules WHERE student_id=? ORDER BY module_id',(sid,))

    def overdue(self):
        rows=[]
        for learner in self.learners():
            state=self.state(learner['student_id'])
            # Module 2 has a real clock but no functioning assessments/content.
            for module in self.module_history(learner['student_id']):
                if self.content_available(module['module_id']) and module['completion_time'] is None and self.clock()>utc(module['deadline']):
                    rows.append(dict(**module, learning_status='Overdue', preference=state['preference']))
        return rows

    def content_available(self, module_id):
        rows=self.read('SELECT available FROM content_availability WHERE module_id=?',(module_id,))
        return bool(rows and rows[0]['available'])
