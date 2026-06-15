"""Subprocess helpers with timeouts for external math tools.

Kept small and dependency-free. ``run_cli`` is the seam tests monkeypatch so the
suite needs neither the real provers nor a network.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class CliResult:
    """Outcome of a CLI invocation."""

    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


def run_cli(
    cmd: list[str],
    *,
    stdin: str | None = None,
    timeout: float = 30.0,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
) -> CliResult:
    """Run a command, capturing stdout/stderr, returning a CliResult.

    A timeout yields ``timed_out=True`` (never raises); other OS errors surface
    as a non-zero return code with the message on stderr.
    """
    try:
        proc = subprocess.run(
            cmd,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=cwd,
            check=False,
        )
        return CliResult(proc.returncode, proc.stdout, proc.stderr)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        err = exc.stderr or ""
        out = out.decode() if isinstance(out, bytes) else out
        err = err.decode() if isinstance(err, bytes) else err
        return CliResult(-1, out, err, timed_out=True)
    except OSError as exc:
        return CliResult(-1, "", str(exc))


def docker_cmd(
    image: str,
    args: list[str],
    *,
    network: bool = False,
    memory: str | None = "4g",
    cpus: str | None = "2",
    mounts: list[tuple[str, str]] | None = None,
    read_only: bool = True,
) -> list[str]:
    """Build a sandboxed ``docker run`` command (per design doc §C).

    Defaults: no network, capped memory/cpus, read-only mounts.
    """
    cmd = ["docker", "run", "--rm"]
    if not network:
        cmd += ["--network", "none"]
    if memory:
        cmd += ["--memory", memory]
    if cpus:
        cmd += ["--cpus", cpus]
    for src, dst in mounts or []:
        cmd += ["-v", f"{src}:{dst}{':ro' if read_only else ''}"]
    cmd += [image, *args]
    return cmd
