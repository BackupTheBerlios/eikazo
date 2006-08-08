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

collect information about plugins

"""

import sane

def scannerinfo(devicename):
    devs = sane.get_devices()
    for dev in devs:
        if dev[0] == devicename:
            vendor = dev[1]
            model = dev[2]
            for info in infos:
                res = info.options(devicename)
                if res != None:
                    return res
            return {}
    return {}