"""Consistent SQLite backup, including WAL; never copy a live .sqlite3 file alone."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')
from backend.wikidex.db import engine

if engine.dialect.name != 'sqlite':
    raise SystemExit('PostgreSQL : utiliser pg_dump plutôt que ce script SQLite.')
source = Path(engine.url.database).resolve()
if not source.exists():
    raise SystemExit('Aucune base SQLite à sauvegarder.')
target = ROOT / 'data' / 'backups' / ('wikidex-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
target.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src, sqlite3.connect(target) as dst:
    src.backup(dst)
print(target)
