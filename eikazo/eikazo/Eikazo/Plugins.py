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

collects information about installed plugins

"""

pluginlist = []

class Plugin:
    """ Each plugin should instatiate this class once
    """
    def __init__(self, name, details, type_, error):
        """ name: the name of the plugin
            details: possible details about the plugin. May be empty.
            type_: name of the "plugin class". At present defined:
                   'device', 'postprocessing', 'output', 'other'
            error: None, if the plugin works; or a string with an error
                   decription, if the plugin is broken, for example,
                   because a Python library is missing
        """
        pluginlist.append(self)
        self.name = name
        self.details = details
        self.type = type_
        self.error = error
    
    def __str__(self):
        """ return name and type of the plugin; add the error if not None
        """
        res = 'Plugin name: %s\nType: %s' % (self.name, self.type)
        if self.details:
            res = '%s\n%s' % (res, self.details)
        if self.error:
            res = '%s\nERROR: %s' % (res, self.error)
        return res


def plugininfo():
    """ return infoamtion about all installed pulgins as a string
    """
    res = pluginlist[:]
    res.sort(lambda x,y: cmp(x.type + x.name, y.type + y.name))
    res = [str(x) for x in res]
    res = '\n\n'.join(res)
    return res
    