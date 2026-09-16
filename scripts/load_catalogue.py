"""Load an additive JSON bundle; run Wikimedia sync afterwards to activate new cards."""
import argparse
import json
from pathlib import Path
import sys
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')
from backend.wikidex.catalogue import load_bundle
from backend.wikidex.db import SessionLocal, begin_write, init_db

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('file', type=Path)
args = parser.parse_args()
try:
    raw = json.loads(args.file.read_text(encoding='utf-8-sig'))
    init_db()
    with SessionLocal() as session:
        begin_write(session)
        result = load_bundle(session, raw)
        session.commit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
except (ValueError, OSError) as exc:
    parser.exit(2, str(exc) + '\n')
