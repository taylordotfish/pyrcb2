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

from .decorators import cast_args, document_attr
from .events import Event
from .itypes import IStr, IDict, ISet
from .messages import Message, Reply, ANY, SELF, WaitResult, MultiWaitResult
from .utils import Sentinel
from . import numerics

from collections.abc import Iterable
from enum import IntEnum
import re
import time

__all__ = ["AccountTracker"]


def who_replies_match(replies, channel, query_type):
    if not replies:
        return False
    for sender, command, *args in replies[:-1]:
        if command != numerics.codes["RPL_WHOSPCRPL"]:
            return False
        # args[1:] should equal [query_type, nickname, account_name]
        if len(args[1:]) != 3 or args[1] != query_type:
            return False
    endofwho = replies[-1]
    sender, command, *args = endofwho
    return (
        command == numerics.codes["RPL_ENDOFWHO"] and
        args[1:] and args[1] == channel
    )


class Status(IntEnum):
    """Represents an ID status; returned by :meth:`IRCBot.get_id_status`.

    These status codes correspond to the values returned by most
    implementations of NickServ. For example, see `Atheme's documentation`__.

    __ https://github.com/atheme/atheme/wiki/NickServ%3AACC
    """
    no_account = 0
    unrecognized = 1
    recognized = 2
    logged_in = 3

_statuses = set(Status)
NONE = Sentinel("NONE")


class AccountTracker:
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger.getChild("accounts")
        self.reset()

        self.track_id_statuses = False
        self._track_known_id_statuses = False
        self.track_accounts = False
        self._whox_query_type = "999"

    def reset(self):
        self.use_acc = True
        self.use_status = True

        self.id_statuses = IDict()
        self._id_status_pending = IDict()
        self.latest_id_status = None
        # Holds the current discover_id_command() future.
        self._discover_future = None

        self.accounts = IDict()
        self._account_pending = IDict()
        self._whox_pending = IDict()
        self.latest_who_replies = []

        self.tracked_users = ISet()
        self.tracked_channels = ISet()
        self.newly_untracked_users = ISet()

    @property
    def account_notify(self):
        return "account-notify" in self.bot.extensions

    @document_attr
    def track_id_statuses(self):
        """Whether or not to track users' ID statuses. If true, this bot will
        track the ID statuses of all users in the channels it is in. The bot
        will send a request to NickServ for each user. This option implies
        `track_known_id_statuses`.

        The IRC extension ``account-notify`` must be enabled for this to work.

        :type: `bool`
        """

    @document_attr
    def track_accounts(self):
        """Whether or not to track users' accounts. If true, this bot will
        track the accounts of all users in the channels it is in.

        The IRC extension ``account-notify`` must be enabled for this to work.

        :type: `bool`
        """

    @property
    def track_known_id_statuses(self):
        """Whether or not to track ID status changes for users whose ID
        statuses were already known. No user's ID status will be tracked by
        default, but if a user's ID status is looked up, then changes in their
        ID status will be monitored. A request to NickServ will be sent for
        each ID status change.

        The IRC extension ``account-notify`` must be enabled for this to work.

        If `track_id_statuses` is true, this attribute will also be true.

        :type: `bool`
        """
        return self.track_id_statuses or self._track_known_id_statuses

    @track_known_id_statuses.setter
    def track_known_id_statuses(self, value):
        self._track_known_id_statuses = value

    @property
    def is_tracking_id_statuses(self):
        """Whether or not this bot is tracking users' ID statuses. For this to
        be true, `track_id_statuses` must be true and the IRC extension
        ``account-notify`` must be enabled.

        This is a read-only property.

        :type: `bool`
        """
        return self.track_id_statuses and self.account_notify

    @property
    def is_tracking_known_id_statuses(self):
        """Whether or not this bot is tracking ID status changes for users
        whose ID statuses were already known. (No new ID statuses will be
        looked up unless `track_id_statuses` is also true.)

        For this to be true, `track_known_id_statuses` or `track_id_statuses`
        must be true and the IRC extension ``account-notify`` must be enabled.

        This is a read-only property.

        :type: `bool`
        """
        return self.track_known_id_statuses and self.account_notify

    @property
    def is_tracking_accounts(self):
        """Whether or not this bot is tracking users' accounts. For this to be
        true, `track_accounts` must be true and the IRC extension
        ``account-notify`` must be enabled.

        This is a read-only property.

        :type: `bool`
        """
        return self.track_accounts and self.account_notify

    @property
    def is_tracking_known_accounts(self):
        """Whether or not this bot is tracking account changes for users whose
        accounts were already known. (No new accounts will be looked up unless
        `track_accounts` is also true.)

        For this to be true, the IRC extension ``account-notify`` must be
        enabled. Because tracking known accounts is passive, there is no option
        to disable this.

        This is a read-only property.

        :type: `bool`
        """
        return self.account_notify

    def is_id_status_synced(self, nickname, ignore_cache=False):
        """Checks if a user's ID status is synced. This means that the user's
        ID status is known, `is_tracking_known_id_statuses` is true, and the
        user shares a channel with this bot.

        :rtype: `bool`
        """
        return (
            self.is_tracking_known_id_statuses and
            nickname != self.bot.nickname and
            (nickname in self.id_statuses or ignore_cache) and
            nickname in self.tracked_users
        )

    def is_account_synced(self, nickname, ignore_cache=False):
        """Checks if a user's account is synced. This means that the user's
        account is known, `is_tracking_known_accounts` is true, and the user
        shares a channel with this bot.

        :rtype: `bool`
        """
        return (
            self.is_tracking_known_accounts and
            nickname != self.bot.nickname and
            (nickname in self.accounts or ignore_cache) and
            nickname in self.tracked_users
        )

    def id_status_pending(self, nickname):
        return self._id_status_pending.get(nickname)

    def account_pending(self, nickname):
        return self._account_pending.get(nickname)

    def whox_pending(self, channel):
        return self._whox_pending.get(channel)

    def set_id_status_pending(self, nickname):
        self._id_status_pending[nickname] = self.bot.loop.create_future()

    def set_account_pending(self, nickname):
        self._account_pending[nickname] = self.bot.loop.create_future()

    def set_whox_pending(self, channel):
        self._whox_pending[channel] = self.bot.loop.create_future()

    def set_id_status_done(self, nickname, value):
        if nickname in self._id_status_pending:
            self._id_status_pending.pop(nickname).set_result(value)

    def set_account_done(self, nickname, value):
        if nickname in self._account_pending:
            self._account_pending.pop(nickname).set_result(value)

    def set_whox_done(self, channel, value):
        if channel in self._whox_pending:
            self._whox_pending.pop(channel).set_result(value)

    def set_tracked(self, *nicknames):
        nicknames = ISet(nicknames)
        nicknames.discard(self.bot.nickname)
        self.logger.debug("Settings users as tracked: %r", nicknames)
        for nickname in self.newly_untracked_users & nicknames:
            self.id_statuses.pop(nickname, None)
            self.accounts.pop(nickname, None)
            self.newly_untracked_users.remove(nickname)
        self.tracked_users |= nicknames

    def set_untracked(self, *nicknames):
        for nick in self.newly_untracked_users:
            self.id_statuses.pop(nick, None)
            self.accounts.pop(nick, None)
        nicknames = ISet(nicknames)
        nicknames.discard(self.bot.nickname)
        self.logger.debug("Setting users as untracked: %r", nicknames)
        self.tracked_users -= nicknames
        self.newly_untracked_users = nicknames

    def is_in_any_channel(self, nickname):
        return any(
            nickname in users for users in self.bot.users.values()
        )

    def is_in_other_channels(self, nickname, *exclude_channels):
        return any(
            nickname in self.bot.users[channel] for channel in
            self.bot.channels - ISet(exclude_channels)
        )

    @Event.notice
    async def on_notice(self, sender, channel, message):
        if sender != "NickServ":
            return

        match = None
        acc_matched, status_matched = False, False

        if self.use_acc and self.use_status:
            if re.match(r"Unknown command ACC\b", message, re.I):
                self.use_acc = False
            elif re.match(r"[^ ]* -> [^ ]* ACC \d", message):
                self.use_status = False

        if self.use_acc:
            match = re.match(r"([^ ]*) ACC (\d)", message)
            if match:
                acc_matched = True
                nick, status = match.groups()

        if self.use_status:
            match = re.match(r"STATUS ([^ ]*) (\d)", message)
            if match:
                status_matched = True
                nick, status = match.groups()

        coroutines = set()
        if match:
            status = int(status)
            status = Status(status) if status in _statuses else status
            self.logger.debug("Got status for %s: %s", nick, status)
            self.latest_id_status = (nick, status)

            synced = self.is_id_status_synced(nick, ignore_cache=True)
            if synced:
                coroutines |= self.get_coroutines(nick, new_id_status=status)
                self.id_statuses[nick] = status

        if self.use_acc and self.use_status:
            if acc_matched != status_matched:
                self.use_acc = acc_matched
                self.use_status = status_matched
        coroutines and await self.bot.gather(*coroutines)

    async def discover_id_command(self):
        self.logger.debug("Discovering NickServ ID status command")
        nickname = self.bot.nickname
        # Wait for messages to be sent.
        await self.bot.gather(
            self.bot.privmsg("NickServ", "ACC {} *".format(nickname)),
            self.bot.privmsg("NickServ", "STATUS {}".format(nickname)),
        )

        def matches_acc(message):
            return re.match(r"[^ ]* -> [^ ]* ACC \d", message)

        def matches_status(message):
            return re.match(r"STATUS [^ ]* \d", message)

        await self.bot.wait_for(
            Message("NickServ", "NOTICE", SELF, matches_acc),
            Message("NickServ", "NOTICE", SELF, matches_status),
        )

    @cast_args
    def get_id_status(self, nickname: IStr, use_cache=True, use_pending=True):
        """Gets the specified user's ID status. This may send a query to
        NickServ, depending on whether or not the user's ID status is cached.

        :param str nickname: The user whose ID status to get.
        :param bool use_cache: Whether or not to use a user's cached ID status
          if it is available. The cache will be used only if it is guaranteed
          to be up-to-date.
        :param bool use_pending: Whether or not to avoid sending another
          ID status request if there is already one in progress.
        :returns: A coroutine or future; when awaited, returns a `WaitResult`
          with the user's ID status. If the user's ID status is synced/cached,
          a completed `~asyncio.Future` is returned, so you can call
          :meth:`Future.result() <asyncio.Future.result>` to get the result
          immediately.
        :rtype: When awaited, a `WaitResult` where ``value`` is a `Status`.
        """
        self.logger.debug("Getting ID status for %s", nickname)
        if use_cache and self.is_id_status_synced(nickname):
            self.logger.debug("Returning cached ID status for %s", nickname)
            status = self.id_statuses[nickname]
            future = self.bot.loop.create_future()
            future.set_result(WaitResult(True, status))
            return future

        pending = self.id_status_pending(nickname)
        if pending and use_pending:
            return pending
        self.set_id_status_pending(nickname)

        async def coroutine():
            if self.use_acc and self.use_status:
                future = self._discover_future
                if future is None or future.done():
                    future = self.bot.ensure_future(self.discover_id_command())
                    self._discover_future = future
                await self._discover_future

            futures = []
            if self.use_acc:
                futures.append(self.bot.privmsg(
                    "NickServ", "ACC {}".format(nickname),
                ))
            if self.use_status:
                futures.append(self.bot.privmsg(
                    "NickServ", "STATUS {}".format(nickname),
                ))
            await self.bot.gather(*futures)

            def matches_acc(message):
                match = re.match(r"([^ ]*) ACC \d", message)
                return match and match.group(1) == nickname

            def matches_status(message):
                match = re.match(r"STATUS ([^ ]*) \d", message)
                return match and match.group(1) == nickname

            result = await self.bot.wait_for(
                Message("NickServ", "NOTICE", SELF, matches_acc),
                Message("NickServ", "NOTICE", SELF, matches_status),
            )

            status = None
            if result.success:
                nick, status = self.latest_id_status
            result.value = status
            self.set_id_status_done(nickname, result)
            return result
        return coroutine()

    def get_id_statuses(
            self, chan_or_nicks, use_cache=True, use_pending=True,
            no_self=True):
        """Gets multiple users' ID statuses.

        :param chan_or_nicks: A channel or list of users to look up ID statuses
          for.
        :param bool use_cache: Same as in :meth:`get_id_status`.
        :param bool use_pending: Same as in :meth:`get_id_status`.
        :param bool no_self: If true and ``chan_or_nicks`` is a channel, this
          bot will be excluded from the channel. This bot can't track its own
          ID status like other users, so if it's included, it could prevent the
          cache from being used effectively.
        :returns: A coroutine; when awaited, returns a `WaitResult` with the
          users' ID statuses.
        :rtype: When awaited, a `WaitResult` where ``value`` is an `IDict` that
          maps nicknames to `Status` objects.
        """
        if not isinstance(chan_or_nicks, (str, Iterable)):
            raise TypeError("'chan_or_nicks' must be a str or an iterable.")
        is_channel = isinstance(chan_or_nicks, str)
        nicknames = set(
            self.bot.users.get(chan_or_nicks, [])
            if is_channel else chan_or_nicks
        ) - ({self.bot.nickname} if is_channel and no_self else set())

        statuses_coro = self.bot.gather(*(
            self.get_id_status(nickname, use_cache, use_pending)
            for nickname in nicknames
        ))

        async def coroutine():
            results = IDict(zip(nicknames, await statuses_coro))
            statuses = IDict({
                k: v.value for k, v in results.items() if v.success})
            return MultiWaitResult(results, statuses)
        return coroutine()

    @Event.reply("RPL_WHOREPLY", "RPL_WHOSPCRPL")
    def on_who_reply_start(self, *args):
        if not self.bot.is_capturing:
            self.logger.debug("Capturing WHO replies")
            self.bot.start_capturing()

    @Event.reply("RPL_ENDOFWHO")
    def on_endofwho(self, *args):
        self.logger.debug("Done capturing WHO replies")
        self.latest_who_replies = self.bot.stop_capturing()

    def get_accounts_whox(self, channel, use_cache=True, use_pending=True):
        self.logger.debug("Getting accounts for %s using WHOX", channel)
        nicks = self.bot.users[channel]
        if use_cache and all(self.is_account_synced(n) for n in nicks):
            self.logger.debug("Returning cached accounts for %s", channel)
            accounts = IDict({n: self.accounts[n] for n in nicks})

            async def coroutine():
                return WaitResult(True, accounts)
            return coroutine()

        pending = self.whox_pending(channel)
        if pending and use_pending:
            return pending

        for nick in nicks:
            self.set_account_pending(nick)
        self.set_whox_pending(channel)

        def set_accounts_done(whox_result):
            for nick in nicks:
                success = whox_result.success and nick in whox_result.value
                account = (whox_result.value or {}).get(nick)
                error, error_cause = whox_result.error, whox_result.error_cause
                if whox_result.success and not success:
                    error_cause = "not_in_whox"
                result = WaitResult(success, account, error, error_cause)
                self.set_account_done(nick, result)

        async def coroutine():
            query_type = self.whox_query_type
            await self.bot.send_command(
                "WHO", channel, "%tna,{}".format(query_type),
            )

            timeout = self.bot.default_timeout
            end_time = time.monotonic() + timeout
            result = None
            while timeout > 0:
                result = await self.bot.wait_for(
                    Reply("RPL_ENDOFWHO", channel, ANY))
                if not result.success:
                    break
                replies = self.latest_who_replies
                if who_replies_match(replies, channel, query_type):
                    accounts = self.parse_whox_replies(channel, replies)
                    result.value = accounts
                    break
                timeout = end_time - time.monotonic()
                result = None

            if result is None:
                result = WaitResult(success=False, error_cause="timeout")
            set_accounts_done(result)
            self.set_whox_done(channel, result)
            return result
        return coroutine()

    def parse_whox_replies(self, channel, replies):
        accounts = IDict()
        coroutines = set()

        for sender, command, *args in replies:
            if command != numerics.codes["RPL_WHOSPCRPL"]:
                continue
            target, query_type, nickname, account = args
            account = None if account == "0" else IStr(account)
            accounts[nickname] = account
            if self.is_account_synced(nickname, ignore_cache=True):
                coroutines |= self.get_coroutines(
                    nickname, new_account=account,
                )
                self.accounts[nickname] = account

        for coroutine in coroutines:
            future = self.bot.ensure_future(coroutine)
            self.bot.add_listen_future(future)
        return accounts

    @Event.whois
    async def on_whois(self, nickname, whois_reply):
        self.logger.debug(
            "Received WHOIS reply for %s: account is %s",
            nickname, whois_reply.account)
        coroutines = set()
        synced = self.is_account_synced(nickname, ignore_cache=True)
        if synced:
            account = whois_reply.account
            coroutines |= self.get_coroutines(nickname, new_account=account)
            self.accounts[nickname] = account
        coroutines and await self.bot.gather(*coroutines)

    @cast_args
    def get_account(self, nickname: IStr, use_cache=True, use_pending=True):
        """Gets the specified user's account. This may send a WHOIS query,
        depending on whether or not the user's account is cached.

        :param str nickname: The user whose account to get.
        :param bool use_cache: Whether or not to use a user's cached account
          if it is available. The cache will be used only if it is guaranteed
          to be up-to-date.
        :param bool use_pending: Whether or not to avoid sending another
          account request if there is already one in progress.
        :returns: A coroutine or future; when awaited, returns a `WaitResult`
          with the user's account. If the user's account is synced/cached, a
          completed `~asyncio.Future` is returned, so you can call
          :meth:`Future.result() <asyncio.Future.result>` to get the result
          immediately.
        :rtype: When awaited, a `WaitResult` where ``value`` is an `IStr`.
        """
        self.logger.debug("Getting account for %s", nickname)
        if use_cache and self.is_account_synced(nickname):
            self.logger.debug("Returning cached account for %s", nickname)
            account = self.accounts[nickname]
            future = self.bot.loop.create_future()
            future.set_result(WaitResult(True, account))
            return future

        pending = self.account_pending(nickname)
        if pending and use_pending:
            async def coroutine():
                result = await pending
                if not result.success and result.error_cause == "not_in_whox":
                    return await self.get_account(nickname, use_cache)
                return result
            return coroutine()

        self.set_account_pending(nickname)

        async def coroutine():
            result = await self.bot.whois(nickname)
            result.value = result.value.account if result.success else None
            if result.error:
                if result.error.command == numerics.codes["ERR_NOSUCHNICK"]:
                    result.success = True
            self.set_account_done(nickname, result)
            return result
        return coroutine()

    def get_accounts_whois(self, nicknames, use_cache=True, use_pending=True):
        accounts_coro = self.bot.gather(*(
            self.get_account(nickname, use_cache, use_pending)
            for nickname in nicknames
        ))

        async def coroutine():
            results = IDict(zip(nicknames, await accounts_coro))
            accounts = IDict({
                k: v.value for k, v in results.items() if v.success})
            return MultiWaitResult(results, accounts)
        return coroutine()

    def get_accounts(
            self, chan_or_nicks, use_cache=True, use_pending=True,
            no_self=True):
        """Gets multiple users' accounts.

        :param chan_or_nicks: A channel or list of users to look up accounts
          for.
        :param bool use_cache: Same as in :meth:`get_account`.
        :param bool use_pending: Same as in :meth:`get_account`.
        :param bool no_self: If true and ``chan_or_nicks`` is a channel, this
          bot will be excluded from the channel. This bot can't track its own
          account like other users, so if it's included, it could prevent the
          cache from being used effectively.
        :returns: A coroutine; when awaited, returns a `WaitResult` with the
          users' accounts.
        :rtype: When awaited, a `WaitResult` where ``value`` is an `IDict` that
          maps nicknames to `IStr` accounts.
        """
        if not isinstance(chan_or_nicks, (str, Iterable)):
            raise TypeError("'chan_or_nicks' must be a str or an iterable.")
        is_channel = isinstance(chan_or_nicks, str)
        channel = chan_or_nicks if is_channel else None
        nicknames = None if is_channel else chan_or_nicks

        if "WHOX" in self.bot.isupport and is_channel:
            accounts_coro = self.get_accounts_whox(
                channel, use_cache, use_pending,
            )

            async def coroutine():
                result = await accounts_coro
                return MultiWaitResult(
                    None, result.value, result.error, result.error_cause,
                    success=result.success,
                )
            return coroutine()

        users = set(
            self.bot.users.get(channel, []) if is_channel else nicknames
        ) - ({self.bot.nickname} if is_channel and no_self else set())
        accounts_coro = self.get_accounts_whois(users, use_cache, use_pending)

        async def coroutine():
            return await accounts_coro
        return coroutine()

    @Event.join
    async def on_join(self, sender: IStr, channel, account):
        if not self.account_notify:
            return

        coroutines = set()
        if sender == self.bot.nickname:
            self.set_tracked(*self.bot.users[channel])
            self.tracked_channels.add(channel)
            if self.is_tracking_accounts:
                coroutines.add(self.get_accounts(channel, no_self=True))
            if self.is_tracking_id_statuses:
                coroutines.add(self.get_id_statuses(channel, no_self=True))
            coroutines and await self.bot.gather(*coroutines)
            return

        self.set_tracked(sender)
        if account is not None and self.is_account_synced(sender, True):
            new_account = None if account == "*" else account
            coroutines |= self.get_coroutines(sender, new_account=new_account)
            self.accounts[sender] = new_account

        if self.is_tracking_accounts and account is None:
            if not self.is_account_synced(sender):
                coroutines.add(self.get_account(sender))
        if self.is_tracking_id_statuses:
            if not self.is_id_status_synced(sender):
                coroutines.add(self.get_id_status(sender))
        coroutines and await self.bot.gather(*coroutines)

    @Event.part
    async def on_part(self, sender, channel, message):
        if self.account_notify:
            await self.on_left_channel(sender, channel)

    @Event.kick
    async def on_kick(self, sender, channel, target, message):
        if self.account_notify:
            await self.on_left_channel(target, channel)

    @Event.quit
    async def on_quit(self, sender, message):
        if not self.account_notify:
            return
        coroutines = self.get_coroutines(sender, known=False)
        self.set_untracked(sender)
        coroutines and await self.bot.gather(*coroutines)

    @cast_args
    async def on_left_channel(self, nickname: IStr, channel: IStr):
        nicks = [nickname]
        if nickname == self.bot.nickname:
            nicks = list(self.bot.users[channel])
            self.tracked_channels.discard(channel)
        untracked_users = set(
            nick for nick in nicks
            if not self.is_in_other_channels(nick, channel))
        coroutines = set()
        for user in untracked_users:
            coroutines |= self.get_coroutines(user, known=False)
        self.set_untracked(*untracked_users)
        coroutines and await self.bot.gather(*coroutines)

    @Event.command("ACCOUNT")
    async def on_account(self, sender, account):
        if not self.is_account_synced(sender, ignore_cache=True):
            return
        account = None if account == "*" else IStr(account)
        coroutines = self.get_coroutines(sender, new_account=account)
        self.accounts[sender] = account

        # If self.is_tracking_id_statuses is false, but the ID status
        # for "sender" is synced, then self.is_tracking_known_id_statuses
        # must be true.
        check_id_status = self.is_id_status_synced(sender, True) and (
            self.is_tracking_id_statuses or self.is_id_status_synced(sender))
        if check_id_status:
            coroutines.add(self.get_id_status(sender, use_cache=False))
        coroutines and await self.bot.gather(*coroutines)

    @Event.nick
    async def on_nick(self, old_nickname, new_nickname):
        coroutines = self.get_coroutines(old_nickname, known=False)
        if self.is_account_synced(old_nickname):
            account = self.accounts[old_nickname]
            coroutines |= self.get_coroutines(
                new_nickname, new_account=account,
            )
            self.accounts[new_nickname] = account

        check_id_status = self.is_id_status_synced(new_nickname, True) and (
            self.is_tracking_id_statuses or
            self.is_id_status_synced(old_nickname))
        self.set_untracked(old_nickname)
        self.set_tracked(new_nickname)
        if check_id_status:
            coroutines.add(self.get_id_status(new_nickname, use_cache=False))
        coroutines and await self.bot.gather(*coroutines)

    def get_coroutines(
            self, user, new_account=NONE, new_id_status=NONE, known=True):
        if user == self.bot.nickname:
            return set()
        account_synced = self.is_account_synced(user)
        id_status_synced = self.is_id_status_synced(user)
        account = self.accounts[user] if account_synced else NONE
        id_status = self.id_statuses[user] if id_status_synced else NONE
        coroutines = set()
        if not known:
            if account_synced:
                coroutines.add(self.bot.call(
                    Event, "account_unknown", user, account))
            if id_status_synced:
                coroutines.add(self.bot.call(
                    Event, "id_status_unknown", user, id_status))
            return coroutines

        tracking_acc = self.is_tracking_known_accounts
        tracking_id = self.is_tracking_known_id_statuses
        if tracking_acc and account != new_account is not NONE:
            coroutines.add(self.bot.call(
                Event, "account_known", user, new_account,
                None if account is NONE else account, account_synced))
        if tracking_id and id_status != new_id_status is not NONE:
            coroutines.add(self.bot.call(
                Event, "id_status_known", user, new_id_status,
                None if id_status is NONE else id_status, id_status_synced))
        return coroutines

    @property
    def whox_query_type(self):
        return self._whox_query_type

    @whox_query_type.setter
    def whox_query_type(self, value):
        if not isinstance(value, (int, str)):
            raise TypeError("Query type must be a string or an integer.")
        if isinstance(value, int):
            value = str(value)
        if not (1 <= len(value) <= 3):
            raise ValueError("Query type must be 1 to 3 characters.")
        self._whox_query_type = value
