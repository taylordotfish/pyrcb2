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

from .mocks import MockClock, MockAsyncSleep
from .mocks import MockOpenConnection, MockReader, MockWriter
from .utils import async_tests, mock_event

from pyrcb2 import IRCBot, Event, IStr, ISet, IDict, Message, WaitError, astdio
from pyrcb2.itypes import Sender
import pyrcb2.pyrcb2
import pyrcb2.utils

from collections import defaultdict
from unittest import mock, TestCase
import asyncio
import functools
import inspect
import logging
import ssl
import sys
import time
import unittest


class BaseTest(TestCase):
    def patch(self, *args, **kwargs):
        patch_obj = mock.patch(*args, **kwargs)
        patch_obj.start()
        self.addCleanup(patch_obj.stop)

    def _assertCalled(self, func, args, kwargs, assert_method):
        self.assertIsNone(assert_method(*args, **kwargs))
        self.assertTrue(getattr(func, "_awaited", True))

    def assertCalled(self, *args, **kwargs):
        func, args = args[0], args[1:]
        self._assertCalled(func, args, kwargs, func.assert_called_with)

    def assertCalledOnce(self, *args, **kwargs):
        func, args = args[0], args[1:]
        self._assertCalled(func, args, kwargs, func.assert_called_once_with)

    def assertAnyCall(self, *args, **kwargs):
        func, args = args[0], args[1:]
        self._assertCalled(func, args, kwargs, func.assert_any_call)


class BaseBotTest(BaseTest):
    @classmethod
    def create_loop(cls):
        return asyncio.new_event_loop()

    @classmethod
    def create_bot(cls, loop):
        bot = IRCBot(loop=loop)
        bot.delay_messages = False
        bot.delay_privmsgs = False
        return bot

    def setUp(self):
        self.loop = self.create_loop()
        self.bot = self.create_bot(self.loop)
        self.addCleanup(self.loop.close)

        self.clock = MockClock(loop=self.loop)
        self.patch("time.monotonic", new=self.clock)
        self.patch("time.time", new=self.clock)
        self.patch("time.clock", new=self.clock)
        mock_sleep = MockAsyncSleep(self.clock)
        self.patch("asyncio.sleep", new=mock_sleep)
        self.reader = MockReader(loop=self.loop)
        self.writer = MockWriter(self.clock, self.reader, loop=self.loop)
        mock_open_connection = MockOpenConnection(
            self.reader, self.writer, loop=self.loop)
        self.patch("asyncio.open_connection", new=mock_open_connection)

    async def async_setup(self):
        await self.bot.connect("irc.example.com", 6667)
        await self.from_server(
            ":server CAP * ACK :multi-prefix",
            ":server CAP * ACK :account-notify")
        await self.register_bot()
        await self.standard_setup()
        self.clear_sent()

    def standard_setup(self):
        return self.from_server(
            ":server 005 self PREFIX=(aohv)&@%+ :are supported",
            ":server 005 self CHANMODES=A,b,c,d WHOX :are supported",
            ":self JOIN #channel",
            ":server 353 self @ #channel :&@user1 +user2 self",
            ":server 366 self #channel :End of names",
            ":self JOIN #channel2",
            ":server 353 self @ #channel2 :self user2 @user3 +&user4",
            ":server 366 self #channel2 :End of names",
        )

    def from_server(self, *lines):
        for line in lines:
            self.reader.add_line(line)
        return self.handle_lines()

    def handle_lines(self):
        return self.reader.lines_empty.wait()

    async def register_bot(self, nickname="self"):
        self.from_server(":server 001 %s :Welcome" % nickname)
        await self.bot.register(nickname)

    def run_async_test(self, function):
        async def coroutine():
            await self.async_setup()
            result = function(self)
            if inspect.isawaitable(result):
                await result
            self.bot.close_connection()
            await self.bot.listen()
        self.bot.call_coroutine(coroutine())

    def clear_sent(self):
        self.writer.lines.clear()
        self.writer.lines_with_time.clear()

    def pop_sent(self):
        lines = list(self.writer.lines)
        self.clear_sent()
        return lines

    def assertSent(self, *lines):
        self.assertSequenceEqual(self.writer.lines, lines)
        self.writer.lines.clear()

    def assertInChannel(self, channel):
        self.assertIn(channel, self.bot.channels)
        self.assertIn(self.bot.nickname, self.bot.users[channel])

    def assertNotInChannel(self, channel):
        self.assertNotIn(channel, self.bot.channels)

    def assertUserInChannel(self, user, channel):
        self.assertIn(user, self.bot.users[channel])

    def assertUserNotInChannel(self, user, channel):
        self.assertNotIn(user, self.bot.users[channel])

    def assertSuccess(self, wait_result):
        self.assertTrue(wait_result.success)

    def assertNotSuccess(self, wait_result):
        self.assertFalse(wait_result.success)


@async_tests
class TestCommands(BaseBotTest):
    async def test_join(self):
        future = self.bot.ensure_future(self.bot.join("#channel3"))
        self.assertSent("JOIN :#channel3")
        await self.from_server(":self JOIN :#channel3")
        await self.from_server(":server 353 self @ #channel3 :user2 self")
        self.assertFalse(future.done())
        await self.from_server(":server 366 self #channel3 :End of names")
        self.assertTrue(future.done())
        self.assertSuccess(future.result())
        self.assertInChannel("#channel3")
        users = self.bot.users["#channel3"]
        self.assertIsInstance(users, IDict)
        self.assertCountEqual(users, ISet({"self", "user2"}))

    async def test_part(self):
        messages = [
            ("#channel", None, "PART :#channel"),
            ("#channel2", "Message", "PART #channel2 :Message")]
        for channel, part_msg, expected in messages:
            coroutine = self.bot.part(channel, part_msg)
            self.assertSent(expected)
            self.from_server(":self " + expected)
            self.assertInChannel(channel)
            self.assertSuccess(await coroutine)
            self.assertNotInChannel(channel)

    async def test_quit(self):
        coroutine = self.bot.quit()
        self.assertSent("QUIT")
        self.writer.close()
        await coroutine

    async def test_quit_message(self):
        coroutine = self.bot.quit("Message")
        self.assertSent("QUIT :Message")
        self.writer.close()
        await coroutine

    async def test_privmsg(self):
        self.bot.privmsg("#channel", "Message")
        self.assertSent("PRIVMSG #channel :Message")
        self.bot.privmsg("target", "Message 2")
        self.assertSent("PRIVMSG target :Message 2")

    async def test_notice(self):
        self.bot.notice("#channel", "Message")
        self.assertSent("NOTICE #channel :Message")

    async def test_nick(self):
        coroutine = self.bot.nick("self2")
        self.assertSent("NICK :self2")
        self.from_server(":self NICK :self2")
        self.assertEqual(self.bot.nickname, "self")
        self.assertSuccess(await coroutine)
        self.assertEqual(self.bot.nickname, "self2")

    async def test_whois(self):
        future = self.bot.ensure_future(self.bot.whois("user1"))
        self.assertSent("WHOIS :user1")
        await self.from_server(
            ":server 311 self user1 user host * :realname",
            ":server 312 self user1 server-name :server-info",
            ":server 313 self user1 :is a server operator",
            ":server 317 self user1 10 :seconds idle",
            ":server 319 self User1 :+#channel #channel2 @+#channel4",
            ":server 301 self User1 :Away message",
            ":server 330 self User1 account :is logged in as",
        )

        self.assertFalse(future.done())
        await self.from_server(":server 318 self user1 :End of whois")
        result = future.result()
        self.assertSuccess(result)
        reply = result.value

        self.assertEqual(reply.nickname, "User1")
        self.assertEqual(reply.username, "user")
        self.assertEqual(reply.hostname, "host")
        self.assertEqual(reply.server, "server-name")
        self.assertEqual(reply.server_info, "server-info")
        self.assertIs(reply.is_irc_op, True)
        raw_channels = ["+#channel", "#channel2", "@+#channel4"]
        channels = ["#channel", "#channel2", "#Channel4"]
        self.assertEqual(reply.raw_channels, raw_channels)
        self.assertEqual(reply.channels, channels)
        self.assertIs(reply.is_away, True)
        self.assertEqual(reply.away_message, "Away message")
        self.assertEqual(reply.account, "Account")

    async def test_cap_req(self):
        coroutine = self.bot.cap_req("extension")
        # Some IRC servers add trailing spaces; make sure
        # the bot can handle this.
        self.from_server(":server CAP * ACK :Extension ")
        self.assertSuccess(await coroutine)
        self.assertIn("EXTENSION", self.bot.extensions)

        coroutine = self.bot.cap_req("extension2")
        self.from_server(":server CAP * NAK :Extension2  ")
        self.assertNotSuccess(await coroutine)
        self.assertNotIn("Extension2", self.bot.extensions)

    async def test_send_command(self):
        self.bot.send_command("COMMAND", "arg1", "arg2")
        self.assertSent("COMMAND arg1 :arg2")


@async_tests
class TestEvents(BaseBotTest):
    async def test_ping(self):
        await self.from_server("PING :test")
        self.assertSent("PONG :test")

    async def test_join(self):
        @mock_event(self.bot)
        @Event.join
        async def on_join(sender, channel):
            self.assertUserInChannel(sender, channel)
            user = self.bot.users[channel][sender]
            self.assertCountEqual(user.prefixes, {})
        await self.from_server(":user5 JOIN #channel")
        self.assertCalledOnce(on_join, "User5", "#channel")

    async def test_join_self(self):
        @mock_event(self.bot)
        @Event.join
        async def on_join(sender, channel):
            self.assertInChannel(channel)
            users = self.bot.users[channel]
            self.assertIsInstance(users, IDict)
            self.assertCountEqual(users, ISet({"self", "user5"}))
        await self.from_server(
            ":self JOIN :#channel3",
            ":server 353 self @ #channel3 :self user5",
            ":server 366 self #channel3 :End of names")
        self.assertCalledOnce(on_join, "self", "#Channel3")

    async def test_part(self):
        @mock_event(self.bot)
        @Event.part
        async def on_part(sender, channel, message):
            self.assertUserNotInChannel(sender, channel)
        self.assertUserInChannel("user1", "#channel")
        await self.from_server(":user1 PART #channel :Message")
        self.assertCalledOnce(on_part, "user1", "#channel", "Message")

    async def test_part_self(self):
        @mock_event(self.bot)
        @Event.part
        async def on_part(sender, channel, message):
            self.assertNotInChannel(channel)
        self.assertInChannel("#channel")
        await self.from_server(":self PART #channel")
        self.assertCalledOnce(on_part, "self", "#channel", None)

    async def test_quit(self):
        @mock_event(self.bot)
        @Event.quit
        async def on_quit(sender, message, channels):
            self.assertEqual(channels, {"#Channel2"})
            self.assertUserNotInChannel(sender, "#channel2")
        await self.from_server(":user3 QUIT :Message")
        self.assertCalledOnce(on_quit, "user3", "Message", {"#Channel2"})

    async def test_quit_self(self):
        @mock_event(self.bot)
        @Event.quit
        async def on_quit(sender, message, channels):
            self.assertEqual(channels, {"#Channel", "#Channel2"})
            self.assertEqual(self.bot.channels, {})
        await self.from_server(":self QUIT")
        self.assertCalledOnce(on_quit, "self", None, {"#Channel", "#Channel2"})

    async def test_kick(self):
        @mock_event(self.bot)
        @Event.kick
        async def on_kick(sender, channel, target, message):
            self.assertUserNotInChannel(target, channel)
            self.assertUserInChannel(sender, channel)
        self.assertUserInChannel("user2", "#channel")
        await self.from_server(":user1 KICK #channel user2 :Message")
        self.assertCalledOnce(on_kick, "user1", "#channel", "user2", "Message")

    async def test_kick_self(self):
        @mock_event(self.bot)
        @Event.kick
        async def on_kick(sender, channel, target, message):
            self.assertNotInChannel(channel)
        self.assertInChannel("#channel")
        await self.from_server(":user1 KICK #channel self")
        self.assertCalledOnce(on_kick, "user1", "#channel", "self", None)

    async def test_privmsg(self):
        @mock_event(self.bot)
        @Event.privmsg
        async def on_privmsg(sender, channel, message, is_query):
            pass
        await self.from_server(":user5 PRIVMSG #channel :Msg")
        self.assertCalledOnce(on_privmsg, "user5", "#channel", "Msg", False)

    async def test_privmsg_query(self):
        @mock_event(self.bot)
        @Event.privmsg
        async def on_privmsg(sender, channel, message, is_query):
            pass
        await self.from_server(":user5 PRIVMSG self :Message")
        self.assertCalledOnce(on_privmsg, "user5", None, "Message", True)

    async def test_notice(self):
        @mock_event(self.bot)
        @Event.notice
        async def on_notice(sender, channel, message, is_query):
            pass
        await self.from_server(":user5 NOTICE #channel :Notice")
        self.assertCalledOnce(on_notice, "user5", "#channel", "Notice", False)

    async def test_notice_query(self):
        @mock_event(self.bot)
        @Event.notice
        async def on_notice(sender, channel, message, is_query):
            pass
        await self.from_server(":user5 NOTICE self :Notice")
        self.assertCalledOnce(on_notice, "user5", None, "Notice", True)

    async def test_whois(self):
        @mock_event(self.bot)
        @Event.whois
        async def on_whois(nickname, whois_reply):
            self.assertEqual(nickname, "User2")
            self.assertEqual(whois_reply.nickname, "User2")
            self.assertEqual(whois_reply.account, "account")
        await self.from_server(
            ":server 311 self user2 user host * :realname",
            ":server 330 self User2 account :is logged in as",
            ":server 318 self user2 :End of whois")
        self.assertEqual(on_whois.call_count, 1)

    async def test_names(self):
        await self.from_server(
            ":self JOIN #channel3",
            ":server 353 self = #channel3 :@+a self",
            ":server 353 self = #channel3 :&+user1",
            ":server 366 self #channel3 :End of names")
        users = self.bot.users["#channel3"]
        self.assertIsInstance(users, IDict)
        self.assertCountEqual(users, ISet({"a", "user1", "self"}))
        self.assertCountEqual(users["a"].prefixes, "@+")
        self.assertCountEqual(users["user1"].prefixes, "&+")
        self.assertCountEqual(users["self"].prefixes, "")

    async def test_mode(self):
        users = self.bot.users["#channel"]
        user1, user2 = users["user1"], users["user2"]
        self.assertCountEqual(user1.prefixes, "&@")
        self.assertCountEqual(user2.prefixes, "+")

        await self.from_server(":svr MODE #channel +Advca A user1 B user2")
        user1, user2 = users["user1"], users["user2"]
        self.assertCountEqual(user1.prefixes, "&@+")
        self.assertCountEqual(user2.prefixes, "+&")

        await self.from_server(":svr MODE #channel +hb-cda user1 A user2")
        user1, user2 = users["user1"], users["user2"]
        self.assertCountEqual(user1.prefixes, "&@+%")
        self.assertCountEqual(user2.prefixes, "+")

    async def test_command(self):
        @mock_event(self.bot)
        @Event.command("Xyz")
        async def on_xyz(sender, arg1, arg2):
            pass
        await self.from_server(":user5 XYZ arg1")
        self.assertCalledOnce(on_xyz, "user5", "arg1", None)
        await self.from_server(":user6 xyz arg1 arg2 arg3")
        self.assertCalled(on_xyz, "user6", "arg1", "arg2")

    async def test_reply(self):
        for reply_name in ["RPL_LUSEROP", "252", 252]:
            @mock_event(self.bot)
            @Event.reply(reply_name)
            async def on_luserop(sender, target, op_count, message):
                pass
            await self.from_server(":server 252 self 10 :ops")
            self.assertCalledOnce(on_luserop, "server", "self", "10", "ops")

    async def test_any(self):
        @mock_event(self.bot)
        @Event.any
        async def on_any(sender, command, *args):
            self.assertEqual(args, ("arg1", "arg2"))
            self.assertNotEqual(args, ("Arg1", "Arg2"))
        await self.from_server(":user5 COMMAND arg1 :arg2")
        self.assertCalledOnce(on_any, "User5", "command", "arg1", "arg2")

    async def test_load_events(self):
        calls = defaultdict(list)

        class Events1:
            @Event.join
            async def on_join(_self, sender, channel):
                calls[_self.on_join].append((sender, channel))

            @Event.part
            def on_part(_self, sender, channel):
                calls[_self.on_part].append((sender, channel))

            @Event.command("XYZ")
            async def on_xyz(_self, *args):
                calls[_self.on_xyz].append(tuple(args))

        class Events2:
            @Event.part
            async def on_part(_self, sender, channel):
                args = (sender, channel)
                self.assertEqual(calls[events1.on_part], [args])
                calls[_self.on_part].append((sender, channel))

            @Event.command("XYZ")
            def on_xyz(_self, *args):
                self.assertEqual(calls[events1.on_xyz], [tuple(args)])
                calls[_self.on_xyz].append(tuple(args))

        events1 = Events1()
        events2 = Events2()
        self.bot.load_events(events1)
        self.bot.load_events(events2)
        await self.from_server(
            ":user5 JOIN #channel",
            ":user2 PART #channel :Message",
            ":user3 XYZ a b")
        self.assertEqual(calls[events1.on_join], [("user5", "#Channel")])
        self.assertEqual(calls[events2.on_part], [("User2", "#channel")])
        self.assertEqual(calls[events2.on_xyz], [("User3", "a", "b")])


@async_tests
class TestConnect(BaseBotTest):
    async def async_setup(self):
        pass

    async def connect_bot(self):
        await self.bot.connect("irc.example.com", 6667)
        self.clear_sent()

    def test_connect(self):
        self.assertFalse(self.bot.is_alive)
        self.bot.connect("irc.example.com", 6667)
        self.assertTrue(self.bot.is_alive)
        self.assertCalledOnce(
            asyncio.open_connection, "irc.example.com", 6667,
            loop=self.loop, ssl=False)
        self.assertSent(
            "CAP REQ :multi-prefix", "CAP REQ :account-notify",
            "CAP REQ :extended-join",
        )

    async def test_connect_async(self):
        self.assertFalse(self.bot.is_alive)
        await self.bot.connect("irc.example.com", 6667)
        self.assertTrue(self.bot.is_alive)
        self.assertCalledOnce(
            asyncio.open_connection, "irc.example.com", 6667,
            loop=self.loop, ssl=False)
        self.assertSent(
            "CAP REQ :multi-prefix", "CAP REQ :account-notify",
            "CAP REQ :extended-join",
        )

    def test_connect_ssl(self):
        self.bot.connect("irc.example.com", 6697, ssl=True)
        self.assertCalledOnce(
            asyncio.open_connection, "irc.example.com", 6697, loop=self.loop,
            ssl=mock.ANY)
        context = asyncio.open_connection.call_args[1]["ssl"]
        self.assertIsInstance(context, ssl.SSLContext)

    async def test_connect_client_cert(self):
        # Need to subclass SSLContext to modify load_cert_chain.
        class SSLContext(ssl.SSLContext):
            pass
        context = SSLContext()
        context.load_cert_chain = mock.Mock(
            spec=context.load_cert_chain, return_value=None)
        await self.bot.connect(
            "irc.example.com", 6697, ssl=context,
            client_cert=("/certfile", "/keyfile", "password"))
        self.assertCalledOnce(
            asyncio.open_connection, "irc.example.com", 6697, loop=self.loop,
            ssl=context)
        self.assertCalledOnce(
            context.load_cert_chain, "/certfile", "/keyfile", "password")

    async def test_connect_no_extensions(self):
        await self.bot.connect("irc.example.com", 6667, extensions=False)
        self.assertCalledOnce(
            asyncio.open_connection, "irc.example.com", 6667,
            loop=self.loop, ssl=False)
        self.assertSent()  # Nothing should have been sent.

    def test_sasl_auth(self):
        self.bot.connect("irc.example.com", 6667, extensions=False)
        self.from_server(
            ":server CAP * ACK :sasl",
            ":server AUTHENTICATE :+",
            ":server 903 * :SASL authentication successful")
        self.bot.sasl_auth("account", "password")
        self.assertSent(
            "CAP REQ :sasl",
            "AUTHENTICATE :PLAIN",
            "AUTHENTICATE :YWNjb3VudABhY2NvdW50AHBhc3N3b3Jk")
        self.bot.close_connection()
        self.bot.listen()

    async def test_sasl_auth_fail(self):
        await self.bot.connect("irc.example.com", 6667, extensions=False)
        self.from_server(
            ":server CAP * ACK :sasl",
            ":server AUTHENTICATE :+",
            ":server 904 * :SASL authentication failed")
        with self.assertRaises(WaitError):
            await self.bot.sasl_auth("account", "password")

    async def test_sasl_auth_external(self):
        await self.bot.connect(
            "irc.example.com", 6697, ssl=True, extensions=False)
        self.from_server(
            ":server CAP * ACK :sasl",
            ":server AUTHENTICATE +",
            ":server 903 * :SASL authentication successful")
        await self.bot.sasl_auth(mechanism="EXTERNAL")
        self.assertSent(
            "CAP REQ :sasl", "AUTHENTICATE :EXTERNAL", "AUTHENTICATE :+")

    def test_register(self):
        self.bot.connect("irc.example.com", 6667)
        self.clear_sent()
        self.from_server(":server 001 self1 :Welcome")
        self.bot.register("self1")
        self.assertSent("CAP :END", "NICK :self1", "USER self1 8 * :self1")
        self.bot.close_connection()
        self.bot.listen()

    async def test_register_async(self):
        await self.connect_bot()
        self.from_server(":server 001 self1 :Welcome")
        await self.bot.register("self1", "realname", "user1", mode="0")
        self.assertSent("CAP :END", "NICK :self1", "USER user1 0 * :realname")

    async def test_register_nickname_in_use(self):
        await self.connect_bot()
        self.from_server(":server 433 * self1 :Nickname in use")
        with self.assertRaises(WaitError):
            await self.bot.register("self1")

    async def test_register_lost_connection(self):
        await self.connect_bot()
        self.writer.close()
        with self.assertRaises(ConnectionError):
            await self.bot.register("self1")


@async_tests
class TestDelay(BaseBotTest):
    async def async_setup(self):
        await super().async_setup()
        self.bot.delay_messages = True
        self.bot.delay_privmsgs = True

    async def test_privmsg_delay(self):
        # Ensure consecutive messages count resets to 0.
        await asyncio.sleep(10, loop=self.loop)  # Mocked; won't actually wait.
        expected_time = time.monotonic()
        for i in range(30):
            await self.bot.privmsg("user1", "Message %s" % i)

        self.assertEqual(len(self.writer.lines_with_time), 30)
        for i, (msg, msg_time) in enumerate(self.writer.lines_with_time):
            expected_time += min(
                i * self.bot.privmsg_delay_multiplier,
                self.bot.privmsg_max_delay)
            expected_msg = "PRIVMSG user1 :Message %s" % i
            self.assertEqual(msg, expected_msg)
            self.assertAlmostEqual(msg_time, expected_time)

        await asyncio.sleep(10, loop=self.loop)
        self.assertIn("user1", self.bot.last_sent)
        await self.bot.privmsg("user2", "Message")
        self.assertNotIn("user1", self.bot.last_sent)

    async def test_delay(self):
        await asyncio.sleep(10, loop=self.loop)
        expected_time = time.monotonic()
        for i in range(30):
            await self.bot.send_command("COMMAND", "arg", i)

        self.assertEqual(len(self.writer.lines_with_time), 30)
        for i, (msg, msg_time) in enumerate(self.writer.lines_with_time):
            expected_time += min(
                i * self.bot.delay_multiplier, self.bot.max_delay)
            expected_msg = "COMMAND arg :%s" % i
            self.assertEqual(msg, expected_msg)
            self.assertAlmostEqual(msg_time, expected_time)


class TestMisc(BaseBotTest):
    @classmethod
    def create_bot(cls, loop, **kwargs):
        bot = IRCBot(loop=loop, **kwargs)
        bot.delay_messages = False
        bot.delay_privmsgs = False
        return bot

    def test_parse(self):
        message = IRCBot.parse(
            ":nickname!user@example.com COMMAND arg1 arg2 :trailing arg")
        self.assertIs(type(message), Message)
        nick, cmd, *args = message
        self.assertIs(type(nick), Sender)
        self.assertIs(type(cmd), IStr)
        for arg in args:
            self.assertIs(type(arg), str)
        self.assertEqual(nick, "nickname")
        self.assertEqual(nick.username, "user")
        self.assertEqual(nick.hostname, "example.com")
        self.assertEqual(cmd, "COMMAND")
        self.assertEqual(args, ["arg1", "arg2", "trailing arg"])

    def test_format(self):
        self.assertEqual(IRCBot.format("CMD"), "CMD")
        self.assertEqual(IRCBot.format("CMD", ["a:", "b c"]), "CMD a: :b c")
        with self.assertRaises(ValueError):
            IRCBot.format("CMD", ["arg", ""])
        with self.assertRaises(ValueError):
            IRCBot.format("", ["arg"])
        with self.assertRaises(ValueError):
            IRCBot.format("CMD$", ["arg"])
        with self.assertRaises(ValueError):
            IRCBot.format("CMD", "Invalid\nCharacters")
        with self.assertRaises(ValueError):
            IRCBot.format("CMD", [":arg1", "arg2"])
        with self.assertRaises(ValueError):
            IRCBot.format("CMD", ["arg one", "arg two"])

    def test_split_message(self):
        split = IRCBot.split_string("test§ test", 10)
        self.assertEqual(split, ["test§", "test"])
        split = IRCBot.split_string("test§ test", 6)
        self.assertEqual(split, ["test§", "test"])
        split = IRCBot.split_string("test§test", 5)
        self.assertEqual(split, ["test", "§tes", "t"])
        split = IRCBot.split_string("test§§  test", 10)
        self.assertEqual(split, ["test§§ ", "test"])
        split = IRCBot.split_string("test§§  test0123456789", 10, once=True)
        self.assertEqual(split, ["test§§ ", "test0123456789"])
        split = IRCBot.split_string("abcd abcd", 4)
        self.assertEqual(split, ["abcd", "abcd"])
        split = IRCBot.split_string("abcd  abcd", 4)
        self.assertEqual(split, ["abcd", " ", "abcd"])
        split = IRCBot.split_string("abcd   abcd", 4)
        self.assertEqual(split, ["abcd", "  ", "abcd"])
        split = IRCBot.split_string("abcd  abcd", 4, nobreak=False)
        self.assertEqual(split, ["abcd", "  ab", "cd"])
        split = IRCBot.split_string("abcd\u0308abcd", 4)
        self.assertEqual(split, ["abc", "d\u0308a", "bcd"])
        split = IRCBot.split_string("a b\u0308  abcd", 4)
        self.assertEqual(split, ["a", "b\u0308 ", "abcd"])
        split = IRCBot.split_string("ab\u0308\u0308abc", 4)
        self.assertEqual(split, ["a", "b\u0308", "\u0308ab", "c"])
        split = IRCBot.split_string("ab\u0308\u0308 abc", 4)
        self.assertEqual(split, ["a", "b\u0308", "\u0308", "abc"])
        with self.assertRaises(ValueError):
            IRCBot.split_string("test", 0)

    def test_safe_message_length(self):
        self.bot.nickname = "self"
        # :self!<user>@<host> PRIVMSG testnick :+<message>\r\n
        # <user> is max 10 bytes, <host> is max 63 bytes
        # One extra character (+ or -) if identify-msg is enabled
        # 410 bytes left for <message>
        self.assertEqual(self.bot.safe_message_length("testnick"), 410)

    def test_logging_setup(self):
        self.patch("logging.basicConfig", spec=True)
        self.bot = self.create_bot(
            log_communication=True, log_debug=True,
            log_kwargs={"stream": sys.stdout, "arg": "value"},
            loop=self.loop)
        self.assertEqual(logging.basicConfig.call_count, 1)
        args, kwargs = logging.basicConfig.call_args
        self.assertEqual(args, ())

        log_format = kwargs.pop("format")
        handlers = kwargs.pop("handlers")
        self.assertEqual(log_format, pyrcb2.pyrcb2.DEFAULT_LOG_FORMAT)
        self.assertEqual(len(handlers), 1)
        self.assertIsInstance(handlers[0], pyrcb2.utils.StreamHandler)
        self.assertNotIn("stream", kwargs)
        self.assertEqual(kwargs.pop("arg"), "value")
        self.assertFalse(kwargs)

    def test_listen_exception(self):
        class TestException(Exception):
            pass

        @mock_event(self.bot)
        @Event.command("XYZ")
        async def on_xyz(self):
            raise TestException

        self.bot.connect("irc.example.com", 6667)
        self.from_server(":server 001 self :Welcome")
        self.bot.register("self")
        self.clear_sent()
        self.from_server("XYZ")
        with self.assertRaises(TestException):
            async def coroutine():
                await self.bot.listen()
            self.bot.call_coroutine(coroutine())
        self.assertSent("QUIT")

    async def _test_call_single(self):
        async def _function(a, b, c):
            pass
        function = mock.Mock(wraps=_function)
        functools.update_wrapper(function, _function)

        await self.bot.call_single(function, [5], dict())
        self.assertCalled(function, 5, None, None)
        await self.bot.call_single(function, [5, 1, 2, 3], dict())
        self.assertCalled(function, 5, 1, 2)
        await self.bot.call_single(function, [5], dict(c=10))
        self.assertCalled(function, 5, None, c=10)

        def _function(a, b: int, *args, c, d=0):
            pass
        function = mock.Mock(wraps=_function)
        functools.update_wrapper(function, _function)

        await self.bot.call_single(function, [1, 2, 3, 4], dict(d=5))
        self.assertCalled(function, 1, 2, 3, 4, c=None, d=5)

    def test_call_single(self):
        self.loop.run_until_complete(self._test_call_single())

    def test_reuse(self):
        def setup():
            self.reader.alive = True
            self.bot.connect("irc.example.com", 6667)
            self.from_server(":server CAP * ACK account-notify")
            self.from_server(":server 001 self :Welcome")
            self.bot.register("self")

        setup()
        self.from_server(
            ":self JOIN #channel",
            ":server 353 self @ #channel :self user1",
            ":server 366 self #channel :End of names", None)
        self.bot.listen()
        self.assertInChannel("#channel")
        account_tracker = self.bot.account_tracker
        self.assertTrue(account_tracker.tracked_users)

        setup()
        self.assertNotInChannel("#channel")
        self.from_server(None)
        self.bot.listen()
        self.assertIs(self.bot.account_tracker, account_tracker)
        self.assertFalse(account_tracker.tracked_users)

    def test_astdio(self):
        py_input = mock.Mock(spec=input, return_value="xyz")
        py_print = mock.Mock(spec=print, return_value=None)
        self.patch("pyrcb2.astdio._py_input", new=py_input)
        self.patch("pyrcb2.astdio._py_print", new=py_print)

        async def coroutine():
            line = await astdio.input(loop=self.loop)
            self.assertEqual(line, "xyz")
            await astdio.print("abc", loop=self.loop)

        self.loop.run_until_complete(coroutine())
        self.assertCalledOnce(py_input)
        self.assertCalledOnce(py_print, "abc")


def main():
    asyncio.set_event_loop(None)
    unittest.main()

if __name__ == "__main__":
    main()
