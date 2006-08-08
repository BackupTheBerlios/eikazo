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

"cleaning" filter

"""
import gtk, gobject
from Eikazo.SaneError import SaneError
from Eikazo import Processor, I18n, Config, MeanFilter, Plugins
import procinfo

DEBUG = 1

t = I18n.get_translation('eikazo')
if t:
    _ = t.gettext
else:
    _ = lambda x: x

N_ = lambda x: x
        
providers = []

_plugin_info = Plugins.Plugin('Clean', '', 'postprocessing', None)

try:
    from Eikazo import MeanFilter
    # check, if AdaptiveThresholdFilter is installed.
    MeanFilter.fixedThresholdFilter
    
    class AdaptiveThreshold(procinfo.ProcessingProvider, 
                            Config.ConfigAware):
        sortpos = (procinfo.BILEVEL, procinfo.BILEVEL, 10)
        name = N_("Clean")
        connectlabel = N_("Enable Clean Filter")
        filterdescription = N_("""\
Clean Filter:
This filter removes "small black dots" in the image.

For each image pixel it counts the number of white and black pixels 
in a square area. If the number of black pixels in this area is less
than the threshold, the value of the center pixel becomes "white"

This filter is used only if the input image is in lineart mode
""")
        def __init__(self, notify_hub, enabled, config):
            procinfo.ProcessingProvider.__init__(self, notify_hub, enabled, config)
            Config.ConfigAware.__init__(self, config)
            
            self.averageSize = 2.0
            self.threshold = 12
            
            self.build_widget()
            self.readConfig()
            self.processor = procinfo.ScanJobFilterProcessor(self, 
                 self.processor_input, notify_hub, self.name, self.enabled)
        
        def build_widget(self):
            self.widget = gtk.Table(3, 4, homogeneous=False)
            
            w = gtk.Label(_(self.filterdescription))
            w.set_alignment(0, 0)
            w.set_alignment(0, 0)
            self.widget.attach(w, 0, 3, 1, 2, xoptions=gtk.FILL|gtk.EXPAND,
                               yoptions=gtk.FILL)
            w.show()
            
            w = gtk.Label(_('length of averaging square (mm)'))
            w.set_alignment(0, 0)
            self.widget.attach(w, 0, 1, 2, 3, xoptions=gtk.FILL,
                               yoptions=gtk.FILL)
            w.show()
            
            w = gtk.Label(_('Threshold: Percentage of black pixels'))
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
            
            self.offsadj = gtk.Adjustment(self.threshold, 0, 100, 1, 10, 10)
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
            self.threshold = adj.get_value()
        
        def filter(self, job):
            img = job.img
            
            mode = img.mode
            if mode != '1':
                return
            
            len = self.averageSize * job.resolution / 25.4
            len = int(len) | 1
            
            thrsh = int(len*len * self.threshold / 100)
            
            job.img = MeanFilter.fixedThresholdFilter(img, len, thrsh)
    
        def readConfig(self):
            procinfo.ProcessingProvider.readConfig(self)
            val = self.config.getfloat('postprocessing', 'clean-size')
            if val != None:
                self.averageSize = val
                self.sizeadj.set_value(val)
                
            val = self.config.getfloat('postprocessing', 'clean-threshold')
            if val != None:
                self.threshold = val
                self.offsadj.set_value(val)

        def writeConfig(self):
            procinfo.ProcessingProvider.writeConfig(self)
            self.config.set('postprocessing', 'clean-size',
                            str(self.averageSize))
            self.config.set('postprocessing', 'clean-threshold',
                            str(self.threshold))
    
    providers.append(AdaptiveThreshold)
        
except AttributeError, val:
    if str(val) == "'module' object has no attribute 'fixedThresholdFilter'":
        print "warning: could not create threshold module. The PIL module"
        print "         ImageFilter has no class AdaptiveThresholdFilter"
        _plugin_info.error = 'Could not find module MeanFilter'

def register():
    return providers