"""Presentation helpers; no changes to simulation, scoring or support persistence."""
import pandas as pd

STATUS_ORDER = ['In progress', 'Overdue', 'Completed all eight modules']


def current_learners(modules):
    result = modules.sort_values(['student_id', 'module_id']).drop_duplicates('student_id', keep='last').copy()
    result.loc[result.learning_status.str.startswith('Completed'), 'learning_status'] = STATUS_ORDER[2]
    return result


def status_counts(current):
    counts = current.learning_status.value_counts().reindex(STATUS_ORDER, fill_value=0)
    assert int(counts.sum()) == len(current), 'Current statuses must partition enrolled learners'
    return counts


def filter_cases(frame, query='', status='All', module='All', staff='All', review='All'):
    result = frame
    if query.strip():
        result = result[result.student_id.str.contains(query.strip(), case=False, regex=False)]
    for column, value in [('learning_status', status), ('module_id', module), ('Assigned staff', staff), ('Support status', review)]:
        if value != 'All':
            result = result[result[column].eq(value)]
    return result.copy()


def date_label(value):
    return 'Not recorded' if pd.isna(value) else pd.Timestamp(value).strftime('%d %b %Y, %H:%M UTC')


def duration_label(delta):
    minutes = max(0, int(pd.Timedelta(delta).total_seconds() // 60))
    if minutes < 60:
        return f'{minutes} min'
    days, hours = divmod(minutes // 60, 24)
    day_text = f'{days} day' + ('' if days == 1 else 's')
    hour_text = f'{hours} hour' + ('' if hours == 1 else 's')
    return f'{day_text} {hour_text}' if days else f'{hour_text} {minutes % 60} min'


def last_assessed_label(assessed_at, as_of):
    """Elapsed checkpoint time, always relative to the selected historical view."""
    if pd.isna(assessed_at):
        return 'Not yet assessed'
    seconds = (pd.Timestamp(as_of) - pd.Timestamp(assessed_at)).total_seconds()
    if seconds < 0:
        return 'Not yet assessed'
    for unit, size in [('day', 86400), ('hour', 3600), ('minute', 60)]:
        count = int(seconds // size)
        if count:
            return f'{count} {unit}' + ('' if count == 1 else 's') + ' ago'
    return 'Just assessed'


def input_groups(values):
    def number(key, suffix, missing, signed=False):
        value = values[key]
        if pd.isna(value):
            return missing
        return (f'{value:+.1f}' if signed else f'{value:.1f}') + suffix
    sessions_missing = pd.isna(values['session_length'])
    return {
        'Engagement': [
            ('Average session duration', number('session_length', ' min', 'No sessions recorded'), 'Mean session duration in the current module, including idle time.'),
            ('Total active study time', 'No sessions recorded' if sessions_missing else number('time_on_task', ' min', 'No sessions recorded'), 'Cumulative active time in the current module, excluding idle time.'),
            ('Time since last login', number('days_since_login', ' days', 'No login recorded'), ''),
            ('Interrupted sessions', 'No sessions recorded' if sessions_missing else str(int(values['failed_or_dropped_sessions'])), 'Count in the current module.')],
        'Assessment': [('Quiz score change', number('quiz_score_trend', ' percentage points', 'Needs two attempts to calculate change', signed=True), 'Latest valid quiz score minus the preceding valid score.')],
        'Submission history': [('Previous late practice submissions', str(int(values['past_late_submissions'])), 'Count of recorded practice submissions after their module deadlines.')]
    }


def evaluation_table(frame, fields):
    """Transpose wide saved outputs into readable, explicitly formatted comparisons."""
    models = {'logistic_regression':'Logistic regression', 'gradient_boosting':'Gradient boosting',
              'flag_all':'Flag every eligible snapshot'}
    rows = []
    for column, label, formatting in fields:
        row = {'Measure': label}
        for record in frame.to_dict('records'):
            value = record[column]
            row[models.get(record['model'], record['model'].replace('_', ' ').capitalize())] = (
                'Undefined' if pd.isna(value) else format(value, formatting))
        rows.append(row)
    return pd.DataFrame(rows)
