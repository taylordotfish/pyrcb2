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

from .tests import BaseBotTest
from .utils import async_tests, mock_event
from pyrcb2 import Event
import asyncio
import unittest

WHOIS_ACCOUNTS = [
    ":server 311 self user1 user host * :realname",
    ":server 330 self user1 acc1 :is logged in as",
    ":server 318 self user1 :End of whois",
    ":server 311 self user2 user host * :realname",
    ":server 330 self user2 acc2 :is logged in as",
    ":server 318 self user2 :End of whois",
    ":server 311 self user3 user host * :realname",
    ":server 330 self user3 acc3 :is logged in as",
    ":server 318 self user3 :End of whois",
]

WHOX_ACCOUNTS = [
    ":server 354 self 999 user1 acc1",
    ":server 354 self 999 user2 acc2",
    ":server 354 self 999 user3 acc3",
    ":server 315 self #channel :End of who",
]

ACC_ID_STATUSES = [
    ":NickServ NOTICE self :self -> * ACC 0",
    ":NickServ NOTICE self :user1 ACC 0",
    ":NickServ NOTICE self :user2 ACC 1",
    ":NickServ NOTICE self :user3 ACC 3",
]

STATUS_ID_STATUSES = [
    ":NickServ NOTICE self :STATUS self 2",
    ":NickServ NOTICE self :STATUS user1 0",
    ":NickServ NOTICE self :STATUS user2 1",
    ":NickServ NOTICE self :STATUS user3 3",
]


@async_tests
class TestAccountTracker(BaseBotTest):
    @classmethod
    def create_bot(cls):
        bot = super().create_bot()
        bot.track_known_id_statuses = True
        return bot

    def standard_setup(self):
        return self.from_server(
            ":server 005 self PREFIX=(aohv)&@%+ CHANMODES=A,b,c,d :supported",
        )

    async def join_channel(self, get_accounts=False, get_id_statuses=False):
        await self.from_server(
            ":self JOIN #channel",
            ":server 353 self @ #channel :user1 user2 user3 self",
            ":server 366 self #channel :End of names")
        if get_accounts:
            self.from_server(*WHOIS_ACCOUNTS)
            await self.bot.get_accounts("#channel")
        if get_id_statuses:
            self.from_server(*ACC_ID_STATUSES)
            await self.bot.get_id_statuses("#channel")
        self.clear_sent()

    async def _test_accounts(self, synced):
        self.from_server(*WHOIS_ACCOUNTS)
        result = await self.bot.get_accounts(["user1", "user2", "user3"])
        self.assertSuccess(result)
        expected = {"user1": "Acc1", "user2": "Acc2", "user3": "Acc3"}
        self.assertEqual(result.value, expected)
        for user in ["user1", "user2", "user3"]:
            self.assertIs(self.bot.is_account_synced(user), synced)

    async def test_accounts_untracked(self):
        await self._test_accounts(synced=False)

    async def test_accounts_tracked(self):
        await self.join_channel()
        await self._test_accounts(synced=True)

    async def test_accounts_channel(self):
        await self.join_channel()
        self.from_server(*WHOIS_ACCOUNTS)
        result = await self.bot.get_accounts("#channel")
        self.assertSuccess(result)
        expected = {"user1": "Acc1", "user2": "Acc2", "user3": "Acc3"}
        self.assertEqual(result.value, expected)
        for user in ["user1", "user2", "user3"]:
            self.assertTrue(self.bot.is_account_synced(user))

    async def _test_accounts_channel_whox(self, whox_accounts):
        await self.from_server(":server 005 self WHOX :supported")
        await self.join_channel()
        self.from_server(*whox_accounts)
        result = await self.bot.get_accounts("#channel")
        self.assertSuccess(result)
        self.assertEqual(result.value, {
            "user1": "Acc1", "user2": "Acc2", "user3": "Acc3"})
        for user in ["user1", "user2", "user3"]:
            self.assertTrue(self.bot.is_account_synced(user))

    async def test_accounts_channel_whox(self):
        await self._test_accounts_channel_whox(WHOX_ACCOUNTS)

    async def test_custom_whox_query_type(self):
        with self.assertRaises(TypeError):
            self.bot.whox_query_type = []
        with self.assertRaises(ValueError):
            self.bot.whox_query_type = 1234
        self.bot.whox_query_type = 123
        await self._test_accounts_channel_whox(
            [line.replace("999", "123") for line in WHOX_ACCOUNTS],
        )

    async def test_auto_account_tracking(self):
        self.bot.track_accounts = True
        await self.join_channel()
        await self.writer.data_received.wait()
        self.assertCountEqual(self.pop_sent(), {
            "WHOIS :user1", "WHOIS :user2", "WHOIS :user3",
        })

        await self.from_server(*WHOIS_ACCOUNTS)
        await self.from_server(":user4 JOIN #channel")
        self.assertSent("WHOIS :user4")

    async def _test_id_statuses(self, acc, synced):
        self.from_server(*(ACC_ID_STATUSES if acc else STATUS_ID_STATUSES))
        result = await self.bot.get_id_statuses(["user1", "user2", "user3"])
        self.assertSuccess(result)
        expected = {"user1": 0, "user2": 1, "user3": 3}
        self.assertEqual(result.value, expected)
        for user in ["user1", "user2", "user3"]:
            self.assertIs(self.bot.is_id_status_synced(user), synced)

    async def test_id_statuses_untracked_acc(self):
        await self._test_id_statuses(acc=True, synced=False)

    async def test_id_statuses_untracked_status(self):
        await self._test_id_statuses(acc=False, synced=False)

    async def test_id_statuses_tracked_acc(self):
        await self.join_channel()
        await self._test_id_statuses(acc=True, synced=True)

    async def test_id_statuses_tracked_status(self):
        await self.join_channel()
        await self._test_id_statuses(acc=False, synced=True)

    async def test_id_statuses_channel(self):
        await self.join_channel()
        self.from_server(*ACC_ID_STATUSES)
        result = await self.bot.get_id_statuses("#channel")
        self.assertSuccess(result)
        expected = {"user1": 0, "user2": 1, "user3": 3}
        self.assertEqual(result.value, expected)
        for user in ["user1", "user2", "user3"]:
            self.assertTrue(self.bot.is_id_status_synced(user))

    async def test_auto_id_status_tracking(self):
        self.bot.track_id_statuses = True
        await self.join_channel()
        await self.writer.data_received.wait()
        self.assertCountEqual(self.pop_sent(), {
            "PRIVMSG NickServ :ACC self *",
            "PRIVMSG NickServ :STATUS self"})
        self.from_server(":NickServ NOTICE self :STATUS self 3")
        await self.writer.data_received.wait()
        self.assertCountEqual(self.pop_sent(), {
            "PRIVMSG NickServ :STATUS user1",
            "PRIVMSG NickServ :STATUS user2",
            "PRIVMSG NickServ :STATUS user3",
        })

        await self.from_server(*STATUS_ID_STATUSES)
        await self.from_server(":user4 JOIN #channel")
        self.assertSent("PRIVMSG NickServ :STATUS user4")

    async def test_accounts_cache(self):
        await self.join_channel()
        self.from_server(*WHOIS_ACCOUNTS)
        value = (await self.bot.get_accounts("#channel")).value
        self.clear_sent()
        value2 = (await self.bot.get_accounts("#channel")).value
        self.assertSent()  # Nothing should have been sent.
        self.assertEqual(value, value2)

    async def test_id_statuses_cache(self):
        await self.join_channel()
        self.from_server(*STATUS_ID_STATUSES)
        value = (await self.bot.get_id_statuses("#channel")).value
        self.clear_sent()
        value2 = (await self.bot.get_id_statuses("#channel")).value
        self.assertSent()  # Assert nothing sent
        self.assertEqual(value, value2)

    async def test_accounts_pending(self):
        await self.join_channel()
        coroutine = self.bot.get_accounts("#channel")
        coroutine2 = self.bot.get_accounts("#channel")
        self.from_server(*WHOIS_ACCOUNTS)
        result, result2 = await asyncio.gather(coroutine, coroutine2)
        self.assertEqual(result.value, result2.value)
        self.assertEqual(len(self.pop_sent()), 3)  # 3 tracked users

    async def test_accounts_pending_whox(self):
        await self.from_server(":server 005 self WHOX :supported")
        await self.join_channel()
        coroutine = self.bot.get_accounts("#channel")
        coroutine2 = self.bot.get_accounts("#channel")
        self.from_server(*WHOX_ACCOUNTS)
        result, result2 = await asyncio.gather(coroutine, coroutine2)
        self.assertEqual(result.value, result2.value)
        self.assertEqual(len(self.pop_sent()), 1)  # 1 WHO query

    async def test_id_statuses_pending(self):
        await self.join_channel()
        coroutine = self.bot.get_id_statuses("#channel")
        coroutine2 = self.bot.get_id_statuses("#channel")
        self.from_server(*ACC_ID_STATUSES)
        result, result2 = await asyncio.gather(coroutine, coroutine2)
        self.assertEqual(result.value, result2.value)
        # 3 tracked users plus 2 messages to discover the NickServ ID command.
        self.assertEqual(len(self.pop_sent()), 5)

    async def test_account_message(self):
        await self.join_channel(get_accounts=True, get_id_statuses=True)
        await self.from_server(":user1 ACCOUNT :new-account")
        self.assertSent("PRIVMSG NickServ :ACC user1")
        await self.from_server(":NickServ NOTICE self :user1 ACC 3")
        account = (await self.bot.get_account("user1")).value
        id_status = (await self.bot.get_id_status("user1")).value
        self.assertEqual(account, "new-account")
        self.assertEqual(id_status, 3)
        self.assertSent()  # Assert nothing sent

    async def test_left_channel(self):
        await self.join_channel(get_accounts=True, get_id_statuses=True)
        self.assertTrue(self.bot.is_account_synced("user1"))
        self.assertTrue(self.bot.is_id_status_synced("user1"))
        await self.from_server(":user1 PART #channel")
        self.assertFalse(self.bot.is_account_synced("user1"))
        self.assertFalse(self.bot.is_id_status_synced("user1"))

        self.assertTrue(self.bot.is_account_synced("user2"))
        await self.from_server(":self PART #channel")
        self.assertFalse(self.bot.is_account_synced("user2"))

    async def test_extended_join(self):
        await self.join_channel(get_accounts=True, get_id_statuses=True)
        self.bot.track_accounts = True
        await self.from_server("CAP self ACK :extended-join")
        await self.from_server(":user4 JOIN #channel acc4 :realname")
        self.assertSent()  # Assert nothing sent
        self.assertTrue(self.bot.is_account_synced("user4"))
        self.assertEqual(self.bot.accounts["user4"], "acc4")

    async def test_id_status_known(self):
        @mock_event(self.bot)
        @Event.id_status_known
        async def handler(nickname, status, old):
            pass
        await self.from_server(":NickServ NOTICE self :STATUS user1 0")
        self.assertIs(handler.called, False)
        await self.join_channel()
        await self.from_server(":NickServ NOTICE self :STATUS user1 0")
        self.assertCalledOnce(handler, "user1", 0, None)
        handler.reset_mock()
        await self.from_server(":NickServ NOTICE self :STATUS user1 0")
        self.assertIs(handler.called, False)
        await self.from_server(":NickServ NOTICE self :STATUS user1 1")
        self.assertCalledOnce(handler, "user1", 1, 0)

    async def test_id_status_unknown(self):
        @mock_event(self.bot)
        @Event.id_status_unknown
        async def handler(nickname, old):
            pass
        await self.from_server(":NickServ NOTICE self :STATUS user1 0")
        self.assertIs(handler.called, False)
        await self.join_channel()
        await self.from_server(":user1 QUIT")
        self.assertIs(handler.called, False)
        await self.from_server(":NickServ NOTICE self :STATUS user2 1")
        await self.from_server(":NickServ NOTICE self :STATUS user3 3")
        await self.from_server(":user4 JOIN #channel")
        await self.from_server(":NickServ NOTICE self :STATUS user4 3")
        self.assertIs(handler.called, False)
        await self.from_server(":user2 QUIT")
        self.assertCalledOnce(handler, "user2", 1)
        handler.reset_mock()
        await self.from_server(":user3 PART #channel")
        self.assertCalledOnce(handler, "user3", 3)
        handler.reset_mock()
        await self.from_server(":user4 NICK user5")
        self.assertCalledOnce(handler, "user4", 3)
        handler.reset_mock()
        await self.from_server(":NickServ NOTICE self :STATUS user5 3")
        await self.from_server(":self PART #channel")
        self.assertCalledOnce(handler, "user5", 3)

    async def test_account_known(self):
        @mock_event(self.bot)
        @Event.account_known
        async def handler(nickname, account, old, was_known):
            pass
        await self.from_server(*WHOIS_ACCOUNTS)
        self.assertIs(handler.called, False)
        await self.join_channel()
        await self.from_server(
            ":server 311 self user1 user host * :realname",
            ":server 330 self user1 acc1 :is logged in as",
            ":server 318 self user1 :End of whois",
        )
        self.assertCalledOnce(handler, "user1", "acc1", None, False)
        handler.reset_mock()
        await self.from_server(":user1 ACCOUNT acc1")
        await self.from_server(":user1 ACCOUNT acc0")
        self.assertCalledOnce(handler, "user1", "acc0", "acc1", True)
        handler.reset_mock()
        await self.from_server(":user3 ACCOUNT *")
        self.assertCalledOnce(handler, "user3", None, None, False)
        handler.reset_mock()
        await self.from_server(":user4 JOIN #channel acc4 :User 4")
        self.assertCalledOnce(handler, "user4", "acc4", None, False)
        handler.reset_mock()

        await self.from_server(":server 005 self WHOX :supported")
        self.from_server(
            ":server 354 self 999 user1 0",
            ":server 354 self 999 user2 acc2",
            ":server 354 self 999 user3 acc3",
            ":server 354 self 999 user4 acc4",
            ":server 315 self #channel :End of who",
        )
        await self.bot.get_accounts("#channel")
        # Make sure coroutines started by get_accounts() (with
        # IRCBot.add_listen_future()) have a chance to be awaited.
        await self.from_server(":server PING")
        self.assertAnyCall(handler, "user1", None, "acc0", True)
        self.assertAnyCall(handler, "user2", "acc2", None, False)
        self.assertAnyCall(handler, "user3", "acc3", None, True)
        self.assertEqual(handler.call_count, 3)
        handler.reset_mock()
        await self.from_server(":user3 NICK user5")
        self.assertCalledOnce(handler, "user5", "acc3", None, False)

    async def test_account_unknown(self):
        @mock_event(self.bot)
        @Event.account_unknown
        async def handler(nickname, old):
            pass
        await self.from_server(*WHOIS_ACCOUNTS)
        await self.from_server(":user1 ACCOUNT acc1")
        self.assertIs(handler.called, False)
        await self.join_channel()
        await self.from_server(":user1 QUIT")
        self.assertIs(handler.called, False)
        await self.from_server(":user2 ACCOUNT acc2")
        await self.from_server(
            ":server 311 self user3 user host * :realname",
            ":server 330 self user3 acc3 :is logged in as",
            ":server 318 self user3 :End of whois",
        )
        await self.from_server(":user4 JOIN #channel acc4 :User 4")
        self.assertIs(handler.called, False)
        await self.from_server(":user2 QUIT")
        self.assertCalledOnce(handler, "user2", "acc2")
        handler.reset_mock()
        await self.from_server(":user3 PART #channel")
        self.assertCalledOnce(handler, "user3", "acc3")
        handler.reset_mock()
        await self.from_server(":user4 NICK user5")
        self.assertCalledOnce(handler, "user4", "acc4")
        handler.reset_mock()
        await self.from_server(":self PART #channel")
        self.assertCalledOnce(handler, "user5", "acc4")

    async def test_account_tracking_on_nick_change(self):
        await self.join_channel()
        await self.from_server(
            ":server 311 self user3 user host * :realname",
            ":server 330 self user3 acc3 :is logged in as",
            ":server 318 self user3 :End of whois",
        )
        self.assertTrue(self.bot.is_account_synced("user3"))
        await self.from_server(":user3 NICK :user4")
        self.assertTrue(self.bot.is_account_synced("user4"))
        await self.from_server(":user4 NICK :user3")
        self.assertTrue(self.bot.is_account_synced("user3"))


def main():
    unittest.main()


if __name__ == "__main__":
    main()
