# Copyright (C) 2015-2016, 2021 taylor.fish <contact@taylor.fish>
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

from unittest import mock
import asyncio
import time


class BaseMock(mock.Mock):
    # Override in subclasses.
    spec = None

    def __init__(self, spec=None, **kwargs):
        spec = spec or self.spec
        kwargs.setdefault("side_effect", TypeError("Object is not callable."))
        super().__init__(spec=spec, **kwargs)

    def wrap_mock(self, *names):
        for name in names:
            method = getattr(self, name)
            mock_method = mock.Mock(spec=method, side_effect=method)
            setattr(self, name, mock_method)

    @classmethod
    def get_mock_class(cls, instance=None, spec=None):
        spec = spec or cls.spec
        instance = instance or cls(spec=spec)
        mock_cls = mock.Mock(spec=spec, return_value=instance)
        return mock_cls

    def _get_child_mock(self, **kwargs):
        return mock.Mock(**kwargs)


class MockReader(BaseMock):
    spec = asyncio.StreamReader

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.wrap_mock("readline")
        self.reset()

    def reset(self):
        self.lines = asyncio.Queue()
        self.lines_empty = asyncio.Event()
        self.alive = True

    def add_line(self, line):
        self.lines.put_nowait(line)
        self.lines_empty = asyncio.Event()

    async def readline(self):
        if not self.alive:
            return b""
        if self.lines.empty():
            self.lines_empty.set()
        line = await self.lines.get()
        if line is None:
            self.alive = False
            return b""
        return line.encode() + b"\r\n"


class MockWriter(BaseMock):
    spec = asyncio.StreamWriter

    def __init__(self, clock, reader=None, **kwargs):
        super().__init__(**kwargs)
        self.wrap_mock("write", "close")
        self.clock = clock
        self.reader = reader
        self.lines = []
        self.lines_with_time = []
        self.data_received = asyncio.Event()

    def write(self, data):
        line = data.decode().rstrip("\r\n")
        self.lines.append(line)
        self.lines_with_time.append((line, self.clock.time))
        self.data_received.set()
        self.data_received = asyncio.Event()

    def close(self):
        if self.reader is not None:
            self.reader.alive = False
            if self.reader.lines.empty():
                self.reader.lines.put_nowait(None)


class MockOpenConnection(BaseMock):
    def __init__(self, reader, writer, **kwargs):
        super().__init__(side_effect=self._call, **kwargs)
        self.reader = reader
        self.writer = writer

    def _call(self, *args, **kwargs):
        future = asyncio.get_event_loop().create_future()
        future.set_result((self.reader, self.writer))
        return future


class MockClock(BaseMock):
    spec = time.monotonic

    def __init__(self, **kwargs):
        super().__init__(side_effect=self._call, **kwargs)
        self.time = 0

    def _call(self):
        return self.time


class MockAsyncSleep(BaseMock):
    spec = asyncio.sleep

    def __init__(self, clock, **kwargs):
        super().__init__(side_effect=self._call, **kwargs)
        self.clock = clock

    def _call(self, delay, result=None):
        # Keep asyncio.sleep()'s original behavior if delay is 0.
        if delay == 0:
            @asyncio.coroutine
            def coroutine():
                yield
            return coroutine()

        self.clock.time += delay
        future = asyncio.get_event_loop().create_future()
        future.set_result(result)
        return future
