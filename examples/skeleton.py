#!/usr/bin/env python3
# This file contains the basic structure of a pyrcb2 bot.
# You can use this as a template.
#
# To the extent possible under law, the author(s) have dedicated all
# copyright and neighboring rights to this software to the public domain
# worldwide. This software is distributed without any warranty. See
# <http://creativecommons.org/publicdomain/zero/1.0/> for a copy of the
# CC0 Public Domain Dedication.

from pyrcb2 import IRCBot, Event


class MyBot:
    def __init__(self):
        # You can set log_communication to False to disable logging.
        self.bot = IRCBot(log_communication=True)
        self.bot.load_events(self)

    def start(self):
        self.bot.call_coroutine(self.start_async())

    async def start_async(self):
        await self.bot.connect("irc.example.com", 6667)
        await self.bot.register("nickname")
        # More code here (optional)...
        await self.bot.listen()


def main():
    mybot = MyBot()
    mybot.start()

if __name__ == "__main__":
    main()
