# -*- coding: utf-8 -*-
# Modified from <https://github.com/sphinx-doc/sphinx/pull/1826>.
# Copyright 2007-2015 by the Sphinx team, see ../sphinx-license/AUTHORS.
# License: FreeBSD (2-clause), see ../sphinx-license/LICENSE for details.

from sphinx import addnodes
from sphinx.domains.python import PyModulelevel, PyClassmember
from sphinx.ext.autodoc import (
    FunctionDocumenter as _FunctionDocumenter,
    MethodDocumenter as _MethodDocumenter)
from asyncio import iscoroutinefunction


class FunctionDocumenter(_FunctionDocumenter):
    """
    Specialized Documenter subclass for functions and coroutines.
    """

    def import_object(self):
        ret = _FunctionDocumenter.import_object(self)
        if not ret:
            return ret

        obj = self.parent.__dict__.get(self.object_name)
        if iscoroutinefunction(obj):
            self.directivetype = 'coroutine'
            self.member_order = _FunctionDocumenter.member_order + 2
        return ret


class MethodDocumenter(_MethodDocumenter):
    """
    Specialized Documenter subclass for methods and coroutines.
    """

    def import_object(self):
        ret = _MethodDocumenter.import_object(self)
        if not ret:
            return ret

        obj = self.parent.__dict__.get(self.object_name)
        if iscoroutinefunction(obj):
            self.directivetype = 'coroutinemethod'
            self.member_order = _MethodDocumenter.member_order + 2
        return ret


class PyCoroutineMixin(object):
    def handle_signature(self, sig, signode):
        ret = super(PyCoroutineMixin, self).handle_signature(sig, signode)
        signode.insert(0, addnodes.desc_annotation('coroutine ', 'coroutine '))
        return ret


class PyCoroutineFunction(PyCoroutineMixin, PyModulelevel):
    def run(self):
        self.name = 'py:function'
        return PyModulelevel.run(self)


class PyCoroutineMethod(PyCoroutineMixin, PyClassmember):
    def run(self):
        self.name = 'py:method'
        return PyClassmember.run(self)


def setup(app):
    app.add_directive_to_domain('py', 'coroutine', PyCoroutineFunction)
    app.add_directive_to_domain('py', 'coroutinemethod', PyCoroutineMethod)

    app.add_autodocumenter(FunctionDocumenter)
    app.add_autodocumenter(MethodDocumenter)
