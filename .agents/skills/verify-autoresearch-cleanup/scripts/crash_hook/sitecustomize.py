"""Crash-point hook that check.py loads into the real cleanup.py through PYTHONPATH."""

import os
import signal
import sys

WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
MUTATIONS = frozenset(
    (
        "os.chflags",
        "os.chmod",
        "os.chown",
        "os.link",
        "os.mkdir",
        "os.mkfifo",
        "os.mknod",
        "os.posix_spawn",
        "os.remove",
        "os.removexattr",
        "os.rename",
        "os.replace",
        "os.rmdir",
        "os.setxattr",
        "os.symlink",
        "os.system",
        "os.truncate",
        "os.utime",
        "shutil.copyfile",
        "shutil.copytree",
        "shutil.move",
        "shutil.rmtree",
        "subprocess.Popen",
    )
)


def names(args):
    out = []
    for arg in args:
        if isinstance(arg, (list, tuple)):
            out.append(names(arg))
        elif isinstance(arg, (str, bytes, os.PathLike)):
            text = os.fsdecode(arg)
            out.append(os.path.basename(text) or text)
    return " ".join(out)


def mutates(event, args):
    if event == "open":
        path, _, flags = args
        return (
            not isinstance(path, int)
            and not os.fsdecode(path).startswith("/dev/")
            and isinstance(flags, int)
            and bool(flags & WRITE_FLAGS)
        )
    return event in MUTATIONS


def install():
    crash_at = int(os.environ.pop("CLEANUP_CRASH_AT", "-1"))
    how = os.environ.pop("CLEANUP_CRASH_SIGNAL", "KILL")
    count = 0

    def hook(event, args):
        nonlocal count
        if not mutates(event, args):
            return
        shown = names(args[1:2] if event == "subprocess.Popen" else args)
        sys.__stderr__.write(f"crash-point {count}: {event} {shown}\n")
        sys.__stderr__.flush()
        count += 1
        if count - 1 == crash_at:
            if how == "INT":
                signal.raise_signal(signal.SIGINT)
            os.kill(os.getpid(), signal.SIGKILL)

    sys.addaudithook(hook)


if os.path.basename(sys.argv[0]) == "cleanup.py":
    install()
