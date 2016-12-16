# Written in 2016 by taylor.fish <contact@taylor.fish>
#
# To the extent possible under law, the author(s) have dedicated all
# copyright and neighboring rights to this software to the public domain
# worldwide. This software is distributed without any warranty. See
# <http://creativecommons.org/publicdomain/zero/1.0/> for a copy of the
# CC0 Public Domain Dedication.
#
# This file contains code from Python (CPython), which is covered by the
# following copyright notice:
#
# Copyright (c) 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009,
# 2010, 2011, 2012, 2013, 2014, 2015, 2016 Python Software Foundation;
# All Rights Reserved.
#
# See the end of this file for a copy of Python's license.
#
# ----------------------------------------------------------------------
#
# This module provides versions of input() and print() that can be called
# from asynchronous code without blocking. (The regular print() function can
# raise a BlockingIOError when dealing with large volumes of data.)
#
# Usage:
# >>> import astdio
# >>> async def coroutine():
# ...     line = await astdio.input("Enter some text: ")
# ...     await astdio.print("You said: ", line)
# ...
# >>> import asyncio
# >>> loop = asyncio.get_event_loop()
# >>> loop.run_until_complete(coroutine())
# Enter some text: something
# You said: something
# >>> # (Loop complete)
#
# astdio.input() and astdio.print() forward all arguments to the regular
# input() and print(), except for the optional `loop` argument which
# can be used to specify the event loop.
#
# The real input() and print() functions are each run in a ThreadPoolExecutor;
# specifically, a subclass called DaemonThreadPoolExecutor, which doesn't wait
# for the threads to finish when Python exits. `input_executor` and
# `print_executor` are the executor instances used.

import asyncio
import functools
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures.thread import _worker


class DaemonThreadPoolExecutor(ThreadPoolExecutor):
    """A version of `~concurrent.futures.ThreadPoolExecutor` that doesn't
    wait for threads to finish before exiting.
    """

    # Modified from the code for ThreadPoolExecutor._adjust_thread_count().
    # See <https://hg.python.org/cpython/file/bb2a7134d82b/Lib
    # /concurrent/futures/thread.py>.
    # This version of _adjust_thread_count() doesn't add threads to
    # `threads_queues`, so the threads aren't joined when Python exits.
    def _adjust_thread_count(self):
        def weakref_cb(_, q=self._work_queue):
            q.put(None)

        num_threads = len(self._threads)
        if num_threads < self._max_workers:
            thread_name = "%s_%d" % (self, num_threads)
            t = threading.Thread(
                name=thread_name, target=_worker,
                args=(weakref.ref(self, weakref_cb), self._work_queue))
            t.daemon = True
            t.start()
            self._threads.add(t)

    def shutdown(self, wait=True):
        self.shutdown(wait=False)


input_executor = DaemonThreadPoolExecutor()
print_executor = DaemonThreadPoolExecutor()

input_executor.__doc__ = """
The executor used by :func:`input`.

:type: `DaemonThreadPoolExecutor`
"""

print_executor.__doc__ = """
The executor used by :func:`print`.

:type: `DaemonThreadPoolExecutor`
"""

_py_input = input
_py_print = print


async def input(*args, loop=None, **kwargs):
    """Calls :func:`python:input` asynchronously, using the
    `DaemonThreadPoolExecutor` `input_executor`.

    Arguments are passed to :func:`python:input`.

    :param ~asyncio.AbstractEventLoop loop: The event loop to use. If ``None``,
      the default event loop is used.
    """
    if loop is None:
        loop = asyncio.get_event_loop()
    func = functools.partial(_py_input, *args, **kwargs)
    return await loop.run_in_executor(input_executor, func)


async def print(*args, loop=None, **kwargs):
    """Calls :func:`python:print` asynchronously, using the
    `DaemonThreadPoolExecutor` `print_executor`.

    Arguments are passed to :func:`python:print`.

    :param ~asyncio.AbstractEventLoop loop: The event loop to use. If ``None``,
      the default event loop is used.
    """
    if loop is None:
        loop = asyncio.get_event_loop()
    func = functools.partial(_py_print, *args, **kwargs)
    return await loop.run_in_executor(print_executor, func)


# Python's license
# ================
#
# This file contains code from Python (CPython), which is covered by the
# following license:
#
# 1. This LICENSE AGREEMENT is between the Python Software Foundation
# ("PSF"), and the Individual or Organization ("Licensee") accessing and
# otherwise using this software ("Python") in source or binary form and
# its associated documentation.
#
# 2. Subject to the terms and conditions of this License Agreement, PSF
# hereby grants Licensee a nonexclusive, royalty-free, world-wide
# license to reproduce, analyze, test, perform and/or display publicly,
# prepare derivative works, distribute, and otherwise use Python alone
# or in any derivative version, provided, however, that PSF's License
# Agreement and PSF's notice of copyright, i.e., "Copyright (c) 2001,
# 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012,
# 2013, 2014, 2015, 2016 Python Software Foundation; All Rights
# Reserved" are retained in Python alone or in any derivative version
# prepared by Licensee.
#
# 3. In the event Licensee prepares a derivative work that is based on
# or incorporates Python or any part thereof, and wants to make
# the derivative work available to others as provided herein, then
# Licensee hereby agrees to include in any such work a brief summary of
# the changes made to Python.
#
# 4. PSF is making Python available to Licensee on an "AS IS"
# basis.  PSF MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR
# IMPLIED.  BY WAY OF EXAMPLE, BUT NOT LIMITATION, PSF MAKES NO AND
# DISCLAIMS ANY REPRESENTATION OR WARRANTY OF MERCHANTABILITY OR FITNESS
# FOR ANY PARTICULAR PURPOSE OR THAT THE USE OF PYTHON WILL NOT
# INFRINGE ANY THIRD PARTY RIGHTS.
#
# 5. PSF SHALL NOT BE LIABLE TO LICENSEE OR ANY OTHER USERS OF PYTHON
# FOR ANY INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES OR LOSS AS
# A RESULT OF MODIFYING, DISTRIBUTING, OR OTHERWISE USING PYTHON,
# OR ANY DERIVATIVE THEREOF, EVEN IF ADVISED OF THE POSSIBILITY THEREOF.
#
# 6. This License Agreement will automatically terminate upon a material
# breach of its terms and conditions.
#
# 7. Nothing in this License Agreement shall be deemed to create any
# relationship of agency, partnership, or joint venture between PSF and
# Licensee.  This License Agreement does not grant permission to use PSF
# trademarks or trade name in a trademark sense to endorse or promote
# products or services of Licensee, or any third party.
#
# 8. By copying, installing or otherwise using Python, Licensee
# agrees to be bound by the terms and conditions of this License
# Agreement.
