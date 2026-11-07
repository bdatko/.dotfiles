#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = ["click==8.5.1"]
# ///

"""Verification harness for the tmux config in this dotfiles repo.

Every check runs against a throwaway server on a unique socket. The default
socket is never touched except by the read-only ``--live`` version check.
"""

from __future__ import annotations

import contextlib
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import click

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "tmux/dot-config/tmux/tmux.conf"
SOCKET_PREFIX = "dotfiles-tmux-test"
DEFAULT_SOCKET = "default"

CHECK_IDS = (
    "preflight",
    "discovery",
    "load",
    "options",
    "features",
    "idempotence",
    "bindings",
    "pane-env",
    "client-features",
    "version",
)

EXPECTED_FEATURES = {
    "xterm*:clipboard:ccolour:cstyle:focus:title",
    "screen*:title",
    "rxvt*:ignorefkeys",
    "alacritty*:RGB:clipboard:ccolour:cstyle:focus:title",
}

failures: list[str] = []


def emit(name: str, ok: bool, detail: str = "") -> bool:
    suffix = f" ({detail})" if detail else ""
    click.echo(f"== tmux/{name} == {'PASS' if ok else 'FAIL'}{suffix}")
    if not ok:
        failures.append(name)
    return ok


def skip(name: str, detail: str = "") -> None:
    suffix = f" ({detail})" if detail else ""
    click.echo(f"== tmux/{name} == SKIP{suffix}")


def tmux(
    sock: str | None,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = ["tmux"]
    if sock is not None:
        command += ["-L", sock]
    command += list(args)
    return subprocess.run(command, capture_output=True, text=True, check=check)


def option(sock: str, scope: str, name: str) -> str:
    return tmux(sock, "show-options", scope, name).stdout.strip()


def poll(fn: Callable[[], str | None], timeout: float = 10.0) -> str | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(0.1)
    return None


@contextlib.contextmanager
def socket() -> Iterator[str]:
    """A unique socket that is torn down on exit, never the default socket."""
    name = f"{SOCKET_PREFIX}-{os.getpid()}-{random.randrange(0x1000000):06x}"
    assert name != DEFAULT_SOCKET
    try:
        yield name
    finally:
        subprocess.run(
            ["tmux", "-L", name, "kill-server"],
            capture_output=True,
            check=False,
            text=True,
        )
        # macOS often leaves the socket file behind after kill-server.
        for base in {Path("/tmp"), Path(tempfile.gettempdir())}:
            (base.resolve() / f"tmux-{os.getuid()}" / name).unlink(missing_ok=True)


def start(sock: str, *, with_config: bool) -> None:
    """Start a detached server, optionally sourcing the real config."""
    if with_config:
        tmux(sock, "-f", "/dev/null", "new-session", "-d", "-s", "main", "sleep", "300")
        tmux(sock, "source-file", str(CONFIG))
    else:
        tmux(sock, "new-session", "-d", "-s", "main", "sleep", "300")


def check_preflight() -> None:
    problems: list[str] = []

    version = subprocess.run(
        ["tmux", "-V"], capture_output=True, check=False, text=True
    ).stdout.strip()
    match = re.search(r"(\d+)\.(\d+)", version)
    if match is None:
        problems.append(f"unparsable version {version!r}")
    elif tuple(map(int, match.groups())) < (3, 2):
        problems.append(f"{version} is older than 3.2")

    if not CONFIG.is_file():
        problems.append(f"missing {CONFIG}")

    detail = version
    if shutil.which("script") is None:
        detail += "; script missing (client-features will skip)"

    emit("preflight", not problems, "; ".join(problems) or detail)


def check_discovery() -> None:
    with socket() as sock:
        # No -f: let tmux perform its normal config search.
        tmux(sock, "new-session", "-d", "-s", "main", "sleep", "300")
        listing = tmux(sock, "display", "-p", "#{config_files}").stdout.strip()

    found = {Path(path).resolve() for path in listing.split(",") if path.strip()}
    ok = CONFIG.resolve() in found
    emit("discovery", ok, f"config_files={listing}" if ok else f"not in {listing}")


def check_load() -> None:
    with socket() as sock:
        tmux(sock, "-f", "/dev/null", "new-session", "-d", "-s", "main", "sleep", "300")
        proc = tmux(sock, "source-file", str(CONFIG), check=False)

    ok = proc.returncode == 0 and not proc.stderr.strip()
    detail = proc.stderr.strip().replace("\n", " ")
    emit("load", ok, detail or "config sourced cleanly")


def check_options() -> None:
    with socket() as sock:
        start(sock, with_config=True)
        actual = {
            "default-terminal": option(sock, "-sv", "default-terminal"),
            "escape-time": option(sock, "-sv", "escape-time"),
            "focus-events": option(sock, "-sv", "focus-events"),
            "extended-keys": option(sock, "-sv", "extended-keys"),
            "base-index": option(sock, "-gv", "base-index"),
            "mode-keys": option(sock, "-gwv", "mode-keys"),
        }

    expected = {
        "default-terminal": "tmux-256color",
        "escape-time": "0",
        "focus-events": "on",
        "extended-keys": "on",
        "base-index": "1",
        "mode-keys": "vi",
    }
    problems = [
        f"{name}={actual[name]!r} (want {want!r})"
        for name, want in expected.items()
        if actual[name] != want
    ]
    emit("options", not problems, "; ".join(problems) or "6 options set")


def check_features() -> None:
    with socket() as sock:
        start(sock, with_config=True)
        listing = tmux(sock, "show-options", "-s", "terminal-features").stdout

    values = [line.split(" ", 1)[1] for line in listing.splitlines() if " " in line]
    problems = []
    for want in sorted(EXPECTED_FEATURES):
        count = values.count(want)
        if count != 1:
            problems.append(f"{want} appears {count}x")
    if set(values) != EXPECTED_FEATURES:
        problems.append(f"unexpected entries {sorted(set(values) - EXPECTED_FEATURES)}")

    emit("features", not problems, "; ".join(problems) or "4 entries, no duplicates")


def snapshot(sock: str) -> str:
    parts = []
    for scope in ("-s", "-g", "-gw"):
        parts.append(tmux(sock, "show-options", scope).stdout)
    return "\n".join(parts)


def check_idempotence() -> None:
    with socket() as sock:
        start(sock, with_config=True)
        before = snapshot(sock)
        tmux(sock, "source-file", str(CONFIG))
        after = snapshot(sock)

    ok = before == after
    detail = "reload changes nothing" if ok else "options changed on second source"
    emit("idempotence", ok, detail)


def list_key(sock: str, table: str, key: str) -> str:
    return tmux(sock, "list-keys", "-T", table, key, check=False).stdout.strip()


def check_bindings() -> None:
    with socket() as sock:
        start(sock, with_config=True)
        reload_line = list_key(sock, "prefix", "r")
        keys = {
            "C-f": list_key(sock, "prefix", "C-f"),
            "y": list_key(sock, "copy-mode-vi", "y"),
            "h": list_key(sock, "prefix", "h"),
            "j": list_key(sock, "prefix", "j"),
            "k": list_key(sock, "prefix", "k"),
            "l": list_key(sock, "prefix", "l"),
        }

    problems: list[str] = []

    match = re.search(r"source-file\s+(\S+)", reload_line)
    if match is None:
        problems.append(f"bind r: {reload_line!r}")
    else:
        path = Path(match.group(1))
        if not path.exists():
            problems.append(f"bind r target missing: {path}")
        elif path.resolve() != CONFIG.resolve():
            problems.append(f"bind r points at {path.resolve()}")

    expectations = {
        "C-f": "tmux-sessionizer.sh",
        "y": "pbcopy",
        "h": "select-pane -L",
        "j": "select-pane -D",
        "k": "select-pane -U",
        "l": "select-pane -R",
    }
    problems += [
        f"{key}: {keys[key]!r}"
        for key, needle in expectations.items()
        if needle not in keys[key]
    ]

    emit("bindings", not problems, "; ".join(problems) or "reload path + 6 keys")


def check_pane_env() -> None:
    with socket() as sock:
        start(sock, with_config=True)
        tmux(
            sock,
            "new-session",
            "-d",
            "-s",
            "env",
            '/bin/sh -c \'printf "TERM=%s\\n" "$TERM"; sleep 60\'',
        )

        def read() -> str | None:
            pane = tmux(sock, "capture-pane", "-p", "-t", "env", check=False).stdout
            return pane if "TERM=" in pane else None

        pane = poll(read, timeout=10.0)

    match = re.search(r"^TERM=(\S+)$", pane or "", re.MULTILINE)
    actual = match.group(1) if match else None
    emit("pane-env", actual == "tmux-256color", f"TERM={actual}")


def check_client_features() -> None:
    if shutil.which("script") is None:
        skip("client-features", "script not found")
        return

    with socket() as sock:
        start(sock, with_config=True)
        env = os.environ | {"TERM": "alacritty"}
        attach = subprocess.Popen(
            ["script", "-q", "/dev/null", "tmux", "-L", sock, "attach", "-t", "main"],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:

            def read() -> str | None:
                clients = tmux(
                    sock, "list-clients", "-F", "#{client_termfeatures}", check=False
                )
                return clients.stdout.strip() if clients.returncode == 0 else None

            features = poll(read, timeout=10.0)
        finally:
            tmux(sock, "detach-client", "-a", check=False)
            try:
                attach.wait(timeout=5)
            except subprocess.TimeoutExpired:
                attach.terminate()

    values = set((features or "").split(","))
    wanted = {"clipboard", "ccolour", "cstyle", "focus", "RGB", "title"}
    missing = sorted(wanted - values)
    emit(
        "client-features",
        not missing,
        f"missing {missing}" if missing else ",".join(sorted(values)),
    )


def check_version() -> None:
    running = subprocess.run(
        ["tmux", "-L", DEFAULT_SOCKET, "list-sessions"],
        capture_output=True,
        check=False,
        text=True,
    )
    if running.returncode != 0:
        skip("version", "no default server")
        return

    live = tmux(None, "display", "-p", "#{version}").stdout.strip()
    binary = subprocess.run(
        ["tmux", "-V"], capture_output=True, check=False, text=True
    ).stdout.strip()
    match = re.search(r"(\d+\.\d+)", binary)
    expected = match.group(1) if match else binary
    emit(
        "version",
        live == expected,
        f"running {live}, binary {expected}"
        + ("" if live == expected else "; restart server"),
    )


@click.command()
@click.option(
    "--only",
    multiple=True,
    type=click.Choice(CHECK_IDS, case_sensitive=True),
    help="Run only the selected check ID. Repeatable.",
)
@click.option(
    "--live",
    is_flag=True,
    help="Also query the default tmux server (read-only).",
)
def main(only: tuple[str, ...], live: bool) -> None:
    """Run the tmux config verification harness."""
    selected = set(only) if only else set(CHECK_IDS)

    if "preflight" in selected:
        check_preflight()
    if "discovery" in selected:
        check_discovery()
    if "load" in selected:
        check_load()
    if "options" in selected:
        check_options()
    if "features" in selected:
        check_features()
    if "idempotence" in selected:
        check_idempotence()
    if "bindings" in selected:
        check_bindings()
    if "pane-env" in selected:
        check_pane_env()
    if "client-features" in selected:
        check_client_features()
    if "version" in selected:
        if live:
            check_version()
        else:
            skip("version", "use --live")

    if failures:
        click.echo(f"CHECKS FAILED: {', '.join(failures)}")
        sys.exit(1)

    click.echo("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
