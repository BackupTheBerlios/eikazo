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

Some base classes for the output plugins; collection of available
plugins

"""

import gtk
from Eikazo import I18n, Config

t = I18n.get_translation('eikazo')
if t:
    _ = t.gettext
else:
    _ = lambda x: x

N_ = lambda x: x


# base class for output providers

class OutputProvider(Config.ConfigAware):
    # derived classes must define these attributes:
    #   - name: Name of the output. Shown in a UI tab. (class attribute)
    #   - processor: A Processor.ScanProcessor instance
    #   - widget: The GUI widget for the output provider
    #   - connectlabel: Text to show for the checkbutton connect_widget
    
    def __init__(self, notify_hub, config):
        Config.ConfigAware.__init__(self, config)
        self.processor_input = None

        self.name_label = gtk.HBox()
        self.name_label_icon = gtk.Image()
        self.name_label_icon.set_from_stock(gtk.STOCK_CANCEL, 1)
        self.name_label.pack_start(self.name_label_icon, 
                                   expand=False, fill=True)
        self.name_label_icon.show()

        w = gtk.Label(_(self.name))
        self.name_label.pack_start(w, expand=False, fill=True)
        w.show()
        
        self.connected = False
        self.connect_widget = gtk.CheckButton(_(self.connectlabel))
        self.connect_widget.set_active(False)
        self.connect_widget.connect("toggled", self.cb_connect_widget)
        

    def cb_connect_widget(self, w):
        v = w.get_active()
        self.enable_input(v)
    
    def get_widget(self):
        return self.widget
    
    def get_name(self):
        return self.name
    
    def get_name_label(self):
        return self.name_label
    
    def get_processor(self):
        return self.processor
        
    def get_connect_widget(self):
        return self.connect_widget
    
    def set_processor_input(self, input):
        self.processor_input = input
        if self.connected:
            self.processor.set_input(input)
    
    def enable_input(self, v):
        if v != self.connected:
            self.connected = v
            self.connect_widget.set_active(v)
            if v:
                self.processor.set_input(self.processor_input)
                self.name_label_icon.set_from_stock(gtk.STOCK_OK, 1)
            else:
                self.processor.set_input(None)
                self.name_label_icon.set_from_stock(gtk.STOCK_CANCEL, 1)
    
    def activate(self, v):
        """ - toggle "sensitiveness" of self.connect_widget
            - enable/disable this output provider
        """
        self.connect_widget.set_sensitive(v)
        if not v:
            self.enable_input(v)
        
    
    def readConfig(self):
        val = self.config.getboolean('output', '%s-connected' % self.name)
        if val != None:
            self.enable_input(val)
    
    def writeConfig(self):
        self.config.set('output', '%s-connected' % self.name, 
                        str(self.connected))
