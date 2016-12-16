.. Written in 2016 by taylor.fish <contact@taylor.fish>

.. To the extent possible under law, the author(s) have dedicated all
   copyright and neighboring rights to this file to the public domain
   worldwide. This file is distributed without any warranty. See
   <http://creativecommons.org/publicdomain/zero/1.0/> for a copy of the
   CC0 Public Domain Dedication.

.. module:: pyrcb2.astdio

Asynchronous stdio
==================

The `pyrcb2.astdio` module contains asynchronous, non-blocking versions of
:func:`python:input` and :func:`python:print` that run the real functions
in executors (see :meth:`AbstractEventLoop.run_in_executor()
<asyncio.AbstractEventLoop.run_in_executor>`).

An asynchronous version of :func:`python:print` may not seem particularly
useful, but :func:`python:print` can actually raise a `BlockingIOError` when
handling large volumes of data. Using the asynchronous version in this module
prevents that. ::

    >>> from pyrcb2 import astdio
    >>> async def coroutine():
    ...     line = await astdio.input("Enter some text: ")
    ...     await astdio.print("You said:", line)
    ...
    >>> import asyncio
    >>> loop = asyncio.get_event_loop()
    >>> loop.run_until_complete(coroutine())
    Enter some text: something
    You said: something
    >>> # (Loop complete)

.. autofunction:: input
.. autofunction:: print
.. autodata:: input_executor
   :annotation:
.. autodata:: print_executor
   :annotation:
.. autoclass:: DaemonThreadPoolExecutor
