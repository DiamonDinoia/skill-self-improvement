"""install.sh checks: non-destructive links, arguments, idempotent reruns.

The suite runs the script that INSTALL_SH names. The default is the repo copy.
"""
import hashlib
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = Path(os.environ.get("INSTALL_SH", REPO_ROOT / "install.sh"))

COMMAND_LINK = "xdg/opencode/commands/self-improvement.md"
SKILL_LINK = "home/.hermes/skills/self-improvement"
OC_SKILL_LINK = "xdg/opencode/skills/self-improvement"
FIXED_TS = "20260101T000000"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def manifest(root):
    """List every path with its hash or link target; equal lists mean no change."""
    entries = []
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root))
        if path.is_symlink():
            entries.append(f"{rel} -> {os.readlink(path)}")
        elif path.is_file():
            entries.append(f"{rel} {sha256(path.read_bytes())}")
        else:
            entries.append(rel)
    return entries


def install_env(tmp_path, path_prepend=None):
    """Build the environment with HOME and XDG_CONFIG_HOME inside tmp_path."""
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env.pop("HERMES_HOME", None)
    if path_prepend is not None:
        env["PATH"] = str(path_prepend) + os.pathsep + env["PATH"]
    return env


def run_install(tmp_path, *args, path_prepend=None):
    """Run install.sh with HOME and XDG_CONFIG_HOME inside tmp_path."""
    return subprocess.run(
        ["bash", str(INSTALL_SH), *args],
        capture_output=True,
        text=True,
        env=install_env(tmp_path, path_prepend),
        check=False,
    )


def backups_of(path):
    """List the preserved old paths: the payload inside each backup dir."""
    out = []
    for p in sorted(path.parent.glob(path.name + ".bak*")):
        out.append(p / path.name if p.is_dir() and not p.is_symlink() else p)
    return out


def make_shim(tmp_path, name, body):
    """Write one PATH shim and return its directory."""
    shims = tmp_path / "shims"
    shims.mkdir(exist_ok=True)
    shim = shims / name
    shim.write_text("#!/bin/sh\n" + body)
    shim.chmod(0o755)
    return shims


def test_help_writes_nothing(tmp_path):
    before = manifest(tmp_path)
    result = run_install(tmp_path, "--help")
    assert result.returncode == 0
    assert "usage" in result.stdout
    assert manifest(tmp_path) == before, "--help must not write"


def test_dry_run_writes_nothing(tmp_path):
    before = manifest(tmp_path)
    result = run_install(tmp_path, "--dry-run")
    assert result.returncode == 0
    assert manifest(tmp_path) == before, "--dry-run must not write"


def test_unknown_argument_exits_two(tmp_path):
    before = manifest(tmp_path)
    result = run_install(tmp_path, "--bogus")
    assert result.returncode == 2
    assert manifest(tmp_path) == before, "a rejected argument must not write"


def test_manifest_hashes_content_and_link_target(tmp_path):
    file = tmp_path / "a.txt"
    file.write_bytes(b"one")
    before = manifest(tmp_path)
    file.write_bytes(b"two")
    assert manifest(tmp_path) != before, "manifest must hash file content"
    link = tmp_path / "b"
    link.symlink_to(file)
    before = manifest(tmp_path)
    link.unlink()
    link.symlink_to(tmp_path / "other")
    assert manifest(tmp_path) != before, "manifest must record the link target"


def test_regular_file_at_link_path_is_backed_up(tmp_path):
    dst = tmp_path / COMMAND_LINK
    dst.parent.mkdir(parents=True)
    original = b"USER FILE - MUST SURVIVE\n"
    dst.write_bytes(original)
    result = run_install(tmp_path)
    assert result.returncode == 0
    backups = backups_of(dst)
    assert len(backups) == 1, "the old file must survive as one backup"
    assert sha256(backups[0].read_bytes()) == sha256(original)
    assert dst.is_symlink(), "the link must replace the backed-up file"
    target = Path(os.readlink(dst))
    assert target.name == "self-improvement.md"


def test_real_directory_at_link_path_is_backed_up(tmp_path):
    dst = tmp_path / SKILL_LINK
    dst.mkdir(parents=True)
    (dst / "mine.md").write_text("keep me\n")
    result = run_install(tmp_path)
    assert result.returncode == 0
    backups = backups_of(dst)
    assert len(backups) == 1, "the old directory must survive as one backup"
    assert (backups[0] / "mine.md").read_text() == "keep me\n"
    assert dst.is_symlink(), "the link must replace the backed-up directory"


def test_foreign_symlink_at_link_path_is_backed_up(tmp_path):
    foreign = tmp_path / "foreign.md"
    foreign.write_bytes(b"foreign")
    dst = tmp_path / COMMAND_LINK
    dst.parent.mkdir(parents=True)
    dst.symlink_to(foreign)
    result = run_install(tmp_path)
    assert result.returncode == 0
    backups = backups_of(dst)
    assert len(backups) == 1, "the foreign link must survive as one backup"
    assert backups[0].is_symlink(), "the backup keeps the link form"
    assert Path(os.readlink(backups[0])) == foreign
    assert foreign.read_bytes() == b"foreign", "the foreign target must stay intact"
    assert dst.is_symlink()
    assert Path(os.readlink(dst)).name == "self-improvement.md"


def test_dangling_symlink_at_link_path_is_backed_up(tmp_path):
    gone = tmp_path / "no-such-target"
    dst = tmp_path / SKILL_LINK
    dst.parent.mkdir(parents=True)
    dst.symlink_to(gone)
    result = run_install(tmp_path)
    assert result.returncode == 0
    backups = backups_of(dst)
    assert len(backups) == 1, "the dangling link must survive as one backup"
    assert backups[0].is_symlink(), "the backup keeps the link form"
    assert Path(os.readlink(backups[0])) == gone
    assert dst.is_symlink()
    assert Path(os.readlink(dst)).name == "self-improvement"


def test_bak_name_collision_gets_distinct_name(tmp_path):
    dst = tmp_path / COMMAND_LINK
    dst.parent.mkdir(parents=True)
    original = b"USER FILE - MUST SURVIVE\n"
    dst.write_bytes(original)
    first = Path(str(dst) + ".bak-" + FIXED_TS)
    first.write_bytes(b"first backup - unchanged\n")
    shims = make_shim(tmp_path, "date", f"echo {FIXED_TS}\n")
    result = run_install(tmp_path, path_prepend=shims)
    assert result.returncode == 0
    assert first.read_bytes() == b"first backup - unchanged\n", (
        "the colliding backup must stay unchanged"
    )
    second = Path(str(first) + ".1") / dst.name
    assert second.is_file(), "the second backup needs a distinct name"
    assert sha256(second.read_bytes()) == sha256(original)
    assert len(backups_of(dst)) == 2
    assert dst.is_symlink()


def test_success_exits_zero_with_empty_stderr(tmp_path):
    result = run_install(tmp_path)
    assert result.returncode == 0
    assert result.stderr == "", "a successful install must print no failure report"


def test_failure_reports_done_missing_and_backups(tmp_path):
    dst = tmp_path / COMMAND_LINK
    dst.parent.mkdir(parents=True)
    original = b"USER FILE - MUST SURVIVE\n"
    dst.write_bytes(original)
    state = tmp_path / "ln-calls"
    real_ln = shutil.which("ln")
    shims = make_shim(
        tmp_path,
        "ln",
        f'n=$(cat {state} 2>/dev/null || echo 0)\n'
        f'echo $((n + 1)) > {state}\n'
        'if [ "$n" -ge 1 ]; then echo "ln: injected failure" >&2; exit 1; fi\n'
        f'exec {real_ln} "$@"\n',
    )
    result = run_install(tmp_path, path_prepend=shims)
    assert result.returncode != 0, "the injected ln failure must fail the run"
    text = result.stdout + result.stderr
    backups = backups_of(dst)
    assert len(backups) == 1, "the backup made before the failure must stay"
    assert sha256(backups[0].read_bytes()) == sha256(original)
    lines = text.splitlines()
    linked_line = next(l for l in lines if l.startswith("install.sh: linked:"))
    missing_line = next(l for l in lines if l.startswith("install.sh: not linked:"))
    assert str(tmp_path / OC_SKILL_LINK) in linked_line
    for missing in (dst, tmp_path / SKILL_LINK):
        assert str(missing) in missing_line, "the report must name the missing link"
    assert str(backups[0]) in text, "the report must name the backup made so far"
    assert (tmp_path / OC_SKILL_LINK).is_symlink(), "a done link must stay in place"


def test_sigint_reports_the_signal_and_the_process_dies_of_it(tmp_path):
    state = tmp_path / "ln-calls"
    real_ln = shutil.which("ln")
    shims = make_shim(
        tmp_path,
        "ln",
        f'n=$(cat {state} 2>/dev/null || echo 0)\n'
        f'echo $((n + 1)) > {state}\n'
        'if [ "$n" -ge 1 ]; then sleep 30; fi\n'
        f'exec {real_ln} "$@"\n',
    )
    proc = subprocess.Popen(
        ["bash", str(INSTALL_SH)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=install_env(tmp_path, shims),
        start_new_session=True,
    )
    try:
        for _ in range(200):
            if state.exists() and state.read_text().strip() == "2":
                break
            time.sleep(0.05)
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGINT)
        try:
            out, err = proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise AssertionError("install.sh must stop on SIGINT")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()
    assert proc.returncode == -2, "the process must die of SIGINT"
    text = out + err
    assert "interrupted by SIGINT" in text, "the report must name the signal"
    assert "install.sh: linked:" in text, "the report must list the links as for a failure"


def test_second_run_is_idempotent(tmp_path):
    dst = tmp_path / COMMAND_LINK
    dst.parent.mkdir(parents=True)
    original = b"USER FILE - MUST SURVIVE\n"
    dst.write_bytes(original)
    assert run_install(tmp_path).returncode == 0
    first = backups_of(dst)
    assert len(first) == 1, "the first run must keep the old file as one backup"
    assert sha256(first[0].read_bytes()) == sha256(original)
    assert run_install(tmp_path).returncode == 0
    assert backups_of(dst) == first, "a second run must add no new backup"
    assert dst.is_symlink()


def _raise_timeout(*_):
    raise TimeoutError("an install never reached the backup move")


def test_two_concurrent_installs_keep_the_user_file(tmp_path):
    """Two installs at once must keep the user file in a backup and both exit 0."""
    dst = tmp_path / OC_SKILL_LINK
    dst.parent.mkdir(parents=True)
    original = b"USER FILE - MUST SURVIVE\n"
    dst.write_bytes(original)
    real_mv = shutil.which("mv")
    shims = make_shim(tmp_path, "date", f"echo {FIXED_TS}\n")
    make_shim(
        tmp_path,
        "mv",
        'printf ready > "$READY"\n'
        'read -r _ < "$RELEASE"\n'
        f'exec {real_mv} "$@"\n',
    )
    env = install_env(tmp_path, shims)
    processes = []
    for index in (1, 2):
        ready = tmp_path / f"ready{index}"
        release = tmp_path / f"release{index}"
        os.mkfifo(ready)
        os.mkfifo(release)
        proc = subprocess.Popen(
            ["bash", str(INSTALL_SH)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=dict(env, READY=str(ready), RELEASE=str(release)),
            cwd=tmp_path,
        )
        processes.append((proc, ready, release))
    results = []
    signal.signal(signal.SIGALRM, _raise_timeout)
    try:
        # The FIFO handshake pins both installs at their backup move.
        for _, ready, _ in processes:
            signal.alarm(30)
            with ready.open() as f:
                assert f.read() == "ready", "each install must reach its backup move"
            signal.alarm(0)
        for proc, _, release in processes:
            with release.open("w") as f:
                f.write("go\n")
            proc.communicate(timeout=30)
            results.append(proc.returncode)
    finally:
        signal.alarm(0)
        for proc, _, _ in processes:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
    assert results == [0, 0], "both concurrent installs must exit 0"
    kept = [
        p
        for p in backups_of(dst)
        if p.is_file() and not p.is_symlink() and p.read_bytes() == original
    ]
    assert kept, "the user file must survive in a backup"
    assert dst.is_symlink(), "the link must sit at the destination"
    assert Path(os.readlink(dst)).name == "self-improvement"


def test_signal_after_move_names_the_backup(tmp_path):
    """A signal after the backup move must name the backup in the report."""
    real_mv = shutil.which("mv")
    for sig in ("INT", "TERM"):
        case = tmp_path / sig
        case.mkdir()
        dst = case / OC_SKILL_LINK
        dst.parent.mkdir(parents=True)
        original = b"USER FILE - MUST SURVIVE\n"
        dst.write_bytes(original)
        shims = make_shim(
            case,
            "mv",
            f'{real_mv} "$@" || exit $?\n' f'kill -{sig} "$PPID"\n',
        )
        result = run_install(case, path_prepend=shims)
        assert result.returncode == -getattr(signal, "SIG" + sig), (
            f"SIG{sig}: the process must die of the signal"
        )
        assert f"interrupted by SIG{sig}" in result.stderr
        backups = backups_of(dst)
        assert len(backups) == 1, "the move must leave one backup"
        assert str(backups[0]) in result.stderr, (
            f"SIG{sig}: the report must name the moved backup"
        )
        assert backups[0].is_file() and not backups[0].is_symlink(), (
            "the moved user file must stay"
        )
        assert backups[0].read_bytes() == original


def test_backup_move_failure_keeps_user_file_and_fails(tmp_path):
    """A failed backup move must keep the user file and name the failure."""
    dst = tmp_path / OC_SKILL_LINK
    dst.parent.mkdir(parents=True)
    original = b"USER FILE - MUST SURVIVE\n"
    dst.write_bytes(original)
    real_mv = shutil.which("mv")
    shims = make_shim(
        tmp_path,
        "mv",
        # Fail only at the backup move, after mkdir reserved the backup dir.
        'case "$2" in\n'
        "  *.bak-*)\n"
        '    if [ -d "${2%/*}" ]; then\n'
        '      echo "mv: injected failure" >&2\n'
        "      exit 1\n"
        "    fi\n"
        "    ;;\n"
        "esac\n"
        f'exec {real_mv} "$@"\n',
    )
    result = run_install(tmp_path, path_prepend=shims)
    assert result.returncode != 0, "a failed backup move must fail the run"
    assert dst.is_file() and not dst.is_symlink(), (
        "the user file must stay at its original path with no link over it"
    )
    assert dst.read_bytes() == original, "the user file must keep its bytes"
    text = result.stdout + result.stderr
    assert "cannot back up" in text, "the report must name the backup failure"
    assert "failed with exit" in text, "the report must name the failed run"
    reserved = list(dst.parent.glob(dst.name + ".bak*"))
    assert not reserved or all(str(p) in text for p in reserved), (
        "the reserved backup dir must be gone or named in the report"
    )


def copy_installer_with_sources(tmp_path):
    """Copy install.sh and its link sources so a stray link stays in tmp_path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copy2(INSTALL_SH, repo / "install.sh")
    for rel in ("skills", ".opencode"):
        src = INSTALL_SH.parent / rel
        if src.is_dir():
            shutil.copytree(src, repo / rel, symlinks=True)
    return repo


def test_two_concurrent_installs_at_link_make_no_self_link(tmp_path):
    """Two installs racing at ln must leave no symlink inside the source tree."""
    repo = copy_installer_with_sources(tmp_path)
    real_ln = shutil.which("ln")
    shims = make_shim(
        tmp_path,
        "ln",
        'case "$3" in\n'
        "  */opencode/skills/self-improvement)\n"
        '    printf ready > "$READY"\n'
        '    read -r _ < "$RELEASE"\n'
        "    ;;\n"
        "esac\n"
        f'exec {real_ln} "$@"\n',
    )
    env = install_env(tmp_path, shims)
    processes = []
    for index in (1, 2):
        ready = tmp_path / f"ready{index}"
        release = tmp_path / f"release{index}"
        os.mkfifo(ready)
        os.mkfifo(release)
        proc = subprocess.Popen(
            ["bash", str(repo / "install.sh")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=dict(env, READY=str(ready), RELEASE=str(release)),
            cwd=tmp_path,
        )
        processes.append((proc, ready, release))
    signal.signal(signal.SIGALRM, _raise_timeout)
    try:
        # The FIFO handshake pins both installs at ln with the destination absent.
        for _, ready, _ in processes:
            signal.alarm(30)
            with ready.open() as f:
                assert f.read() == "ready", "each install must reach ln"
            signal.alarm(0)
        runs = []
        # Release in order so the second install meets the finished link.
        for proc, _, release in processes:
            with release.open("w") as f:
                f.write("go\n")
            stdout, stderr = proc.communicate(timeout=30)
            runs.append((proc.returncode, stdout, stderr))
    finally:
        signal.alarm(0)
        for proc, _, _ in processes:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
    assert [rc for rc, _, _ in runs] == [0, 0], "both concurrent installs must exit 0"
    dst = tmp_path / OC_SKILL_LINK
    assert dst.is_symlink(), "the link must sit at the destination"
    assert Path(os.readlink(dst)) == repo / "skills" / "self-improvement"
    stray = [p for p in (repo / "skills").rglob("*") if p.is_symlink()]
    assert not stray, f"no symlink may appear inside the source tree: {stray}"


def test_real_directory_at_link_path_at_ln_fails_and_stays_untouched(tmp_path):
    """A directory that appears at the link path before ln must fail the run."""
    dst = tmp_path / OC_SKILL_LINK
    dst.parent.mkdir(parents=True)
    dst.write_bytes(b"USER FILE - MUST SURVIVE\n")
    real_ln = shutil.which("ln")
    # The shim plants the occupying directory at DST in the window between
    # the backup move and the link, then runs the real ln with the same args.
    shims = make_shim(
        tmp_path,
        "ln",
        'case "$3" in\n'
        "  */opencode/skills/self-improvement)\n"
        '    mkdir "$3"\n'
        '    printf "OCCUPIER - MUST SURVIVE\\n" > "$3/inside.txt"\n'
        "    ;;\n"
        "esac\n"
        f'exec {real_ln} "$@"\n',
    )
    result = run_install(tmp_path, path_prepend=shims)
    assert result.returncode != 0, "a real directory at the link path must fail"
    text = result.stdout + result.stderr
    assert str(dst) in text, "the report must name the occupied link path"
    assert sorted(p.name for p in dst.iterdir()) == ["inside.txt"], (
        "nothing new may appear inside the occupying directory"
    )
    assert (dst / "inside.txt").read_text() == "OCCUPIER - MUST SURVIVE\n", (
        "the occupying directory must keep its contents"
    )


def test_signalled_backup_move_reports_the_backup(tmp_path):
    """A backup move that finishes before its mv dies must be reported."""
    dst = tmp_path / OC_SKILL_LINK
    dst.parent.mkdir(parents=True)
    original = b"USER FILE - MUST SURVIVE\n"
    dst.write_bytes(original)
    real_mv = shutil.which("mv")
    shims = make_shim(
        tmp_path,
        "mv",
        f'{real_mv} "$@" || exit $?\n' "kill -TERM $$\n",
    )
    result = run_install(tmp_path, path_prepend=shims)
    assert result.returncode == 0, "the finished move must let the install continue"
    backups = backups_of(dst)
    assert len(backups) == 1, "the move must leave one backup"
    assert backups[0].read_bytes() == original, "the backup must keep the original bytes"
    assert str(backups[0]) in result.stdout + result.stderr, (
        "the report must name the backup that the signalled mv completed"
    )
    assert dst.is_symlink(), "the link must sit at the destination"
