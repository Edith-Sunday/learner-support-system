"""Read-only comparison against the pre-implementation preservation baseline."""
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def verify():
    baseline = json.loads((ROOT / 'runtime/final_before_hashes.json').read_text())
    changed = [name for name, digest in baseline.items()
               if not (ROOT / name).is_file()
               or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    databases = {}
    for name in ('interactive_demo', 'staff_demo'):
        before = ROOT / f'runtime/{name}_before_final.sqlite3'
        current = ROOT / f'runtime/{name}.sqlite3'
        with sqlite3.connect(before.as_uri() + '?mode=ro', uri=True) as old, \
                sqlite3.connect(current.as_uri() + '?mode=ro', uri=True) as new:
            tables = [r[0] for r in old.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            results = {}
            for table in tables:
                quoted = '"' + table.replace('"', '""') + '"'
                a = sorted(old.execute('SELECT * FROM ' + quoted).fetchall(), key=repr)
                b = sorted(new.execute('SELECT * FROM ' + quoted).fetchall(), key=repr)
                results[table] = {'rows': len(a), 'identical': a == b}
            databases[name] = results
    result = {'baseline_files': len(baseline), 'changed_files': changed, 'databases': databases}
    result['passed'] = not changed and all(t['identical'] for d in databases.values() for t in d.values())
    (ROOT / 'reports/final_preservation_audit.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise SystemExit('Preservation mismatch')


if __name__ == '__main__':
    verify()
