"""
One-step build script for Spellbook.

Produces a single self-contained executable at ``dist/spellbook.exe`` using the
bundled ``main.spec`` (PyInstaller onefile mode). Run this whenever you want to
test a fresh build:

    python build.py              # normal build
    python build.py --clean      # also wipe PyInstaller's cache + build/ first
    python build.py --run        # launch the exe when the build succeeds
    python build.py --keep-data  # don't reset the test database / settings

Behaviour:
  * Deletes any existing dist/spellbook.exe (and dist/Spellbook.exe) first, so a
    stale binary can never be mistaken for a successful build.
  * Resets the test data next to the exe (dist/spellbook.db, dist/settings.json)
    so the next run regenerates them from the bundled content. Pass --keep-data
    to preserve them instead.
  * Leaves character data (dist/characters.json, dist/character_sheets.json)
    alone regardless.
  * Uses the project virtualenv's Python if one is present (.venv/).
"""

import argparse
import os
import shutil
import subprocess
import sys
import time


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SPEC_FILE = "main.spec"
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")
BUILD_DIR = os.path.join(PROJECT_ROOT, "build")
# main.spec builds `name='spellbook'`; also clean the capitalised variant that
# Spellbook.spec would produce, just in case an old one is lying around.
EXE_NAMES = ("spellbook.exe", "Spellbook.exe")

# Files the app generates next to the exe on first run. Wiped by default so each
# test build starts from freshly generated state (skip with --keep-data).
# Character data is deliberately NOT listed here - a build shouldn't nuke that.
RUNTIME_DATA = ("spellbook.db", "settings.json")


def find_python() -> str:
    """Return the interpreter to build with - the project venv if it exists."""
    for candidate in (
        os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe"),  # Windows
        os.path.join(PROJECT_ROOT, ".venv", "bin", "python"),          # POSIX
    ):
        if os.path.isfile(candidate):
            return candidate
    return sys.executable


def check_pyinstaller(python: str) -> bool:
    result = subprocess.run(
        [python, "-c", "import PyInstaller; print(PyInstaller.__version__)"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("ERROR: PyInstaller is not installed for this interpreter:")
        print(f"  {python}")
        print("\nInstall it with:")
        print(f'  "{python}" -m pip install pyinstaller')
        return False
    print(f"PyInstaller {result.stdout.strip()}")
    return True


def delete_old_exe() -> None:
    for name in EXE_NAMES:
        path = os.path.join(DIST_DIR, name)
        if os.path.isfile(path):
            try:
                os.remove(path)
                print(f"Removed old executable: {os.path.relpath(path, PROJECT_ROOT)}")
            except OSError as e:
                print(f"ERROR: could not delete {path}: {e}")
                print("Is the app still running? Close it and try again.")
                sys.exit(1)


def delete_runtime_data() -> None:
    """Remove the exe's generated database / settings so they regenerate."""
    for name in RUNTIME_DATA:
        path = os.path.join(DIST_DIR, name)
        if os.path.isfile(path):
            try:
                os.remove(path)
                print(f"Reset test data: {os.path.relpath(path, PROJECT_ROOT)}")
            except OSError as e:
                print(f"WARNING: could not delete {path}: {e}")


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Spellbook into a single exe.")
    parser.add_argument(
        "--clean", action="store_true",
        help="wipe PyInstaller's cache and build/ before building (slower, fully fresh)",
    )
    parser.add_argument(
        "--run", action="store_true",
        help="launch the built executable if the build succeeds",
    )
    parser.add_argument(
        "--keep-data", action="store_true",
        help="keep the existing dist/spellbook.db and dist/settings.json "
             "instead of resetting them",
    )
    args = parser.parse_args()

    os.chdir(PROJECT_ROOT)
    python = find_python()
    print(f"Interpreter: {python}")

    if not os.path.isfile(os.path.join(PROJECT_ROOT, SPEC_FILE)):
        print(f"ERROR: {SPEC_FILE} not found in {PROJECT_ROOT}")
        return 1

    if not check_pyinstaller(python):
        return 1

    # 1. Remove the previous executable so success/failure is unambiguous.
    delete_old_exe()

    # 1b. Reset generated test data so the next run rebuilds it from scratch.
    if args.keep_data:
        print("Keeping existing test data (--keep-data).")
    else:
        delete_runtime_data()

    # 2. Optionally clear caches for a from-scratch build.
    if args.clean and os.path.isdir(BUILD_DIR):
        print("Removing build/ ...")
        shutil.rmtree(BUILD_DIR, ignore_errors=True)

    # 3. Build.
    cmd = [python, "-m", "PyInstaller", SPEC_FILE, "--noconfirm"]
    if args.clean:
        cmd.append("--clean")
    print("\n" + " ".join(cmd) + "\n")

    start = time.time()
    result = subprocess.run(cmd)
    elapsed = time.time() - start

    if result.returncode != 0:
        print(f"\nBUILD FAILED (exit {result.returncode}) after {elapsed:.1f}s")
        return result.returncode

    # 4. Report.
    exe_path = os.path.join(DIST_DIR, "spellbook.exe")
    if not os.path.isfile(exe_path):
        print("\nBUILD REPORTED SUCCESS but dist/spellbook.exe is missing.")
        return 1

    print("\n" + "=" * 52)
    print(f"BUILD OK in {elapsed:.1f}s")
    print(f"  {os.path.relpath(exe_path, PROJECT_ROOT)}  ({human_size(os.path.getsize(exe_path))})")
    print("=" * 52)

    if args.run:
        print("\nLaunching...")
        subprocess.Popen([exe_path], cwd=DIST_DIR)

    return 0


if __name__ == "__main__":
    sys.exit(main())
