#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Compare brew packages declared in this repo with what is installed.

Declarations come from:

  - install-scripts/**/*.sh   (run by babo)
  - ./install                 (Homebrew bootstrap + stow)

Outputs one ``== <check> == PASS|FAIL|WARN`` line per check, matching the
other harnesses in this repo.

Exit status:
  0  every declared package is installed
  1  a declared package is missing, or --strict found an undeclared one
  2  brew could not be queried

Packages installed for personal reasons can be listed in ``brew-ignore``
(one per line, fnmatch globs supported).
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IGNORE_FILE = ROOT / "brew-ignore"
INSTALL_RE = re.compile(r"brew\s+install\s+([^&|;\n\r]+)")


def run(*args: str) -> list[str]:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(
            f"check-brew: {' '.join(args)} failed:\n{result.stderr.strip()}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def declared() -> dict[str, Path]:
    """Map package name -> the file that declares it."""
    files = sorted(ROOT.glob("install-scripts/**/*.sh"))
    root_install = ROOT / "install"
    if root_install.exists():
        files.append(root_install)

    found: dict[str, Path] = {}
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for args in INSTALL_RE.findall(text):
            try:
                tokens = shlex.split(args, comments=True)
            except ValueError:
                tokens = args.split()
            for token in tokens:
                if token.startswith("-"):
                    continue
                found.setdefault(token, path)
    return found


def ignored() -> list[str]:
    if not IGNORE_FILE.exists():
        return []
    patterns: list[str] = []
    for raw in IGNORE_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            patterns.append(line)
    return patterns


def is_ignored(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="also fail when an installed package is neither declared nor ignored",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="list declared and ignored packages"
    )
    args = parser.parse_args(argv)

    wanted = declared()
    formulae = set(run("brew", "list", "--formula"))
    casks = set(run("brew", "list", "--cask"))
    leaves = set(run("brew", "leaves"))

    installed = formulae | casks
    missing = sorted(name for name in wanted if name not in installed)

    status = "PASS" if not missing else "FAIL"
    print(
        f"== brew/declared == {status} "
        f"({len(wanted)} declared, {len(wanted) - len(missing)} installed)"
    )
    for name in missing:
        print(f"   missing: {name}  ({wanted[name].relative_to(ROOT)})")

    patterns = ignored()
    candidates = leaves | casks
    undeclared = sorted(
        name
        for name in candidates
        if name not in wanted and not is_ignored(name, patterns)
    )
    ignored_count = sum(
        1
        for name in candidates
        if name not in wanted and is_ignored(name, patterns)
    )

    status2 = "PASS" if not undeclared else "WARN"
    print(
        f"== brew/undeclared == {status2} "
        f"({ignored_count} ignored, {len(undeclared)} unexpected)"
    )
    for name in undeclared:
        print(f"   warn: {name} (add an install-script or list it in brew-ignore)")

    if args.verbose:
        print("== brew/declared-list ==")
        for name in sorted(wanted):
            print(f"   {name}  ({wanted[name].relative_to(ROOT)})")

    if missing:
        return 1
    if args.strict and undeclared:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
