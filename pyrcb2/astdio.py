# To the extent possible under law, the author(s) have dedicated all
# copyright and neighboring rights to this file to the public domain
# worldwide. This software is distributed without any warranty. See
# <http://creativecommons.org/publicdomain/zero/1.0/> for a copy of the
# CC0 Public Domain Dedication.

try:
    from aioconsole import aprint, ainput
except ImportError as e:
    raise ImportError("aioconsole must be installed") from e
import sys

__all__ = ["input", "print"]


def print(*args, **kwargs):
    try:
        file = kwargs["file"]
    except KeyError:
        pass
    else:
        if file in [None, sys.stdout, sys.stderr]:
            del kwargs["file"]
            if file is sys.stderr:
                kwargs["use_stderr"] = True
    return aprint(*args, **kwargs)


def input(*args, **kwargs):
    return ainput(*args, **kwargs)
