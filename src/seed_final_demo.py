"""Reproducible isolated fixtures; these are seeded records, not browser journeys."""
import argparse
import json
from pathlib import Path
import pandas as pd
from src.interactive_store import InteractiveStore,saved_now
from src.interactive_assessment import AssessmentService
from src.interactive_support import SupportService,CATEGORIES
from src.chemistry_content import PRACTICE,QUIZ
from src.pilot import example,PROTOCOL,FIELDS
from src.simulate import ROOT

STAFF='Demo staff — Amina'
def answers(questions,correct=True):
    return {q['id']:(','.join(map(str,q['answer'])) if correct else ','.join('1' for _ in q['answer'])) if isinstance(q['answer'],tuple) else q['answer'] if correct else 'A' for q in questions}

def seed(path):
    path=Path(path)
    if path.exists(): raise ValueError('Refusing to replace an existing demonstration database.')
    store=InteractiveStore(path,pd.Timestamp('2026-10-01T08:00Z'))
    overdue=store.enrol(); late=store.enrol()
    store.submit(overdue,'practice',answers(PRACTICE),'seed-overdue-practice')
    store.submit(late,'practice',answers(PRACTICE),'seed-late-practice')
    store.advance(pd.Timestamp('2026-10-16T08:00Z'),STAFF,'Seeded demonstration chronology')
    store.grant(late,1,STAFF,'Seeded authorised late completion','seed-grant')
    store.submit(late,'quiz',answers(QUIZ),'seed-late-quiz')
    early=store.enrol(); progress=store.enrol('email'); help_sid=store.enrol('WhatsApp'); waiting=store.enrol()
    store.submit(progress,'practice',answers(PRACTICE),'seed-progress-practice')
    store.submit(progress,'quiz',answers(QUIZ,False),'seed-progress-quiz')
    store.submit(waiting,'practice',answers(PRACTICE),'seed-wait-practice')
    store.submit(waiting,'quiz',answers(QUIZ),'seed-wait-quiz')
    store.request_help(help_sid,'Seeded demonstration request: I need offline materials and help with balancing.','seed-request')
    store.advance(pd.Timestamp('2026-10-19T08:00Z'),STAFF,'Seeded day-three checkpoint')
    service=AssessmentService(store)
    at=store.clock().isoformat()
    captured=json.dumps(service.feature_values(early,store.clock(),3))
    # Preserve one deliberately seeded legacy attempt to demonstrate versioning.
    with store.transaction() as db:
        db.execute('INSERT INTO assessments VALUES(?,?,?,?,?,?,?,?,?,?)',(early,1,3,at,at,saved_now(),captured,'legacy-unscored-fixture',None,'Seeded old unscored attempt; retained for version audit.'))
        db.execute('CREATE TABLE demo_scenarios(student_id TEXT PRIMARY KEY,scenario TEXT,provenance TEXT)')
        for sid,name in [(overdue,'Overdue — authorise an extra attempt'),(late,'Completed late after authorised attempt'),(early,'Early checkpoint — versioned assessment'),(progress,'Practice and quiz progress'),(help_sid,'Connectivity support request'),(waiting,'Completed — waiting for Module 2')]:
            db.execute('INSERT INTO demo_scenarios VALUES(?,?,?)',(sid,name,'Seeded demonstration record; not a browser-tested journey'))
    service.run_due(); SupportService(store)
    pilot=ROOT/'pilot'; pilot.mkdir(exist_ok=True)
    example().to_csv(pilot/'illustrative_synthetic_example.csv',index=False)
    (pilot/'protocol.md').write_text('# Pilot workflow\n\n'+PROTOCOL+'\n\nInput columns: '+', '.join(FIELDS),encoding='utf-8')
    pd.DataFrame(columns=FIELDS).to_csv(pilot/'input_template.csv',index=False)
    print('Seeded isolated demonstration:',path.resolve())
    print(store.read('SELECT * FROM demo_scenarios'))

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--database',default=str(ROOT/'runtime/final_demo.sqlite3'))
    seed(parser.parse_args().database)
