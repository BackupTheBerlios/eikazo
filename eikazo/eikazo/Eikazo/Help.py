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

help widget and help window
"""

# FIXME: Where is some documentation for gtkhtml2 ???
# couldn't find anything, neither for the C libs nor for the Python wrapper
# So the stuff here is based on the Python example and some trial and error...
#
# FIXME: a decent url parser should be used instead of the wuickly
# hacked stuff.

import os, sys, traceback
import gtk
import gtkhtml2 # FIXME: use try/except!!
import I18n

t = I18n.get_translation('eikazo')
if t:
    _ = t.gettext
else:
    _ = lambda x: x


class Help:
    def __init__(self):
        self.window = None
    
    def show(self, content=None):
        dir = os.path.split(__file__)[0]
        self.dir = os.path.join(dir, 'doc')
        fname = os.path.join(self.dir, 'index.html')
        
        if not self.window:
            self.window = gtk.Window()
            self.window.set_title(_('Eikazo Help'))

            self.doc = gtkhtml2.Document()
            self.doc.clear()
            
            self.doc.connect('request_url', self.cb_request_url)
            self.doc.connect('link_clicked', self.cb_link_clicked)
            
            self.widget = gtk.ScrolledWindow()
            self.view = gtkhtml2.View()
            self.widget.add(self.view)
            self.view.show()
            
            # when is this callback called???
            #self.view.connect('request_object', self.cb_request_object)

            self.view.set_document(self.doc)

            self.window.add(self.widget)
            self.widget.show()
            self.window.connect("destroy", self.cb_destroy)
            self.window.set_default_size(600, 400)
            self.window.show_all()
        
        self.doc.open_stream('text/html')
        self.doc.write_stream(open(fname).read())
        self.doc.close_stream()
    
    def cb_destroy(self, w):
        self.window = None
        del self.doc
        del self.widget
        del self.view
        
    def cb_request_url(self, doc, url, stream):
        """ called for <img> tags and when a link to an anchor is clicked
        """
        stream.write(open(os.path.join(self.dir, url)).read())
        
    def cb_link_clicked(self, doc, link):
        # contains the plain link as found in an <a href> tag.
        # we may have a filename, an anchor or a filename and an anchor
        link = link.split('#')
        if link[0]:
            try:
                fname = os.path.join(self.dir, link[0])
                text = open(fname).read()
                self.doc.open_stream('text/html')
                self.doc.write_stream(text)
                self.doc.close_stream()
            except:
                # a missing file here is not important enough to crash the 
                # whole application. Obly print the error message
                err = sys.exc_info()
                print str(err[0]), str(err[1])
                traceback.print_tb(err[2])
        if len(link) > 1:
            self.view.jump_to_anchor(link[1])
    
    #def cb_request_object(self, doc, url, stream):
    #    # no idea hwat this is good for...
    #    pass
        
    
if __name__ == '__main__':
    h = Help()
    h.show()
    h.window.show_all()
    gtk.main()