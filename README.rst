pyrcb2
======

Version 0.2.0

**pyrcb2** is an `asyncio`_-based library for writing IRC bots. It is designed
to be easy to use, customizable, and high-level.

pyrcb2 includes features such as account tracking, user prefix tracking (voice,
op, etc.), messaging delaying to prevent throttling, and long message
splitting.

pyrcb2 also makes use of `asyncio`_ and coroutines in Python. This allows you
to write asynchronous code in a linear fashion—you can handle responses to
commands right after you send them.

.. code:: python

   # Wait until the bot has joined #channel.
   await bot.join("#channel")
   print("There are", len(bot.users["#channel"]), "users in #channel.")

   # Get user1's account.
   result = await bot.get_account("user1")
   if result.success:
       account = result.value or "(no account)"
       print("user1 is logged in as", account)

.. _asyncio: https://docs.python.org/3/library/asyncio.html


Installation
------------

Install with pip::

    $ pip3 install pyrcb2

Or clone and install with ``setup.py``::

    $ ./setup.py install

Alternatively, you can clone and install with pip::

    $ pip3 install .

You will need to run the commands above as root if you're installing globally.
You can use the ``--user`` option to install to your home directory instead.


Documentation
-------------

Documentation for pyrcb2 is available at `https://pythonhosted.org/pyrcb2/`__.
If you're new to pyrcb2, start with `this guide`_ and take a look at the
`examples <examples/>`_.

__ https://pythonhosted.org/pyrcb2/
.. _this guide: https://pythonhosted.org/pyrcb2/getting-started.html

This branch contains pyrcb2 version **0.2.0**.
See the `changelog`_ for information about this version.

.. _changelog: https://pythonhosted.org/pyrcb2/release-notes/0.2.html


Tests
-----

To run pyrcb2's tests, run ``python3 -m tests``. If you have `coverage`_
installed, you can run ``coverage run -m tests.__main__`` to get information
on test coverage.

.. _coverage: https://pypi.python.org/pypi/coverage/


License
-------

pyrcb2 is licensed under the GNU Lesser General Public License, version 3 or
later. Some parts are released under other licenses; see the `full license
notice <LICENSE>`_ and individual files for details.
