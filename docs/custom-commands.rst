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

Custom commands
===============

Sending
-------

Sending custom commands is straightforward---simply use `IRCBot.send_command`::

    bot.send_command("INVITE", "nickname", "#channel")

Waiting for responses
~~~~~~~~~~~~~~~~~~~~~

If you send a command that expects a response, you can asynchronously wait for
the response. If you want to do this, it's recommended to create a method that
sends the command and returns a coroutine that waits for the response.

Use :meth:`IRCBot.wait_for` to wait for the expected messages and possible
errors.

Let's create a method for ``INVITE`` commands::

    class MyBot:
        # Initialization code here...
        # self.bot is an IRCBot object.

        def invite(self, nickname, channel):
            future = self.bot.send_command("INVITE", nickname, channel)
            return self.wait_for(
                future,
                Reply("RPL_INVITING", nickname, channel),
                errors=[
                    Error("ERR_NOSUCHNICK", nickname, ANY),
                    Error("ERR_USERONCHANNEL", nickname, channel, ANY),
                    Error([
                        "ERR_USERONCHANNEL", "ERR_CHANOPRIVSNEEDED",
                    ], channel, ANY),
                ]
            )

:meth:`IRCBot.wait_for` returns an `OptionalCoroutine`, so the ``invite()``
method above can be called with or without being awaited.

**Note**: pyrcb2 automatically delays large volumes of messages to prevent
server throttling or disconnecting. :meth:`IRCBot.send_command` returns a
future that blocks until the message has actually been sent---*be sure to pass
this to* :meth:`IRCBot.wait_for` *so that timeouts are accurate*. The timeout
counter shouldn't start until the message has really been sent.

If you want to do some post-processing after the response is received (for
example, setting the ``value`` attribute of the `WaitResult` returned by
:meth:`IRCBot.wait_for`), you can put your asynchronous code in an inner
coroutine function and return it in an `OptionalCoroutine`::

    class MyBot:
        # Initialization code here...

        def invite(self, nickname, channel):
            future = self.bot.send_command("INVITE", nickname, channel)

            async def coroutine():
                # We can await `future` here instead of
                # passing it to wait_for().
                await future

                # Same as the call to wait_for() above, except
                # without the `future` argument.
                result = self.bot.wait_for(...)

                # Any post-processing can go here.
                # For example, setting the `value` attribute.
                if result.success:
                    result.value = {"invited_at": time.time()}
                return result

            # Return an optional coroutine.
            return OptionalCoroutine(coroutine)

If you're writing a method that should be called only asynchronously, you
can skip the inner function and simply make the method a coroutine::

    class MyBot:
        # Initialization code here...

        async def invite(self, nickname, channel):
            await self.bot.send_command("INVITE", nickname, channel)
            result = await self.bot.wait_for(...)
            # Can do post-processing here; no need
            # to use an inner function.
            return result

Handling
--------

To add an event handler for an arbitrary IRC command, use
:func:`@Event.command <Event.command>`::

    @Event.command("INVITE")
    def on_invite(sender, target: IStr, channel: IStr):
        # Code here...

(Remember to include the ``self`` parameter if your event handler is a method.)

When using :func:`@Event.command <Event.command>` (or :func:`@Event.reply
<Event.reply>`), it is important to note that only the first parameter
(``sender``) is a case-insensitive string---other parameters must be converted
to `IStr` if they represent channels, nicknames, or other case-insensitive
values. As explained in :func:`@Event.command <Event.command>`, you can either
convert parameters manually or use parameter annotations like the example
above.

You can use :func:`@Event.reply <Event.reply>` to handle numeric replies::

    @Event.reply("RPL_TOPIC")
    def on_rpl_topic(sender, target, channel, topic):
        # Code here...


.. _custom-events:

Custom events
~~~~~~~~~~~~~

You can also add custom events that you call manually with :meth:`IRCBot.call`.
To do this, subclass `Event` and do one of two things:

Set the class attribute ``events`` to a list of the events you want to add. An
event decorator will be added for each string in the list, with both its name
and the event ID it uses equal to the string. ::

    class Event(Event):
        events = ["self_invited"]

    class MyBot:
        # Initialization code here...
        # self.bot is an IRCBot object.

        @Event.self_invited
        def on_self_invited(self, sender, channel):
            print(sender, "has invited this bot to", channel)

        @Event.command("INVITE")
        async def on_invite(self, sender, target: IStr, channel: IStr):
            if target == self.bot.nickname:
                # Make sure `Event` is the subclass above.
                await self.bot.call(
                    Event, "self_invited", sender, channel,
                )

Or, to have control over the event ID your event decorator uses, use
:func:`@event_decorator <event_decorator>`. This also allows you to add
parameters to your decorator. ::

    class Event(Event):
        @event_decorator
        def user_invited(nickname):
            # Return an (event_class, event_id) tuple.
            return (Event, ("user_invited", nickname))

    class MyBot:
        # Initialization code here...
        # self.bot is an IRCBot object.

        @Event.user_invited("user1")
        def on_user1_invited(self, sender, channel):
            print(sender, "has invited user1 to", channel)

        @Event.user_invited("user2")
        def on_user2_invited(self, sender, channel):
            print(sender, "has invited user2 to", channel)

        @Event.command("INVITE")
        async def on_invite(self, sender, target: IStr, channel: IStr):
            # Make sure `Event` is the subclass above.
            await self.bot.call(
                Event, ("user_invited", target), sender, channel,
            )


Example
-------

Here is an example bot that sends and handles custom commands::

    class MyBot:
        def __init__(self):
            self.bot = IRCBot()
            self.bot.load_events(self)

        @Event.command("INVITE")
        def on_invite(self, sender, target: IStr, channel: IStr):
            print(sender, "has invited", target, "to", channel)

        @Event.privmsg
        def on_privmsg(self, sender, channel, message):
            if channel is None and message == "!invite":
                self.bot.send_command("INVITE", sender, "#channel")

        def start(self):
            self.bot.call_coroutine(self.start_async())

        async def start_async(self):
            await self.bot.connect("irc.example.com", 6667)
            await self.bot.register("mybot")
            self.bot.join("#channel")
            await self.bot.listen()

    mybot = MyBot()
    mybot.start()
