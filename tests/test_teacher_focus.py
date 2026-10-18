from src.interactive_ui import selected_support_rows

def test_support_selection_requires_saved_score_and_keeps_boundary_ties():
    class Service:
        def review_rows(self, ordering):
            assert ordering == 'Model ordering'
            return [dict(student_id=s,score=v,priority_group=g) for s,v,g in [('A',.8,1),('B',.8,1),('C',.2,2),('D',None,3)]]
    assert [r['student_id'] for r in selected_support_rows(Service(),1)] == ['A','B']
    assert [r['student_id'] for r in selected_support_rows(Service())] == ['A','B','C']

def test_teacher_list_matches_saved_predictions(tmp_path,monkeypatch):
    import sqlite3
    from streamlit.testing.v1 import AppTest
    from src.interactive_store import InteractiveStore
    from src.interactive_assessment import AssessmentService
    from src.simulate import ROOT
    source=ROOT/'runtime/usability_demo.sqlite3'
    if not source.exists(): source=ROOT/'demo_seed/demo.sqlite3'
    with sqlite3.connect(source) as a, sqlite3.connect(tmp_path/'copy.sqlite3') as b:
        a.backup(b)
    store=InteractiveStore(tmp_path/'copy.sqlite3')
    monkeypatch.setenv('INTERACTIVE_DEMO_DB',str(store.path))
    app=AppTest.from_file(str(ROOT/'dashboard.py'),default_timeout=60).run()
    app.sidebar.radio[0].set_value('Needs attention').run()
    assert not app.exception
    expected=selected_support_rows(AssessmentService(store))
    assert len(expected)==4
    assert {b.key for b in app.button if b.label=='Review and support'}=={'review-support-'+r['student_id'] for r in expected}
    assert any(s.value=='May need support' for s in app.subheader)
    assert not any(x.label in ['Teacher','Assessment details','Assessment history','Review order'] for x in list(app.selectbox)+list(app.expander))
    sid=expected[0]['student_id']
    app.button(key='review-support-'+sid).click().run()
    assert app.selectbox(key='staff_profile_learner').value==sid
    before=store.read('SELECT * FROM actions')
    next(b for b in app.button if b.label=='Save follow-up').click().run()
    assert len(store.read('SELECT * FROM actions'))==len(before)
    app.selectbox(key='actor-followup-'+sid).set_value('Demo staff — Amina')
    next(b for b in app.button if b.label=='Save follow-up').click().run()
    assert not app.exception
    assert len(store.read('SELECT * FROM actions'))==len(before)+1

