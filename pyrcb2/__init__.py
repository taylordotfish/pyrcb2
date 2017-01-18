# Copyright (C) 2016-2017 taylor.fish <contact@taylor.fish>
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

from .accounts import Status
from .decorators import event_decorator, cast_args
from .events import Event
from .itypes import IStr, IDict, IDefaultDict, ISet, Sender, User
from .messages import Message, Reply, Error, ANY, ANY_ARGS, SELF
from .messages import WaitResult, MultiWaitResult, WaitError, WhoisReply
from .pyrcb2 import IRCBot
from .utils import OptionalCoroutine
from . import accounts
from . import astdio
from . import decorators
from . import messages
from . import numerics
from . import utils

__version__ = "0.3.2"

# Silence Pyflakes warnings about unused imports.
assert [Status]
assert [event_decorator, cast_args]
assert [Event]
assert [IStr, IDict, IDefaultDict, ISet, Sender, User]
assert [Message, Reply, Error, ANY, ANY_ARGS, SELF]
assert [WaitResult, MultiWaitResult, WaitError, WhoisReply]
assert [IRCBot]
assert [OptionalCoroutine]
assert [accounts, astdio, decorators, messages, numerics, utils]
