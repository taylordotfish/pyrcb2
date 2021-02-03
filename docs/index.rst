.. Copyright (C) 2016-2017, 2021 taylor.fish <contact@taylor.fish>

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

pyrcb2
======

Version 0.6.1-dev

**pyrcb2** is an `asyncio`-based library for writing IRC bots. It is designed
to be easy to use, customizable, and high-level.

pyrcb2 includes features such as account tracking, user prefix tracking (voice,
op, etc.), messaging delaying to prevent throttling, and long message
splitting.

pyrcb2 also makes use of `asyncio` and coroutines in Python. This allows you to
write asynchronous code in a linear fashion---you can handle responses to
commands right after you send them. ::

    # Wait until the bot has joined #channel.
    await bot.join("#channel")
    print("There are", len(bot.users["#channel"]), "users in #channel.")

    # Get user1's account.
    result = await bot.get_account("user1")
    if result.success:
        account = result.value or "(no account)"
        print("user1 is logged in as", account)

If you're new to pyrcb2, read :doc:`getting-started` and take a look at the
`examples`_.

This documentation is for the development version of pyrcb2.

Source code for pyrcb2 and this documentation is available at
`<https://github.com/taylordotfish/pyrcb2/>`_.

.. _examples: https://github.com/taylordotfish/pyrcb2/tree/master/examples/


.. toctree::
   :hidden:

   reference/index
   installation
   getting-started
   custom-commands
   release-notes/index
   Source code <https://github.com/taylordotfish/pyrcb2/tree/master/>
   Examples <https://github.com/taylordotfish/pyrcb2/tree/master/examples/>
   License <https://github.com/taylordotfish/pyrcb2/blob/master/LICENSE>
