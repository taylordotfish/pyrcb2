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

from .decorators import event_decorator
from .itypes import IStr
from .utils import reply_name_to_command

__all__ = ["Event"]


class EventMeta(type):
    def __init__(self, name, bases, attrs):
        if hasattr(self, "events"):
            for event in self.events or []:
                self._add_event_decorator(event)
            del self.events

    def _add_event_decorator(self, event_name):
        if not isinstance(event_name, str):
            raise TypeError("Event names must be strings.")

        @event_decorator
        def event_dec():
            return (self, event_name)

        event_dec.__name__ = event_name
        event_dec.__qualname__ = self.__qualname__ + "." + event_name
        if hasattr(self, event_name):
            raise ValueError("Method '%s' already exists." % event_name)
        setattr(self, event_name, event_dec)


class Event(metaclass=EventMeta):
    events = [
        "any", "join", "part", "quit", "kick",
        "privmsg", "notice", "nick", "whois",
        "account_known", "id_status_known",
        "account_unknown", "id_status_unknown",
    ]

    def __init__(*args, **kwargs):
        raise TypeError("This class cannot be instantiated.")

    @event_decorator(returns_multiple=True)
    def command(*commands):
        for command in map(IStr, commands):
            yield (Event, ("command", command))

    @event_decorator(returns_multiple=True)
    def reply(*names_or_codes):
        codes = map(reply_name_to_command, names_or_codes)
        for code in map(IStr, codes):
            yield (Event, ("reply", code))
