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

Base class for filters which invoke external programs

"""
import subprocess, threading, tempfile, os
import gtk, gobject
from Eikazo.SaneError import SaneError
from Eikazo import Processor, I18n
import procinfo
import Image

DEBUG = 1

t = I18n.get_translation('eikazo')
if t:
    _ = t.gettext
else:
    _ = lambda x: x

N_ = lambda x: x
        
providers = []


class Infile:
    def __init__(self, name):
        self.name = name
    
    def __call__(self):
        return self.name

class Outfile:
    def __init__(self, name):
        self.name = name
    
    def __call__(self):
        return self.name

class _ExternalFilter(procinfo.ProcessingProvider):
    filterdescription = N_("""\
Replace this!
""")
    def __init__(self, notify_hub, enabled, config):
        self.connectlabel = N_("Enable %s") % self.name
        procinfo.ProcessingProvider.__init__(self, notify_hub, enabled, config)
        
        self.build_widget(config)
        self.processor = procinfo.ScanJobFilterProcessor(self, 
             self.processor_input, notify_hub, self.name, self.enabled)
        
    
    def build_widget(self):
        raise SaneError("_ExternalFilter.build_widget must be overloaded in derived classes")
    
    def filter(self, job):
        """ called by the procesor for this filter.
            This method must be overloaded
        """
        raise SaneError("_ExternalFilter.build_widget must be overloaded in derived classes")

    def file_out_file_in(self, args, img, imgtype=None):
        """ invoke an external program.
            The input image is written to a temporay file; the output file
            is read from a temporary file

            args is a sequence string defining the "command line"; args[0] 
            is the program name; the following sequence elements are
            parameters for the program. See the subprocess.Popen
            documentation for further details.
            
            Placeholders for the input filename and output filename
            can be given to the args sequence as 
            
                _ExternalFilter.Infile(filename)
            
            resp
            
                _ExternalFilter.Outfile(filename)
            
            where filename is a string with the name of the input resp.
            output file. (The input file is the file to be read by the
            external program.) The filenames must not contain a
            path.
            
            img is the PIL image object to be processed by the external
            program
            
            imgtype is a string specifying the format of the image
            as sent to the external program. If must be recognized by
            the save method of a PIL image. May be None
            
            returns: PIL image instance
        """

        dir = tempfile.mkdtemp()
        infilename = outfilename = None
        
        try:
            for i in xrange(len(args)):
                arg = args[i]
                if isinstance(arg, Infile):
                    infilename = os.path.join(dir, arg())
                    args[i] = infilename
                elif isinstance(arg, Outfile):
                    outfilename = os.path.join(dir, arg())
                    args[i] = outfilename
            
            if imgtype:
                img.save(infilename, imgtype)
            else:
                img.save(outfilename)
            
            res = subprocess.call(args)
            
            if res:
                raise SaneError("external filter returned an error: %s" % res)
            
            return Image.open(outfilename)
        
        finally:
            files = os.listdir(dir)
            for name in files:
                name = os.path.join(dir, name)
                os.unlink(name)
            os.rmdir(dir)
        
def register():
    return []