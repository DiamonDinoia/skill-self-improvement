"""Tests for si.py."""

import datetime
import hashlib
import os
import shlex
import shutil
import subprocess
import sys
import threading
from pathlib import Path

SI = Path(
    os.environ.get(
        "SI_PATH",
        Path(__file__).resolve().parent.parent / "skills" / "self-improvement" / "scripts" / "si.py",
    )
)

PLANTED_DIFF = """\
--- a/skills/self-improvement/SKILL.md
+++ b/skills/self-improvement/SKILL.md
@@ -6,3 +6,3 @@
 6. The approval message names the backup path.
-7. The approval message lists every removed rule.
+7. The report lists every removed rule.
 8. The rule list is empty when nothing was removed.
"""

ADDED_ONLY_DIFF = """\
--- a/skills/self-improvement/SKILL.md
+++ b/skills/self-improvement/SKILL.md
@@ -6,2 +6,3 @@
 6. The approval message names the backup path.
+7. The report lists every removed rule.
 8. The rule list is empty when nothing was removed.
"""


def run_si(*args, **kwargs):
    return subprocess.run(
        [sys.executable, str(SI), *args], capture_output=True, text=True, **kwargs
    )


def manifest(root):
    """Map every entry under root to its kind and content hash or link target."""
    out = {}
    root = Path(root)
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        if p.is_symlink():
            out[rel] = ("symlink", os.readlink(p))
        elif p.is_dir():
            out[rel] = ("dir",)
        else:
            out[rel] = ("file", hashlib.sha256(p.read_bytes()).hexdigest())
    return out


def make_src(tmp_path):
    src = tmp_path / "skill"
    (src / "sub").mkdir(parents=True)
    (src / "SKILL.md").write_text("1. One.\n2. Two.\n")
    (src / "sub" / "data.txt").write_text("data\n")
    os.symlink("data.txt", src / "sub" / "link.txt")
    return src


def parse_backup_path(stdout):
    return Path(shlex.split(stdout.splitlines()[0][len("backup: "):])[0])


def helper_copy_path(backup_path):
    # the rule in si.py: BACKUP_PARENT/.si-helper-BACKUPNAME.py
    return backup_path.parent / (".si-helper-" + backup_path.name + ".py")


def test_backup_modify_restore_roundtrip(tmp_path):
    src = make_src(tmp_path)
    original = manifest(src)
    r = run_si("backup", str(src), "--dest", str(tmp_path / "baks"))
    assert r.returncode == 0
    backup_path = parse_backup_path(r.stdout)
    assert backup_path.exists()
    # exact format is pinned by test_printed_restore_line_runs_anywhere
    line2 = r.stdout.splitlines()[1]
    assert line2.startswith("restore: python3 ")
    assert shlex.quote(str(backup_path)) in line2
    (src / "SKILL.md").write_text("changed\n")
    (src / "new.txt").write_text("new\n")
    r = run_si("restore", str(backup_path), str(src))
    assert r.returncode == 0
    assert manifest(src) == original


def test_restore_keeps_pre_restore_backup(tmp_path):
    src = make_src(tmp_path)
    r = run_si("backup", str(src), "--dest", str(tmp_path / "baks"))
    backup_path = parse_backup_path(r.stdout)
    (src / "SKILL.md").write_text("changed\n")
    modified = manifest(src)
    r = run_si("restore", str(backup_path), str(src))
    assert r.returncode == 0
    pre_lines = [ln[len("backup: "):] for ln in r.stdout.splitlines() if ln.startswith("backup: ")]
    assert len(pre_lines) == 1
    pre = Path(shlex.split(pre_lines[0])[0])
    assert pre != backup_path
    assert manifest(pre) == modified


def test_restore_missing_backup_changes_nothing(tmp_path):
    src = make_src(tmp_path)
    before = manifest(src)
    missing = tmp_path / "baks" / "skill-20260101T000000"
    r = run_si("restore", str(missing), str(src))
    assert r.returncode == 2
    assert manifest(src) == before
    assert not missing.parent.exists()


def test_symlink_survives_as_symlink(tmp_path):
    src = make_src(tmp_path)
    r = run_si("backup", str(src), "--dest", str(tmp_path / "baks"))
    backup_path = parse_backup_path(r.stdout)
    (src / "sub" / "link.txt").unlink()
    (src / "sub" / "link.txt").write_text("now a file\n")
    r = run_si("restore", str(backup_path), str(src))
    assert r.returncode == 0
    link = src / "sub" / "link.txt"
    assert link.is_symlink()
    assert os.readlink(link) == "data.txt"


def test_backup_never_overwrites(tmp_path):
    src = make_src(tmp_path)
    dest = tmp_path / "baks"
    first = parse_backup_path(run_si("backup", str(src), "--dest", str(dest)).stdout)
    second = parse_backup_path(run_si("backup", str(src), "--dest", str(dest)).stdout)
    assert first != second
    assert first.exists() and second.exists()
    assert manifest(first) == manifest(second) == manifest(src)


def test_concurrent_file_backups_reserve_distinct_paths(tmp_path, monkeypatch):
    # two same-basename files in one second must get two reserved paths
    si_mod = load_si()

    class Frozen(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 1, 1, tzinfo=tz)

    a, b = tmp_path / "a" / "skill", tmp_path / "b" / "skill"
    a.parent.mkdir()
    b.parent.mkdir()
    a.write_bytes(b"A original\n")
    b.write_bytes(b"B original\n")
    dest = tmp_path / "baks"
    dest.mkdir()
    real_copy, real_unique = si_mod.copy_entry, si_mod.unique_path
    barrier, used = threading.Barrier(2), set()

    def sync_once():
        # meet the other thread once per thread, on either code path
        if threading.get_ident() not in used:
            used.add(threading.get_ident())
            barrier.wait(timeout=20)

    def racing_pick(base):
        path = real_unique(base)
        sync_once()  # both threads pick before either copies
        return path

    def racing_copy(src, dst):
        sync_once()  # both threads reach the create with the same pick
        return real_copy(src, dst)

    results, errors = [], []

    def worker(src):
        try:
            results.append((si_mod.make_backup(str(src), str(dest)), src.read_bytes()))
        except Exception as exc:
            errors.append(repr(exc))

    monkeypatch.setattr(si_mod.datetime, "datetime", Frozen)
    monkeypatch.setattr(si_mod, "unique_path", racing_pick)
    monkeypatch.setattr(si_mod, "copy_entry", racing_copy)
    threads = [threading.Thread(target=worker, args=(src,)) for src in (a, b)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not any(t.is_alive() for t in threads)
    assert errors == []
    assert len(results) == 2
    paths = {path: data for path, data in results}
    assert len(paths) == 2  # each backup kept its own reserved path
    assert sorted(paths.values()) == [b"A original\n", b"B original\n"]
    assert all(Path(p).read_bytes() == d for p, d in paths.items())


def test_removed_rules_planted_diff(tmp_path):
    diff = tmp_path / "p.diff"
    diff.write_text(PLANTED_DIFF)
    r = run_si("removed-rules", str(diff))
    assert r.returncode == 0
    assert r.stdout == (
        "skills/self-improvement/SKILL.md:7: 7. The approval message lists every removed rule.\n"
    )


def test_removed_rules_reads_stdin(tmp_path):
    r = run_si("removed-rules", "-", input=PLANTED_DIFF)
    assert r.returncode == 0
    assert r.stdout == (
        "skills/self-improvement/SKILL.md:7: 7. The approval message lists every removed rule.\n"
    )


def test_removed_rules_additions_only_prints_nothing(tmp_path):
    diff = tmp_path / "a.diff"
    diff.write_text(ADDED_ONLY_DIFF)
    r = run_si("removed-rules", str(diff))
    assert r.returncode == 0
    assert r.stdout == ""


def load_si():
    import importlib.util

    spec = importlib.util.spec_from_file_location("si_mod", SI)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# git C-quoted headers: quote, backslash, tab and octal escapes
QUOTED_DIFF = r"""--- "a/we\"ird name.md"
+++ "b/we\"ird name.md"
@@ -1,2 +1,2 @@
 keep
-b
+c
--- "a/x\\y\tz\177.md"
+++ "b/x\\y\tz\177.md"
@@ -1,2 +1,2 @@
 keep
-d
+e
"""

# GNU diff headers with a space-separated and a tab-separated timestamp
GNU_TIMESTAMP_DIFF = """\
--- a/q.md 2026-01-01 00:00:00
+++ b/q.md 2026-01-02 00:00:00
@@ -2,2 +2,2 @@
 ctx
-removed q
+added q
--- a/r.md\t2026-03-04 05:06:07.000000000 +0200
+++ b/r.md\t2026-03-04 05:06:08.000000000 +0200
@@ -3 +3 @@
-removed r
+added r
"""


def test_backup_dest_inside_src_refused(tmp_path):
    src = make_src(tmp_path)
    before = manifest(src)
    r = run_si("backup", str(src), "--dest", str(src / "baks"))
    assert r.returncode == 2
    assert manifest(src) == before


def test_restore_backup_inside_src_refused(tmp_path):
    src = make_src(tmp_path)
    inside_backup = src / "baks" / "skill-20260101T000000"
    inside_backup.mkdir(parents=True)
    (inside_backup / "SKILL.md").write_text("old\n")
    before = manifest(src)
    r = run_si("restore", str(inside_backup), str(src))
    assert r.returncode == 2
    assert manifest(src) == before


def test_restore_copy_failure_keeps_src(tmp_path, monkeypatch):
    src = make_src(tmp_path)
    backup_path = parse_backup_path(
        run_si("backup", str(src), "--dest", str(tmp_path / "baks")).stdout
    )
    (src / "SKILL.md").write_text("changed\n")
    modified = manifest(src)
    si_mod = load_si()
    real_copytree = shutil.copytree
    calls, reached = [], []

    def flaky(*args, **kw):
        # copytree recurses through the patched global with 7 positional args;
        # count only the 2-arg top-level calls
        if len(args) == 2:
            calls.append(args)
            if len(calls) == 2:
                # copy_entry reserved the staging dir first; fill it in place
                (Path(args[1]) / "partial.txt").write_text("partial\n")
                reached.append("partial-write")
                reached.append("ENOSPC")
                raise OSError(28, "No space left on device")
        return real_copytree(*args, **kw)

    monkeypatch.setattr(shutil, "copytree", flaky)
    rc = si_mod.cmd_restore(str(backup_path), str(src))
    assert rc == 1
    assert reached == ["partial-write", "ENOSPC"], reached
    assert manifest(src) == modified
    assert not any(p.name.startswith(".si-restore-") for p in tmp_path.iterdir())


def test_symlinked_src_backup_holds_target_content(tmp_path):
    real = tmp_path / "realdir"
    real.mkdir()
    (real / "SKILL.md").write_text("1. One.\n")
    link = tmp_path / "link"
    os.symlink("realdir", link)
    r = run_si("backup", str(link), "--dest", str(tmp_path / "baks"))
    assert r.returncode == 0
    backup_path = parse_backup_path(r.stdout)
    assert not backup_path.is_symlink()
    assert (backup_path / "SKILL.md").read_text() == "1. One.\n"
    (real / "SKILL.md").write_text("changed\n")
    r = run_si("restore", str(backup_path), str(link))
    assert r.returncode == 0
    assert link.is_symlink() and os.readlink(link) == "realdir"
    assert (real / "SKILL.md").read_text() == "1. One.\n"


def test_backup_dest_that_is_file_clean_error(tmp_path):
    src = make_src(tmp_path)
    destfile = tmp_path / "destfile"
    destfile.write_text("x\n")
    r = run_si("backup", str(src), "--dest", str(destfile))
    assert r.returncode == 2
    assert "Traceback" not in r.stderr


def test_removed_rules_unquotes_git_c_path(tmp_path):
    diff = tmp_path / "q.diff"
    diff.write_text(QUOTED_DIFF)
    r = run_si("removed-rules", str(diff))
    assert r.returncode == 0
    assert r.stdout == 'we"ird name.md:2: b\n' + "x\\y\tz\x7f.md:2: d\n"


def test_removed_rules_strips_gnu_timestamp(tmp_path):
    diff = tmp_path / "gnu.diff"
    diff.write_text(GNU_TIMESTAMP_DIFF)
    r = run_si("removed-rules", str(diff))
    assert r.returncode == 0
    assert r.stdout == "q.md:3: removed q\nr.md:3: removed r\n"


def test_printed_restore_line_runs_anywhere(tmp_path):
    src = make_src(tmp_path)
    r = run_si("backup", str(src), "--dest", str(tmp_path / "baks"))
    assert r.returncode == 0
    backup_path = parse_backup_path(r.stdout)
    line = r.stdout.splitlines()[1][len("restore: "):]
    # the line always names the helper copy beside the backup tree
    assert line.startswith("python3 " + shlex.quote(str(helper_copy_path(backup_path))))
    (src / "SKILL.md").write_text("changed\n")
    r2 = subprocess.run(["bash", "-c", line], capture_output=True, text=True, cwd=tmp_path)
    assert r2.returncode == 0
    assert manifest(src) == manifest(backup_path)


def test_printed_restore_line_survives_helper_replacement(tmp_path):
    # the helper runs from inside SRC; an adoption can replace it
    src = make_src(tmp_path)
    helper = src / "scripts" / "si.py"
    helper.parent.mkdir()
    shutil.copy2(SI, helper)
    original = manifest(src)
    r = subprocess.run(
        [sys.executable, str(helper), "backup", str(src), "--dest", str(tmp_path / "baks")],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    line = r.stdout.splitlines()[1][len("restore: "):]
    helper.write_text("import sys\nsys.exit(23)\n")
    (src / "SKILL.md").write_text("broken\n")
    r2 = subprocess.run(["bash", "-c", line], capture_output=True, text=True, cwd=tmp_path)
    assert r2.returncode == 0
    assert manifest(src) == original


def test_restore_ancestor_backup_refused(tmp_path):
    case = tmp_path / "ancestor"
    src = case / "backup" / "middle" / "skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("Current skill\n")
    before = manifest(src)
    r = run_si("restore", str(case / "backup"), str(src))
    assert r.returncode == 2
    assert manifest(src) == before
    # no pre-restore backup and no staging entry appear
    assert sorted(p.name for p in case.iterdir()) == ["backup"]
    assert not any(p.name.startswith(".si-restore-") for p in src.parent.iterdir())


CQUOTE_ESCAPES_DIFF = r"""--- "a/caf\303\251.md"
+++ "b/caf\303\251.md"
@@ -1,2 +1,2 @@
 keep
-b
+c
--- "a/x\a\b\f\v\ry.md"
+++ "b/x\a\b\f\v\ry.md"
@@ -1,2 +1,2 @@
 keep
-d
+e
"""

DATE_IN_PATH_DIFF = """\
--- a/report 2026-01-01 notes.md
+++ b/report 2026-01-01 notes.md
@@ -1,2 +1,2 @@
 keep
-removed x
+added x
"""

CTIME_DIFF = """\
--- a/q.md Thu Jan  1 00:00:00 1970
+++ b/q.md Thu Jan  1 00:00:00 1971
@@ -1,2 +1,2 @@
 keep
-removed z
+added z
"""


def test_restore_symlinked_backup_pre_backup_survives(tmp_path):
    src = make_src(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "backfile").write_text("restored\n")
    os.symlink(os.path.join("..", "outside", "backfile"), src / "lnk")
    (src / "SKILL.md").write_text("changed\n")
    modified = manifest(src)
    r = run_si("restore", str(src / "lnk"), str(src))
    assert r.returncode == 0
    pre_lines = [ln[len("backup: "):] for ln in r.stdout.splitlines() if ln.startswith("backup: ")]
    assert len(pre_lines) == 1
    pre = Path(shlex.split(pre_lines[0])[0])
    assert pre.exists()
    assert manifest(pre) == modified


def test_restore_through_symlinked_backup_keeps_src_a_tree(tmp_path):
    src = make_src(tmp_path)
    original = manifest(src)
    r = run_si("backup", str(src), "--dest", str(tmp_path / "baks"))
    assert r.returncode == 0
    backup_path = parse_backup_path(r.stdout)
    latest = tmp_path / "latest"
    os.symlink(backup_path, latest)
    (src / "SKILL.md").write_text("changed\n")
    r = run_si("restore", str(latest), str(src))
    assert r.returncode == 0
    assert not src.is_symlink()
    assert manifest(src) == original


def test_restore_double_rename_failure_names_stranded_trees(tmp_path, monkeypatch, capsys):
    src = make_src(tmp_path)
    (src / "SKILL.md").write_text("changed\n")
    modified = manifest(src)
    backup = tmp_path / "backfile"
    backup.write_text("restored\n")
    si_mod = load_si()
    real_rename = os.rename
    calls = []

    def flaky(a, b):
        calls.append((a, b))
        if len(calls) in (2, 3):
            raise OSError(13, "Permission denied (probe)")
        return real_rename(a, b)

    monkeypatch.setattr(os, "rename", flaky)
    rc = si_mod.cmd_restore(str(backup), str(src))
    err = capsys.readouterr().err
    assert rc == 1
    old = tmp_path / (".si-restore-old-" + src.name)
    new = tmp_path / (".si-restore-new-" + src.name)
    assert "old content is at %s" % old in err
    assert str(new) in err
    assert manifest(old) == modified


def test_removed_rules_unquotes_octal_bytes_and_escapes(tmp_path):
    diff = tmp_path / "e.diff"
    diff.write_text(CQUOTE_ESCAPES_DIFF)
    # read stdout as bytes: a decoded CR is lost to universal newlines
    r = subprocess.run([sys.executable, str(SI), "removed-rules", str(diff)], capture_output=True)
    assert r.returncode == 0
    assert r.stdout == b"caf\xc3\xa9.md:2: b\nx\a\b\f\v\ry.md:2: d\n"


def test_removed_rules_keeps_date_token_inside_path(tmp_path):
    diff = tmp_path / "d.diff"
    diff.write_text(DATE_IN_PATH_DIFF)
    r = run_si("removed-rules", str(diff))
    assert r.returncode == 0
    assert r.stdout == "report 2026-01-01 notes.md:2: removed x\n"


def test_removed_rules_strips_ctime_timestamp(tmp_path):
    diff = tmp_path / "c.diff"
    diff.write_text(CTIME_DIFF)
    r = run_si("removed-rules", str(diff))
    assert r.returncode == 0
    assert r.stdout == "q.md:2: removed z\n"


RAW_NAME = os.fsdecode(b"caf\xe9")  # one raw byte, as os.fsencode builds it

RAW_BYTE_DIFF = b"""--- "a/caf\\341.md"
+++ "b/caf\\341.md"
@@ -1,2 +1,2 @@
 keep
-b
+c
"""


def run_si_bytes(*args):
    return subprocess.run([sys.executable, str(SI), *args], capture_output=True)


def test_backup_raw_byte_name_prints_lines(tmp_path):
    src = tmp_path / RAW_NAME
    src.mkdir()
    (src / "SKILL.md").write_text("1. One.\n")
    r = run_si_bytes("backup", str(src), "--dest", str(tmp_path / "baks"))
    assert r.returncode == 0
    assert b"Traceback" not in r.stderr
    lines = r.stdout.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith(b"backup: ") and b"caf\xe9" in lines[0]
    assert lines[1].startswith(b"restore: python3 ") and b"caf\xe9" in lines[1]


def test_printed_restore_line_round_trips_raw_byte_name(tmp_path):
    src = tmp_path / RAW_NAME
    src.mkdir()
    (src / "SKILL.md").write_text("1. One.\n")
    original = manifest(src)
    r = run_si_bytes("backup", str(src), "--dest", str(tmp_path / "baks"))
    assert r.returncode == 0
    line = r.stdout.splitlines()[1][len(b"restore: "):]
    (src / "SKILL.md").write_text("changed\n")
    r2 = subprocess.run([b"bash", b"-c", line], capture_output=True, cwd=str(tmp_path))
    assert r2.returncode == 0
    assert manifest(src) == original


def test_raw_byte_name_guard_and_error_exit_clean(tmp_path):
    real = tmp_path / "realdir"
    real.mkdir()
    os.symlink("realdir", tmp_path / "link")
    given = os.path.join(str(tmp_path), "link", RAW_NAME)
    resolved = os.path.join(str(tmp_path), "realdir", RAW_NAME)
    r = run_si_bytes("restore", given, str(real))
    assert r.returncode == 2
    assert b"Traceback" not in r.stderr
    assert b"restore: no such backup: " in r.stderr
    assert os.fsencode(given) in r.stderr
    assert b"(" + os.fsencode(resolved) + b")" in r.stderr
    destfile = tmp_path / ("d" + RAW_NAME)
    destfile.write_text("x\n")
    src = make_src(tmp_path)
    r2 = run_si_bytes("backup", str(src), "--dest", str(destfile))
    assert r2.returncode == 2
    assert b"Traceback" not in r2.stderr
    assert r2.stderr.startswith(b"backup: ")


def test_removed_rules_raw_byte_path(tmp_path):
    diff = tmp_path / "r.diff"
    diff.write_bytes(RAW_BYTE_DIFF)
    r = run_si_bytes("removed-rules", str(diff))
    assert r.returncode == 0
    assert r.stdout == b"caf\xe1.md:2: b\n"


def test_symlink_helper_outside_src_line_survives(tmp_path):
    # A1: SRC holds si.py as a symlink to a target outside SRC
    real = tmp_path / "real"
    real.mkdir()
    shutil.copy2(SI, real / "si.py")
    src = make_src(tmp_path)
    (src / "scripts").mkdir()
    os.symlink(os.path.relpath(real / "si.py", src / "scripts"), src / "scripts" / "si.py")
    original = manifest(src)
    r = subprocess.run(
        [sys.executable, str(src / "scripts" / "si.py"), "backup", str(src),
         "--dest", str(tmp_path / "baks")],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    backup_path = parse_backup_path(r.stdout)
    line = r.stdout.splitlines()[1][len("restore: "):]
    (src / "scripts" / "si.py").write_text("import sys\nsys.exit(23)\n")  # breaks the target
    (src / "SKILL.md").write_text("broken\n")
    r2 = subprocess.run(["bash", "-c", line], capture_output=True, text=True, cwd=tmp_path)
    assert r2.returncode == 0
    assert manifest(src) == manifest(backup_path) == original


def test_src_is_helper_file_line_runs(tmp_path):
    # A4: SRC is the helper file itself
    srcfile = tmp_path / "si.py"
    shutil.copy2(SI, srcfile)
    r = subprocess.run(
        [sys.executable, str(srcfile), "backup", str(srcfile), "--dest", str(tmp_path / "baks")],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    line = r.stdout.splitlines()[1][len("restore: "):]
    srcfile.write_text("import sys\nsys.exit(23)\n")
    r2 = subprocess.run(["bash", "-c", line], capture_output=True, text=True, cwd=tmp_path)
    assert r2.returncode == 0
    assert srcfile.read_bytes() == Path(SI).read_bytes()


def test_printed_line_survives_helper_outside_replaced(tmp_path):
    helper = tmp_path / "si.py"
    shutil.copy2(SI, helper)
    src = make_src(tmp_path)
    original = manifest(src)
    r = subprocess.run(
        [sys.executable, str(helper), "backup", str(src), "--dest", str(tmp_path / "baks")],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    line = r.stdout.splitlines()[1][len("restore: "):]
    helper.write_text("import sys\nsys.exit(23)\n")
    (src / "SKILL.md").write_text("broken\n")
    r2 = subprocess.run(["bash", "-c", line], capture_output=True, text=True, cwd=tmp_path)
    assert r2.returncode == 0
    assert manifest(src) == original


def test_helper_copy_write_failure_falls_back(tmp_path, monkeypatch, capsys):
    src = make_src(tmp_path)
    dest = tmp_path / "baks"
    si_mod = load_si()

    class Frozen(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 1, 1, 12, 0, 0, tzinfo=tz)

    monkeypatch.setattr(si_mod.datetime, "datetime", Frozen)
    blocked = helper_copy_path(dest / "skill-20260101T120000")
    blocked.parent.mkdir()
    blocked.mkdir()  # a directory at the copy path makes the write fail
    rc = si_mod.cmd_backup(str(src), str(dest))
    captured = capsys.readouterr()
    assert rc == 0
    assert "helper copy not written" in captured.err
    backup_path = parse_backup_path(captured.out)
    assert manifest(backup_path) == manifest(src)
    line = captured.out.splitlines()[1][len("restore: "):]
    assert shlex.split(line)[1] == os.path.realpath(SI)
    r2 = subprocess.run(["bash", "-c", line], capture_output=True, text=True, cwd=tmp_path)
    assert r2.returncode == 0


def test_restore_via_live_script_ignores_helper_copy(tmp_path):
    src = make_src(tmp_path)
    original = manifest(src)
    r = run_si("backup", str(src), "--dest", str(tmp_path / "baks"))
    assert r.returncode == 0
    backup_path = parse_backup_path(r.stdout)
    copy = helper_copy_path(backup_path)
    assert copy.is_file() and not copy.is_symlink()
    assert copy.stat().st_mode & 0o777 == 0o755
    copy_bytes = copy.read_bytes()
    (src / "SKILL.md").write_text("changed\n")
    r2 = run_si("restore", str(backup_path), str(src))
    assert r2.returncode == 0
    assert manifest(src) == original
    assert copy.read_bytes() == copy_bytes  # restore keeps the helper copy


def test_backup_fifo_src_refused_no_reservation(tmp_path):
    # a FIFO source blocks a read forever; the backup must refuse it first
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    dest = tmp_path / "baks"
    r = run_si("backup", str(fifo), "--dest", str(dest), timeout=10)
    assert r.returncode == 2
    assert os.path.realpath(fifo) in r.stderr
    assert list(dest.iterdir()) == []  # no reserved file left behind


def test_backup_fifo_in_tree_refused_before_fill(tmp_path, monkeypatch, capsys):
    # a FIFO in a tree is refused before the fill starts; the reservation goes
    src = make_src(tmp_path)
    os.mkfifo(src / "sub" / "pipe")
    dest = tmp_path / "baks"
    si_mod = load_si()

    def no_fill(*args, **kw):
        raise AssertionError("the fill must not start on a FIFO in the tree")

    monkeypatch.setattr(shutil, "copytree", no_fill)
    rc = si_mod.cmd_backup(str(src), str(dest))
    assert rc == 2
    assert os.path.realpath(src / "sub" / "pipe") in capsys.readouterr().err
    assert list(dest.iterdir()) == []  # the reserved tree is removed
