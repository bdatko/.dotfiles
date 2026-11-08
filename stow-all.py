#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Restow every GNU Stow package listed in stow-packages.

Extra flags are forwarded to stow, for example:

    ./stow-all.py -n -v      # simulate
    ./stow-all.py --dry-run  # same, without remembering stow's flag

See also: stow-packages, README.md.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "stow-packages"


def read_packages(path: Path) -> list[str]:
    """Package names, one per line; blank lines and # comments ignored."""
    names: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        name = raw.split("#", 1)[0].strip()
        if name:
            names.append(name)
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="pass -n to stow (simulate)"
    )
    args, passthrough = parser.parse_known_args(argv)

    stow = shutil.which("stow")
    if stow is None:
        print("stow-all: GNU Stow not found on PATH (brew install stow)", file=sys.stderr)
        return 127

    try:
        packages = read_packages(MANIFEST)
    except FileNotFoundError:
        print(f"stow-all: missing manifest: {MANIFEST}", file=sys.stderr)
        return 1

    missing = [name for name in packages if not (ROOT / name).is_dir()]
    if missing:
        print(
            f"stow-all: not package directories: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1
    if not packages:
        print(f"stow-all: no packages listed in {MANIFEST}", file=sys.stderr)
        return 1

    command = [stow, "-R", "--dotfiles", *passthrough]
    if args.dry_run:
        command.append("-n")
    command.extend(packages)

    print("+ " + " ".join(command), file=sys.stderr)
    return subprocess.run(command, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
