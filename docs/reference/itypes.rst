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

Case-insensitive types
======================

IStr
----

.. autoclass:: IStr()
   :show-inheritance:


IDict
-----

.. autoclass:: IDict
   :show-inheritance:


IDefaultDict
------------

.. autoclass:: IDefaultDict

   .. attribute:: default_factory

      The same as `defaultdict.default_factory
      <collections.defaultdict.default_factory>`: the function used to provide
      default values for missing keys.


ISet
----

.. autoclass:: ISet
   :show-inheritance:


User
----

.. autoclass:: User(\*args, prefixes=None, \*\*kwargs)

   .. automethod:: has_prefix
   .. autoattribute:: prefixes


Sender
------

.. autoclass:: Sender(\*args, username=None, hostname=None, \*\*kwargs)

   .. autoattribute:: username
   .. autoattribute:: hostname
