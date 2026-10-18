"""Local demo action log. Effective simulation times are separate from wall time."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

import pandas as pd

STAFF = ['Unassigned', 'Demo staff — Amina', 'Demo staff — Ben', 'Demo staff — Chika']
STATUSES = ['Not reviewed', 'Reviewing', 'Reviewed', 'Follow-up planned']
CHALLENGES = ['Content difficulty', 'Deadline difficulty', 'Connectivity difficulty', 'Unclear', 'Mixed', 'Other']


class StaffStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY, student_id TEXT NOT NULL, module_id INTEGER NOT NULL,
                kind TEXT NOT NULL, effective_at TEXT NOT NULL, created_at TEXT NOT NULL,
                payload TEXT NOT NULL, request_key TEXT NOT NULL UNIQUE)''')
            db.execute('''CREATE TABLE IF NOT EXISTS referrals (
                student_id TEXT NOT NULL, module_id INTEGER NOT NULL,
                effective_at TEXT NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(student_id,module_id))''')

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def record(self, sid, mid, kind, at, payload, request_key):
        if kind not in ('review', 'challenge', 'draft'):
            raise ValueError('Unsupported demonstration action')
        if kind == 'review' and (payload['staff'] not in STAFF or payload['status'] not in STATUSES):
            raise ValueError('Invalid staff/review status')
        if kind == 'challenge' and (payload['category'] not in CHALLENGES or payload['confirmed_by'] not in ('student', 'teacher')):
            raise ValueError('Confirmation must identify student or teacher')
        if kind == 'draft' and payload['channel'] not in ('SMS', 'WhatsApp', 'email'):
            raise ValueError('Invalid draft channel')
        effective = pd.Timestamp(at).isoformat()
        content = json.dumps(payload, sort_keys=True)
        with self.connect() as db:
            previous = db.execute('SELECT payload FROM actions WHERE request_key=?', (request_key,)).fetchone()
            if previous and previous[0] != content:
                raise ValueError('Idempotency key reused with different content')
            db.execute('INSERT OR IGNORE INTO actions(student_id,module_id,kind,effective_at,created_at,payload,request_key) VALUES(?,?,?,?,?,?,?)',
                       (sid, int(mid), kind, effective, datetime.now(timezone.utc).isoformat(), content, request_key))

    def actions(self, at, sid=None, mid=None):
        with self.connect() as db:
            rows = db.execute('SELECT id,student_id,module_id,kind,effective_at,created_at,payload FROM actions').fetchall()
        result = []
        for row in rows:
            if pd.Timestamp(row[4]) > at or (sid is not None and row[1] != sid) or (mid is not None and row[2] != mid):
                continue
            result.append(dict(id=row[0], student_id=row[1], module_id=row[2], kind=row[3],
                               effective_at=row[4], created_at=row[5], payload=json.loads(row[6])))
        return sorted(result, key=lambda r: (pd.Timestamp(r['effective_at']), r['id']))

    def state(self, at, sid, mid):
        reviews = [a for a in self.actions(at, sid, mid) if a['kind'] == 'review']
        return reviews[-1]['payload'] if reviews else dict(staff='Unassigned', status='Not reviewed', notes='', follow_up=None)

    def ensure_referrals(self, overdue):
        with self.connect() as db:
            for r in overdue.itertuples():
                # A deterministic event just after the inclusive deadline, not a page-visit timestamp.
                effective = (r.deadline + pd.Timedelta(microseconds=1)).isoformat()
                db.execute('INSERT OR IGNORE INTO referrals VALUES(?,?,?,?)',
                           (r.student_id, int(r.module_id), effective, datetime.now(timezone.utc).isoformat()))

    def referrals(self, at, sid):
        with self.connect() as db:
            rows = db.execute('SELECT module_id,effective_at FROM referrals WHERE student_id=?', (sid,)).fetchall()
        return [dict(module_id=m, referral_time=t) for m, t in rows if pd.Timestamp(t) <= at]


def message_draft(case, category, at, confirmed_need=''):
    """Pure text preview. No transport, network client, or send action exists."""
    remaining = case['remaining_requirements']
    if case['learning_status'].startswith('Completed'):
        return (f"Hello {case['student_id']}, your recorded chemistry module {case['module_id']} is complete. "
                'Support is still available. Tell your teacher if you would like help with a skill or further revision.')
    elif at > case['deadline']:
        timing = f"Your module is overdue by {(at - case['deadline']).total_seconds() / 86400:.1f} days. Remaining: {remaining}."
    else:
        timing = f"You have {(case['deadline'] - at).total_seconds() / 86400:.1f} days until the deadline. Remaining: {remaining}."
    bodies = {
        'Content difficulty': (f'For the confirmed skill need ({confirmed_need}), ask your teacher for a relevant explanation and practice. ' if confirmed_need else 'Please tell your teacher which chemistry skill needs support, so they can plan an explanation and practice. ') + 'Completion requires submitted practice and a valid quiz score of at least 80%.',
        'Deadline difficulty': 'Plan a short session for the remaining practice, then a quiz check. Ask your teacher to agree a manageable completion plan.',
        'Connectivity difficulty': 'Ask your teacher about the offline lesson and practice route and a teacher-recorded quiz result. Offline work follows the same submission and at-least-80% valid quiz requirements.',
        'Unclear or mixed difficulty': 'What support would help you most? Please tell your teacher about any challenges so you can agree the next step.',
        'Overdue': 'Please ask your teacher for support. After the deadline, quiz attempts require teacher authorisation for one or two additional attempts. This draft does not authorise any attempt.',
    }
    text = f"Hello {case['student_id']}, about chemistry module {case['module_id']}: {timing} {bodies[category]}"
    if at > case['deadline'] and category != 'Overdue' and not case['learning_status'].startswith('Completed'):
        text += ' Any further quiz attempts need a teacher grant of one or two attempts.'
    return text
