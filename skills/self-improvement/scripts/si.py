#!/usr/bin/env python3
"""Backup, restore and removed-rule helpers for skill self-improvement."""

import argparse
import datetime
import os
import re
import shlex
import shutil
import stat
import sys


def out(msg, err=False):
    print(msg, file=sys.stderr if err else sys.stdout)

def named(given, resolved):
    # report the path the caller passed; add the resolved one only when it differs
    return given if given == resolved else "%s (%s)" % (given, resolved)

def check_regular(path):
    # a FIFO, socket or device can block or grow forever; refuse it loudly
    st = os.lstat(path)
    if not (stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode)):
        raise shutil.SpecialFileError("%s is not a regular file" % path)

def copy_entry(src, dst):
    # symlinks stay symlinks in every copy
    # each branch reserves DST at create time and never replaces a taken name
    if os.path.islink(src):
        os.symlink(os.readlink(src), dst)
    elif os.path.isdir(src):
        os.mkdir(dst)  # the reservation; a taken name raises FileExistsError
        try:
            for root, _, names in os.walk(src):
                for name in names:
                    check_regular(os.path.join(root, name))  # refuse before the fill
            shutil.copytree(src, dst, symlinks=True, dirs_exist_ok=True)
        except BaseException:
            discard(dst)  # the reserved name is ours alone
            raise
    else:
        check_regular(src)  # refuse before any destination is reserved
        # O_EXCL reserves the name; copy bytes and metadata into that file
        os.close(os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644))
        try:
            shutil.copyfile(src, dst)
            shutil.copystat(src, dst)
        except BaseException:
            discard(dst)  # the reserved name is ours alone
            raise


def unique_path(base):
    path, counter = base, 1
    while os.path.lexists(path):
        path = "%s-%d" % (base, counter)
        counter += 1
    return path


def copy_entry_fresh(src, base):
    """Copy src to a fresh name at base. Return the copy path."""
    # the create inside copy_entry reserves the name; a clash retries the next suffix
    path, counter = unique_path(base), 1
    while True:
        try:
            copy_entry(src, path)
            return path
        except FileExistsError:
            if not os.path.lexists(path):
                raise  # the fill failed after its cleanup, not a name clash
            path = "%s-%d" % (base, counter)
            counter += 1


def fresh_name(src, base):
    """Reserve a fresh name at base for a rename of src. Return the name."""
    # the rename after this replaces only the reservation, never other data
    path, counter = unique_path(base), 1
    while True:
        try:
            if os.path.isdir(src):
                os.mkdir(path)  # empty dir: a rename can replace it
            else:
                os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644))
            return path
        except FileExistsError:
            path = "%s-%d" % (base, counter)
            counter += 1


def inside(path, root):
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path == root or path.startswith(root + os.sep)


def remove_entry(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.unlink(path)


def discard(path):
    try:
        if os.path.lexists(path):
            remove_entry(path)
    except OSError:
        pass


def make_backup(src, dest):
    """Copy src into dest as NAME-YYYYmmddTHHMMSS. Return the copy path."""
    name = os.path.basename(os.path.normpath(src))
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    return copy_entry_fresh(src, os.path.join(dest, name + "-" + stamp))

def helper_copy(path):
    """Copy the running helper beside the backup tree. Return the path to call."""
    # the copy survives any change to the live helper: a replacement, a
    # symlink inside SRC, or SRC being the helper file itself
    live = os.path.realpath(__file__)
    dst = os.path.join(os.path.dirname(path),
                       ".si-helper-%s.py" % os.path.basename(path))
    try:
        with open(live, "rb") as fh:
            data = fh.read()
        # O_EXCL: never overwrite or write through a symlink at the copy path
        fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o755)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(dst, 0o755)  # the umask must not strip the exec bit
        return dst
    except OSError as exc:
        # the backup is done; the fallback line runs the live helper
        out("backup: helper copy not written: %s" % exc, err=True)
        return live


def cmd_backup(src, dest):
    # a symlinked SRC copies the target tree, so the backup holds data
    given_dest = dest
    src = os.path.realpath(src)
    dest = os.path.realpath(dest)
    if inside(dest, src):
        out("backup: --dest is inside src: %s" % named(given_dest, dest), err=True)
        return 2
    try:
        os.makedirs(dest, exist_ok=True)
        path = make_backup(src, dest)
    except OSError as exc:
        out("backup: %s" % exc, err=True)
        return 2
    out("backup: %s" % shlex.quote(path))
    helper = helper_copy(path)
    out("restore: python3 %s restore %s %s" % (
        shlex.quote(helper), shlex.quote(path), shlex.quote(src)))
    return 0


def cmd_restore(backup_path, src):
    # resolve both once: every check and every write below uses the real paths
    given_backup = backup_path
    backup_path = os.path.realpath(backup_path)
    # a symlinked SRC restores into the target tree, so the link stays
    src = os.path.realpath(src)
    if not os.path.lexists(backup_path):
        out("restore: no such backup: %s" % named(given_backup, backup_path), err=True)
        return 2
    if inside(backup_path, src):
        out("restore: backup is inside src: %s" % named(given_backup, backup_path), err=True)
        return 2
    if inside(src, backup_path):
        # a copy of BACKUP would swallow the staging tree beside SRC
        out("restore: src is inside backup: %s" % named(given_backup, backup_path), err=True)
        return 2
    if os.path.lexists(src):
        # keep the current SRC before the replace step
        # shortcut: with a missing SRC no pre-restore backup exists, upgrade when a caller needs it
        try:
            pre = make_backup(src, os.path.dirname(backup_path))
        except OSError as exc:
            out("restore: %s" % exc, err=True)
            return 1
        out("backup: %s" % shlex.quote(pre))
    # build the restored tree beside SRC, then swap it in: SRC keeps its
    # content until the swap succeeds
    parent = os.path.realpath(os.path.dirname(src) or ".")
    try:
        new = copy_entry_fresh(backup_path, os.path.join(
            parent, ".si-restore-new-" + os.path.basename(src)))
    except OSError as exc:
        out("restore: %s" % exc, err=True)
        return 1
    try:
        if os.path.lexists(src):
            old = fresh_name(src, os.path.join(
                parent, ".si-restore-old-" + os.path.basename(src)))
            try:
                os.rename(src, old)
            except OSError:
                discard(old)  # only the reservation is there, SRC stays
                raise
            try:
                os.rename(new, src)
            except OSError as exc:
                try:
                    os.rename(old, src)  # roll back
                except OSError:
                    # both renames failed: name the stranded trees, keep both
                    out("restore: %s" % exc, err=True)
                    out("restore: old content is at %s; the copy at %s is also kept"
                        % (old, new), err=True)
                    return 1
                raise
            try:
                remove_entry(old)
            except OSError as exc:
                # old may be half-deleted, so the swapped-in tree stays
                out("restore: old tree not removed: %s" % exc, err=True)
                return 1
        else:
            os.rename(new, src)
    except OSError as exc:
        discard(new)
        out("restore: %s" % exc, err=True)
        return 1
    return 0


ESC = {'"': '"', "\\": "\\", "t": "\t", "n": "\n",
       "a": "\a", "b": "\b", "f": "\f", "v": "\v", "r": "\r"}

# a GNU diff or git header appends the timestamp after a tab; tolerate the
# space-separated form only as a full date-time at the end of the line
TS = (r"(?:\t| )(?:\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?(?: [+-]\d{4})?"
      r"|[A-Z][a-z]{2} [A-Z][a-z]{2} +\d{1,2} \d{2}:\d{2}:\d{2} \d{4})$")

def diff_path(head):
    # git C-quotes unusual names; a GNU diff header can append a timestamp
    if head.startswith('"'):
        out, i = bytearray(), 1
        while i < len(head) and head[i] != '"':
            c = head[i]
            if c == "\\" and i + 1 < len(head):
                n = head[i + 1]
                if n in ESC:
                    out += ESC[n].encode("utf-8", "surrogateescape")
                    i += 2
                    continue
                if n in "01234567":
                    j = i + 1
                    while j < len(head) and j < i + 4 and head[j] in "01234567":
                        j += 1
                    out.append(int(head[i + 1:j], 8) & 0xFF)
                    i = j
                    continue
            out += c.encode("utf-8", "surrogateescape")
            i += 1
        # octal escapes are UTF-8 bytes, so decode them together
        head = out.decode("utf-8", "surrogateescape")
    else:
        head = re.sub(TS, "", head)
    return head[2:] if head.startswith("a/") else head


def cmd_removed_rules(diff_arg):
    if diff_arg == "-":
        text = sys.stdin.read()
    else:
        try:
            with open(diff_arg, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            out("removed-rules: %s" % exc, err=True)
            return 2
    path, old_line = None, 0
    for line in text.splitlines():
        if line.startswith("--- "):
            path = diff_path(line[4:])
        elif line.startswith("@@ "):
            m = re.match(r"@@ -(\d+)", line)
            old_line = int(m.group(1)) if m else 0
        elif line.startswith("-"):
            content = line[1:]
            if content.strip():
                out("%s:%d: %s" % (path, old_line, content))
            old_line += 1
        elif line.startswith("+") or line.startswith("\\"):
            pass
        else:
            old_line += 1
    return 0


def main(argv=None):
    # a name can carry raw bytes: write them back unchanged instead of raising
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if reconf is not None:
            reconf(encoding="utf-8", errors="surrogateescape")
    parser = argparse.ArgumentParser(prog="si.py")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("backup")
    p.add_argument("src")
    p.add_argument("--dest", required=True)
    p = sub.add_parser("restore")
    p.add_argument("backup")
    p.add_argument("src")
    p = sub.add_parser("removed-rules")
    p.add_argument("diff")
    args = parser.parse_args(argv)
    if args.command == "backup":
        return cmd_backup(args.src, args.dest)
    if args.command == "restore":
        return cmd_restore(args.backup, args.src)
    return cmd_removed_rules(args.diff)


if __name__ == "__main__":
    sys.exit(main())
