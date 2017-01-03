.. Copyright (C) 2016 taylor.fish <contact@taylor.fish>

.. This file is part of pyrcb2-docs, documentation for pyrcb2.

.. pyrcb2-docs is licensed under the GNU Lesser General Public License
   as published by the Free Software Foundation, either version 3 of
   the License, or (at your option) any later version.

.. As an additional permission under GNU GPL version 3 section 7, you
   may distribute non-source forms of pyrcb2-docs without the copy of
   the GNU GPL normally required by section 4, provided you include a
   URL through which recipients can obtain a copy of the Corresponding
   Source and the GPL at no charge.

.. pyrcb2-docs is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU Lesser General Public License for more details.

.. You should have received a copy of the GNU Lesser General Public License
   along with pyrcb2-docs.  If not, see <http://www.gnu.org/licenses/>.

.. currentmodule:: pyrcb2

Getting started
===============

.. note::

   Throughout pyrcb2, all parameters and attributes that represent nicknames
   or channels are case-insensitive strings (type `IStr`)---equality
   comparisons with those parameters and attributes are case-insensitive.

Begin by importing `IRCBot` and `Event` from ``pyrcb2``::

    from pyrcb2 import IRCBot, Event

Then we'll create our bot class, called ``MyBot``::

    class MyBot:
        def __init__(self):
            self.bot = IRCBot(log_communication=True)
            self.bot.load_events(self)

``MyBot`` objects will create an `IRCBot` object when initialized and store it
in ``self.bot``. ``log_communication=True`` will cause communication with the
server to be logged to standard output (often useful when debugging).

``self.bot.load_events(self)`` loads events that are part of the current
``MyBot`` object. We'll add some events later.

There are a number of ways to start a bot, but this is preferred way, because
it allows all bot initialization code to be run asynchronously::

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

``MyBot.start()`` is the actual method we'll call to start the bot. It simply
runs ``MyBot.start_async()`` on the asyncio event loop and blocks until it
completes.

In place of the "More code here" comment in ``start_async()``, we could call
methods like ``self.bot.join("#mybot")`` if we wanted the bot to do something
right after starting up.

Next, let's add an event to our bot. Events are methods decorated with
`Event` decorators. To add an event that gets called every time a message
(``PRIVMSG``) is received, we could add the following method to ``MyBot``::

    @Event.privmsg
    def on_privmsg(self, sender, channel, message):
        if channel is None:
            # Message was sent in a private query.
            self.bot.privmsg(sender, "You said: " + message)
            return

        # Message was sent in a channel.
        self.bot.privmsg(channel, sender + " said: " + message)


Event handlers can also be coroutines, allowing you to write asynchronous code.
Let's add an asynchronous event handler for ``JOIN`` messages::

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

When someone joins a channel, our bot will perform a WHOIS query on them. We
could have written ``self.bot.whois(sender)`` without the ``await``, but
using ``await`` allows us to wait for the WHOIS response before continuing.
Otherwise, we would need to add an `Event.whois` event handler, which would
split up our code and introduce problems keeping state.

Our main function is simple; it simply creates a ``MyBot`` object and starts
it::

    def main():
        mybot = MyBot()
        mybot.start()

    if __name__ == "__main__":
        main()

Our finished bot now looks like this::

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

If we run our bot, it will work like this in channels:

.. code-block:: none

   [#mybot] --> mybot has joined #mybot
   [#mybot] --> user1234 has joined #mybot
   [#mybot] <mybot> user1234 has joined #mybot
   <a few seconds later...>
   [#mybot] <mybot> user1234 is connected to xyz.example.com
   [#mybot] <user1234> Test message
   [#mybot] <mybot> user1234 said: Test message

And it will work like this in private queries:

.. code-block:: none

   [query] <user1234> Test message
   [query] <mybot> You said: Test message

.. seealso::

   :doc:`reference/index`
      Complete API documentation for pyrcb2.

   :doc:`custom-commands`
      An introduction to sending and handling custom commands.

   `Examples`__
      Example pyrcb2 bots.

   `examples/skeleton.py`__
      A basic template for pyrcb2 bots.

   `examples/example.py`__
      The finished bot created above.

__ https://github.com/taylordotfish/pyrcb2/tree/0.2.0/examples/
__ https://github.com/taylordotfish/pyrcb2/blob/0.2.0/examples/skeleton.py
__ https://github.com/taylordotfish/pyrcb2/blob/0.2.0/examples/example.py
