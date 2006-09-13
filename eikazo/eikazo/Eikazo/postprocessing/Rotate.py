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

More an example than a really useful plugin: Invoke ImageMagick's 
convert program with a small selection of the options of this program
"""

import gtk, gobject
import Image
from Eikazo.SaneError import SaneError
from Eikazo import I18n, Config, Plugins
import procinfo
from _ExternalFilter import _ExternalFilter, Infile, Outfile

DEBUG = 1

t = I18n.get_translation('eikazo')
if t:
    _ = t.gettext
else:
    _ = lambda x: x

N_ = lambda x: x
        

_plugin_info = Plugins.Plugin('Rotate scans', '', 'postprocessing', None)


class RotateFilter(procinfo.ProcessingProvider, Config.ConfigAware):
    sortpos = (procinfo.RGB, procinfo.RGB, 0)
    name = N_("Rotate")
    connectlabel = N_("Enable Rotation")
    filterdescription = N_("""\
Rotate scans. In duplex, the rotation angle can be set differently
for front- and backside scans.

If the scanner is a duplex scanner working in "backside-only" mode, the
frontside rotation value is used.

Angles are counterclockwise.
""")
    def __init__(self, notify_hub, enabled, config):
        procinfo.ProcessingProvider.__init__(self, notify_hub, enabled, config)
        Config.ConfigAware.__init__(self, config)
        
        self.rotate_front = 0
        self.rotate_back = 0
        
        self.readConfig()
        
        self.build_widget()
        self.processor = procinfo.ScanJobFilterProcessor(self,
            self.processor_input, notify_hub, self.name, self.enabled)
    
    def build_widget(self):
        
        self.widget = gtk.Table(5, 2, homogeneous=False)
        
        w = gtk.Label(_(self.filterdescription))
        w.set_alignment(0, 0)
        self.widget.attach(w, 0, 2, 0, 1, xoptions=gtk.FILL,
                                          yoptions=gtk.FILL)
        w.show()
        
        w = gtk.Label(_('Rotate Frontside'))
        w.set_alignment(0,0)
        self.widget.attach(w, 0, 1, 1, 2, xoptions=gtk.FILL,
                                          yoptions=gtk.FILL)
        w.show()
        w = gtk.Label(_('Rotate Backside'))
        w.set_alignment(0,0)
        self.widget.attach(w, 1, 2, 1, 2, xoptions=gtk.FILL,
                                          yoptions=gtk.FILL)
        w.show()
        
        texts = (_('0 Degree'), _('90 Degree'), _('180 Degree'), _('270 Degree'))
        fgroup = bgroup = None
        for i in range(len(texts)):
            w = gtk.RadioButton(fgroup, texts[i])
            self.widget.attach(w, 0, 1, i+2, i+3, xoptions=gtk.FILL,
                                                  yoptions=gtk.FILL)
            w.show()
            w.set_active(self.rotate_front == i)
            w.connect('clicked', self.set_front_rot, i)
            fgroup = w

            w = gtk.RadioButton(bgroup, texts[i])
            self.widget.attach(w, 1, 2, i+2, i+3, xoptions=gtk.FILL,
                                                  yoptions=gtk.FILL)
            w.show()
            w.set_active(self.rotate_back == i)
            w.connect('clicked', self.set_back_rot, i)
            bgroup = w
            
    
    def set_front_rot(self, widget, v):
        self.rotate_front = v
            
    def set_back_rot(self, widget, v):
        self.rotate_back = v
            
    _rot = {1: Image.ROTATE_90, 2: Image.ROTATE_180, 3: Image.ROTATE_270}
    def filter(self, job):
        img = job.img
        if job.duplex_status_backside:
            r = self.rotate_back
        else:
            r = self.rotate_front
        if r: # 0 degree needs no rotation
            job.img = img.transpose(self._rot[r])
        # adjust resolution data, if y_resolution exists
        if r % 1 and job.__dict__.has_key('y_resolution'):
            tmp = job.resolution
            job.resolution = job.y_resolution
            job.y_resolution = tmp
        print "xxx job info", job.__dict__.keys()
    
def register():
    return [RotateFilter]
