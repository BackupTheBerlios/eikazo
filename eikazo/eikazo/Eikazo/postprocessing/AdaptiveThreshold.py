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

Adaptinve Threshold filter

"""
import gtk, gobject
from Eikazo.SaneError import SaneError
from Eikazo import Processor, I18n, Config, Plugins
import procinfo

DEBUG = 1

t = I18n.get_translation('eikazo')
if t:
    _ = t.gettext
else:
    _ = lambda x: x

N_ = lambda x: x
        
providers = []

_plugin_info = Plugins.Plugin('Adaptive Threshold', '', 'postprocessing', None)

try:
    from Eikazo import MeanFilter
    # check, if AdaptiveThresholdFilter is installed
    MeanFilter.adaptiveThresholdFilter
    
    class AdaptiveThreshold(procinfo.ProcessingProvider, Config.ConfigAware):
        sortpos = (procinfo.GRAY, procinfo.BILEVEL, 10)
        name = N_("Adaptive Threshold")
        connectlabel = N_("Enable Threshold Filter")
        filterdescription = N_("""\
Adaptive Threshold Filter:
This filter converts RGB and gray scale images into bi-level images.
It calculates a threshold value for every pixel of an image
by averaging the values in a square area around the pixel and 
subtracting an offset. 

Typical values for the averaging square are 1.5mm .. 10mm; typical
values for the offset are 4% .. 8%
""")
        def __init__(self, notify_hub, enabled, config):
            procinfo.ProcessingProvider.__init__(self, notify_hub, enabled, config)
            Config.ConfigAware.__init__(self, config)
            
            self.averageSize = 2
            self.averageOffset = 5

            self.readConfig()
            
            self.build_widget()
            self.processor = procinfo.ScanJobFilterProcessor(self, 
                 self.processor_input, notify_hub, self.name, self.enabled)
        
        def build_widget(self):
            self.widget = gtk.Table(3, 4, homogeneous=False)
            
            w = gtk.Label(_(self.filterdescription))
            w.set_alignment(0, 0)
            self.widget.attach(w, 0, 3, 1, 2, xoptions=gtk.FILL|gtk.EXPAND,
                               yoptions=gtk.FILL)
            w.show()
            
            w = gtk.Label(_('length of averaging square (mm)'))
            w.set_alignment(0, 0)
            self.widget.attach(w, 0, 1, 2, 3, xoptions=gtk.FILL,
                               yoptions=gtk.FILL)
            w.show()
            
            w = gtk.Label(_('Offset (% of white value)'))
            w.set_alignment(0, 0)
            self.widget.attach(w, 0, 1, 3, 4, xoptions=gtk.FILL,
                               yoptions=gtk.FILL)
            w.show()
            
            self.sizeadj = gtk.Adjustment(self.averageSize, 0, 200, 1, 10, 10)
            self.sizeinput = gtk.SpinButton(self.sizeadj)
            self.widget.attach(self.sizeinput, 1, 2, 2, 3, xoptions=0,
                               yoptions=gtk.FILL)
            self.sizeinput.show()
            self.sizeadj.connect('value-changed', self.cb_size)
            
            self.offsadj = gtk.Adjustment(self.averageOffset, 0, 100, 1, 10, 10)
            self.offsinput = gtk.SpinButton(self.offsadj)
            self.widget.attach(self.offsinput, 1, 2, 3, 4, xoptions=0,
                               yoptions=gtk.FILL)
            self.offsinput.show()
            self.offsadj.connect('value-changed', self.cb_offset)
            
            w = gtk.Label('')
            self.widget.attach(w, 2, 3, 1, 2, xoptions=gtk.FILL|gtk.EXPAND,
                               yoptions=gtk.FILL)
            w.show()
        
        def cb_size(self, adj):
            self.averageSize = adj.get_value()
        
        def cb_offset(self, adj):
            self.averageOffset = adj.get_value()
        
        def filter(self, job):
            img = job.img
            
            mode = img.mode
            if mode == '1':
                return
            elif mode == 'RGB':
                img = img.convert('L')
            elif mode != 'L':
                raise SaneError('unexpected image mode: %s' % mode)
            
            len = self.averageSize * job.resolution / 25.4
            # we need an odd number of pixels as the square length
            len = int(len) | 1
            
            offs = self.averageOffset * 255.0 / 100.0
            offs = int(round(offs))
            
            img = MeanFilter.adaptiveThresholdFilter(img, len, -offs)
            job.img = img.convert('1')

        def readConfig(self):
            procinfo.ProcessingProvider.readConfig(self)
            val = self.config.getfloat('postprocessing', 'adaptivethreshold-size')
            if val != None:
                self.averageSize = val
                self.sizeadj.set_value(val)
            val = self.config.getfloat('postprocessing', 'adaptivethreshold-offset')
            if val != None:
                self.averageOffset = val
                self.offsadj.set_value(val)
    
        def writeConfig(self):
            procinfo.ProcessingProvider.writeConfig(self)
            self.config.set('postprocessing', 'adaptivethreshold-size',
                            str(self.averageSize))
            self.config.set('postprocessing', 'adaptivethreshold-offset',
                            str(self.averageOffset))


    providers.append(AdaptiveThreshold)


        
except AttributeError, val:
    if str(val) == "'module' object has no attribute 'adaptiveThresholdFilter'":
        print "warning: could not activate adaptive threshold module. "
        _plugin_info.error = 'Could not find module MeanFilter'

def register():
    return providers