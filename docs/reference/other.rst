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

Other classes and functions
===========================

OptionalCoroutine
-----------------

.. autoclass:: OptionalCoroutine(func, \*args, \*\*kwargs)


Decorators
----------

.. decorator:: event_decorator(returns_multiple=False)

   Creates an event decorator. This should be used in subclasses of `Event`::

       class Event(Event):
           @event_decorator
           def user_joined(nickname):
               # Return (event_class, event_id).
               return (Event, ("user_joined", nickname))

       class MyBot:
           # Initialization code here...
           # self.bot is an IRCBot object.

           @Event.user_joined("user1")
           def on_user1_joined(self, channel):
               print("user1 joined channel", channel)

           @Event.join
           async def on_join(self, sender, channel):
               # Make sure `Event` is the subclass above.
               await self.bot.call(
                   Event, ("user_joined", sender), channel,
               )

   Event decorators may take arguments, but do not have to. When no arguments
   are required, event decorators may be used with parentheses
   (``@decorator()``) or without (``@decorator``).

   An event decorator should return an *(event_class, event_id)* tuple. The
   event ID can be any hashable value. You can then call :meth:`IRCBot.call`
   with the event ID and the class the decorator was defined in (or a subclass
   of that class).

   .. seealso::

      :ref:`Custom commands → Custom events <custom-events>`
         For more information on adding event decorators.

   This decorator can be called with parentheses
   (``@event_decorator(returns_multiple=True)``) or without
   (``@event_decorator``).

   :param bool returns_multiple: Whether or not the event decorator returns
     multiple event IDs. If true, the event decorator should return a sequence
     of *(event_class, event_id)* tuples rather than a single one.


.. decorator:: cast_args

   Adds automatic argument type casting based on parameter annotations to the
   decorated function.

   If any parameter in the decorated function is annotated with a `callable`,
   the callable will be called with the corresponding argument every time the
   function is called. ::

       >>> @cast_args
       ... def function(arg1, arg2: str, arg3: int):
       ...     print(*map(repr, [arg1, arg2, arg3]), sep=", ")
       ...
       >>> function(1, 2, 3)
       1, '2', 3
       >>> function("1", "2", "3")
       '1', '2', 3

   `Event` decorators apply this decorator automatically::

        @Event.command("INVITE")
        def on_invite(sender, target: IStr, channel: IStr):
            print(sender, "has invited", target, "to", channel)

   When an ``INVITE`` message is received and ``on_invite()`` is called,
   ``target`` and ``channel`` will both be converted to `IStr` first.
