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


widget to display and edit gamma curves etc
"""

import gtk

RADIUS = 3 # radius of the circles showing the control points
SNAP = 10

class Curve(gtk.DrawingArea):
    """ FIXME: 
        - linear interpolation, between control points
        - "special" options: mirror horizontally, mirror vertically
        - extension: allow also a gamma expression like a ** b (regular
          gamma stuff), and a freely definable Python expression
        - load curve from file??
    """
    def __init__(self, xmin, xmax, ymin, ymax, data=None):
        gtk.DrawingArea.__init__(self)
        
        self.xmin = xmin
        self.xmax = xmax
        self.ymin = ymin
        self.ymax = ymax
        self.snapped = False
        
        if data:
            self.data = data
        else:
            self.data = [(xmin, ymin), (xmax, ymax)]
        
        #self.cursor1 = gtk.gdk.Cursor(gtk.gdk.CROSSHAIR)
        self.cursor1 = gtk.gdk.Cursor(gtk.gdk.TCROSS)
        self.cursor2 = gtk.gdk.Cursor(gtk.gdk.FLEUR)
        
        self.set_size_request(200,200)


        self.add_events(gtk.gdk.POINTER_MOTION_MASK |
                        gtk.gdk.BUTTON_PRESS_MASK |
                        gtk.gdk.BUTTON_RELEASE_MASK)
        self.connect("expose-event", self.expose)
        self.connect("motion_notify_event", self.cb_motion)
        self.connect("button-press-event", self.cb_bpressed)
        self.connect("button-release-event", self.cb_breleased)
        self.connect("realize", self.cb_realize)
    
    def cb_realize(self, widget):
        dr = self.window
        cm = dr.get_colormap()
        self.colors = {}
        self.colors['black'] = cm.alloc_color(0, 0, 0)
        self.colors['white'] = cm.alloc_color(65535, 65535, 65535)
        self.colors['grey']  = cm.alloc_color(32768, 32768, 32768)
        self.colors['red']   = cm.alloc_color(65535, 0, 0)
        self.gc = gtk.gdk.GC(self.window,          # drawable
                             self.colors['black'], # foreground color
                             self.colors['white'], # backgorund color
                             None,                 # font
                             gtk.gdk.COPY,         # function
                             gtk.gdk.SOLID,        # fill style
                             None,                 # tile pixmap
                             None,                 # stipple pixmap
                             None,                 # clip_mask pixmap
                             gtk.gdk.CLIP_BY_CHILDREN, # subwindow mode
                             0,                    # ts_x_origin
                             0,                    # ts_y_origin
                             0,                    # clip_x_origin
                             0,                    # clip_y_origin
                             True,                 # graphics_exposures
                             1,                    # line width
                             gtk.gdk.LINE_SOLID,   # line style
                             gtk.gdk.CAP_ROUND,    # cap_style
                             gtk.gdk.JOIN_ROUND)       # join_style
                        
        self.gc.set_function(gtk.gdk.COPY)


    def expose(self, area, event):
        dr = self.window
        cm = dr.get_colormap()
        gc = self.gc
        
        gc.set_foreground(self.colors['white'])
        gc.set_background(self.colors['white'])
        alloc = self.get_allocation()
        self.width, self.height = alloc.width, alloc.height
        # dr.set_backgorund does not seem to have any effect. So 
        # draw a rectangle...
        
        dr.draw_rectangle(gc, True, 0, 0, alloc.width, alloc.height)
        
        gc.set_foreground(self.colors['red'])
        
        xscale = float(alloc.width) / (self.xmax - self.xmin)
        yscale = float(alloc.height) / (self.ymax - self.ymin)
        self.xscale_inv = 1.0 / xscale
        self.yscale_inv = 1.0 / yscale
        
        if self.data:
            start = self.data[0]
            x1 = int((start[0] - self.xmin) * xscale + 0.5)
            y1 = int(alloc.height - (start[1] - self.ymin) * yscale + 0.5)
            dr.draw_arc(gc, False, x1-RADIUS, y1-RADIUS, RADIUS*2, RADIUS*2, 0, 360*64)
            #dr.draw_rectangle(gc, False, x1-RADIUS, y1-RADIUS, RADIUS*2, RADIUS*2)
        
            for end in self.data[1:]:
                x2 = int((end[0] - self.xmin) * xscale)
                y2 = int(alloc.height - (end[1] - self.ymin) * yscale)
                print "line", x1, y1, x2, y2, start, end
                dr.draw_line(gc, x1, y1, x2, y2)
                dr.draw_arc(gc, False, x2-RADIUS, y2-RADIUS, RADIUS*2, RADIUS*2, 0, 360*64)
                #dr.draw_rectangle(gc, False, x2-RADIUS, y2-RADIUS, RADIUS*2, RADIUS*2)
                x1 = x2
                y1 = y2
                start = end

    def cb_motion(self, area, event):
        print "xxx motion", event.x, event.y, event.state
        x1 = (event.x - SNAP) * self.xscale_inv + self.xmin
        x2 = (event.x + SNAP) * self.xscale_inv + self.xmin
        y1 = (self.height - event.y - SNAP) * self.yscale_inv + self.ymin
        y2 = (self.height - event.y + SNAP) * self.yscale_inv + self.ymin
        dr = self.window
        self.snapped = False
        if not self.snapped:
            for i in xrange(len(self.data)):
                x,y = self.data[i]
                if x1 <= x <= x2 and y1 <= y <= y2:
                    self.snapped = True
                    self.sindex = i
                    dr.set_cursor(self.cursor2)
                    break
        if not self.snapped:
            dr.set_cursor(self.cursor1)
        elif event.state & gtk.gdk.BUTTON1_MASK:
            if self.sindex not in (0, len(self.data)-1):
                x = event.x * self.xscale_inv + self.xmin
                if not (self.data[self.sindex-1][0] < x < self.data[self.sindex+1][0]):
                    x = self.data[self.sindex][0]
            else:
                x = self.data[self.sindex][0]
            y = (self.height - event.y) * self.yscale_inv + self.ymin
            self.data[self.sindex] = (x,y)
            self.queue_draw()
                
    
    def cb_bpressed(self, area, event):
        print "xxx bpressed", event.button, event.x, event.y
        x = event.x * self.xscale_inv + self.xmin
        y = (self.height - event.y) * self.yscale_inv + self.ymin
        if event.button == 1:
            if self.snapped:
                # drag a point
                self.data[self.sindex] = (x,y)
            else:
                for i in xrange(len(self.data)-1):
                    if self.data[i][0] < x < self.data[i+1][0]:
                        self.data.insert(i+1, (x,y))
                        self.snapped = True
                        self.sindex = i+1
                        break
            self.queue_draw()
        elif event.button == 3:
            if self.snapped and self.sindex not in (0, len(self.data)-1):
                self.data.pop(self.sindex)
                self.snapped = False
                self.window.set_cursor(self.cursor1)
                self.queue_draw()
            
    
    def cb_breleased(self, area, event):
        print "xxx breleased", event, event.button, event.x, event.y


if __name__ == '__main__':
    w = gtk.Window(gtk.WINDOW_TOPLEVEL)
    c = Curve(0, 100, 0, 100, [(0,0), (50,50), (100,100)])
    w.add(c)
    c.show()
    w.show()
    gtk.main()