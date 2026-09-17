"""Run tests in a fresh workspace temp directory, avoiding stale Windows temp ACLs."""
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
parent = ROOT / "data" / "test-runs"
parent.mkdir(parents=True, exist_ok=True)
temporary = (parent / ("run-" + uuid.uuid4().hex)).resolve()
if not temporary.is_relative_to(parent.resolve()) or temporary.exists():
    raise SystemExit("Refus d’utiliser un dossier temporaire existant ou extérieur au projet.")
raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "backend/tests", "-q", "-p", "no:cacheprovider",
                                 "--basetemp", str(temporary), *sys.argv[1:]], cwd=ROOT))
