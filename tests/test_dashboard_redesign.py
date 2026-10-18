"""Presentation regressions, independent of learning and model rules."""
import pandas as pd
from src.dashboard_data import load_sources, historical_modules, DEFAULT_TIME
from src.dashboard_ui import current_learners, status_counts, filter_cases, input_groups, date_label, duration_label, last_assessed_label
from src.simulate import ROOT


def test_summary_partition_and_filters():
    sources = load_sources()
    for at in [pd.Timestamp('2026-01-01', tz='UTC'), DEFAULT_TIME, pd.Timestamp('2026-05-01', tz='UTC')]:
        current = current_learners(historical_modules(sources['students'], sources['events'], at))
        counts = status_counts(current)
        assert counts.sum() == sources['students'].enrolment_time.le(at).sum()
        assert not current.student_id.duplicated().any()
    current['Assigned staff'] = 'Unassigned'
    current['Support status'] = 'Not reviewed'
    row = current.iloc[0]
    filtered = filter_cases(current, row.student_id.lower(), row.learning_status, row.module_id, 'Unassigned')
    assert filtered.student_id.tolist() == [row.student_id]
    assert filter_cases(current, 'NO SUCH LEARNER').empty


def test_units_and_missing_states():
    values = dict(session_length=None, time_on_task=0, days_since_login=None,
                  failed_or_dropped_sessions=0, quiz_score_trend=None, past_late_submissions=0)
    text = str(input_groups(values))
    assert 'No sessions recorded' in text and 'Needs two attempts' in text and 'No login recorded' in text
    values.update(session_length=56.1, time_on_task=127.8, days_since_login=1,
                  failed_or_dropped_sessions=3, quiz_score_trend=20)
    text = str(input_groups(values))
    assert all(t in text for t in ['56.1 min', '127.8 min', '1.0 days', '+20.0 percentage points'])
    assert duration_label(pd.Timedelta(days=3, hours=4)) == '3 days 4 hours'
    assert duration_label(pd.Timedelta(hours=1)) == '1 hour 0 min'
    assert duration_label(pd.Timedelta(days=1, hours=1)) == '1 day 1 hour'
    assert date_label(DEFAULT_TIME) == '15 Feb 2026, 12:00 UTC'


def test_last_assessed_uses_selected_time():
    assessed = pd.Timestamp('2026-02-13T12:00:00Z')
    for delta, expected in [(pd.Timedelta(days=2), '2 days ago'),
                            (pd.Timedelta(hours=1), '1 hour ago'),
                            (pd.Timedelta(minutes=54), '54 minutes ago'),
                            (pd.Timedelta(minutes=1), '1 minute ago'),
                            (pd.Timedelta(days=1), '1 day ago'),
                            (pd.Timedelta(seconds=30), 'Just assessed')]:
        assert last_assessed_label(assessed, assessed + delta) == expected
    assert last_assessed_label(pd.NaT, DEFAULT_TIME) == 'Not yet assessed'
    assert last_assessed_label(assessed, assessed - pd.Timedelta(minutes=1)) == 'Not yet assessed'


def test_profile_back_filters_empty_and_default(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    from src.interactive_store import InteractiveStore
    store=InteractiveStore(tmp_path/'app.sqlite3','2026-10-01T08:00Z')
    sid=store.enrol()
    monkeypatch.setenv('INTERACTIVE_DEMO_DB',str(store.path))
    app=AppTest.from_file(str(ROOT/'dashboard.py'),default_timeout=60).run()
    assert not app.exception
    assert app.title[0].value=='All learners'
    assert [t.label for t in app.tabs]==['Progress','Quiz results','Support','History']
    next(t for t in app.text_input if t.label=='Search learners').set_value('ABSENT').run()
    assert any('No learners match' in i.value for i in app.info)
    next(t for t in app.text_input if t.label=='Search learners').set_value(sid).run()
    assert [t.label for t in app.tabs]==['Progress','Quiz results','Support','History']
    assert not app.exception
