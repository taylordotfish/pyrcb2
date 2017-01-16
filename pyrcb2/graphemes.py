# Copyright (C) 2017 taylor.fish <contact@taylor.fish>
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

from . import grapheme_break_db as db


def graphemes(string):
    grapheme = ""
    prev_break_value = None
    for i, char in enumerate(string):
        code_point = ord(char)
        break_value = db.code_point_break_map.get(code_point, 0)
        if i > 0 and db.break_table[prev_break_value][break_value] == 0:
            yield grapheme
            grapheme = ""
        grapheme += char
        prev_break_value = break_value
    yield grapheme
