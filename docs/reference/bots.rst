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

Bots and events
===============

IRCBot
------

.. autoclass:: IRCBot

   All of the following methods and attributes are instance methods/attributes
   unless otherwise specified.

IRC commands
~~~~~~~~~~~~

.. automethod:: IRCBot.join
.. automethod:: IRCBot.part
.. automethod:: IRCBot.quit
.. automethod:: IRCBot.kick
.. automethod:: IRCBot.privmsg
.. automethod:: IRCBot.notice
.. automethod:: IRCBot.nick
.. automethod:: IRCBot.whois
.. automethod:: IRCBot.cap_req
.. automethod:: IRCBot.send_command

.. _ircbot-account-tracking:

Account tracking
~~~~~~~~~~~~~~~~

See :ref:`Event → Account tracking <event-account-tracking>` for related event
decorators.

.. autoattribute:: IRCBot.track_accounts
   :annotation: = False
.. autoattribute:: IRCBot.track_id_statuses
   :annotation: = False
.. autoattribute:: IRCBot.track_known_id_statuses
   :annotation: = False
.. automethod:: IRCBot.get_account
.. automethod:: IRCBot.get_accounts
.. automethod:: IRCBot.get_id_status
.. automethod:: IRCBot.get_id_statuses
.. automethod:: IRCBot.is_account_synced(nickname)
.. automethod:: IRCBot.is_id_status_synced(nickname)
.. autoattribute:: IRCBot.is_tracking_accounts
.. autoattribute:: IRCBot.is_tracking_known_accounts
.. autoattribute:: IRCBot.is_tracking_id_statuses
.. autoattribute:: IRCBot.is_tracking_known_id_statuses

Initialization
~~~~~~~~~~~~~~

.. automethod:: IRCBot.load_events
.. automethod:: IRCBot.connect
.. automethod:: IRCBot.register
.. automethod:: IRCBot.call_coroutine
.. automethod:: IRCBot.schedule_coroutine
.. automethod:: IRCBot.listen

Other methods
~~~~~~~~~~~~~

.. automethod:: IRCBot.any_event_handlers
.. automethod:: IRCBot.call(event_id, \*args, \*\*kwargs)
.. automethod:: IRCBot.wait_for
.. automethod:: IRCBot.wait_for_all
.. automethod:: IRCBot.close_connection
.. automethod:: IRCBot.ensure_future
.. automethod:: IRCBot.gather
.. automethod:: IRCBot.safe_message_length
.. automethod:: IRCBot.split_string

Attributes
~~~~~~~~~~

For attributes related to account tracking, see :ref:`ircbot-account-tracking`.

.. autoattribute:: IRCBot.nickname
.. autoattribute:: IRCBot.username
.. autoattribute:: IRCBot.hostname
.. autoattribute:: IRCBot.is_alive
.. autoattribute:: IRCBot.is_registered
.. autoattribute:: IRCBot.extensions
.. autoattribute:: IRCBot.isupport
.. autoattribute:: IRCBot.channels
.. autoattribute:: IRCBot.users

Options
^^^^^^^

These attributes control the bot's behavior and may be modified.

.. autoattribute:: IRCBot.default_timeout
   :annotation: = 120
.. autoattribute:: IRCBot.use_hostname_when_splitting
   :annotation: = True
.. autoattribute:: IRCBot.quit_on_exception
   :annotation: = True
.. autoattribute:: IRCBot.quit_on_exit
   :annotation: = True
.. autoattribute:: IRCBot.delay_messages
   :annotation: = True
.. autoattribute:: IRCBot.delay_multiplier
   :annotation: = 0.01
.. autoattribute:: IRCBot.max_delay
   :annotation: = 0.1
.. autoattribute:: IRCBot.consecutive_timeout
   :annotation: = 0.5
.. autoattribute:: IRCBot.delay_privmsgs
   :annotation: = True
.. autoattribute:: IRCBot.privmsg_delay_multiplier
   :annotation: = 0.1
.. autoattribute:: IRCBot.privmsg_max_delay
   :annotation: = 1.5
.. autoattribute:: IRCBot.privmsg_consecutive_timeout
   :annotation: = 5


Event
-----

.. class:: Event

   The following decorators are all static methods or class methods.

.. decorator:: Event.join

   Decorates functions with the signature::

      def function(sender, channel)

   Called when a user joins a channel.

   :param Sender sender: The user who joined the channel.
   :param IStr channel: The channel the user joined.

.. decorator:: Event.part

   Decorates functions with the signature::

      def function(sender, channel, message)

   Called when a user leaves a channel.

   :param Sender sender: The user who left the channel.
   :param IStr channel: The channel the user left.
   :param str message: The part message, if any, that the user used.

.. decorator:: Event.quit

   Decorates functions with the signature::

      def function(sender, message[, channels])

   Called when a user quits.

   :param Sender sender: The user who quit.
   :param str message: The quit message the user used.
   :param channels: The channels the user was in before quitting.
   :type channels: `list` of `IStr`

.. decorator:: Event.kick

   Decorates functions with the signature::

      def function(sender, channel, target, message)

   Called when a user is kicked from a channel.

   :param Sender sender: The user who kicked ``target``.
   :param IStr channel: The channel that ``target`` was kicked from.
   :param IStr target: The user who was kicked.
   :param str message: The kick message that ``sender`` used.

.. decorator:: Event.privmsg

   Decorates functions with the signature::

      def function(sender, channel, message[, is_query])

   Called when a ``PRIVMSG`` (a normal text message sent to a user or channel)
   is received.

   :param Sender sender: The user who sent the message.
   :param IStr channel: The channel, if any, that the message was sent to. If
     the message was sent in a private query, this will be ``None``.
   :param str message: The text of the message.
   :param bool is_query: Whether or not the message was sent in a private
     query. This is equivalent to ``channel is None``.

.. decorator:: Event.notice

   Decorates functions with the signature::

      def function(sender, channel, message[, is_query])

   Called when a ``NOTICE`` is received.

   :param Sender sender: The user who sent the notice.
   :param IStr channel: The channel, if any, that the notice was sent to. If
     the notice was sent in a private query, this will be ``None``.
   :param str message: The text of the notice.
   :param bool is_query: Whether or not the notice was sent in a private
     query. This is equivalent to ``channel is None``.

.. decorator:: Event.nick

   Decorates functions with the signature::

      def function(sender, nickname)

   Called when a user changes nicknames.

   To check if the bot is the user that changed nicknames, use
   ``nickname == bot.nickname``, not ``sender == bot.nickname``.

   :param Sender sender: The user who changed nicknames. This is the user's old
     nickname.
   :param IStr nickname: The user's new nickname.

.. decorator:: Event.whois

   Decorates functions with the signature::

      def function(nickname, whois_reply)

   Called when a WHOIS reply is received for a user.

   :param IStr nickname: The user that the WHOIS reply corresponds to.
   :param WhoisReply whois_reply: The WHOIS reply.

.. decorator:: Event.command(\*commands)

   Registers an event handler for a specified IRC command (or multiple
   commands).

   The decorated function will be called with a `Sender` object representing
   the user or server that sent the message, followed by arguments to the IRC
   command (but not including the command itself).

   For example, to handle messages of the form ``:sender XYZ arg1 arg2``, an
   appropriate event handler would have the signature::

      def on_xyz(sender, arg1, arg2)

   As with all event handlers, missing arguments that the function requires are
   set to ``None``, and extra arguments that the function doesn't accept are
   discarded. So the event handler above could also be written as
   ``def on_xyz(sender, arg1)`` or ``def on_xyz(sender, arg1, arg2, arg3)``
   and no errors would occur.

   **Note:** Only the ``sender`` parameter is a case-insensitive string (type
   `Sender`, a subclass of `IStr`). If there are any other parameters that
   represent nicknames, channels, or other case-insensitive values, you must
   cast them to IStr; either by manually calling `IStr` on each parameter, or
   by adding annotations::

      def on_xyz(sender, arg1: IStr, arg2)

   If a parameter is annotated with a `callable`, the callable will be called
   with the corresponding argument every time the event handler is called.

   In the event handler above, the parameter ``arg1`` will always be of type
   `IStr` (or ``None``), but ``arg2`` will remain a ``str``.

   **Decorator params:**

   :param commands: The command (or multiple commands) that the event handler
     should be called for. Commands should be of type `str`.

.. decorator:: Event.reply(\*names_or_codes)

   Like :meth:`Event.command`, but registers event handlers for numeric
   replies.

   **Decorator params:**

   :param names_or_codes: The name or code of the numeric reply (or multiple
     replies) that the event handler should be called for. These arguments can
     be the names of numeric replies (like "RPL_VERSION") or their
     corresponding codes (like "351").

.. decorator:: Event.any

   Decorates functions with the signature::

      def function(sender, command, *args)

   Called when any IRC message or command is received.

   Usually it is better to register event handlers for specific commands.

   :param Sender sender: The user who sent the message or command.
   :param IStr command: The command that was sent.
   :param args: Arguments to the command. Arguments are of type `str`.

.. _event-account-tracking:

Account tracking
~~~~~~~~~~~~~~~~

The following event decorators are related to account tracking.
See :ref:`IRCBot → Account tracking <ircbot-account-tracking>`.

.. decorator:: Event.account_known

   Decorates functions with the signature::

      def function(nickname, account[, old_account, was_known])

   Called when a user's account changes or becomes known (and is being
   tracked).

   :param IStr nickname: The nickname of the user.
   :param IStr account: The user's account.
   :param IStr old_account: The user's old account (``None`` if unknown).
   :param bool was_known: Whether or not the user's old account was known.
     Because accounts can be ``None`` even when known, this parameter is
     needed to resolve ambiguity when ``old_account`` is ``None``.

.. decorator:: Event.account_unknown

   Decorates functions with the signature::

      def function(nickname[, old_account])

   Called when a user's account becomes unknown (meaning the user's account can
   no longer be tracked).

   :param IStr nickname: The nickname of the user.
   :param IStr old_account: The user's old account.

.. decorator:: Event.id_status_known

   Decorates functions with the signature::

      def function(nickname, id_status[, old_id_status])

   Called when a user's ID status changes or becomes known (and is being
   tracked).

   :param IStr nickname: The nickname of the user.
   :param Status id_status: The user's ID status.
   :param Status old_id_status: The user's old ID status (``None`` if unknown).

.. decorator:: Event.id_status_unknown

   Decorates functions with the signature::

      def function(nickname[, old_id_status])

   Called when a user's ID status becomes unknown (meaning the user's ID status
   can no longer be tracked).

   :param IStr nickname: The nickname of the user.
   :param Status old_id_status: The user's old ID status.
