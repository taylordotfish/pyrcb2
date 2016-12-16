# Copyright (C) 2016 taylor.fish <contact@taylor.fish>
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

from functools import wraps
from inspect import Parameter
import inspect

__all__ = ["decorator_with_args", "event_decorator", "cast_args"]


def decorator_with_args(dec):
    @wraps(dec)
    def get_decorator(*args, **kwargs):
        def decorator(func):
            return dec(func, *args, **kwargs)
        if not kwargs and len(args) == 1 and callable(args[0]):
            func, *args = args
            return decorator(func)
        return decorator
    return get_decorator


def cast_args(func):
    kwparams = inspect.signature(func).parameters
    params = [
        p for p in kwparams.values() if p.kind in
        [Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD]
    ]
    kwparams = {
        name: value for name, value in kwparams.items()
        if value.kind != Parameter.POSITIONAL_ONLY
    }

    def has_callable_annotation(parameter):
        annotation = parameter.annotation
        return callable(annotation) and annotation is not Parameter.empty

    func.__annotations__ = {}

    @wraps(func)
    def result(*args, **kwargs):
        args, kwargs = list(args), dict(kwargs)
        for i, (arg, info) in enumerate(zip(args, params)):
            if has_callable_annotation(info):
                args[i] = info.annotation(arg)
        for kwarg, value in kwargs.items():
            info = kwparams.get(kwarg)
            if info is not None and has_callable_annotation(info):
                kwargs[kwarg] = info.annotation(value)
        return func(*args, **kwargs)
    return result


def _get_event_info_objects(dec_result, multiple=False):
    exception = TypeError(
        "Event decorator must return {}(event_class, event_id) "
        "tuple{}.".format(*("", "s") if multiple else ("an ", "")))
    if dec_result is None:
        raise exception

    info_objects = dec_result
    if not multiple:
        info_objects = {dec_result}
    info_objects = set(info_objects)

    for info in info_objects:
        try:
            ev_cls, ev_id = info
        except ValueError:
            raise exception from None
        if not (ev_cls is None or isinstance(ev_cls, type)):
            raise exception
    return info_objects


@decorator_with_args
def event_decorator(dec, returns_multiple=False):
    @decorator_with_args
    @wraps(dec)
    def result(*args, **kwargs):
        func, *args = args
        if not hasattr(func, "_pyrcb_events"):
            func._pyrcb_events = set()
        dec_result = dec(*args, **kwargs)
        info_objects = _get_event_info_objects(dec_result, returns_multiple)
        func._pyrcb_events |= info_objects
        return cast_args(func)
    return result


def document_attr(func):
    attr = func.__name__
    real_attr = "_" + attr

    def prop(self):
        return getattr(self, real_attr)

    prop.__doc__ = func.__doc__
    prop = property(prop)

    @prop.setter
    def prop(self, value):
        setattr(self, real_attr, value)
    return prop
