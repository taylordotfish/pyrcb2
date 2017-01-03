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

Messages and results
====================

Message
-------

.. autoclass:: Message

   .. autoattribute:: sender
   .. autoattribute:: command
   .. autoattribute:: args


Reply
-----

.. autoclass:: Reply


Error
-----

.. class:: Error

   An alias to `Reply`.


Special message components
--------------------------

.. attribute:: ANY

   Used in message patterns to match any argument.

   For example, the following messages match::

       Message("abc", ANY, "xyz")  # Pattern
       Message("abc", "123", "xyz")  # From server

.. attribute:: ANY_ARGS

   Used in message patterns to match any number of following arguments.

   For example, the following messages match::

       Message("abc", "XYZ", ANY_ARGS)  # Pattern
       Message("abc", "XYZ", "1", "2", "3")  # From server

.. attribute:: SELF

   Used in message patterns to match the bot's nickname. This should be used
   instead of `IRCBot.nickname`, because the bot's nickname could change
   while waiting for messages.

   This will work::

       bot.nick("new_nickname")
       bot.send_command("JOIN", "#channel")
       await bot.wait_for(Message(SELF, "JOIN", "#channel"))

   But this won't::

       bot.nick("new_nickname")
       bot.send_command("JOIN", "#channel")
       await bot.wait_for(Message(bot.nickname, "JOIN", "#channel"))


WaitResult
----------

.. autoclass:: WaitResult

   .. autoattribute:: success
   .. autoattribute:: value
   .. autoattribute:: error
   .. autoattribute:: error_cause
   .. autoattribute:: messages
   .. automethod:: to_exception


MultiWaitResult
---------------

.. autoclass:: MultiWaitResult

   .. autoattribute:: children


WaitError
---------

.. autoclass:: WaitError

   .. autoattribute:: result


WhoisReply
----------

.. autoclass:: WhoisReply

   .. attribute:: nickname

      :type: `Sender`

   .. attribute:: username
      :annotation: = None

      :type: `str`

   .. attribute:: hostname
      :annotation: = None

      :type: `str`

   .. attribute:: realname
      :annotation: = None

      :type: `str`

   .. attribute:: server
      :annotation: = None

      :type: `str`

   .. attribute:: server_info
      :annotation: = None

      :type: `str`

   .. attribute:: username
      :annotation: = None

      :type: `str`

   .. attribute:: is_irc_op
      :annotation: = False

      :type: `bool`

   .. attribute:: time_idle
      :annotation: = None

      :type: `int`

   .. attribute:: channels
      :annotation: = []

      :type: `list` of `IStr`

   .. attribute:: raw_channels
      :annotation: = []

      The list of channels returned in a WHOIS reply includes the prefixes
      the user has in each channel. This attribute contains the raw channels
      without prefixes stripped.

      For example, if a user were an operator in #chan1 and voiced in #chan2,
      this attribute might be ``["@#chan1", "+#chan2"]``.

      :type: `list` of `str`

   .. attribute:: is_away
      :annotation: = False

      :type: `bool`

   .. attribute:: away_message
      :annotation: = None

      :type: `str`

   .. attribute:: account
      :annotation: = None

      :type: `str`

   .. attribute:: messages

      A list of all messages that compose the WHOIS reply.

      :type: `list` of `Message`


Status
------

.. autoclass:: Status
   :show-inheritance:

   The following attributes are all class attributes.

   .. attribute:: no_account
      :annotation: = 0

      Returned when the given nickname is not registered, or when there
      is no user online with that nickname.

      :type: `~enum.IntEnum`

   .. attribute:: unrecognized
      :annotation: = 1

      Returned when the nickname is registered, but the user using it is not
      identified.

      :type: `~enum.IntEnum`

   .. attribute:: recognized
      :annotation: = 2

      Returned when the nickname is registered and the user is recognized,
      but not identified. Many implementations of NickServ use this status
      code. For example, see Atheme's documentation for `ACC`_ and `ACCESS`_.

      .. _ACC: https://github.com/atheme/atheme/wiki/NickServ%3AACC
      .. _ACCESS: https://github.com/atheme/atheme/wiki/NickServ%3AACCESS

      :type: `~enum.IntEnum`

   .. attribute:: logged_in
      :annotation: = 3

      Returned when the nickname is registered and the user using it is
      identified.

      :type: `~enum.IntEnum`
