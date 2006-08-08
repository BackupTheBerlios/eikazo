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

device plugin for the Fujitsu fi-5120/5220. Should also be
useful for the f1-4120/4220

"""

import time
import sane, gtk
from Eikazo import Widgets, SaneThread, Config, I18n, Plugins

# FIXME: may be reasonable to use domain sane-backends too
t = I18n.get_translation('eikazo')
if t:
    _ = t.gettext
else:
    _ = lambda x: x



class FujitsuCapStatus:
    def widgets(self, device, mainwidget, config):
        _plugin_info.details = """\
Special functions for Fujitsu fi-4120, fi-4220, fi-5120, fi-5220
    (used)"""
        return [('status', 'gtksane_status', FujitsuStatusBox(device, mainwidget))]

class FujitsuStatusBox(gtk.Frame):
    def __init__(self, device, actionwidget):
        gtk.Frame.__init__(self, label="Scanner status")
        
        self.device = device
        
        tbl = gtk.Table(2,2)
        self.add(tbl)
        tbl.set_col_spacing(0,6)
        tbl.show()
        
        lbl = gtk.Label("ADF")
        tbl.attach(lbl, 0, 1, 0, 1, xoptions=gtk.FILL, yoptions=0)
        lbl.set_alignment(0, 0.5)
        lbl.show()
        
        lbl = gtk.Label("Hardware")
        tbl.attach(lbl, 0, 1, 1, 2, xoptions=gtk.FILL, yoptions=0)
        lbl.set_alignment(0, 0.5)
        lbl.show()
        
        self.adfstat = gtk.Label()
        tbl.attach(self.adfstat, 1, 2, 0, 1, xoptions=gtk.FILL, yoptions=0)
        self.adfstat.set_alignment(0, 0.5)
        self.adfstat.show()
        self.adfstat.set_justify(gtk.JUSTIFY_LEFT)

        self.hwstat = gtk.Label()
        tbl.attach(self.hwstat, 1, 2, 1, 2, xoptions=gtk.FILL, yoptions=0)
        self.hwstat.set_alignment(0, 0.5)
        self.hwstat.show()
        self.hwstat.set_justify(gtk.JUSTIFY_LEFT)

        self.update()
        
        FujitsuPollStatus(device, self, actionwidget).start()
    
    _hwtext = {0x00: 'OK',
               0x01: 'Booting',
               0x10: 'Shipping lock',
               0x4a: 'Imprinter cover open',
               0x55: 'Multifeed detected: overlapping paper',
               0x56: 'Multifeed detected: paper length',
               0x5a: 'Imprinter paper jam',
               0x74: 'AGC control failure (ADF front)',
               0x75: 'AGC control failure (ADF back)',
               0x7e: 'AGC control failure (flatbed)',
               0x84: 'Lamp fuse blown',
               0x87: 'FB motor cannot move',
               0xb1: 'Imprinter fuse error (scanner fuse)',
               0xb2: 'Imprinter control board error',
               0xb3: 'Imprinter communication timeout error',
               0xb4: 'Imprinter ink cartidge uninstalled',
               0xb5: 'Imprinter head error',
               0xb6: 'Imprinter EEPROM error',
               0xb7: 'Imprinter cover motor error or sensor error',
               0xb8: 'Imprinter ROM error',
               0xb9: 'Imprinter paper detection error or printing range error',
               0xc2: 'Front side background changeover unit error',
               0xc3: 'Back side background changeover unit error',
              }
    def update(self):
        dev = self.device._device
        if dev.button_doublefeed:
            self.adfstat.set_markup('<span background="#FF0000">double feed detected (1)</span>')
        elif dev.button_omrdf:
            self.adfstat.set_markup('<span background="#FF0000">double feed detected (2)</span>')
        elif dev.button_adfopen:
            self.adfstat.set_label("ADF cover open")
        elif dev.button_adfloaded:
            self.adfstat.set_label("ADF loaded")
        else:
            self.adfstat.set_label("ADF empty")
        
        hwstat = dev.button_errorcode
        if hwstat in self._hwtext.keys():
            self.hwstat.set_label(self._hwtext[hwstat])
        else:
            self.hwstat.set_label('Unknown status code: %02x' % hwstat)
            

class FujitsuPollStatus(SaneThread.Thread):
    def __init__(self, device, statuswidget, mainwidget):
        self.device = device
        self.statuswidget = statuswidget
        self.mainwidget = mainwidget
        self.scan_callback = None
        SaneThread.Thread.__init__(self)
    
    def run(self):
        device = self.device
        statuswidget = self.statuswidget
        mainwidget = self.mainwidget
        while not self.abort:
            if device._devicelock.acquire(0):
                try:
                    gtk.gdk.threads_enter()
                    try:
                        statuswidget.update()
                        scanstart = device._device.button_scan
                        if scanstart:
                            mainwidget.do_scan(None)
                    finally:
                        gtk.gdk.threads_leave()
                finally:
                    device._devicelock.release()
            # the fujitsu backend polls the scanner at most once per second,
            # so it is pointless to ask more often here
            time.sleep(1)


class FujitsuCapOverscan:
    def widgets(self, device, mainwidget, config):
        ctrl = FujitsuOverscanController(device, config)
        ctrl.setWidthWidgets([FujitsuPageScale(ctrl, config, True),
                              FujitsuPageNumField(ctrl, config, True)])
        
        ctrl.setHeightWidgets([FujitsuPageScale(ctrl, config, False),
                              FujitsuPageNumField(ctrl, config, False)])
        
        ctrl.setOverscanButton(FujitsuOverscanButton(ctrl))
        return [('pagewidth',  'main', ctrl.getWidthWidgets()),
                ('pageheight', 'main', ctrl.getHeightWidgets()),
                ('overscan',   'main', ctrl.getOverscanButton()),
               ]


class FujitsuOverscanController(Config.ConfigAware):
    def __init__(self, device, config):
        self.device = device
        # overscan mode. start: off
        self.overscan = False
        Config.ConfigAware.__init__(self, config)
    
    def readConfig(self):
        val = self.config.getboolean('device', 'fujitsu-overscan')
        if val != None:
            self.overscanWidget.set_active(val)
            self.set_overscan(self.overscanWidget)
    
    def writeConfig(self):
        val = self.overscanWidget.get_active()
        self.config.set('device', 'fujitsu-overscan', str(val))
    
    def setWidthWidgets(self, widgets):
        self.widthWidgets = widgets
        for w in widgets:
            self.device._registerWidget('pagewidth', w)
    
    def getWidthWidgets(self):
        return self.widthWidgets

    def setHeightWidgets(self, widgets):
        self.heightWidgets = widgets
        for w in widgets:
            self.device._registerWidget('pageheight', w)
    
    def getHeightWidgets(self):
        return self.heightWidgets

    def setOverscanButton(self, widget):
        self.overscanWidget = widget
    
    def getOverscanButton(self):
        return [self.overscanWidget]
    
    def set_overscan(self, button):
        active = self.overscan = button.get_active()
        self.device._device.overscan = active
        for name in ('tl_x', 'tl_y', 'br_x', 'br_y'):
            wlist = self.device.widgets(name)
            for w in wlist:
                if active:
                    w.hide()
                else:
                    w.show()
        if active:
            self.adjust_scansize()
    
    def adjust_scansize(self):
        """ in overscan mode, adjust the scan window to the
            paper size.
        """
        if self.overscan:
            self.device.tl_x = 0
            self.device.tl_y = 0
            self.device.br_x = self.device._device.pagewidth + 32
            self.device.br_y = self.device._device.pageheight + 32
            for name in ('tl_x', 'tl_y', 'br_x', 'br_y'):
                wlist = self.device.widgets(name)
                for w in wlist:
                    w.Reload()
                    d  = self.device


class xxxFujitsuPageSizeWidget(gtk.VBox):
    def __init__(self, ctrl, config, width):
        gtk.VBox.__init__(self)
        self.ctrl = ctrl
        if width:
            label = gtk.Label("Page Width")
            wh = "pagewidth"
        else:
            label = gtk.Label("Page Height")
            wh = "pageheight"
        self.add(label)
        label.show()
        self.scale = FujitsuPageScale(ctrl, config, wh)
        self.add(self.scale)
        self.scale.show()
        self.textfield = FujitsuPageNumField(ctrl, config, wh)
        self.add(self.textfield)
        self.textfield.show()
    
    def Reload(self):
        self.scale.Reload()
        self.textfield.Reload()
    
    def enable_option(self, value):
        self.scale.enable_option(value)
        self.textfield.enable_option(value)

class FujitsuPageScale(Widgets.HScale):
    def __init__(self, ctrl, config, wh):
        if wh:
            optname = 'pagewidth'
        else:
            optname = 'pageheight'
        Widgets.HScale.__init__(self, optname, ctrl.device, config)
        self.ctrl = ctrl
        self.set_draw_value(False)

    def ChangeDeviceValue(self):
        Widgets.HScale.ChangeDeviceValue(self)
        self.ctrl.adjust_scansize()
            
    

class FujitsuPageNumField(Widgets.NumberField):
    def __init__(self, ctrl, config, wh):
        if wh:
            optname = 'pagewidth'
        else:
            optname = 'pageheight'
        Widgets.NumberField.__init__(self, optname, ctrl.device, config)
        self.ctrl = ctrl

    def ChangeDeviceValue(self):
        Widgets.NumberField.ChangeDeviceValue(self)
        self.ctrl.adjust_scansize()
    
        

class FujitsuOverscanButton(gtk.CheckButton):
    def __init__(self, ctrl):
        self.ctrl = ctrl
        gtk.Button.__init__(self, label="Overscan Mode")
        self.connect("toggled", ctrl.set_overscan)
        self.tLabel = None
    
    def titleWidget(self):
        if not self.tLabel:
            self.tLabel = gtk.Label(_('Overscan'))
        return self.tLabel
    
    def show(self):
        self.tLabel.show()
        gtk.CheckButton.show(self)
    
    def hide(self):
        self.tLabel.hide()
        gtk.CheckButton.hide(self)


_vendors = ['FUJITSU']
_models = ['fi-5120', 'fi-5220', 'fi-4120', 'fi-4220']

_fi4120_5220 = [
    # What does this option mean??
    {'name': 'button_topedge',
     'type': 'info',
     'usage': None,
     'widget': None,
    },
    # paper size info is not implemented for these devices
    {'name': 'button_a3',
     'type': 'info',
     'usage': None,
     'widget': None
    },
    {'name': 'button_b4',
     'type': 'info',
     'usage': None,
     'widget': None
    },
    {'name': 'button_a4',
     'type': 'info',
     'usage': None,
     'widget': None
    },
    {'name': 'button_b5',
     'type': 'info',
     'usage': None,
     'widget': None
    },
    {'name': 'button_adfloaded',
     'type': 'info',
     'usage': None,  # in FujitsuStatusBox
     'widget': None
    },
    {'name': 'button_omrdf',
     'type': 'info',
     'usage': None,  # in FujitsuStatusBox
     'widget': None
    },
    {'name': 'button_adfopen',
     'type': 'info',
     'usage': None,  # in FujitsuStatusBox
     'widget': None
    },
    # really not that important for a GUI...
    {'name': 'button_powersave',
     'type': 'info',
     'usage': None,
     'widget': None
    },
    # somwhat arbitrary to choose "copy". But sending emails
    # (if this is it, what is intended for  by Fujitsu)
    # seems to be a bit pointless for a quite fast ADF scanner
    {'name': 'button_send',
     'type': 'button',
     'usage': 'copy',
     'widget': None
    },
    {'name': 'button_manualfeed',
     'type': 'button',
     'usage': None,
     'widget': None
    },
    {'name': 'button_scan',
     'type': 'button',
     'usage': 'scan',
     'widget': None
    },
    {'name': 'button_function',
     'type': 'selection',
     'usage': None, # not very  useful as a simple display
     'widget': None
    },
    # FIXME: this one is tricky. We don't know, if an imprinter is
    # installed. Would depend on some other option. For now, let's
    # simply disable the option. The backend has anyway not yet (June 2006) 
    # an option to define the text to be printed.
    {'name': 'button_inklow',
     'type': 'info',
     'usage': None,
     'widget': None
    },
    {'name': 'button_doublefeed',
     'type': 'info',
     'usage': None,  # in FujitsuStatusBox
     'widget': None
    },
    {'name':  'button_errorcode',
     'type': 'info',
     'usage': None, # in FujitsuStatusBox
     'widget': None
    },
    # not available
    {'name': 'button_skewangle',
     'type': 'info',
     'usage': None,
     'widget': None
    },
    # see above: when to display?
    {'name': 'button_inkremain',
     'type': 'info',
     'usage': None,
     'widget': None
    },
    {'name': 'button_density',
     'type': 'info',
     'usage': None,
     'widget': None
    },
    {'name': 'button_duplex',
     'type': 'info',
     'usage': None,
     'widget': None
    },
    {'name': 'overscan',
     'type': 'cap',
     'usage': FujitsuCapOverscan,
     'widget': None
    },
    {'name': 'status',
     'type': 'cap',
     'usage': FujitsuCapStatus,
     'widget': None
    },
]

class Fujitsu:
    def vendor_names(self):
        return _vendors
    
    def model_names(self):
        return _models
    
    def options(self, devicename):
        devs = sane.get_devices()
        for dev in devs:
            if dev[0] == devicename:
                if dev[1] in _vendors and \
                   [x for x in _models if dev[2].find(x)==0]:
                       return _fi4120_5220
        return None
    
_plugin_info = Plugins.Plugin('fujitsu', 
"""Special functions for Fujitsu fi-4120, fi-4220, fi-5120, fi-5220
    (not used)""",
    'device', None)

def register():
    return (Fujitsu, )
