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

import subprocess
import gtk, gobject
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
        

class MagickOption(Config.ConfigAware):
    # way too trivial: this class does not allow to set parameters
    # for an option...
    def __init__(self, name, text, config):
        Config.ConfigAware.__init__(self, config)
        self.name = name
        self.widget = gtk.CheckButton(text)
        self.widget.set_active(False)
        self.readConfig()
    
    def get_value(self):
        if self.widget.get_active():
            return self.name
        else:
            return ''
    
    def get_widget(self):
        return self.widget
    
    def readConfig(self):
        val = self.config.getboolean('postprocessing', 'magick'+self.name)
        if val != None:
            self.widget.set_active(val)
    
    def writeConfig(self):
        val = self.widget.get_active()
        self.config.set('postprocessing', 'magick'+self.name, str(val))


_options = (('-despeckle', N_('reduce the speckles within an image')),
            ('-dither',    N_('apply Floyd/Steinberg error diffusion to the image')),
            ('-enhance',   N_('apply a digital filter to enhance a noisy image')),
            ('-equalize',  N_('perform histogram equalization to the image')),
            ('-normalize', N_('transform image to span the full range of color values')),
           )

_progname = 'convert'

_found = False
for testpath in ('', '/usr/bin/', '/usr/local/bin/'):
    try:
        p = subprocess.Popen([testpath + _progname, '-help'], 
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE)
        stdout, stderr = p.communicate()
    except OSError, val:
        if str(val).find('Errno 2') >= 0:
            pass
        else:
            raise
    else:
        _progname = testpath + _progname
        _found = True
        break

if not _found:
    _plugin_info = Plugins.Plugin('ImageMagick', '', 'postprocessing',
                      'Program "convert" not found')
else:
    _plugin_info = Plugins.Plugin('ImageMagick', '', 'postprocessing', None)


class MagickFilter(_ExternalFilter):
    sortpos = (procinfo.RGB, procinfo.RGB, 10)
    name = N_("ImageMagick")
    filterdescription = N_("""\
Invoke ImageMagick's convert program to manipulate the scanned image.
For details about the options, please refer to the ImageMagick documentation.
""")
    def __init__(self, notify_hub, enabled, config):
        _ExternalFilter.__init__(self, notify_hub, enabled, config)
        
    
    def build_widget(self, config):
        
        self.widget = gtk.Table(3, len(_options) + 1, homogeneous=False)
        
        w = gtk.Label(_(self.filterdescription))
        w.set_alignment(0, 0)
        self.widget.attach(w, 0, 3, 0, 1, xoptions=gtk.FILL|gtk.EXPAND,
                           yoptions=gtk.FILL)
        w.show()
        
        line = 1
        self.options = []
        for name, text in _options:
            opt = MagickOption(name, text, config)
            w = opt.get_widget()
            self.options.append(opt)
            self.widget.attach(w, 0, 1, line, line+1, 
                               xoptions=gtk.FILL, yoptions=gtk.FILL)
            w.set_alignment(0, 0.5)
            w.show()
            line += 1
        
    
    def filter(self, job):
        img = job.img
        args = [_progname]
        for opt in self.options:
            v = opt.get_value()
            if v:
                args.append(v)
        args.append(Infile('infile.tif'))
        args.append(Outfile('outfile.tif'))
        res = self.file_out_file_in(args, img, 'TIFF')
        job.img = res
    
    
def register():
    if _found:
        return [MagickFilter]
    else:
        return []