"""
Copyright (c) Abel Deuring 2006 <adeuring@gmx.net>

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""
import os, procinfo

procinfo.infos = []


def keep(name):
    if name.rfind(".py") != len(name) - 3:
        return False
    for test in ["__init__.py", "procinfo.py"]:
        if name.find(test) == 0:
            return False
    return True

files = os.listdir(os.path.join(os.path.dirname(__file__)))

files = [x for x in files if keep(x)]


for name in files:
    name = name[:-3]
    exec("import %s" % name)
    try:
        exec("classes = %s.register()" % name)
        procinfo.infos += classes
    except AttributeError, v:
        if str(v)=="'module' object has no attribute 'register'":
            print "warning: file %s.py has no function register" % name
        else:
            raise

# the order of the filters is of course important; we must
# sort them to achieve a reasonable order. Each filter provides
# a class attribute sortpos, a 3-tuple of number. The first two
# numbers represent the input image format, and the output
# format. the last number represents the sort order for filters
# with the same input and output formats.
# The sort order is RGB first, then gray scale,  last bi-level.
#
# FIXME this leads easily to conflicts, if a 3rd-level number is used
# twice! Think about a better way to "arrange" the filters

procinfo.infos.sort(lambda x,y: cmp(x.sortpos, y.sortpos))
