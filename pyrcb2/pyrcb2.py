# Copyright (C) 2015-2017 taylor.fish <contact@taylor.fish>
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

from .accounts import AccountTracker
from .decorators import cast_args, document_attr
from .events import Event
from .graphemes import graphemes as iter_graphemes
from .itypes import IStr, IDict, IDefaultDict, ISet, User, Sender
from .messages import (
    Message, Reply, Error, ANY, ANY_ARGS, SELF, matches_pattern,
    matches_any_pattern, WaitResult, WhoisReply)
from .sasl import SASL
from .utils import (
    ensure_list, ensure_coroutine_obj, cancel_future, cancel_futures,
    cancel_tasks, gather, optargs, get_argument_info, OptionalCoroutine,
    forward_attrs, StreamHandler)
from . import numerics

from collections import defaultdict, deque, namedtuple, OrderedDict
from inspect import isawaitable
import asyncio
import heapq
import logging
import ssl as ssl_module
import re
import time


__all__ = ["IRCBot"]

DEFAULT_LOG_FORMAT = "[%(levelname)s][%(name)s] %(message)s"


class UsersDict(IDict):
    def __missing__(self, key):
        return None


class IRCBot:
    """An IRC bot---handles sending and receiving IRC messages. Instances
    of this class are reusable.

    :param bool log_communication: If true, communication with the IRC
      server will be logged (to stdout by default).
    :param bool log_debug: If true, debug messages will be logged (to
      stdout by default). This option implies ``log_communication``.
    :param dict log_kwargs: A list of keyword arguments to be passed to
      :func:`logging.basicConfig`. Applies only when ``log_communication``
      or ``log_debug`` is true and logging has not been set up yet.
    :param ~asyncio.AbstractEventLoop loop: The event loop to use. If not
      given, the default event loop will be used.
    """
    def __init__(self, log_communication=False, log_debug=False,
                 log_kwargs=None, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self._first_use = True
        self.reset()

        self.logger = None
        self.set_up_logging(log_communication, log_debug, log_kwargs)
        self.account_tracker = AccountTracker(self)
        self.sasl = SASL(self)
        self.load_events(self)
        self.load_events(self.account_tracker)

        self.default_timeout = 120
        self.use_hostname_when_splitting = True
        self.quit_on_exception = True
        self.quit_on_exit = True

        self.delay_messages = True
        self.delay_multiplier = 0.01
        self.max_delay = 0.1
        self.consecutive_timeout = 0.5

        self.delay_privmsgs = True
        self.privmsg_delay_multiplier = 0.1
        self.privmsg_max_delay = 1.5
        self.privmsg_consecutive_timeout = 5

    def reset(self):
        self.server_address = None
        self.reader = None
        self.writer = None

        self.read_message_future = self.loop.create_future()
        self.event_handlers = []
        self.event_objects = []
        self.existing_event_ids = set()
        self.read_message_coro_created = asyncio.Event(loop=self.loop)
        self.new_events_called = False

        if hasattr(self, "connected"):
            self.connected.set()
        self.connected = asyncio.Event(loop=self.loop)

        self.listen_future = None
        self.listen_futures = set()
        self.new_listen_future = self.loop.create_future()
        self.scheduled_coroutines = set()
        self.scheduled_futures = {}
        self.new_scheduled = self.loop.create_future()

        self.nickname = None
        self.username = None
        self.hostname = None
        self.old_nickname = None
        self.pending_username = None
        self.pending_nicknames = IDict()

        self.is_alive = False
        self.is_registered = False
        self.extensions = ISet()
        self.isupport = IDict()
        self.prefixes = OrderedDict(zip("ov", "@+"))
        self.chanmodes = ("", "", "", "")

        self.channels = ISet()
        self.newly_left_channels = ISet()
        self.users = UsersDict()
        self.raw_names = IDefaultDict(list)

        self.current_message = None
        self.captured_messages = []
        self.capture_messages = False
        self.latest_whois_reply = None

        # Maps target -> (last_time, consecutive).
        self.last_sent = IDict()
        self.message_queues = IDict()
        self.new_queue_targets = []
        self.new_queue_targets_event = asyncio.Event(loop=self.loop)
        self.delay_heap = []
        self.old_delay_targets = IDict()
        if not self._first_use:
            self.account_tracker.reset()

    @document_attr
    def loop(self):
        """The event loop used by this bot. If ``loop`` was not given when
        this bot was created, this will be the default event loop.

        :type: `~asyncio.AbstractEventLoop`
        """

    @document_attr
    def default_timeout(self):
        """The default timeout used by :meth:`wait_for`. This affects how long
        coroutines returned by commands like :meth:`join` and :meth:`whois`
        will wait before timing out.

        :type: `float`
        """

    @document_attr
    def use_hostname_when_splitting(self):
        """Whether or not to use this bot's hostname (if known) when splitting
        long ``PRIVMSG`` and ``NOTICE`` messages. If ``False``, a hostname of
        63 characters (the maximum) is assumed.

        :type: `bool`
        """

    @document_attr
    def quit_on_exception(self):
        """Whether or not this bot should send a ``QUIT`` message when an
        unhandled exception occurs.

        :type: `bool`
        """

    @document_attr
    def quit_on_exit(self):
        """Whether or not this bot should send a ``QUIT`` message when the
        process is terminated (with a ``SIGTERM``, for example) or when
        :meth:`sys.exit` is called.

        :type: `bool`
        """

    @document_attr
    def delay_messages(self):
        """Whether or not this bot should delay large volumes of IRC messages
        sent to the server to prevent throttling or auto-disconnecting.

        See `delay_multiplier`, `max_delay`, and `consecutive_timeout`. Also
        see `delay_privmsgs`.

        :type: `bool`
        """

    @document_attr
    def delay_multiplier(self):
        """Multiplied by the number of consecutive IRC messages sent to
        determine how many seconds to wait before sending the next one. Used
        when `delay_messages` is true.

        :type: `float`
        """

    @document_attr
    def max_delay(self):
        """The maximum number of seconds to wait before sending an IRC message.
        Used when `delay_messages` is true.

        :type: `float`
        """

    @document_attr
    def consecutive_timeout(self):
        """How many seconds must pass before an IRC message is not considered
        consecutive. Used when `delay_messages` is true.

        :type: `float`
        """

    @document_attr
    def delay_privmsgs(self):
        """Whether or not this bot should delay large volumes of ``PRIVMSG``
        and ``NOTICE`` messages (in addition to the delay from
        `delay_messages`) to prevent throttling or auto-disconnecting.

        See `privmsg_delay_multiplier`, `privmsg_max_delay`, and
        `privmsg_consecutive_timeout`.

        :type: `bool`
        """

    @document_attr
    def privmsg_delay_multiplier(self):
        """Multiplied by the number of consecutive ``PRIVMSG`` and ``NOTICE``
        messages sent to determine how many seconds to wait before sending the
        next one. Used when `delay_privmsgs` is true.

        :type: `float`
        """

    @document_attr
    def privmsg_max_delay(self):
        """The maximum number of seconds to wait before sending a ``PRIVMSG``
        or ``NOTICE``. Used when `delay_privmsgs` is true.

        :type: `float`
        """

    @document_attr
    def privmsg_consecutive_timeout(self):
        """How many seconds must pass before a ``PRIVMSG`` or ``NOTICE`` is not
        considered consecutive. Used when `delay_privmsgs` is true.

        :type: `float`
        """

    @document_attr
    def nickname(self):
        """This bot's nickname.

        :type: `IStr`
        """

    @document_attr
    def username(self):
        """This bot's username (if known).

        :type: `str`
        """

    @document_attr
    def hostname(self):
        """This bot's hostname (if known).

        :type: `str`
        """

    @document_attr
    def is_alive(self):
        """Whether or not this bot is currently connected to a server.

        :type: `bool`
        """

    @document_attr
    def is_registered(self):
        """Whether or not this bot has registered with the IRC server.

        :type: `bool`
        """

    @document_attr
    def extensions(self):
        """A list of IRCv3 extensions currently enabled for this bot.

        :type: `list` of `IStr`
        """

    @document_attr
    def isupport(self):
        """A collection of options sent by the server in ``RPL_ISUPPORT``
        messages. IRC servers usually send ``RPL_ISUPPORT`` messages after
        the bot registers.

        :type: `IDict`; maps `IStr` to `str` or ``None``
        """

    @document_attr
    def channels(self):
        """The set of channels this bot is in.

        :type: `ISet` of `IStr`
        """

    @document_attr
    def users(self):
        """The collection of users in each channel the bot is in. This is a
        dictionary that maps a channel name to a dictionary, where that
        dictionary maps a nickname to a `User` object.

        For example::

            >>> list(bot.users["#channel"])
            [IStr('nickname1'), IStr('nickname2'), IStr('nickname3')]

        You can still iterate over the sub-dictionaries in `users` like a list
        or set; ``for nick in bot.users["#channel"]:`` will iterate over the
        keys in ``bot.users["#channel"]``, which are normal `IStr` nicknames.

            >>> bot.users["#channel"]
            IDefaultDict([(IStr('nickname'), User('nickname'))])
            >>> user = bot.nicklist["#channel"]["nickname"]
            >>> user
            User('nickname')
            >>> user.has_prefix("+")
            True
            >>> user.has_prefix("@")
            False

        If the users in a given channel are not known, a dictionary lookup for
        that channel will return an empty collection instead of raising a
        `KeyError`.

        :type: `IDict`; maps `IStr` to `IDict`; sub-dictionaries map `IStr` to
          `User`.
        """

    def set_up_logging(self, log_communication, log_debug, log_kwargs):
        if log_communication or log_debug or log_kwargs is not None:
            log_kwargs = log_kwargs or {}
            log_kwargs.setdefault("format", DEFAULT_LOG_FORMAT)
            if "stream" in log_kwargs:
                stream = log_kwargs.pop("stream")
                log_kwargs.setdefault("handlers", [StreamHandler(stream)])
            elif "filename" not in log_kwargs:
                log_kwargs.setdefault("handlers", [StreamHandler(None)])
            logging.basicConfig(**log_kwargs)

        self.logger = logging.getLogger("pyrcb2")
        if log_debug:
            self.logger.setLevel(logging.DEBUG)
        elif log_communication:
            self.logger.setLevel(logging.INFO)

    @classmethod
    def forward_account_attrs(cls):
        forward_attrs(
            cls, "account_tracker", AccountTracker, get_attrs=[
                "get_id_status", "get_id_statuses", "get_account",
                "get_accounts", "is_id_status_synced", "is_account_synced",
                "id_status_pending", "account_pending", "id_statuses",
                "accounts", "is_tracking_id_statuses", "is_tracking_accounts",
                "is_tracking_known_id_statuses", "is_tracking_known_accounts",
            ], get_set_attrs=[
                "track_id_statuses", "track_known_id_statuses",
                "track_accounts", "whox_query_type",
            ],
        )

    def load_events(self, obj, index=None):
        """Loads event handlers from the object ``obj``. ``obj`` is usually
        an instance of a class containing methods decorated with `Event`
        decorators. ``obj`` can also be a single event handler itself.

        :param object obj: The object to load event handlers from. Event
          handlers should be attributes of this object decorated with `Event`
          decorators. Alternatively, this can be a single event handler itself.
        :param int index: Where events from the object should be placed, in
          terms of order. Events with lower indices will be called first. If
          not given, new events will be placed after all existing ones.
          `event_objects` contains the current order of events.
        """
        index = len(self.event_handlers) if index is None else index
        handlers = defaultdict(set)
        self.event_handlers.insert(index, handlers)
        self.event_objects.insert(index, obj)

        def load_single(handler):
            if hasattr(handler, "_pyrcb_events") and callable(handler):
                events = handler._pyrcb_events
                for event in events:
                    handlers[event].add(handler)
                    self.existing_event_ids.add(event)

        load_single(obj)
        for attr_name in dir(obj):
            try:
                attr = getattr(obj, attr_name)
            except AttributeError:
                continue
            load_single(attr)

    def any_event_handlers(self, event_class, event_id):
        """Checks if there are any event handlers for a given event class (a
        subclass of `Event`) and event ID.

        :param event_class: The event class.
        :param event_id: The event ID.
        :returns: Whether or not event handlers exist for the given event class
          and event ID.
        :rtype: `bool`
        """
        return (event_class, event_id) in self.existing_event_ids

    async def call(*args, **kwargs):
        """Calls all event handlers for a specific event ID.

        Arguments after the ``event_id`` parameter will be passed to each
        event handler. If a handler doesn't accept certain arguments passed
        to this method, the extra arguments will be discarded, and if a handler
        requires arguments not provided, they will be set to ``None``.

        The ``event_class`` and ``event_id`` parameters are not actually named
        ``event_class`` and ``event_id`` internally. This is so you can still
        pass keyword arguments named ``event_class`` and ``event_id`` to
        handlers. For example, the following is valid code::

            bot.call(EventClass, "event_id", "arg1", "arg2", event_id=10)

        :param event_class: The event class (`Event` or a subclass of `Event`).
        :param event_id: The event ID.
        """
        self, event_cls, event_id, *args = args
        handlers = []
        for handler_dict in self.event_handlers:
            for handler in handler_dict.get((event_cls, event_id), set()):
                handlers.append(handler)

        if handlers:
            self.new_events_called = True
            await self.gather(*(
                self.call_single(func, args, kwargs)
                for func in handlers
            ))

    # Calls a single event handler.
    async def call_single(self, func, args, kwargs):
        arginfo = get_argument_info(func)
        new_kwargs = {}
        new_args = list(args)

        given_args = set(arginfo.required_args[:len(args)])
        missing_args = arginfo.required_args[len(args):]
        for i, arg in enumerate(missing_args):
            if arg in kwargs:
                break
            new_args.append(None)
        missing_args = missing_args[len(new_args) - len(args):]

        for arg in arginfo.required_kwargs | set(missing_args):
            new_kwargs[arg] = kwargs.get(arg)
        for arg in arginfo.optional_kwargs:
            if arg in kwargs:
                new_kwargs[arg] = kwargs[arg]
        if arginfo.varkwargs:
            valid_kwargs = {k: v for k, v in kwargs if k not in given_args}
            new_kwargs.update(valid_kwargs)
        if not arginfo.varargs:
            new_args = new_args[:len(arginfo.required_args)]

        result = func(*new_args, **new_kwargs)
        if isawaitable(result):
            await result

    def start_capturing(self, include_current=True):
        """Starts capturing IRC messages received by this bot. Call
        :meth:`stop_capturing` to retrieve the captured messages.

        :param bool include_current: Whether to include the current IRC message
          in the list of captured messages.
        """
        self.capture_messages = True
        self.captured_messages = []
        if include_current:
            self.captured_messages.append(self.current_message)

    def stop_capturing(self):
        """Stops capturing IRC messages (:meth:`start_capturing`) should have
        been previously called).

        :returns: A list of the captured messages. Messages are of type
          `Message`.
        :rtype: `list`
        """
        self.capture_messages = False
        messages = list(self.captured_messages)
        self.captured_messages = []
        return messages

    @property
    def is_capturing(self):
        """Whether or not this bot is currently capturing IRC messages (see
        :meth:`start_capturing` and :meth:`stop_capturing`).
        """
        return self.capture_messages

    async def wait_for_events_called(self):
        async def new_events_called():
            return self.new_events_called

        while True:
            self.new_events_called = False
            future = self.ensure_future(new_events_called())
            called = await future
            if not called:
                return

    @Event.any
    async def on_any(self, sender, command, *args):
        if sender == self.nickname and sender.username and sender.hostname:
            self.username = sender.username
            self.hostname = sender.hostname
            self.pending_username = None

        message = Message(sender, command, *args)
        self.current_message = message
        if self.capture_messages:
            self.captured_messages.append(message)

        await self.gather(
            self.call(Event, ("command", command), sender, *args),
            self.call(
                Event, ("reply", command), sender,
                *map(IStr, args[:1]), *args[1:],
            ),
        )

    @Event.command("PING")
    def on_ping(self, sender, *args):
        self.send_command("PONG", *args)

    @Event.command("JOIN")
    async def on_join(self, sender, channel: IStr, account, realname):
        self.add_nickname(sender, channel)
        if sender == self.nickname:
            await self.wait_for(Reply("RPL_ENDOFNAMES", channel, ANY))
        await self.call(Event, "join", sender, channel, account, realname)

    @Event.command("PART")
    async def on_part(self, sender, channel: IStr, message):
        self.remove_nickname(sender, channel)
        await self.call(Event, "part", sender, channel, message)

    @Event.command("QUIT")
    async def on_quit(self, sender, message):
        channels = self.remove_nickname(sender, *self.channels)
        await self.call(Event, "quit", sender, message, channels)

    @Event.command("KICK")
    async def on_kick(self, sender, channel: IStr, target: IStr, message):
        self.remove_nickname(target, channel)
        await self.call(Event, "kick", sender, channel, target, message)

    @Event.command("PRIVMSG")
    async def on_privmsg(self, sender, target: IStr, message):
        channel = None if target == self.nickname else target
        is_query = channel is None
        await self.call(Event, "privmsg", sender, channel, message, is_query)

    @Event.command("NOTICE")
    async def on_notice(self, sender, target: IStr, message):
        channel = None if target == self.nickname else target
        is_query = channel is None
        await self.call(Event, "notice", sender, channel, message, is_query)

    @Event.command("NICK")
    async def on_nick(self, sender, new_nickname: IStr):
        self.replace_nickname(sender, new_nickname)
        await self.call(Event, "nick", sender, new_nickname)

    @Event.command("MODE")
    def on_mode(self, sender, channel: IStr, modes, *args):
        users = self.users[channel]
        index = 0
        for char in modes:
            if char in "+-":
                plus = char == "+"
                continue
            if char in self.prefixes:
                nick = args[index]
                user = users[nick]
                method = user.add_prefix if plus else user.remove_prefix
                users[nick] = method(self.prefixes[char])
            takes_arg = (
                char in self.prefixes or
                char in self.chanmodes[0] or
                char in self.chanmodes[1] or
                char in self.chanmodes[2] and plus)
            if takes_arg:
                index += 1
                if index > len(args):
                    return

    @Event.command("CAP")
    def on_cap(self, sender, target, subcommand: IStr, *args):
        if subcommand == "ACK":
            extensions = set(args[0].split())
            self.extensions |= extensions

    @Event.reply("RPL_WELCOME")
    def on_welcome(self, sender, target: IStr, *args):
        self.is_registered = True
        self.old_nickname = target
        self.nickname = target

    @Event.reply("RPL_ISUPPORT")
    def on_isupport(self, sender, target, *args):
        for arg in args[:-1]:
            name, value, *_ = arg.split("=", 1) + [None]
            self.isupport[name] = value
            if name == "PREFIX":
                modes, prefixes = value[1:].split(")", 1)
                self.prefixes = OrderedDict(zip(modes, prefixes))
            elif name == "CHANMODES":
                self.chanmodes = tuple((value + ",,,").split(",")[:4])

    @Event.reply("RPL_NAMREPLY")
    def on_namreply(self, sender, target, chantype, channel: IStr, names):
        self.raw_names[channel] += names.split()

    @Event.reply("RPL_ENDOFNAMES")
    def on_endofnames(self, sender, target, channel: IStr):
        users = IDefaultDict()
        nick_chars = r"a-zA-Z0-9-" + re.escape(r"[]\`_^{|}")
        nick_pattern = r"([^{}]*)(.*)".format(nick_chars)
        for name in self.raw_names[channel]:
            prefixes, name = re.match(nick_pattern, name).groups()
            users[name] = User(name, prefixes=prefixes)
        self.raw_names[channel] = []
        self.users[channel] = users

    @Event.reply(
        "RPL_WHOISUSER", "RPL_WHOISSERVER", "RPL_WHOISOPERATOR",
        "RPL_WHOISIDLE", "RPL_WHOISCHANNELS")
    def on_whois_start(self, *args):
        if not self.is_capturing:
            self.start_capturing()

    @Event.reply("RPL_ENDOFWHOIS")
    async def on_endofwhois(self, sender, target, nickname: IStr, *args):
        if not self.is_capturing:
            self.start_capturing()
        self.latest_whois_reply = self.parse_whois(self.stop_capturing())
        await self.call(Event, "whois", nickname, self.latest_whois_reply)

    @cast_args
    def join(self, channel: IStr):
        """Joins the specified channel. (``JOIN`` command)

        :param str channel: The channel to join.
        :returns: A coroutine that blocks until the bot has joined the channel
          or an error has occurred.
        :rtype: `OptionalCoroutine`; returns a `WaitResult` when awaited.
        """
        future = self.send_command("JOIN", channel)
        return self.wait_for_all(
            future,
            Message(SELF, "JOIN", channel),
            Reply("RPL_ENDOFNAMES", channel, ANY),
            errors=Error([
                "ERR_BANNEDFROMCHAN", "ERR_INVITEONLYCHAN",
                "ERR_BADCHANNELKEY", "ERR_CHANNELISFULL",
                "ERR_BADCHANMASK", "ERR_NOSUCHCHANNEL",
                "ERR_TOOMANYCHANNELS", "ERR_UNAVAILRESOURCE",
                "ERR_TOOMANYTARGETS",
            ], channel, ANY),
        )

    @cast_args
    def part(self, channel: IStr, message=None):
        """Leaves the specified channel. (``PART`` command)

        :param str channel: The channel to leave.
        :param str message: An optional part message to use.
        :returns: A coroutine that blocks until the bot has left the channel or
          an error has occurred.
        :rtype: `OptionalCoroutine`; returns a `WaitResult` when awaited.
        """
        future = self.send_command("PART", channel, *optargs(message))
        return self.wait_for(
            future,
            Message(SELF, "PART", channel, ANY), errors=Error({
                "ERR_NOSUCHCHANNEL", "ERR_NOTONCHANNEL",
            }, channel, None),
        )

    def quit(self, message=None):
        """Disconnects from the server by sending a ``QUIT`` message.
        (:meth:`close_connection()` closes the connection immediately.)

        :param str message: An optional quit message to use.
        :returns: A coroutine that blocks until the bot has quit.
        :rtype: `OptionalCoroutine`
        """
        self.send_command("QUIT", *optargs(message))
        return self.wait_for_close()

    @cast_args
    def kick(self, channel: IStr, target: IStr, message=None):
        """Kicks a user from a channel. (``KICK`` command)

        :param str channel: The channel to kick the user from.
        :param str target: The user to kick.
        :param str message: An optional kick message.
        """
        future = self.send_command("KICK", channel, target, *optargs(message))
        return self.wait_for(
            future,
            Message(SELF, "KICK", channel, target, ANY),
            errors=[
                Error("ERR_USERNOTINCHANNEL", target, channel, ANY),
                Error({
                    "ERR_NOSUCHCHANNEL", "ERR_BADCHANMASK",
                    "ERR_CHANOPRIVSNEEDED", "ERR_NOTONCHANNEL",
                }, channel, ANY),
            ]
        )

    @cast_args
    def privmsg(self, target: IStr, message, split=True, nobreak=True):
        """Sends a message to a channel or user. (``PRIVMSG`` command)

        :param str target: The recipient of the message (a channel or user).
        :param str message: The message to send.
        :param bool split: If true, long messages will be split into multiple
          pieces to avoid truncation. See :meth:`split_string`.
        :param bool nobreak: If true (and ``split`` is true), long messages
          will be split only where spaces occur to avoid breaking words, unless
          this is not possible.
        :returns: A coroutine that blocks until the message is sent. Useful
          when message delaying is enabled.
        :rtype: `OptionalCoroutine`
        """
        return self.privmsg_or_notice(
            target, message, split, nobreak, is_notice=False,
        )

    @cast_args
    def notice(self, target: IStr, message, split=True, nobreak=True):
        """Sends a notice to a channel or user. (``NOTICE`` command)

        :param str target: The recipient of the notice (a channel user).
        :param str message: The message to send.
        :param bool split: If true, long messages will be split into multiple
          pieces to avoid truncation. See :meth:`split_string`.
        :param bool nobreak: If true (and ``split`` is true), long messages
          will be split only where spaces occur to avoid breaking words, unless
          this is not possible.
        :returns: A coroutine that blocks until the notice is sent. Useful
          when message delaying is enabled.
        :rtype: `OptionalCoroutine`
        """
        return self.privmsg_or_notice(
            target, message, split, nobreak, is_notice=True,
        )

    def privmsg_or_notice(self, target, message, split, nobreak, is_notice):
        command = "NOTICE" if is_notice else "PRIVMSG"
        return self.add_delayed_message(
            target, Message(None, command, target, message),
            split=({"nobreak": nobreak} if split else None),
        )

    @cast_args
    def nick(self, nickname: IStr):
        """Changes the bot's nickname (``NICK`` command)

        :param str nickname: The bot's new nickname.
        :returns: A coroutine that blocks until the bot's nickname is changed
          or an error occurs.
        :rtype: `OptionalCoroutine`; returns a ``WaitResult`` when awaited.
        """
        self.pending_nickname = nickname
        future = self.send_command("NICK", nickname)

        async def pending_nick_coro():
            await future
            new_val = self.pending_nicknames.get(nickname, 0) + 1
            self.pending_nicknames[nickname] = new_val

            def matches_old_nick(nick):
                return nick == self.old_nickname
            result = await self.wait_for(
                Message(matches_old_nick, "NICK", nickname), errors=Error({
                    "ERR_ERRONEUSNICKNAME", "ERR_NICKNAMEINUSE",
                    "ERR_NICKCOLLISION", "ERR_UNAVAILRESOURCE",
                }, nickname, ANY),
            )

            if nickname in self.pending_nicknames:
                self.pending_nicknames[nickname] -= 1
                if self.pending_nicknames[nickname] <= 0:
                    del self.pending_nicknames[nickname]
            return result

        pending_nick_future = self.ensure_future(pending_nick_coro())
        self.add_listen_future(pending_nick_future)

        async def coroutine():
            return await pending_nick_future
        return OptionalCoroutine(coroutine)

    @cast_args
    def whois(self, nickname: IStr):
        """Performs a ``WHOIS`` query for the specified user.

        :param str nickname: The user to query.
        :returns: A coroutine the blocks until a response has been received or
          an error occurs.
        :rtype: `OptionalCoroutine`; returns a `WaitResult` when awaited.
          The ``value`` attribute of the `WaitResult` will be a `WhoisReply`
          object.
        """
        future = self.send_command("WHOIS", nickname)

        async def coroutine():
            await future
            result = await self.wait_for(
                Reply("RPL_ENDOFWHOIS", nickname, ANY),
                errors=Error("ERR_NOSUCHNICK", nickname, ANY))
            if result.success:
                result.value = self.latest_whois_reply
            return result
        return OptionalCoroutine(coroutine)

    @cast_args
    def parse_whois(self, messages: list):
        reply = WhoisReply()
        reply.messages = messages
        for sender, command, *args in messages:
            if command == numerics.codes["RPL_WHOISUSER"]:
                nick, user, host, _, realname = args[1:]
                nickname = Sender(nick, username=user, hostname=host)
                reply.nickname, reply.realname = nickname, realname
                reply.username, reply.hostname = user, host
            elif command == numerics.codes["RPL_WHOISSERVER"]:
                nick, reply.server, reply.server_info = args[1:]
            elif command == numerics.codes["RPL_WHOISOPERATOR"]:
                reply.is_irc_op = True
            elif command == numerics.codes["RPL_WHOISIDLE"]:
                nick, time_idle, *_ = args[1:]
                reply.time_idle = int(time_idle)
            elif command == numerics.codes["RPL_WHOISCHANNELS"]:
                nick, channels = args[1:]
                prefixes = "".join(self.prefixes.values())
                channels = channels.split()
                reply.raw_channels = channels
                reply.channels = [IStr(c.lstrip(prefixes)) for c in channels]
            elif command == numerics.codes["RPL_AWAY"]:
                nick, away_message = args[1:]
                reply.is_away = True
                reply.away_message = away_message
            elif command == numerics.codes["RPL_WHOISACCOUNT"]:
                try:
                    nick, account, _ = args[1:]
                except ValueError:
                    continue
                if account != "0":
                    reply.account = IStr(account)
        return reply

    @cast_args
    def cap_req(self, extension: IStr):
        """Requests an IRC extension. (``CAP REQ`` command)

        When calling this method before the bot has been registered, remember
        to send a ``CAP END`` message, either by setting the ``end_cap``
        parameter to ``True`` in :meth:`register` (the default), or by manually
        sending the message.

        :param str extension: The extension to request.
        :returns: A coroutine that blocks until the extension has been enabled
          or an error occurs.
        :rtype: `OptionalCoroutine`; returns a `WaitResult` when awaited. The
          ``success`` attribute of the `WaitResult` will indicate if the
          extension has been enabled.
        """
        future = self.send_command("CAP", "REQ", extension)

        def matches_extension(ext):
            return ext.rstrip() == extension
        return self.wait_for(
            future,
            Message(ANY, "CAP", ANY, "ACK", matches_extension), errors=[
                Message(ANY, "CAP", ANY, "NAK", matches_extension),
                Error("ERR_UNKNOWNCOMMAND", "CAP", ANY),
            ], capture=True,
        )

    def get_and_update_delay(self, target):
        delay_multiplier, max_delay, consecutive_timeout = (
            (self.delay_multiplier, self.max_delay, self.consecutive_timeout)
            if target is None else (
                self.privmsg_delay_multiplier, self.privmsg_max_delay,
                self.privmsg_consecutive_timeout,
            )
        )

        last_time, consecutive = self.last_sent.get(target, (None, 0))
        if last_time is not None:
            last_delta = time.monotonic() - last_time
            if last_delta >= consecutive_timeout:
                consecutive = 0

        last_time = time.monotonic() if last_time is None else last_time
        delay_from_last = min(consecutive * delay_multiplier, max_delay)
        message_time = last_time + delay_from_last
        delay = max(message_time - time.monotonic(), 0)
        message_time = max(message_time, time.monotonic())
        self.last_sent[target] = (message_time, consecutive + 1)
        return delay

    def add_delayed_message(self, target, message, future=None, split=None):
        future = self.loop.create_future() if future is None else future
        if target is not None and not self.delay_privmsgs:
            target = None
        if target is None and not self.delay_messages:
            messages = [message]
            if split is not None:
                messages = self.split_message(message, **split)
            for msg in messages:
                self.send_command(*msg[1:], delay=False)
            future.set_result(None)
            return future

        if target not in self.message_queues:
            self.message_queues[target] = deque()
            self.old_delay_targets.pop(target, None)
            self.new_queue_targets.append(target)
            self.new_queue_targets_event.set()
        queue = self.message_queues[target]
        queue.append(DelayedMessage(message, target, future, split))
        return future

    def add_to_delay_heap(self, target, delayed_msg=None, replace=False):
        heap = self.delay_heap
        delayed_msg = delayed_msg or self.message_queues[target].popleft()
        msg_time = time.monotonic() + self.get_and_update_delay(target)
        func = heapq.heapreplace if replace else heapq.heappush
        func(heap, (msg_time, target, delayed_msg))

    def prune_last_sent(self):
        if not self.old_delay_targets:
            return
        gc_time = next(iter(self.old_delay_targets.values()))
        while time.monotonic() > gc_time:
            target, _ = self.old_delay_targets.popitem(last=False)
            del self.last_sent[target]
            if not self.old_delay_targets:
                return
            gc_time = next(iter(self.old_delay_targets.values()))

    # Splits a message once and adds the rest to the front of the
    # queue (so that it will be the next message retrieved).
    def split_and_queue_rest(self, delayed_msg):
        message, orig_target, future, split = delayed_msg
        message, *rest = self.split_message(message, once=True, **split)
        rest = rest[0] if rest else None
        if rest is not None:
            self.add_to_delay_heap(
                orig_target, delayed_msg._replace(message=rest), replace=True,
            )
        return (message, rest)

    def handle_delayed_message(self, target, delayed_msg):
        message, orig_target, future, split = delayed_msg
        if target is not None:
            self.add_to_delay_heap(None, delayed_msg, replace=True)
            return

        if split is not None:
            message, rest = self.split_and_queue_rest(delayed_msg)
            if rest is not None:
                self.send_command(*message[1:], delay=False)
                return

        self.send_command(*message[1:], delay=False)
        future.set_result(None)

        if self.message_queues.get(orig_target):
            self.add_to_delay_heap(orig_target, replace=True)
            return
        heapq.heappop(self.delay_heap)
        self.message_queues.pop(orig_target)
        if orig_target is not None:
            self.prune_last_sent()
            gc_time = time.monotonic() + self.privmsg_max_delay
            self.old_delay_targets[orig_target] = gc_time

    async def delay_loop(self):
        heap = self.delay_heap
        event = self.new_queue_targets_event

        while True:
            if not heap and not event.is_set():
                await event.wait()
            if event.is_set():
                event.clear()
                for target in self.new_queue_targets:
                    self.add_to_delay_heap(target)
                self.new_queue_targets.clear()

            msg_time, target, delayed_msg = heap[0]
            message, orig_target, future, split = delayed_msg
            delay = msg_time - time.monotonic()

            if delay > 0:
                done, pending = await asyncio.wait(
                    {event.wait(), asyncio.sleep(delay, loop=self.loop)},
                    loop=self.loop, return_when=asyncio.FIRST_COMPLETED)
                await cancel_futures(pending)
                if event.is_set():
                    continue
            self.handle_delayed_message(target, delayed_msg)

    @cast_args
    def add_nickname(self, nickname: IStr, *channels):
        for channel in map(IStr, channels):
            if nickname == self.nickname:
                self.channels.add(channel)
                self.users[channel] = IDict()
            user = User(nickname)
            self.users[channel][nickname] = user

    @cast_args
    def remove_nickname(self, nickname: IStr, *channels):
        if nickname == self.nickname:
            for channel in self.newly_left_channels:
                self.users.pop(channel, None)
            self.newly_left_channels = ISet()

        removed_channels = ISet()
        pairs = [(c, self.users[c]) for c in map(IStr, channels)]
        pairs = [(c, n) for c, n in pairs if nickname in n]
        for channel, users in pairs:
            if nickname == self.nickname and channel in self.channels:
                self.channels.remove(channel)
                self.newly_left_channels.add(channel)
            users.pop(nickname, None)
            removed_channels.add(channel)
        return removed_channels

    @cast_args
    def replace_nickname(self, nickname: IStr, new_nickname: IStr):
        new_nickname = IStr(new_nickname)
        if nickname == self.nickname:
            self.old_nickname = self.nickname
            self.nickname = new_nickname
        for channel in self.channels:
            users = self.users[channel]
            if nickname in users:
                new_user = users[nickname].replace(nickname=new_nickname)
                users.pop(nickname, None)
                users[new_nickname] = new_user

    async def _wait_for(self, *expected, errors, capture, match_all, timeout):
        logger = self.logger.getChild("IRCBot.wait_for")
        expected = list(expected)
        coroutines = pop_coroutines(expected)
        if coroutines:
            logger.debug("Waiting for coroutines: %r", coroutines)
            await self.gather(*coroutines)

        timeout = self.default_timeout if timeout is None else timeout
        timeout = None if timeout <= 0 else timeout
        end_time = timeout and time.monotonic() + timeout

        errors = ensure_list(errors)
        capture = list(expected) if capture is True else ensure_list(capture)
        captured = []

        logger.debug("Waiting for expected patterns")
        logger.debug("Patterns: %r", expected)
        logger.debug("Errors: %r", errors)
        while True:
            timeout = None if end_time is None else end_time - time.monotonic()
            if timeout is not None and timeout <= 0:
                return WaitResult(False, error_cause="timeout")

            logger.debug("Waiting for read_message()")
            try:
                message = await asyncio.wait_for(
                    self.read_message(), timeout, loop=self.loop,
                )
            except asyncio.TimeoutError:
                return WaitResult(False, None, None, "timeout", captured)
            logger.debug("Got message: %r", message)

            if message is None:
                logger.debug("Message is None; returning")
                return WaitResult(False, None, None, "disconnected", captured)
            if matches_any_pattern(message, errors):
                logger.debug("Message matches an error; returning")
                return WaitResult(False, None, message, messages=captured)
            if matches_any_pattern(message, capture):
                logger.debug("Message matches a capture pattern")
                captured.append(message)
            for i, pattern in reversed(list(enumerate(expected))):
                if matches_pattern(message, pattern, self.nickname):
                    logger.debug("Message matches pattern: %r", pattern)
                    if not match_all:
                        logger.debug("Don't need to match all; returning")
                        return WaitResult(True, messages=captured)
                    del expected[i]
            if not expected:
                logger.debug("Matched all patterns; returning")
                return WaitResult(True, messages=captured)

    def wait_for(self, *expected, errors=None, capture=None, timeout=None):
        """Returns a coroutine that blocks until the specified message or
        messages have been received.

        If you pass awaitable objects like coroutines or futures as positional
        arguments to this function (the ``*expected`` parameter), all awaitable
        objects will be awaited before this method starts waiting for the
        expected messages.

        This is because of pyrcb2's message delaying feature. To ensure
        accurate timeouts, this method shouldn't start waiting for the response
        to a command until the command has actually been sent, but methods
        like :meth:`send_command` may delay the command first.
        :meth:`send_command` returns a future that blocks until the command
        has actually been sent---this should be passed to this method::

            def custom_command():
                future = bot.send_command("COMMAND", "arg1", "arg2")
                return bot.wait_for(
                    future,
                    Message("sender", "RESPONSE", "arg1", "arg2"),
                )

        :param expected: The messages to wait for. When any of these messages
          are received, the coroutine will return. Messages should be
          `Message`, `Reply`, or `Error` patterns. These can also be awaitable
          objects like coroutines and futures (see above).
        :param errors: The errors to wait for. When any of these errors is
          received, the coroutine will return. This parameter can either be
          a single error message or a list. Error messages should be `Error`,
          `Reply`, or `Message` patterns.
        :param capture: The messages to capture. Messages that match these
          patterns will be captured and returned in the `WaitResult`. This
          parameter can be a single message or a list, or set to `True`, in
          which case message that match ``expected`` will be captured.
          be captured.
        :param timeout: How many seconds to wait before returning with a
          timeout error. If set to None, `default_timeout` will be used. If set
          to 0 or a negative value, no timeout will be used.
        :rtype: `OptionalCoroutine`; returns a `WaitResult` when awaited. The
          ``success`` attribute will be ``False`` if an error was received or
          a timeout occurred, and ``True`` otherwise.
        """
        return OptionalCoroutine(
            self._wait_for, *expected, errors=errors, capture=capture,
            match_all=False, timeout=timeout)

    def wait_for_all(self, *expected, errors=None, capture=None, timeout=None):
        """Like :meth:`wait_for`, but waits for all expected messages before
        returning. Will still return if any error message is received.
        """
        return OptionalCoroutine(
            self._wait_for, *expected, errors=errors, capture=capture,
            match_all=True, timeout=timeout)

    def wait_for_close(self):
        async def wait():
            while await self.read_message() is not None:
                pass
        return OptionalCoroutine(wait)

    def send_command(self, command, *args, delay=True):
        """Sends an IRC command.

        :param str command: The command to send.
        :param args: Arguments to the command.
        :param bool delay: Whether or not to delay this message if message
          delaying (`delay_messages`) is enabled.
        :returns: A coroutine that blocks until the message has been sent.
          Useful when message delaying is enabled.
        :rtype: `OptionalCoroutine`
        """
        if not delay:
            self.writeline(self.format(command, args))
            return None
        return self.add_delayed_message(None, Message(None, command, *args))

    def create_read_message(self):
        if self.read_message_future.done():
            self.read_message_future = self.loop.create_future()

        async def coroutine():
            line = await self.readline()
            return None if line is None else self.parse(line)
        return coroutine()

    def read_message(self):
        return self.read_message_future

    async def readline(self):
        line = await self.reader.readline()
        if not line:
            return None
        line = line.rstrip(b"\r\n").decode("utf8", "ignore")
        self.logger.info("[%s] %s", self.server_address, line)
        return line

    def writeline(self, line):
        self.logger.info("[%s] >>> %s", self.server_address, line)
        if isinstance(line, str):
            line = line.encode("utf8")
        self.writer.write(line + b"\r\n")

    def close_connection(self):
        """Disconnects from the server immediately without sending a ``QUIT``
        message.
        """
        self.writer.close()

    async def connect_async(
            self, hostname, port, ssl=False, extensions=True,
            client_cert=None):
        if not self._first_use:
            self.reset()
        self._first_use = False

        if ssl:
            if not isinstance(ssl, ssl_module.SSLContext):
                ssl = ssl_module.create_default_context()
            if isinstance(client_cert, str):
                client_cert = (client_cert,)
            if client_cert is not None:
                ssl.load_cert_chain(*client_cert)
        elif client_cert:
            raise ValueError(
                "'ssl' must be true when using a client certificate.")

        self.server_address = "{}:{}".format(hostname, port)
        self.reader, self.writer = await asyncio.open_connection(
            hostname, port, loop=self.loop, ssl=ssl)
        self.is_alive = True
        self.connected.set()
        if extensions:
            self.cap_req("multi-prefix")
            self.cap_req("account-notify")

    async def sasl_auth_async(
            self, account=None, password=None, mechanism="PLAIN", **kwargs):
        await self.sasl.authenticate(account, password, mechanism, **kwargs)

    async def register_async(
            self, nickname, realname=None, username=None,
            password=None, mode="8", end_cap=True):
        realname = realname or nickname
        username = username or nickname
        self.pending_username = username

        if end_cap:
            await self.send_command("CAP", "END")
        if password:
            await self.send_command("PASS", password)
        await self.send_command("NICK", nickname)
        await self.send_command("USER", username, mode, "*", realname)

        result = await self.wait_for(
            Reply("RPL_WELCOME", ANY_ARGS), errors=Error({
                "ERR_ERRONEUSNICKNAME", "ERR_NICKNAMEINUSE",
                "ERR_NICKCOLLISION", "ERR_UNAVAILRESOURCE",
            }, ANY_ARGS),
        )

        if not result.success:
            raise result.to_exception("Could not register.")

    async def _listen_async(self):
        await self.connected.wait()
        read_message = self.ensure_future(self.create_read_message())
        delay_loop = self.ensure_future(self.delay_loop())
        self.listen_futures |= {
            read_message, delay_loop, self.new_listen_future,
        }

        async def cleanup():
            self.is_alive = False
            await cancel_futures(self.listen_futures)

        while True:
            done, pending = await asyncio.wait(
                self.listen_futures, return_when=asyncio.FIRST_COMPLETED,
                loop=self.loop
            )

            self.listen_futures -= set(done)
            for future in done:
                future.result()
            if self.new_listen_future.done():
                self.new_listen_future = self.loop.create_future()
            if not read_message.done():
                continue

            message = read_message.result()
            if message is not None:
                call = self.call(Event, "any", *message)
                self.listen_futures.add(self.ensure_future(call))
                # Wait until every event has reached its first await
                # (not including self.call()).
                await self.wait_for_events_called()
            # This will cause calls to self.read_message() to finish.
            self.read_message_future.set_result(message)
            if message is not None:
                read_message_coro = self.create_read_message()

            # Calls to self.wait_for() may have just finished. Give functions
            # a chance to call events in response to this before moving on to
            # the next message.
            await self.wait_for_events_called()
            if message is None:
                await cleanup()
                return
            read_message = self.ensure_future(read_message_coro)
            self.listen_futures.add(read_message)

    def listen_async(self):
        if self.listen_future is None:
            self.logger.debug("Creating new _listen_async() future")
            self.listen_future = self.ensure_future(self._listen_async())
        return self.listen_future

    async def await_with_listen(self, coroutine, wait_for_scheduled=False):
        logger = self.logger.getChild("IRCBot.await_with_listen")
        listen = self.listen_async()
        coroutine = self.ensure_future(coroutine)
        scheduled = self.ensure_future(
            self.run_scheduled_coroutines(catch_listen_exc=True))

        futures = {listen, coroutine, scheduled}
        while not coroutine.done():
            done, pending = await asyncio.wait(
                futures, return_when=asyncio.FIRST_COMPLETED, loop=self.loop,
            )

            if listen.done() and listen.exception():
                logger.debug("'listen' raised an exception")
                logger.debug("Cancelling other coroutines")
                await cancel_futures(futures - {listen})
                # Without returning control to the event loop, the exception
                # generated by `listen.result()` will be described as occurring
                # during the handling of a CancelledError.
                await asyncio.sleep(0)
                listen.result()
            futures = set(pending)
            for future in done:
                future.result()

        logger.debug("'coroutine' is done")
        if not scheduled.done():
            if not wait_for_scheduled:
                logger.debug("Cancelling 'scheduled'")
                await cancel_future(scheduled)
                return
            logger.debug("Waiting for 'scheduled'")
            await scheduled

    def run_with_listen(self, coroutine, wait_for_scheduled=False):
        self.run_until_complete(
            self.await_with_listen(coroutine, wait_for_scheduled),
        )

    async def run_scheduled_coroutines(self, catch_listen_exc=False):
        self.connected.wait()
        listen = self.listen_async()

        def process_scheduled():
            for coroutine, stay_alive in self.scheduled_coroutines:
                future = self.ensure_future(coroutine)
                self.scheduled_futures[future] = stay_alive
            self.scheduled_coroutines = set()
            self.new_scheduled = self.loop.create_future()
        process_scheduled()

        while not listen.done():
            done, pending = await asyncio.wait(
                list(self.scheduled_futures) + [listen, self.new_scheduled],
                return_when=asyncio.FIRST_COMPLETED, loop=self.loop,
            )
            for future in done:
                self.scheduled_futures.pop(future, None)
                if not (catch_listen_exc and future is listen):
                    future.result()
            if self.scheduled_coroutines:
                process_scheduled()
        self.logger.debug("'listen' in run_scheduled_coroutines() is done")

        for future, stay_alive in list(self.scheduled_futures.items()):
            if not stay_alive:
                del self.scheduled_futures[future]
                await cancel_future(future)
        if self.scheduled_futures:
            await self.gather(*self.scheduled_futures)

    def connect(
            self, hostname, port, ssl=False, extensions=True,
            client_cert=None):
        """Connects to an IRC server.

        This method can be used synchronously or asynchronously. When called
        from a coroutine, it must be awaited.

        :param str hostname: The hostname or IP address of the IRC server.
        :param str port: The port of the IRC server.
        :param bool ssl: Whether to use SSL/TLS. This can also be an
          `ssl.SSLContext` object, in which case it will be used instead of the
          default context.
        :param bool extensions: If true, the bot will request some IRCv3
          extensions using the ``CAP REQ`` command. Currently, ``multi-prefix``
          and ``account-notify`` will be requested.
        :param client_cert: A client SSL/TLS certificate to be used.
          If this is a string, it is passed as the ``certfile`` argument to
          :meth:`ssl.SSLContext.load_cert_chain`; otherwise, this should be
          a tuple or list that contains the arguments to be passed to
          :meth:`ssl.SSLContext.load_cert_chain`. ``ssl`` must be true.
        :returns: A coroutine if this method was called from another coroutine.
          Otherwise, this method will block.
        """
        coroutine = self.connect_async(
            hostname, port, ssl, extensions, client_cert)
        if asyncio.Task.current_task(loop=self.loop) is not None:
            return coroutine
        self.run_until_complete(coroutine)

    def sasl_auth(
            self, account=None, password=None, mechanism="PLAIN", **kwargs):
        """Authenticate (log in to an account) using SASL. The IRCv3 extension
        ``sasl`` must be supported by the server.

        This method should be called after :meth:`connect`, but before
        :meth:`register`.

        This method can be used synchronously or asynchronously. When called
        from a coroutine, it must be awaited.

        :param str account: The account to log in to.
        :param str password: The password for the account.
        :param str mechanism: The SASL mechanism to use. Currently, the
          supported mechanisms are "PLAIN" and "EXTERNAL". To use EXTERNAL
          authentication, provide a client certificate (``client_cert``) when
          calling :meth:`connect`, and do not provide ``account`` or
          ``password`` to this method.
        :param kwargs: Keyword arguments to be used by the specified SASL
          mechanism. Some SASL mechanisms may need arguments other than
          ``account`` and ``password``.
        :returns: A coroutine if the method was called from another coroutine.
          Otherwise, this method will block.
        :raises WaitError: if authentication fails.
        """
        coroutine = self.sasl_auth_async(
            account, password, mechanism, **kwargs)
        if asyncio.Task.current_task(loop=self.loop) is not None:
            return coroutine
        self.run_with_listen(coroutine)

    def register(self, nickname, realname=None, username=None,
                 password=None, mode="8", end_cap=True):
        """Registers with the server. (Sends the ``NICK`` and ``USER``
        commands.)

        If ``nickname`` contains non-alphanumeric characters, it may be
        necessary to provide a separate username (see the ``username``
        parameter).

        This method can be used synchronously or asynchronously. When called
        from a coroutine, it must be awaited.

        :param str nickname: The nickname to use. A `WaitError` is raised if
          the nickname is already in use.
        :param str realname: The real name to use. If not specified,
          ``nickname`` will be used.
        :param str username: The username to use. If not specified,
          ``nickname`` will be used.
        :param str password: If specified, a ``PASS`` message will be sent with
          the given password. This can be used to log in to accounts on many
          servers; however, if SASL is supported, it is better to use
          :meth:`sasl_auth`.
        :param str mode: The mode to use when sending the ``USER`` message.
        :param bool end_cap: Whether or not to end IRCv3 capability negotiation
          by sending a ``CAP END`` message. If any ``CAP LS`` or ``CAP REQ``
          (requests IRCv3 extensions) messages have been sent, sending a ``CAP
          END`` message is required, or registration will not complete. By
          default, :meth:`connect` requests extensions and thus requires ``CAP
          END`` to be sent.
        :returns: A coroutine if this method was called from another coroutine.
          Otherwise, this method will block.
        :raises WaitError: if the nickname is already in use.
        """
        coroutine = self.register_async(
            nickname, realname, username, password, mode)
        if asyncio.Task.current_task(loop=self.loop) is not None:
            return coroutine
        self.run_with_listen(coroutine)

    def listen(self):
        """Listens for incoming messages and calls the appropriate events.

        This method can be used synchronously or asynchronously. When called
        from a coroutine, it must be awaited.

        This method should be called after registering and setting up the bot.
        """
        if asyncio.Task.current_task(loop=self.loop) is not None:
            return self.listen_async()
        self.run_until_complete(self.gather(
            self.listen_async(),
            self.run_scheduled_coroutines(catch_listen_exc=True),
        ))

    def call_coroutine(self, coroutine):
        """Calls the specified coroutine. This is useful when you want all of
        your bot code to be asynchronous; for example::

            async def coroutine():
                await bot.connect("irc.example.com", 6667)
                await bot.register("nickname")
                # More code here...
                await bot.listen()

            bot = IRCBot()
            bot.call_coroutine(coroutine())

        :param awaitable coroutine: The coroutine or awaitable object to run.
        """
        self.run_with_listen(
            ensure_coroutine_obj(coroutine), wait_for_scheduled=True,
        )

    def schedule_coroutine(self, coroutine, stay_alive=False):
        """Schedules the specified coroutine to be run. The coroutine will be
        run when control returns to the event loop (from synchronous code, when
        a method like :meth:`listen` or :meth:`call_coroutine` is called, and
        from asynchronous code, when an ``await`` expression is hit).

        From synchronous code::

            bot = IRCBot()
            bot.connect("irc.example.com", 6667)
            bot.register("nickname")
            bot.schedule_coroutine(some_coroutine())
            bot.listen()

        From asynchronous code::

            await bot.connect("irc.example.com", 6667)
            await bot.register("nickname")
            bot.schedule_coroutine(some_coroutine())
            await bot.listen()

        :param awaitable coroutine: The coroutine or awaitable object to run.
        :param bool stay_alive: Whether or not the coroutine should continue
          running when connection to the server is lost. If ``False``, the
          coroutine will be cancelled. Blocking calls to `call_coroutine` and
          `listen` will not return until there are no scheduled coroutines
          running.
        """
        coroutine = ensure_coroutine_obj(coroutine)
        self.scheduled_coroutines.add((coroutine, stay_alive))
        self.new_scheduled.done() or self.new_scheduled.set_result(None)

    def add_listen_future(self, future):
        future = self.ensure_future(future)
        self.listen_futures.add(future)
        if not self.new_listen_future.done():
            self.new_listen_future.set_result(None)

    def run_until_complete(self, coroutine):
        try:
            self.loop.run_until_complete(coroutine)
        except (Exception, KeyboardInterrupt, SystemExit) as e:
            send_quit = (
                self.quit_on_exit
                if isinstance(e, (KeyboardInterrupt, SystemExit))
                else self.quit_on_exception)
            if send_quit and self.is_registered:
                self.send_command("QUIT", delay=False)
                self.close_connection()
            cancel_tasks(self.loop)
            raise

    def ensure_future(self, coroutine):
        """Calls :func:`asyncio.ensure_future` with the loop this bot is using.

        :param awaitable coroutine: The coroutine or awaitable to use.
        """
        return asyncio.ensure_future(coroutine, loop=self.loop)

    def gather(self, *coroutines):
        """Calls :func:`asyncio.gather` with the loop this bot is using.
        Additionally, coroutines are ensured to be awaited in the order
        provided (but still simultaneously).

        :param awaitable coroutine: The coroutine or awaitable to use.
        """
        return gather(*coroutines, loop=self.loop)

    # Parses an IRC message.
    @classmethod
    def parse(cls, message):
        # Regex to parse IRC messages.
        match = re.match(r"""
            (?::  # Start of prefix
              (.*?)(?:  # Nickname
                (?:!(.*?))?  # User
                @(.*?)  # Host
              )?\ +
            )?
            ([^ ]+)  # Command
            ((?:\ +[^: ][^ ]*){0,14})  # Arguments
            (?:\ +:?(.*))?  # Trailing argument
        """, message, re.VERBOSE)
        nick, user, host, cmd, args, trailing = match.groups("")
        nick = Sender(nick, username=user, hostname=host)
        args = re.split(r" +", args.strip(" ")) if args else []
        if trailing:
            args.append(trailing)
        return Message(nick, cmd, *args)

    # Formats an IRC message.
    @classmethod
    def format(cls, command, args=[]):
        command = str(command)
        args = list(map(str, args))
        if not all(args + [command]):
            raise ValueError("Command/args may not be empty strings.")
        if not re.match(r"^[a-zA-Z0-9]+$", command):
            raise ValueError("Command must be alphanumeric.")
        if not all(re.match(r"^[^\0\r\n]+$", arg) for arg in args):
            raise ValueError(r"Arguments may not contain [\0\r\n].")
        if any(arg[0] == ":" for arg in args[:-1]):
            raise ValueError("Only the last argument may start with ':'.")
        if any(" " in arg for arg in args[:-1]):
            raise ValueError("Only the last argument may contain ' '.")
        if args:
            args[-1] = ":" + args[-1]
        return " ".join([command] + args)

    def safe_message_length(self, target, is_notice=False):
        """Gets the maximum number of bytes the text of an IRC PRIVMSG (or
        optionally a NOTICE) can be without the message possibly being cut off
        due to the 512-byte IRC message limit. This method accounts for extra
        information added by the IRC server.

        You will most likely want to use the value returned by this function
        with :meth:`split_string`.

        However, it is often not necessary to use this method; :meth:`privmsg`
        and :meth:`notice` automatically split messages if they're too long.

        :param str target: The channel or nickname the PRIVMSG will be sent to.
        :param bool is_notice: If true, the calculation will be performed for
          an IRC NOTICE, instead of a PRIVMSG.
        """
        return self.safe_length("NOTICE" if is_notice else "PRIVMSG", target)

    # Gets the maximum number of bytes the trailing argument of
    # an IRC message can be without possibly being cut off.
    def safe_length(self, *args):
        # :<nickname>!<user>@<host>
        # <user> commonly has a 10-character maximum
        # <host> is 63 characters maximum
        nicknames = [self.nickname or ""] + list(self.pending_nicknames)
        nickname = max(nicknames, key=len)

        user_len = len(self.username) if self.username else 10
        if self.pending_username:
            user_len = max(len(self.pending_username), user_len)

        host_len = (
            len(self.hostname) if self.hostname and
            self.use_hostname_when_splitting else 63
        )

        mask = len(":" + nickname + "!") + user_len + len("@") + host_len
        # If a client has "identify-msg" enabled, messages contain
        # one extra character (+ or -).
        msg = mask + len(" " + " ".join(args) + " :+\r\n")
        # IRC messages are limited to 512 bytes.
        return 512 - msg

    @classmethod
    def split_string(cls, string, bytelen, nobreak=True, once=False):
        """Splits a string into pieces that will take up no more than the
        specified number of bytes when encoded as UTF-8.

        IRC messages are limited to 512 bytes, so it is sometimes necessary to
        split longer messages. This method splits strings based on how many
        bytes, rather than characters, they take up, keeping multi-byte
        characters and multi-character graphemes intact. For example::

            >>> IRCBot.split_string("This is a test§§§§", 8)
            ['This is', 'a', 'test§§', '§§']
            >>> IRCBot.split_string("This is a test§§§§", 8, nobreak=False)
            ['This is ', 'a test§', '§§§']
            >>> IRCBot.split_string("This is a test§§§§", 8, once=True)
            ['This is', 'a test§§§§']
            >>> # "c\\u0308" is a single grapheme and shouldn't be split:
            ... IRCBot.split_string("abc\\u0308 abc", 4)
            ['ab', 'c\\u0308', 'abc']

        You can use :meth:`safe_message_length` and :meth:`safe_notice_length`
        to determine how large each string piece should be.

        However, it is often not necessary to call this method because
        :meth:`privmsg` and :meth:`notice` both split long messages by default.

        :param str string: The string to split.
        :param int bytelen: The maximum number of bytes string pieces should
          take up when encoded as UTF-8.
        :param bool nobreak: If true, strings will be split only where spaces
          occur to avoid breaking words, unless this is not possible. If
          present, one space character will be removed between string pieces.
        :param bool once: If true, the string will only be split once. The
          second piece is not guaranteed to be less than ``bytelen``.
        :returns: A list of the split string pieces.
        :rtype: `list`
        """
        if not string:
            return string
        if once:
            split = next(cls._split_string(string, bytelen, nobreak))
            rest = string[len(split):]
            if rest and next(iter_graphemes(rest)) == " ":
                rest = rest[1:]
            return list(filter(None, [split, rest]))
        return list(cls._split_string(string, bytelen, nobreak))

    @classmethod
    def _split_string(cls, string, bytelen, nobreak):
        if bytelen <= 0:
            raise ValueError("Number of bytes must be positive.")
        if len(string.encode("utf8")) <= bytelen:
            yield string
            return

        graphemes = graphemes_with_bytes(string, end_with_none=True)
        grapheme, grapheme_bytes = next(graphemes)
        piece, piece_bytelen = [], 0
        space_index, space_byte_index, nonspace = None, None, None

        while grapheme is not None:
            if piece_bytelen + len(grapheme_bytes) <= bytelen:
                piece.append(grapheme)
                piece_bytelen += len(grapheme_bytes)
                if grapheme == " ":
                    space_index = len(piece) - 1
                    space_byte_index = piece_bytelen - 1
                elif nonspace is None:
                    nonspace = len(piece) - 1
                grapheme, grapheme_bytes = next(graphemes)
                continue

            if not piece:
                # Forced to split grapheme.
                *grapheme_parts, grapheme_bytes = (
                    cls._split_bytes_by_code_points(grapheme_bytes, bytelen))
                grapheme = grapheme_bytes.decode("utf8")
                nonspace = 0  # Should count as a non-space char.
                yield from (b.decode("utf8") for b in grapheme_parts)
                continue

            new_piece, new_bytelen = [], 0
            if not nobreak:
                pass
            elif grapheme == " ":
                grapheme, grapheme_bytes = next(graphemes)
            elif space_index is not None:
                new_piece = piece[space_index + 1:]
                piece = piece[:space_index + (space_index <= nonspace)]
                new_bytelen = piece_bytelen - space_byte_index - 1
            yield "".join(piece)
            piece, piece_bytelen = new_piece, new_bytelen
            space_index, space_byte_index, nonspace = None, None, None
        yield "".join(piece)

    @classmethod
    def _split_bytes_by_code_points(cls, bytestr, bytelen):
        if bytelen <= 0:
            raise ValueError("Number of bytes must be positive.")
        while len(bytestr) > bytelen:
            split, rest = bytestr[:bytelen], bytestr[bytelen:]
            # If the last byte of "split" is non-ASCII and the first byte of
            # "rest" is neither ASCII nor the start of a multi-byte character,
            # then a multi-byte Unicode character has been split.
            if ord(split[-1:]) >= 0x80 and 0x80 <= ord(rest[:1]) <= 0xc0:
                chars = reversed(list(enumerate(split)))
                start = next(i for i, c in chars if c >= 0xc0)
                split, rest = split[:start], split[start:] + rest
            yield split
            bytestr = rest
        yield bytestr

    def split_message(self, message, **kwargs):
        bytelen = self.safe_length(*message[1:-1])
        strings = self.split_string(message[-1], bytelen, **kwargs)
        messages = []
        for string in strings:
            messages.append(Message(*message[:-1], string))
        return messages

IRCBot.forward_account_attrs()


def pop_coroutines(objects):
    if not isinstance(objects, list):
        raise TypeError("'objects' must be a list.")
    coroutines = []
    for i, item in reversed(list(enumerate(objects))):
        if isawaitable(item):
            coroutines.insert(0, item)
            del objects[i]
    return coroutines

DelayedMessage = namedtuple("DelayedMessage", [
    "message", "target", "future", "split",
])


class DelayedMessage(DelayedMessage):
    def __new__(cls, message, orig_target, future=None, split=None):
        return super().__new__(cls, message, orig_target, future, split)


def graphemes_with_bytes(string, end_with_none=False):
    for grapheme in iter_graphemes(string):
        yield grapheme, grapheme.encode("utf8")
    if end_with_none:
        yield None, None
