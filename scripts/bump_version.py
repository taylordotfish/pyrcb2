#!/usr/bin/env python3
# Copyright (C) 2016 taylor.fish <contact@taylor.fish>
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

import os
import re
import sys

USAGE = "Usage: bump_version.py <version> [--dev]"
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
ROOT_DIR = os.path.join(SCRIPT_DIR, "..")


def read_lines(rel_path):
    abs_path = os.path.join(ROOT_DIR, rel_path)
    with open(abs_path, encoding="utf8") as f:
        return f.read().splitlines()


def write_lines(rel_path, lines):
    abs_path = os.path.join(ROOT_DIR, rel_path)
    with open(abs_path, "w", encoding="utf8") as f:
        for line in lines:
            print(line, file=f)


def update_readme(version, short_version, dev):
    version_lines = [] if dev else ["", "Version %s" % version]
    version_desc_lines = [
        "This branch contains the development version of pyrcb2.",
        "See the ``stable`` branch for the latest stable release.",
    ] if dev else [
        "This branch contains pyrcb2 version **%s**." % version,
        "See the `changelog`_ for information about this version.", "",

        ".. _changelog: https://taylor.fish/pyrcb2"
        "/release-notes/{0}.html".format(short_version),
    ]

    lines = read_lines("README.rst")
    if lines[3].startswith("Version "):
        del lines[2:4]

    for i, line in enumerate(lines):
        if line.startswith("This branch contains the development "):
            del lines[i:i+2]
            break
        if line.startswith("This branch contains pyrcb2 version "):
            del lines[i:i+4]
            break
    desc_index = i

    write_lines(
        "README.rst", lines[:2] + version_lines + lines[2:desc_index] +
        version_desc_lines + lines[desc_index:]
    )


def update_setup(version, short_version, dev):
    lines = read_lines("setup.py")
    for i, line in enumerate(lines):
        if line.startswith("    version="):
            lines[i] = '    version="%s",' % version
    write_lines("setup.py", lines)


def update_docs_conf(version, short_version, dev):
    lines = read_lines("docs/conf.py")
    for i, line in enumerate(lines):
        if line.startswith("version = "):
            lines[i] = "version = '%s'" % short_version
        elif line.startswith("release = "):
            lines[i] = "release = '%s'" % version
    write_lines("docs/conf.py", lines)


def update_docs_index(version, short_version, dev):
    source_link = "`<https://github.com/taylordotfish/pyrcb2/%s>`_."
    source_link %= ("" if dev else "tree/[version]/")
    version_desc_lines = [
        "This documentation is for the development version of pyrcb2.",
    ] if dev else [
        "This documentation is for pyrcb2 version **%s**." % version,
        "See the :doc:`changelog <release-notes/%s>`" % short_version,
        "for information about this version.",
    ]

    lines = read_lines("docs/index.rst")
    for i, line in enumerate(lines):
        if line.startswith("Version "):
            lines[i] = "Version %s" % version
        if line.startswith("Source code for pyrcb2 and this "):
            lines[i+1] = source_link

    for i, line in enumerate(lines):
        if line.startswith("This documentation is for the development "):
            del lines[i]
            break
        if line.startswith("This documentation is for pyrcb2 version "):
            del lines[i:i+3]
            break
    desc_index = i

    for i, line in enumerate(lines):
        lines[i] = re.sub(
            r"(/pyrcb2/(?:tree|blob)/).*?/",
            r"\g<1>%s/" % ("master" if dev else version), line,
        )

    write_lines(
        "docs/index.rst", lines[:desc_index] + version_desc_lines +
        lines[desc_index:],
    )


def update_getting_started(version, short_version, dev):
    lines = read_lines("docs/getting-started.rst")
    for i, line in enumerate(lines):
        lines[i] = re.sub(
            r"(/pyrcb2/(?:tree|blob)/).*?/",
            r"\g<1>%s/" % ("master" if dev else version), line,
        )
    write_lines("docs/getting-started.rst", lines)


def update_source_init(version, short_version, dev):
    lines = read_lines("pyrcb2/__init__.py")
    for i, line in enumerate(lines):
        if line.startswith("__version__ = "):
            lines[i] = '__version__ = "%s"' % version
    write_lines("pyrcb2/__init__.py", lines)


def invalid_args():
    print(USAGE, file=sys.stderr)
    return 1


def main(argv):
    if not (2 <= len(argv) <= 3):
        return invalid_args()
    if len(argv) > 2 and argv[2] != "--dev":
        return invalid_args()

    version = argv[1]
    dev = len(argv) > 2
    if dev and "-dev" not in version:
        print("Warning: Dev version doesn't contain '-dev'.", file=sys.stderr)
    if not dev and '-dev' in version:
        print("Warning: Regular version contains '-dev'.", file=sys.stderr)
    match = re.match(r"(\d+\.\d+)", version)
    short_version = match.group(0) if match else version

    update_readme(version, short_version, dev)
    update_setup(version, short_version, dev)
    update_docs_conf(version, short_version, dev)
    update_docs_index(version, short_version, dev)
    update_getting_started(version, short_version, dev)
    update_source_init(version, short_version, dev)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
