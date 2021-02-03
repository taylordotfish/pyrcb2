# Copyright (C) 2015-2016, 2021 taylor.fish <contact@taylor.fish>
#
# This file is part of pyrcb2.
#
# pyrcb2 is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# As an additional permission under GNU GPL version 3 section 7, you may
# distribute non-source forms of comments (lines beginning with "#") and
# strings (text enclosed in quotation marks) in pyrcb2 source code without
# the copy of the GNU GPL normally required by section 4, provided you
# include a URL through which recipients can obtain a copy of the
# Corresponding Source and the GPL at no charge.
#
# pyrcb2 is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pyrcb2.  If not, see <http://www.gnu.org/licenses/>.

from .tests import BaseTest
from pyrcb2 import IStr, ISet, IDict, IDefaultDict
from pyrcb2.itypes import User, Sender
from functools import partial
import unittest


class TestItypes(BaseTest):
    def test_istr(self):
        self.assertEqual(IStr("TEST~"), "Test^")
        self.assertEqual("TEST~", IStr("Test^"))
        self.assertEqual(repr(IStr("Test")), "IStr(" + repr("Test") + ")")

        self.assertEqual(str(IStr("TEST~")), "TEST~")
        self.assertNotEqual(str(IStr("TEST~")), "Test^")
        self.assertEqual(IStr("Test^").lower(), "test^")
        self.assertEqual(IStr("Test^").upper(), "TEST~")

    def test_idict(self, cls=IDict):
        d = cls(test=20)
        d["Test^"] = 10
        d["TEST~"] += 5
        self.assertEqual(d["Test"], 20)
        self.assertEqual(d["TEST~"], 15)
        self.assertEqual(str(list(d.keys())[1]), "Test^")
        if cls is IDict:
            expected_repr = "IDict([(IStr('test'), 20), (IStr('Test^'), 15)])"
            self.assertEqual(repr(d), expected_repr)

    def test_idefaultdict(self):
        self.test_idict(cls=partial(IDefaultDict, None))
        with self.assertRaises(TypeError):
            IDefaultDict("test")
        d = IDefaultDict(int)
        self.assertEqual(d["test"], 0)
        self.assertEqual(d["test"], 0)
        expected_repr = "IDefaultDict(%r, [(IStr('test'), 0)])" % int
        self.assertEqual(repr(d), expected_repr)

    def test_idict_order(self, cls=IDict):
        d = cls([("q", 0), ("w", 0)], e=0)
        keys = "rtyuiopasdfghjklzxcvbnm"
        for key in keys:
            d[key] = 0
        self.assertEqual("".join(list(d.keys())), "qwe" + keys)

    def test_idefaultdict_order(self):
        self.test_idict_order(cls=partial(IDefaultDict, None))

    def test_idefaultdict_missing(self):
        d = IDefaultDict()
        with self.assertRaises(KeyError):
            d["test"]

    def test_idict_other_methods(self, cls=IDict):
        d = cls(test=10)
        self.assertIn("test", d)
        del d["TEST"]
        self.assertNotIn("test", d)

        d["test"] = 15
        self.assertEqual(d.get("TEST"), 15)
        self.assertEqual(d.get("abc"), None)

        self.assertEqual(d.pop("TEST"), 15)
        self.assertNotIn("test", d)

    def test_idefaultdict_other_methods(self):
        self.test_idict_other_methods(cls=partial(IDefaultDict, None))

    def test_iset(self):
        s = ISet(["test1"])
        s.add("Test2")
        s.add("TEST3")
        s -= {"test2"}
        self.assertTrue("TEST1" in s)
        self.assertTrue("test3" in s)
        self.assertFalse("test2" in s)
        self.assertFalse("test1" in s ^ {"Test1"})
        self.assertEqual(s, {"TEST1", "Test3"})

    def test_sender(self):
        nick = Sender("Test", username="user", hostname="host")
        self.assertEqual(nick, "TEST")
        self.assertEqual(nick.username, "user")
        self.assertEqual(nick.hostname, "host")
        self.assertNotEqual(nick.username, "User")
        self.assertNotEqual(nick.username, "Hser")

    def test_user(self):
        user = User("Test", prefixes="+&")
        self.assertEqual(user, "TEST")
        self.assertTrue(user.has_prefix("+"))
        self.assertTrue(user.has_prefix("&"))
        self.assertFalse(user.has_prefix("@"))
        user = User("Test", prefixes="@%")
        self.assertFalse(user.has_prefix("+"))
        self.assertCountEqual(user.prefixes, "@%")


def main():
    unittest.main()


if __name__ == "__main__":
    main()
