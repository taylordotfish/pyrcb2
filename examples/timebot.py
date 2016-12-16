#!/usr/bin/env python3
# To the extent possible under law, the author(s) have dedicated all
# copyright and neighboring rights to this software to the public domain
# worldwide. This software is distributed without any warranty. See
# <http://creativecommons.org/publicdomain/zero/1.0/> for a copy of the
# CC0 Public Domain Dedication.

from pyrcb2 import IRCBot, Event
from datetime import datetime
import asyncio


class MyBot:
    def __init__(self):
        # You can set log_communication to False to disable logging.
        self.bot = IRCBot(log_communication=True)
        self.bot.load_events(self)

    def start(self):
        self.bot.call_coroutine(self.start_async())

    async def start_async(self):
        await self.bot.connect("irc.example.com", 6667)
        await self.bot.register("timebot")
        await self.bot.join("#timebot")
        self.bot.schedule_coroutine(self.auto_time_loop(10*60))
        await self.bot.listen()

    @Event.privmsg
    async def on_privmsg(self, sender, channel, message):
        # Say the time when someone says "!time".
        if message == "!time":
            time = str(datetime.utcnow())
            if channel is None:
                self.bot.privmsg(sender, time)
            else:
                self.bot.privmsg(channel, sender + ": " + time)
            return

        # Join the specified channel (channel ops only).
        if message.startswith("!join ") and channel is not None:
            # User must be an operator.
            if not self.bot.users[channel][sender].has_prefix("@"):
                return

            try:
                new_channel = message.split()[1]
            except IndexError:
                return

            if new_channel in self.bot.channels:
                response = "{}: Already in {}".format(sender, new_channel)
                self.bot.privmsg(channel, response)
                return

            result = await self.bot.join(new_channel)
            self.bot.privmsg(channel, "{}: {} {}.".format(
                sender, "Joined" if result.success else "Could not join",
                new_channel,
            ))

    async def auto_time_loop(self, interval):
        # Say the time at specified intervals.
        while True:
            await asyncio.sleep(interval)
            time = str(datetime.utcnow())
            for channel in self.bot.channels:
                self.bot.privmsg(channel, "(auto) " + time)


def main():
    mybot = MyBot()
    mybot.start()

if __name__ == "__main__":
    main()


# Example IRC log:
# [#timebot] timebot has joined #timebot
# [#timebot] <user1234> !time
# [#timebot] <timebot> user1234: 2016-11-02 04:41:25.227800
#
# 10 minutes later:
# [#timebot] <timebot> (auto) 2016-11-02 04:51:18.551725


# In a private query:
# [query] <user1234> !time
# [query] <timebot> 2016-11-02 05:28:17.395795


# Joining channels:
# [#timebot] <@channel-op> !join #timebot2
#
# A few seconds later:
# [#timebot2] timebot has joined #timebot2
# [#timebot] <timebot> channel-op: joined #timebot2.
