# This example bot corresponds to the "Getting started" guide at
# <https://pythonhosted.org/pyrcb2/getting-started.html>.
#
# To the extent possible under law, the author(s) have dedicated all
# copyright and neighboring rights to this software to the public domain
# worldwide. This software is distributed without any warranty. See
# <http://creativecommons.org/publicdomain/zero/1.0/> for a copy of the
# CC0 Public Domain Dedication.

from pyrcb2 import IRCBot, Event


class MyBot:
    def __init__(self):
        self.bot = IRCBot(log_communication=True)
        self.bot.load_events(self)

    def start(self):
        self.bot.call_coroutine(self.start_async())

    async def start_async(self):
        await self.bot.connect("irc.example.com", 6667)
        await self.bot.register("mybot")
        # More code here (optional)...
        await self.bot.listen()

    @Event.privmsg
    def on_privmsg(self, sender, channel, message):
        if channel is None:
            # Message was sent in a private query.
            self.bot.privmsg(sender, "You said: " + message)
            return

        # Message was sent in a channel.
        self.bot.privmsg(channel, sender + " said: " + message)

    @Event.join
    async def on_join(self, sender, channel):
        if sender == self.nickname:
            # Don't do anything if this bot is the user who joined.
            return
        self.privmsg(channel, sender + " has joined " + channel)

        # This will execute a WHOIS request for `sender` and will
        # block until the request is complete. Since this is a
        # coroutine, the rest of the bot won't freeze up.

        result = await self.bot.whois(sender)
        if result.success:
            whois_reply = result.value
            server = whois_reply.server or "an unknown server"
            msg = sender + " is connected to " + server
            self.privmsg(channel, msg)


def main():
    mybot = MyBot()
    mybot.start()

if __name__ == "__main__":
    main()


# Example IRC log:
# [#mybot] --> mybot has joined #mybot
# [#mybot] --> user1234 has joined #mybot
# [#mybot] <mybot> user1234 has joined #mybot
# <a few seconds later...>
# [#mybot] <mybot> user1234 is connected to xyz.example.com
# [#mybot] <user1234> Test message
# [#mybot] <mybot> user1234 said: Test message

# In a private query:
# [query] <user1234> Test message
# [query] <mybot> You said: Test message
