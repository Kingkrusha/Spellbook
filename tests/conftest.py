"""Test setup: run against a throwaway copy of the data files.

``paths.user_data_dir()`` honours SPELLBOOK_DATA_DIR, so setting it here (before any
app module is imported) keeps the tests away from the developer's real
``spellbook.db``, ``characters.json`` and ``settings.json``.
"""

import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_DATA = tempfile.mkdtemp(prefix="spellbook-tests-")
os.environ["SPELLBOOK_DATA_DIR"] = _DATA
# The committed database (it is migrated in place, so never point tests at the real one)
if os.path.exists(os.path.join(ROOT, "spellbook.db")):
    shutil.copy(os.path.join(ROOT, "spellbook.db"), os.path.join(_DATA, "spellbook.db"))


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_DATA, ignore_errors=True)
