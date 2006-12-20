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

adds some features to class sane.SaneDev from PIL's Sane module that make
debugging and development easier. A challenge for the development of a Sane 
frontend is that it is very difficult to predict all possible "weirdnesses" 
of a backend. For example, some backends do not provide options to set
the scan window. If the device supported by such a backend is not available,
it is hard to predict all possible error raised by attempts to access
a non-existing option.
"""

from sane import *
import _sane, os

    
test = os.getenv("SANE_DISABLE_OPTIONS")
if test:
    disabled_options = test.split(',')
else:
    disabled_options = []


_origSaneDev = SaneDev
class SaneDev(_origSaneDev):
    def __load_option_dict(self):
        global disabled_options
        d = self.__dict__
        d['opt'] =  {}
        optlist = d['dev'].get_options()
        for t in optlist:
            o = Option(t, self)
            if o.type != TYPE_GROUP and not o.py_name in disabled_options:
                d['opt'][o.py_name] = o
    
    def __setattr__(self, key, value):
        global disabled_options
        if not key in disabled_options:
            _origSaneDev.__setattr__(self, key, value)
        else:
            # this does not correspond to the normal behaviour of
            # SaneDev, but it does not make sense to 
            raise AttributeError, "Option disabled for debugging: " + key
    
    def __getattr__(self, key):
        global disabled_options
        if not key in disabled_options:
            return _origSaneDev.__getattr__(self, key)
        else:
            raise AttributeError, 'No such attribute: ' + key
    
    def get_options(self):
        res = _origSaneDev.get_options(self)
        return [x for x in res if not x[1].replace('-', '_') in disabled_options]
        

def open(devname):
    return SaneDev(devname)
    