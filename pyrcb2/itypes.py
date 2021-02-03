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

from collections import OrderedDict

__all__ = ["IStr", "IDict", "IDefaultDict", "ISet", "Sender", "User"]


# Decorator to implement case-insensitive methods for IStr.
def istr_methods(cls):
    def get_method(name):
        def method(self, string, *args, **kwargs):
            if isinstance(string, str):
                string = IStr.make_lower(string)
            return getattr(self._lower, name)(string, *args, **kwargs)
        return method

    for name in ["index", "find", "count", "startswith", "endswith"]:
        setattr(cls, name, get_method(name))
    for name in ["lt", "le", "ne", "eq", "gt", "ge", "contains"]:
        name = "__{0}__".format(name)
        setattr(cls, name, get_method(name))
    return cls


# Decorator to implement case-insensitive methods for IDict.
def idict_methods(cls):
    def get_method(name):
        def method(self, key, *args, **kwargs):
            if not isinstance(key, IStr) and isinstance(key, str):
                key = IStr(key)
            return getattr(super(cls, self), name)(key, *args, **kwargs)
        return method

    for name in ["get", "pop"]:
        setattr(cls, name, get_method(name))
    for name in ["getitem", "setitem", "delitem", "contains"]:
        name = "__{0}__".format(name)
        setattr(cls, name, get_method(name))
    return cls


# Decorator to implement case-insensitive methods for ISet.
def iset_methods(cls):
    def get_item_method(name):
        def method(self, item, *args, **kwargs):
            if not isinstance(item, IStr) and isinstance(item, str):
                item = IStr(item)
            return getattr(super(cls, self), name)(item, *args, **kwargs)
        return method

    def get_operation_method(name):
        def method(self, set_, *args, **kwargs):
            if not isinstance(set_, ISet):
                set_ = ISet(set_)
            result = getattr(super(cls, self), name)(set_, *args, **kwargs)
            if isinstance(result, set) and not isinstance(result, ISet):
                result = ISet(result)
            return result
        return method

    operators = [
        "sub", "isub", "and", "iand", "le", "lt", "ge", "gt", "xor", "ixor",
        "or", "ior", "eq", "ne"]
    operation_methods = [
        "difference", "difference_update", "intersection",
        "intersection_update", "isdisjoint", "issubset", "issuperset",
        "symmetric_difference", "symmetric_difference_update", "union",
        "update"]
    for name in operators:
        name = "__{0}__".format(name)
        setattr(cls, name, get_operation_method(name))
    for name in operation_methods:
        setattr(cls, name, get_operation_method(name))
    for name in ["add", "discard", "remove", "__contains__"]:
        setattr(cls, name, get_item_method(name))
    return cls


@istr_methods
class IStr(str):
    r"""A case-insensitive string class based on `IRC case rules`_. (``{}|^``
    are lowercase equivalents of ``[]\~``.)

    Equality comparisons are case-insensitive, but the original string is
    preserved. `str` can be used to obtain a case-sensitive version of the
    string. For example::

        >>> IStr("STRing^") == "string^"
        True
        >>> IStr("STRing^") == "STRING~"
        True
        >>> str(IStr("STRing^")) == "STRING~"
        False

    Throughout pyrcb2, all parameters and attributes that represent nicknames
    or channels are of type `IStr`, so they can be tested for equality without
    worrying about case-sensitivity.

    Arguments are passed to and handled by `str`. This class behaves just like
    `str`, except for equality comparisons and methods which
    rely on equality comparisons, such as :meth:`str.index`.

    When used as keys in dictionaries, IStr objects will act like the lowercase
    version of the string they represent. If you want a case-insensitive
    dictionary, use `IDict`.

    .. _IRC case rules: https://tools.ietf.org/html/rfc2812#section-2.2
    """

    def __init__(self, *args, **kwargs):
        string = str(self)
        self._lower = self.make_lower(string)
        self._upper = self.make_upper(string)

    def __hash__(self):
        return hash(self._lower)

    def __repr__(self):
        name = type(self).__name__
        return "{0}({1})".format(name, super().__repr__())

    def lower(self):
        return self._lower

    def upper(self):
        return self._upper

    # Returns a lowercase version of a string, according to IRC case rules.
    @classmethod
    def make_lower(cls, string):
        lower = string.lower()
        for char, replacement in zip(r"[]\~", r"{}|^"):
            lower = lower.replace(char, replacement)
        return lower

    # Returns an uppercase version of a string, according to IRC case rules.
    @classmethod
    def make_upper(cls, string):
        upper = string.upper()
        for char, replacement in zip(r"{}|^", r"[]\~"):
            upper = upper.replace(char, replacement)
        return upper


@idict_methods
class IDict(OrderedDict):
    """A case-insensitive dictionary class based on `IRC case
    rules`_.

    Key equality is case-insensitive. Keys are converted to `IStr` upon
    assignment (as long as they are instances of `str`).

    This class is a subclass of `~collections.OrderedDict`, so keys
    are kept in the order they were added in.

    .. _IRC case rules: https://tools.ietf.org/html/rfc2812#section-2.2
    """


class IDefaultDict(IDict):
    """
    Bases: `IDict`

    Like `IDict`, but with the functionality of `~collections.defaultdict`.
    Keys are still ordered.
    """
    def __init__(self, default_factory=None, *args, **kwargs):
        factory_valid = (
            default_factory is None or hasattr(default_factory, "__call__"))
        if not factory_valid:
            raise TypeError("First argument must be callable or None.")
        super().__init__(*args, **kwargs)
        self.default_factory = default_factory

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        self[key] = self.default_factory()
        return self[key]

    def __repr__(self):
        start, end = super().__repr__().split("(", 1)
        format_str = "%s(%r%s" if end == ")" else "%s(%r, %s"
        return format_str % (start, self.default_factory, end)

    __str__ = __repr__


@iset_methods
class ISet(set):
    """A case-insensitive `set` class based on `IRC case rules`_.

    Item equality is case-insensitive. Items are converted to `IStr` during all
    operations. For example::

        >>> x = ISet(["TEST"])
        >>> x.add("another_test")
        >>> x
        ISet({IStr('TEST'), IStr('another_test')})
        >>> x - {"test"}
        ISet({IStr('another_test')})

    .. _IRC case rules: https://tools.ietf.org/html/rfc2812#section-2.2
    """
    def __init__(self, iterable=None):
        if iterable is not None:
            for item in iterable:
                self.add(item)


class Sender(IStr):
    """
    Bases: `IStr`

    A subclass of `IStr` that represents a nickname and also stores the
    associated user's username and hostname. This class behaves just like
    `IStr`; it simply has extra attributes.

    In events, nicknames are sometimes of this type (when the command
    originated from the associated user). See individual `Event` decorators for
    more information.

    It shouldn't be necessary to create objects of this type.
    """
    def __new__(cls, *args, username=None, hostname=None, **kwargs):
        return super().__new__(cls, *args, **kwargs)

    def __init__(self, *args, username=None, hostname=None, **kwargs):
        self._username = username
        self._hostname = hostname
        super().__init__(*args, **kwargs)

    @property
    def username(self):
        """The user's username.

        :type: `str`
        """
        return self._username

    @property
    def hostname(self):
        """The user's hostname.

        :type: `str`
        """
        return self._hostname


class User(IStr):
    """
    Bases: `IStr`

    A subclass of `IStr` that represents a nickname and also stores the
    associated user's prefixes in a certain channel. This class behaves just
    like `IStr`; it simply has extra attributes.

    Nicknames in `IRCBot.users` are of this type, so you can easily check if
    a user has a certain prefix. See `IRCBot.users` for more information.

    It shouldn't be necessary to create objects of this type.
    """
    def __new__(cls, *args, prefixes=None, **kwargs):
        return super().__new__(cls, *args, **kwargs)

    def __init__(self, *args, prefixes=None, **kwargs):
        self._prefixes = frozenset(prefixes or ())
        super().__init__(*args, **kwargs)

    @property
    def prefixes(self):
        """The user's prefixes.

        :type: `frozenset` of `str`
        """
        return self._prefixes

    def has_prefix(self, prefix):
        """Checks if the user has a certain prefix.

        :param str prefix: The prefix to check for (should be one character).
        :rtype: `bool`
        """
        return prefix in self._prefixes

    def replace(self, **kwargs):
        nickname = kwargs.pop("nickname", self)
        kwargs.setdefault("prefixes", self.prefixes)
        return type(self)(nickname, **kwargs)

    def add_prefix(self, prefix):
        prefixes = self.prefixes | set(prefix)
        return self.replace(prefixes=prefixes)

    def remove_prefix(self, prefix):
        prefixes = self.prefixes - set(prefix)
        return self.replace(prefixes=prefixes)
