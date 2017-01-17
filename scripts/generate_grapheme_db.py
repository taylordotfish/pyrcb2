#!/usr/bin/env python3
# Copyright (C) 2017 taylor.fish <contact@taylor.fish>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# This file contains data originally from the Unicode Character Database,
# which is covered by the following copyright and license notice:
# © 2016 Unicode®, Inc.
# Licensed under the Unicode Inc. License Agreement for Data Files and
# Software, available at <http://www.unicode.org/copyright.html>.

from collections import OrderedDict
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
INPUT = os.path.join(SCRIPT_DIR, "..", "misc", "GraphemeBreakProperty.txt")
OUTPUT = os.path.join(SCRIPT_DIR, "..", "pyrcb2", "grapheme_break_db.py")


BREAK_VALUES = [
	"Other", "CR", "LF", "Control", "Extend", "Prepend", "SpacingMark", "L",
	"V", "T", "LV", "LVT", "Regional_Indicator", "E_Base", "E_Modifier", "ZWJ",
	"Glue_After_Zwj", "E_Base_GAZ",
]

BREAK_MAP = dict(zip(BREAK_VALUES, range(len(BREAK_VALUES))))

# From http://www.unicode.org/Public/9.0.0/ucd/auxiliary/GraphemeBreakTest.html
BREAK_TABLE = [
    [0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    [1, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1, 1, 0, 0, 0, 1, 0, 0],
    [0, 0, 0, 0, 1, 0, 1, 0, 1, 1, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 0, 0, 1, 0, 1, 0, 1, 1, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0],
    [0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0],
    [0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1],
    [0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
    [0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0],
]

OUTPUT_HEADER = """\
# This file contains data originally from the Unicode Character Database,
# which is covered by the following copyright and license notice:
{}
# Licensed under the Unicode Inc. License Agreement for Data Files and
# Software, available at <http://www.unicode.org/copyright.html>.
"""


def main():
    code_point_break_map = OrderedDict()
    copyright_line = "# © 2016 Unicode®, Inc."
    with open(INPUT) as f:
        for line in f:
            if line.startswith("# ©"):
                copyright_line = line.rstrip()
                continue
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            range_, break_val = map(str.strip, line.split(";", 1))
            if break_val not in BREAK_VALUES:
                print("Unknown break value found:", break_val, file=sys.stderr)
                continue
            start, end, *_ = [int(s, 16) for s in range_.split("..")] + [None]
            end = start if end is None else end
            for i in range(start, end + 1):
                code_point_break_map[i] = BREAK_MAP[break_val]

    with open(OUTPUT, "w") as f:
        print(OUTPUT_HEADER.format(copyright_line), file=f)
        print("break_table = [", file=f)
        for row in BREAK_TABLE:
            print("    {!r},".format(row), file=f)
        print("]\n", file=f)

        print("code_point_break_map = {", file=f)
        line = "   "
        for code_point, value in code_point_break_map.items():
            code = " {!r}: {!r},".format(code_point, value)
            if len(line) + len(code) >= 80:
                print(line, file=f)
                line = "   "
            line += code
        print(line, file=f)
        print("}", file=f)

if __name__ == "__main__":
    main()
