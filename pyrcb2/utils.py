# Copyright (C) 2016, 2021 taylor.fish <contact@taylor.fish>
#
# This file is part of pyrcb2.
#
# pyrcb2 is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# As an additional permission under GNU GPL version 3 section 7, you may
# distribute non-source forms of comments (lines beginning with "#") and
# strings (text enclosed in quotation marks) in pyrcb2 source code without
# the copy of the GNU GPL normally required by section 4, provided you
# include a URL through which recipients can obtain a copy of the
# Corresponding Source and the GPL at no charge.
#
# pyrcb2 is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pyrcb2.  If not, see <http://www.gnu.org/licenses/>.

from .itypes import IStr
from . import numerics

from collections import namedtuple
from functools import wraps
from inspect import Parameter
import asyncio
import inspect
import logging
import sys

__all__ = ["optargs", "cancel_tasks", "create_future", "cancel_future",
           "cancel_future", "cancel_futures", "reply_name_to_command",
           "ensure_list", "ensure_coroutine_obj", "gather",
           "get_argument_info", "OptionalCoroutine", "forward_attrs",
           "StreamHandler", "Sentinel"]


# Filters out arguments that are None and returns an iterable.
def optargs(*args):
    return (arg for arg in args if arg is not None)


def create_future():
    return asyncio.get_running_loop().create_future()


def cancel_tasks(loop):
    tasks = asyncio.all_tasks(loop=loop)
    for task in (t for t in tasks if not t.done()):
        task.cancel()
        try:
            loop.run_until_complete(task)
        except (asyncio.CancelledError, RuntimeError):
            pass


async def cancel_future(future):
    future.cancel()
    try:
        await future
    except asyncio.CancelledError:
        pass


async def cancel_futures(futures):
    for future in futures:
        await cancel_future(future)


def reply_name_to_command(name):
    if isinstance(name, str):
        if name.isnumeric():
            return IStr("%03d" % int(name) if len(name) < 3 else name)
        return numerics.codes[name]
    if isinstance(name, int):
        return IStr("%03d" % name)
    raise TypeError("'name' must be a str or an int.")


def ensure_list(obj):
    if not (obj is None or isinstance(obj, list)):
        return [obj]
    return obj or []


def ensure_coroutine_obj(coroutine):
    if asyncio.iscoroutine(coroutine) or hasattr(coroutine, "__await__"):
        return coroutine
    return coroutine()


# Like asyncio.gather(), but ensures that coroutines are called in order.
async def gather(*coroutines, **kwargs):
    return await asyncio.gather(
        *(asyncio.ensure_future(coro) for coro in coroutines), **kwargs,
    )


ArgumentInfo = namedtuple("ArgumentInfo", [
    "required_args", "required_kwargs", "optional_kwargs",
    "varargs", "varkwargs",
])


def get_argument_info(func):
    signature = inspect.signature(func)
    required_args = []
    required_kwargs = set()
    optional_kwargs = set()
    varargs, varkwargs = False, False
    for param in signature.parameters.values():
        has_default = param.default is not Parameter.empty
        if param.kind == Parameter.POSITIONAL_ONLY and not has_default:
            required_args.append(None)
        elif param.kind == Parameter.POSITIONAL_OR_KEYWORD and not has_default:
            required_args.append(param.name)
        elif param.kind == Parameter.KEYWORD_ONLY and not has_default:
            required_kwargs.add(param.name)
        elif param.kind == Parameter.KEYWORD_ONLY:
            optional_kwargs.add(param.name)
        elif param.kind == Parameter.VAR_POSITIONAL:
            varargs = True
        elif param.kind == Parameter.VAR_KEYWORD:
            varkwargs = True
    return ArgumentInfo(
        required_args, required_kwargs, optional_kwargs, varargs, varkwargs,
    )


class OptionalCoroutine:
    """A coroutine that can be optionally awaited. Normal coroutines produce
    a warning if they are never awaited, but objects of this type do not. ::

        async def coroutine(arg1, arg2):
            await asyncio.sleep(2)
            print(arg1, arg2)

        optional_coro = OptionalCoroutine(coroutine, "abc", "xyz")

    In the example above, ``optional_coro`` will not produce a warning if it
    is never awaited, but when it is awaited, it will print "abc xyz" after
    two seconds.

    `OptionalCoroutine` objects are returned by :meth:`IRCBot.wait_for` and
    methods such as :meth:`IRCBot.join` and :meth:`IRCBot.nick`.

    The ``func`` parameter is not actually named ``func`` internally, so you
    can still pass a keyword argument named ``func``::

        async def coroutine(func):
            await asyncio.sleep(2)
            print("'func' returned:", func())

        optional_coro = OptionalCoroutine(coroutine, func=int)

    :param func: A coroutine function.
    :param args: Positional arguments for the coroutine function.
    :param kwargs: Keyword arguments for the coroutine function.
    """
    def __init__(*args, **kwargs):
        self, func, *args = args
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def __await__(self, *args, **kwargs):
        coroutine = self.func(*self.args, **self.kwargs)
        return coroutine.__await__(*args, **kwargs)


def _forward_getter(to_cls, from_attr, from_cls, attr):
    if callable(getattr(from_cls, attr, None)):
        _forward_method(to_cls, from_attr, from_cls, attr)
        return

    def getter(self):
        return getattr(getattr(self, from_attr), attr)

    if hasattr(from_cls, attr):
        value = getattr(from_cls, attr)
        if hasattr(value, "__doc__"):
            getter.__doc__ = value.__doc__

    getter = property(getter)
    setattr(to_cls, attr, getter)


def _forward_setter(to_cls, from_attr, from_cls, attr):
    decorator = getattr(to_cls, attr).setter

    @decorator
    def setter(self, value):
        setattr(getattr(self, from_attr), attr, value)
    setattr(to_cls, attr, setter)


def _forward_method(to_cls, from_attr, from_cls, attr):
    @wraps(getattr(from_cls, attr))
    def method(self, *args, **kwargs):
        return getattr(getattr(self, from_attr), attr)(*args, **kwargs)
    setattr(to_cls, attr, method)


def forward_attrs(
        to_cls, from_attr, from_cls=None, get_attrs=[],
        get_set_attrs=[]):
    for attr in get_attrs + get_set_attrs:
        _forward_getter(to_cls, from_attr, from_cls, attr)
    for attr in get_set_attrs:
        _forward_setter(to_cls, from_attr, from_cls, attr)


class StreamHandler(logging.StreamHandler):
    def emit(self, record):
        if not self.stream.closed:
            super().emit(record)

    def handleError(self, record):
        exc_type, exc_value, traceback = sys.exc_info()
        if issubclass(exc_type, BrokenPipeError):
            try:
                self.stream.close()
            except BrokenPipeError:
                pass
            return
        super().handleError(record)


class Sentinel:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name
