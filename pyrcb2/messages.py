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

from .decorators import cast_args, document_attr
from .itypes import IStr
from .utils import Sentinel, reply_name_to_command
from . import numerics

__all__ = ["ANY", "ANY_ARGS", "SELF", "Message", "Reply", "matches_pattern",
           "matches_any_pattern", "WaitResult", "MultiWaitResult",
           "WaitError", "WhoisReply"]

# Used in message patterns to match any argument (including no argument).
ANY = None
# Used in message patterns to match any number of following arguments.
ANY_ARGS = Sentinel("ANY_ARGS")
# Used in message patterns to match the bot's nickname.
SELF = Sentinel("SELF")


class Message:
    """Represents an IRC message. Objects of this type are used as message
    patterns for :meth:`IRCBot.wait_for`.

    You can use `ANY`, `ANY_ARGS`, and `SELF` as components of the message.

    Additionally, message components can be callables---when checking if
    a message pattern matches a message received from the server and a callable
    is encountered, the message component received from the server will be
    passed to the callable and the result (should be a `bool`) will be used to
    Determine whether or not it matches.

    Message components can also be sets, lists, or tuples, in which case the
    component of a message received from the server must appear in the
    set, list, or tuple to match.

    Examples of matching messages::

        # The first two arguments are case-insensitive.
        Message("a", "b", "c")  # Pattern
        Message("A", "B", "c")  # From server

    ::

        # "sender" matches ANY and "y" appears in the set.
        Message(ANY, "A", {"x", "y", "z"})  # Pattern
        Message("sender", "A", "y")  # From server

    ::

        # ANY matches the lack of an argument as well.
        Message("a", "b", "c", ANY)  # Pattern
        Message("a", "b", "c")  # From server

    ::

        # All arguments after "XYZ" are accepted due to ANY_ARGS.
        Message("sender", "XYZ", ANY_ARGS)  # Pattern
        Message("sender", "XYZ", "arg1", "arg2")  # From server

    ::

        # `(lambda s: s[0] == "x")("xyz")` returns True.
        Message("sender", lambda s: s[0] == "x", "abc")  # Pattern
        Message("sender", "xyz", "abc")  # From server

    Examples of non-matching messages::

        # Server message has too many args.
        Message("sender", "ABC")  # Pattern
        Message("sender", "ABC", "xyz")  # From server

    ::

        # "d" is not in the set.
        Message("sender", "XYZ", {"a", "b", "c"})  # Pattern
        Message("sender", "XYZ", "d")  # From server

    This class can be used like a tuple::

        >>> m = Message("sender", "CMD", "arg1", "arg2")
        >>> tuple(m)
        (IStr('sender'), IStr('CMD'), 'arg1', 'arg2')
        >>> m[1]
        IStr('CMD')
        >>> len(m)
        4

    :param str sender: The sender of the message (usually a server or
      nickname).
    :param str command: The message's command.
    :param args: Arguments to the command.
    """
    def __init__(self, sender, command, *args):
        def ensure_istr(value):
            def ensure_single(value):
                return IStr(value) if type(value) is str else value
            if isinstance(value, (set, list, tuple)):
                return set(map(ensure_single, value))
            return ensure_single(value)

        sender = ensure_istr(sender)
        command = ensure_istr(command)
        self._sender = sender
        self._command = command
        self._args = args
        self._message_tuple = (sender, command, *args)

    @property
    def sender(self):
        """The sender of the message (usually a server or nickname).

        :type: `IStr`
        """
        return self._sender

    @property
    def command(self):
        """The message's command (e.g., "PRIVMSG", "JOIN", or "351").

        :type: `IStr`
        """
        return self._command

    @property
    def args(self):
        """The arguments to the IRC command.

        :type: `list` of `str`
        """
        return self._args

    def __iter__(self):
        return iter(self._message_tuple)

    def __len__(self):
        return len(self._message_tuple)

    def __getitem__(self, index):
        return self._message_tuple[index]

    def __str__(self):
        return str(self._message_tuple)

    def __repr__(self):
        return repr(self._message_tuple)

    def __hash__(self):
        return hash(self._message_tuple)


class Reply(Message):
    """
    Bases: `Message`

    Represents a numeric reply. Objects of this type are used as message
    patterns for :meth:`IRCBot.wait_for`.

    This class is a subclass of `Message`. Like `Message`, you can use `ANY`,
    `ANY_ARGS`, `SELF`, and callables as message components.

    An object of this type is functionally equivalent to a `Message` object
    with ``sender`` and the first IRC argument both set to `ANY`.

    This class is named both `Reply` and `Error`---there is no difference.

    :param str reply_name_or_code: The numeric reply name (e.g., "RPL_VERSION")
      or code (e.g., "351").
    :param args: The arguments of the numeric reply, not including the first
      argument, which is always the recipient's nickname.
    """
    def __init__(self, reply_name_or_code, *args):
        def ensure_command(value):
            def ensure_single(value):
                if type(value) in [str, IStr, int]:
                    return reply_name_to_command(value)
                return value
            if isinstance(value, (set, list, tuple)):
                return set(map(ensure_single, value))
            return ensure_single(value)

        command = ensure_command(reply_name_or_code)
        super().__init__(ANY, command, ANY, *args)

Error = Reply


@cast_args
def matches_pattern(message, pattern, bot_nickname: IStr = None):
    if callable(pattern):
        return pattern(message)
    if len(message) > len(pattern) and ANY_ARGS not in pattern:
        return False

    for i, pattern_arg in enumerate(pattern):
        if pattern_arg is ANY:
            continue
        if pattern_arg is ANY_ARGS:
            return True
        if i >= len(message):
            return False

        message_arg = message[i]
        if i <= 1 and isinstance(message_arg, str):
            message_arg = IStr(message_arg)

        if pattern_arg is SELF:
            if message_arg != bot_nickname:
                return False
        elif callable(pattern_arg):
            if not pattern_arg(message_arg):
                return False
        elif isinstance(pattern_arg, (set, list, tuple)):
            if message_arg not in pattern_arg:
                return False
        elif message_arg != pattern_arg:
            return False
    return True


def matches_any_pattern(message, patterns):
    return any(matches_pattern(message, p) for p in patterns)


class WaitResult:
    """The result of waiting for an IRC message. Returned when
    :meth:`IRCBot.wait_for` and methods such as :meth:`IRCBot.join` and
    :meth:`IRCBot.whois` are awaited.

    :param bool success: Whether or not the expected messages were received.
    :param value: An optional value associated with this result.
    :param Message error: If ``error_cause`` is "message", this is the error
      message from the server that was received. Otherwise, this is ``None``.
    :param str error_cause: If ``success`` is false, this is the cause of the
      error. Values include "message" (when an error message from the server
      is received), "timeout", and "disconnected" (when connection to the
      server is lost).
    :param list messages: The IRC messages associated with this result (if
      any). Messages should be of type `Message`.
    """
    def __init__(self, success, value=None, error=None, error_cause=None,
                 messages=None):
        self.success = success
        self.error = error
        self.error_cause = error_cause
        self.value = value
        self.messages = messages
        if error_cause is None and error is not None:
            self.error_cause = "message"

    @document_attr
    def success(self):
        """Whether or not this result was successful---specifically, whether
        or not the expected messages were received.

        :type: `bool`
        """

    @document_attr
    def value(self):
        """The value associated with this result (if any). This can be any
        object.
        """

    @document_attr
    def error(self):
        """The error message that caused this result to be unsuccessful (if
        any).

        :type: `Message`
        """

    @document_attr
    def error_cause(self):
        """The cause of the error if this result was unsuccessful. Possible
        values include "message", "timeout", and "disconnected". If this is
        "message", `error` should be set to a `Message` object.

        :type: `str`
        """

    @document_attr
    def messages(self):
        """The IRC messages associated with this result (if any).
        :meth:`IRCBot.wait_for` sets this to the list of captured messages.

        :type: `list` of `Message`
        """

    def to_exception(self, *args, **kwargs):
        """Returns an exception that represents this object. If `error_cause`
        is "disconnected", a `ConnectionError` is returned. Otherwise, a
        `WaitError` is returned.

        Arguments passed to this method are forwarded to `WaitError`'s
        constructor. The first argument to `WaitError` is always this object.

        :rtype: `ConnectionError` or `WaitError`
        """
        if self.success:
            raise ValueError("This WaitResult is successful.")
        if self.error_cause == "disconnected":
            return ConnectionError("Lost connection to the server.")
        return WaitError(self, *args, **kwargs)


class MultiWaitResult(WaitResult):
    """
    Bases: `WaitResult`

    A `WaitResult` composed of multiple child `WaitResult` objects. This
    class is a subclass of `WaitResult`.

    By default, if any child is not successful, the ``success`` attribute of
    this object will be ``False`` and ``error_cause`` will be "multiple".

    :param children: The child `WaitResult` objects.
    :type children: `list` of `WaitResult`

    All other parameters are the same as `WaitResult`.
    """
    def __init__(self, children, value=None, error=None, error_cause=None,
                 messages=None, success=None):
        children = children or dict()
        if not isinstance(children, dict):
            children = dict(enumerate(children))
        if success is None:
            success = all(c.success for c in children.values())
        if error_cause is None:
            if any(not c.success for c in children.values()):
                error_cause = "multiple"
        self.children = children
        super().__init__(success, value, error, error_cause, messages)

    @document_attr
    def children(self):
        """The child `WaitResult` objects that constitute this result. If
        `~WaitResult.error_cause` is "multiple", at least one of these children
        was unsuccessful.

        :type: `list` of `WaitResult`
        """


class WaitError(Exception):
    """Raised when an erroneous response to an IRC command is received and an
    exception should be generated, rather than returning an unsuccessful
    `WaitResult`.

    Some methods, such as :meth:`IRCBot.register` and :meth:`IRCBot.sasl_auth`,
    raise this exception when errors are encountered.

    Exceptions of this type correspond to unsuccessful `WaitResult` objects,
    which can be accessed with the `result` attribute.

    Also see :meth:`WaitResult.to_exception`.

    :param WaitResult wait_result: The `WaitResult` associated with this
      exception. The exception's message is generated from this parameter.
    :param str prefix: An optional prefix to be placed before the
      automatically-generated exception message.
    :param str message: If provided, this parameter will be used as the
      exception's message instead of generating one from the `WaitResult`.
    """
    def __init__(self, wait_result, prefix=None, message=None):
        self.result = wait_result
        exc_message = prefix + ": " if prefix else ""

        if message is not None:
            exc_message += str(message)
            super().__init__(exc_message)
            return

        if wait_result.error_cause != "message":
            exc_message += "Error cause: {}".format(wait_result.error_cause)
            super().__init__(exc_message)
            return

        sender, command, *args = wait_result.error
        if command in numerics.replies:
            exc_message += numerics.replies[command] + ": "
        if sender:
            exc_message += ":" + sender + " "
        exc_message += command
        if len(args) > 1:
            exc_message += " " + " ".join(args[:-1])
        if args:
            exc_message += " :" + args[-1]
        super().__init__(exc_message)

    @document_attr
    def result(self):
        """The `WaitResult` associated with this exception. This object
        provides details about the type and cause of the error.

        :type: `WaitResult`
        """


class WhoisReply:
    """Represents the reply to a WHOIS query.

    :meth:`IRCBot.whois` returns an object of this type (as the ``value``
    attribute of a `WaitResult`).
    """
    def __init__(self):
        self.nickname = None
        self.username = None
        self.hostname = None
        self.realname = None
        self.server = None
        self.server_info = None
        self.is_irc_op = False
        self.time_idle = None
        self.channels = []
        self.raw_channels = []
        self.is_away = False
        self.away_message = None
        self.account = None
        self.messages = []
