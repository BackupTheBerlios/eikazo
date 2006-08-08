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

configuration.

Based on SafeConfigParser from the standard Python library,
which provides ervices for config files similar to Windows .ini
files. Quite simple, but good enough for this package

section names:

[device]
    status information for/from the Sane backends:
    Chosen resolution, scan size etc
[eikazo]
    information for/from Eikazo
[device-<someName>]
    information for/from device plugins.
"""

import ConfigParser

class SaneConfigError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return self.value

class SaneConfig:
    def __init__(self, filenames=None):
        """ filenames: optional list of files that may be
            searched for inital cconfiguration values. See
            RawConfigParser.read() for details
        """
        self.parser = ConfigParser.SafeConfigParser()
        # list of ConfigAware instances
        # FIXME: since the config objects keep a reference to this
        # class, we have circular references. Not that much
        # of a problem, as long as the SaneMainWindow instance
        # lives as long as the program, but we will need a
        # method to break the reference circle, if SaneMainWindow
        # is destroyed and rebuild during a program run, or if
        # a class from Widgets.py are used elsewhere
        self.elements = []
        self.currentFile = None
        if filenames:
            self.parser.read(filenames)

    def register(self, ca):
        """ ca: a configAware instance. 
        """
        if not ca in self.elements:
            self.elements.append(ca)
    
    def loadConfig(self, filename):
        # load a config file. FIXME: should we use a new parser object??
        f = open(filename) # FIXME: check for errors
        self.currentFile = filename
        self.parser.readfp(f, filename)
        f.close()
        for ca in self.elements:
            ca.readConfig()

    def saveConfig(self, filename):
        # load a config file
        for ca in self.elements:
            ca.writeConfig()
        f = open(filename, 'w') # FIXME: check for errors
        self.parser.write(f)
        f.close()
        self.currentFile = filename
    
    def set(self, section, option, value):
        """ see the SafeConfigParser method
        """
        if not self.parser.has_section(section):
            self.parser.add_section(section)
        # we don't need "Percent-expansion", so let's replace
        # every '%' by '%%'. Otherwise, we'll get an exception
        # when we try to read a string with a '%' symbol
        value = value.replace('%', '%%')
        return self.parser.set(section, option, value)
    
    def get(self, section, option):
        """ see the SafeConfigParser method
        """
        try:
            return self.parser.get(section, option)
        except ConfigParser.NoSectionError:
            return None
        except ConfigParser.NoOptionError:
            return None

    def getint(self, section, option):
        """ see the SafeConfigParser method
        """
        try:
            return self.parser.getint(section, option)
        except ConfigParser.NoSectionError:
            return None
        except ConfigParser.NoOptionError:
            return None

    def getfloat(self, section, option):
        """ see the SafeConfigParser method
        """
        try:
            return self.parser.getfloat(section, option)
        except ConfigParser.NoSectionError:
            return None
        except ConfigParser.NoOptionError:
            return None

    def getboolean(self, section, option):
        """ see the SafeConfigParser method
        """
        try:
            return self.parser.getboolean(section, option)
        except ConfigParser.NoSectionError:
            return None
        except ConfigParser.NoOptionError:
            return None


class ConfigAware:
    """ base class; to be used for gtSaneWidget classes etc.
        Implements communication with a SaneConfig instance
        
        Many methods must be overloaded, because this class
        cannot know for example the data type required for a
        config value
    """
    def __init__(self, config):
        """ config: SaneConfig instance
        """
        self.config = config
        config.register(self)
    
    def readConfig(self):
        """ get config data from the SaneConfig instance.
            Called by SaneConfig fromo loadConfig; 
            should also be called in the constructor of 
            "config aware" classes
            
            Must be overloaded
        """
        raise SaneConfigError("readConfig method must be overloaded")
    
    def writeConfig(self):
        """ write config data into the config object
            Called by SaneConfig.saveConfig
            
            Must be overloaded
        """
        raise SaneConfigError("writeConfig method must be overloaded")
        