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
from unittest import mock
import asyncio
import functools


def async_test(func):
    @wraps(func)
    def result(self):
        self.run_async_test(func)
    return result


def async_tests(cls):
    for name in dir(cls):
        if name.startswith("test_"):
            attr = getattr(cls, name)
            if asyncio.iscoroutinefunction(attr):
                setattr(cls, name, async_test(attr))
    return cls


def mock_event(bot, async_event=True):
    if async_event:
        return mock_async_event(bot)

    def decorator(func):
        mock_func = mock.Mock(wraps=func)
        functools.update_wrapper(mock_func, func)

        class Container:
            pass
        container = Container()
        container.event_handler = mock_func
        bot.load_events(container)
        return mock_func
    return decorator


def mock_async_event(bot):
    def decorator(func):
        mock_func = mock.Mock(wraps=func)
        mock_func._awaited = False
        functools.update_wrapper(mock_func, func)

        @wraps(mock_func)
        async def handler(*args, **kwargs):
            await mock_func(*args, **kwargs)
            mock_func._awaited = True

        class Container:
            pass
        container = Container()
        container.event_handler = handler
        bot.load_events(container)
        return mock_func
    return decorator
