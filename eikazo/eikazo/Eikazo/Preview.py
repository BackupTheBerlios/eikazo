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

"preview" for scanned images

"""
DEBUG=0

import os, sys, traceback, time
import Image
import gtk
import I18n
import Processor
from SaneError import SaneError

t = I18n.get_translation('eikazo')
if t:
    _ = t.gettext
else:
    _ = lambda x: x


class SanePreviewProcessor(Processor.SaneThreadingQueueingProcessor):
    def __init__(self, input_processor, notify_hub, queue_length, preview):
        # this class does not need to emit notifications about jobs
        Processor.SaneThreadingQueueingProcessor.__init__(self, 
            input_processor, notify_hub, queue_length)
        self.previews = [preview]
        input_processor.add_output(self)
        self.start()
    
    def append(self, job):
        Processor.SaneThreadingQueueingProcessor.append(self, job)
    
    def run(self):
        while not self.abort:
            if len(self.queue):
                self.queuelock.acquire()
                job = self.queue.pop(0)
                self.queuelock.release()
                self.notify('removed', job)
                try:
                    # FIXME: update only a preview which is
                    # actually displayed!
                    for p in self.previews:
                        gtk.gdk.threads_enter()
                        p.setImage(job.img, job.scanwindow)
                        gtk.gdk.threads_leave()
                except:
                    # catch all errors: If anything does wrong here,
                    # it's not worth to stop the entire program
                    error = sys.exc_info()
                    print str(error[0]), str(error[1])
                    traceback.print_tb(error[2])
            else:
                time.sleep(0.1)
    
    def numjobs(self, cascade):
        return len(self.queue)
    
    def add_preview(self, preview):
        self.previews.append(preview)

class SanePreview(gtk.Alignment):
    """ we want a preview which shows the image with a correct
        aspect raito, and with correct rulers. Hence we need a 
        container which does not try to fill its entire space with 
        child widgets
    """
    def __init__(self, device, config, size=(300,300), data=None):
        gtk.Alignment.__init__(self)
        
        self.table = gtk.Table(5, 4, False)
        self.table.show()
        self.add(self.table)
        
        tlx, brx, tly, bry = device.getMaxScanArea()
        # FIXME: aspect ratio may need to be re-calculated, during
        # the reload-options event!
        self.aspectratio = float(brx-tlx) / (bry-tly)
        self.vrulerwidth = [0, 0, 0]
        self.hrulerheight = [0, 0, 0, 0]

        self.preview = _SanePreview(device, size,data)

        self.table.attach(self.preview, 2, 3, 3, 4, 
                          gtk.EXPAND|gtk.FILL, gtk.EXPAND|gtk.FILL, 0, 0)
        self.preview.show()
        
        self.limitDisplaySize = gtk.CheckButton(_("Limit display to scan window"))
        self.table.attach(self.limitDisplaySize, 0, 4, 0, 1, gtk.EXPAND|gtk.FILL, 0, 0, 0)
        self.limitDisplaySize.show()
        self.limitDisplaySize.connect("toggled", self.setLimitMode)
        
        self.vruler = gtk.VRuler()
        self.vruler.set_range(tly, bry, 10, 0)
        self.table.attach(self.vruler, 1, 2, 3, 4, 0, gtk.EXPAND|gtk.FILL, 0, 0)
        self.vruler.show()
        self.preview.connect_object("motion_notify_event", 
            lambda ruler, event: ruler.emit("motion_notify_event", event),
            self.vruler)
        self.hruler = gtk.HRuler()
        self.hruler.set_range(tlx, brx, 10, 0)
        self.table.attach(self.hruler, 2, 3, 2, 3, gtk.EXPAND|gtk.FILL, 0, 0, 0)
        self.hruler.show()
        self.preview.connect_object("motion_notify_event", 
            lambda ruler, event: ruler.emit("motion_notify_event", event),
            self.hruler)
        
        self.tlxscale = device.createOptionWidget('tl_x', config, 'hscale')
        self.tlxscale.set_property('draw-value', False)
        self.table.attach(self.tlxscale, 2, 3, 1, 2, gtk.EXPAND|gtk.FILL, 0, 0, 0)
        self.tlxscale.show()
        
        self.brxscale = device.createOptionWidget('br_x', config, 'hscale')
        self.brxscale.set_property('draw-value', False)
        self.table.attach(self.brxscale, 2, 3, 4, 5, gtk.EXPAND|gtk.FILL, 0, 0, 0)
        self.brxscale.show()
        
        self.tlyscale = device.createOptionWidget('tl_y', config, 'vscale')
        self.tlyscale.set_property('draw-value', False)
        self.table.attach(self.tlyscale, 0, 1, 3, 4, 0, gtk.EXPAND|gtk.FILL, 0, 0)
        self.tlyscale.show()
        
        self.bryscale = device.createOptionWidget('br_y', config, 'vscale')
        self.bryscale.set_property('draw-value', False)
        self.table.attach(self.bryscale, 3, 4, 3, 4, 0, gtk.EXPAND|gtk.FILL, 0, 0)
        self.bryscale.show()
        
        self.connect("size-allocate", self.alloc_childs)
        self.hruler.connect("size-request", self.get_hruler_height, 0)
        self.tlxscale.connect("size-request", self.get_hruler_height, 1)
        self.brxscale.connect("size-request", self.get_hruler_height, 2)
        self.limitDisplaySize.connect("size-request", self.get_hruler_height, 3)
        self.vruler.connect("size-request", self.get_vruler_width, 0)
        self.tlyscale.connect("size-request", self.get_vruler_width, 1)
        self.bryscale.connect("size-request", self.get_vruler_width, 2)
    
    def	get_hruler_height(self, w, size, i):
        self.hrulerheight[i] = size.height
    
    def	get_vruler_width(self, w, size, i):
        self.vrulerwidth[i] = size.width
    
    def alloc_childs(self, w, allocation):
        """ event function for size-allocate. Here, we know how large
            this widget is, and we know the width of the vruler and
            the height of the hruler. Hence we can calculate, how much space
            to give to the drawingArea. We'll do this by re-sizing the
            entire table
        """
        if not self.vrulerwidth or not self.hrulerheight:
            return
        w,h = tuple(allocation)[2:]
        
        # we want a certain apsect ratio of the drawing area
        # Additionally, we must not give all available space to the table,
        # otherwise would not be able to make the widdget smaller
        w -= sum(self.vrulerwidth)+3
        h -= sum(self.hrulerheight)+3
        
        if h>0 and w>0:
            r = float(w)/h
            if r < self.aspectratio:
                h = int(w / self.aspectratio)
            elif r > self.aspectratio:
                w = int(h * self.aspectratio)
            
            self.preview.set_size_request(w-1, h-1)
            self.preview.map = None
    
    def setImage(self, img, scanwindow):
        """ img:        a PIL image
            scanwindow: (tly, brx, tly, bry), physical coordinates corrsponding
                        to this image
        """
        self.preview.setImage(img, scanwindow)
    
    def setLimitMode(self, w):
        # checkbox "limit display" changed
        # FIXME: move this method to the preview container.
        self.preview.limitDisplay = w.get_active()
        if self.preview.limitDisplay:
            w = self.preview.device.br_x - self.preview.device.tl_x
            h = self.preview.device.br_y - self.preview.device.tl_y
            if w > 0 and h > 0:
                self.aspectratio = float(w) / h
                self.imageScale = -1
                self.tlxscale.hide()
                self.brxscale.hide()
                self.tlyscale.hide()
                self.bryscale.hide()
                self.hruler.set_property('lower', self.preview.device.tl_x)
                self.hruler.set_property('upper', self.preview.device.br_x)
                self.vruler.set_property('lower', self.preview.device.tl_y)
                self.vruler.set_property('upper', self.preview.device.br_y)
                self.preview.map = None
                self.queue_resize()
                return

        tlx, brx, tly, bry = self.preview.device.getMaxScanArea()
        self.aspectratio = float(brx-tlx) / (bry-tly)
        self.tlxscale.show()
        self.brxscale.show()
        self.tlyscale.show()
        self.bryscale.show()
        self.hruler.set_property('lower', tlx)
        self.hruler.set_property('upper', brx)
        self.vruler.set_property('lower', tly)
        self.vruler.set_property('upper', bry)
        self.preview.map = None
        self.queue_resize()
    

class _SanePreview(gtk.DrawingArea):
    """ displays a preview image, allows to select the scan window
    """
    def __init__(self, device, size=(300,300), data=None):
        """ device: a Widgets.SaneDevice instance
            size:   initial widget size
            data:   (img, scanwindow), optional PIL Image object and scan
                    window coordinates for inital display
        """
        gtk.DrawingArea.__init__(self)
        self.set_size_request(*size)
        self.limitDisplay = False

        self.add_events(gtk.gdk.POINTER_MOTION_MASK |
                        gtk.gdk.BUTTON_PRESS_MASK |
                        gtk.gdk.BUTTON_RELEASE_MASK)
        self.connect("expose-event", self.expose)
        
        self.device = device
        self.map = None
        
        if data:
            self.setImage(*data)
        else:
            im = Image.new('L', (500,500))
            self.setInitImage(im)
        
        self.connect("motion_notify_event", self.motion_notify)
        self.connect("button-press-event", self.button_pressed)
        self.connect("button-release-event", self.button_released)
        
        self.buttons = 0
        self.imagescale = -1
        
        self.device.connect("sane-geometry", self.geometryUpdate)
    
    def geometryUpdate(self, device):
        self.queue_draw()
    
    def motion_notify(self, widget, event):
        if event.state & (gtk.gdk.BUTTON1_MASK | gtk.gdk.BUTTON3_MASK):
            w,h = tuple(self.get_allocation())[2:]
            xmin, xmax, ymin, ymax = self.device.getMaxScanArea()
            scalex = float(xmax-xmin)/w
            scaley = float(ymax-ymin)/h
            self.queue_draw()
        
        if event.state & gtk.gdk.BUTTON1_MASK:
            # redefine scan window
            self.device.tl_x = scalex * min(self.corner1[0], event.x)
            self.device.br_x = scalex * max(self.corner1[0], event.x)
            self.device.tl_y = scaley * min(self.corner1[1], event.y)
            self.device.br_y = scaley * max(self.corner1[1], event.y)
            self.buttons = 1
        elif event.state & gtk.gdk.BUTTON3_MASK:
            # move scan window
            deltax = event.x - self.corner1[0]
            deltay = event.y - self.corner1[1]
            tlx, brx, tly, bry = self.lastwindow
            w,h = tuple(self.get_allocation())[2:]
            if deltax < 0:
                if tlx + deltax < 0:
                    deltax = -tlx
            elif deltax > 0:
                if brx + deltax > w:
                    deltax = w - brx
            if deltay < 0:
                if tly + deltay < 0:
                    deltay = -tly
            elif deltay > 0:
                if bry + deltay > h:
                    deltay = h - bry
            tlx += deltax
            brx += deltax
            tly += deltay
            bry += deltay
            self.device.tl_x = scalex * tlx
            self.device.br_x = scalex * brx
            self.device.tl_y = scaley * tly
            self.device.br_y = scaley * bry
            self.buttons = 2
            self.corner1 = (event.x, event.y)
            
            
    
    def button_pressed(self, widget, event):
        self.corner1 = (event.x, event.y)
    
    def button_released(self, widget, event):
        if self.buttons == 1:
            w,h = tuple(self.get_allocation())[2:]
            xmin, xmax, ymin, ymax = self.device.getMaxScanArea()
            scalex = float(xmax-xmin)/w
            scaley = float(ymax-ymin)/h
            self.device.tl_x = scalex * min(self.corner1[0], event.x)
            self.device.br_x = scalex * max(self.corner1[0], event.x)
            self.device.tl_y = scaley * min(self.corner1[1], event.y)
            self.device.br_y = scaley * max(self.corner1[1], event.y)
            self.queue_draw()
        self.buttons = 0
    
    def draw_scanwindow(self):
        """ draw a rectangle for the currently selected scan window.
        """
        gc = self.style.white_gc
        # take the settigs directly from the device. This way,
        # we always get a precise display
        xmin, xmax, ymin, ymax = self.device.getMaxScanArea()
        w,h = tuple(self.get_allocation())[2:]
        scalex = float(w)/(xmax-xmin)
        scaley = float(h)/(ymax-ymin)
        device = self.device
        tlx = device.tl_x * scalex
        brx = device.br_x * scalex
        tly = device.tl_y * scaley
        bry = device.br_y * scaley

        w = int(brx - tlx)
        h = int(bry - tly)
        tlx = int(tlx)
        tly = int(tly)
        # scan window corners in display pixel units
        self.lastwindow = (tlx, tlx + w, tly, tly + w)
        gc.set_line_attributes(1, gtk.gdk.LINE_DOUBLE_DASH, 
                               gtk.gdk.CAP_BUTT, gtk.gdk.JOIN_MITER)
        device = device._device
        self.window.draw_rectangle(gc, False, tlx, tly, w, h)
        
    
    def setImage(self, image, scanwindow):
        """ image: a PIL Image instance
        """
        self.image = image
        self.scanwindow = scanwindow
        self.map = None
        if getattr(self, 'scaledImage', None):
            del self.scaledImage
        self.queue_draw()
    
    def expose(self, widget, event):
        # use PIL's Image.transform to scale the image to 
        if self.image:
            if not self.map or not self.scaledImage:
                # rebuild the preview image
                imWidth, imHeight = self.image.size
                if imWidth == 0 or imHeight == 0:
                    return
            
                wWidth, wHeight = tuple(self.get_allocation())[2:]
                if not self.limitDisplay:
                    wtlx, wbrx, wtly, wbry = self.device.getMaxScanArea()
                else:
                    #wtlx = self.device.tl_x
                    #wbrx = self.device.br_x
                    #wtly = self.device.tl_y
                    #wbry = self.device.br_y
                    wtlx, wbrx, wtly, wbry,  = self.scanwindow
                
                if wbrx <= wtlx or wbry < wtly:
                    return
                wScaleX = float(wbrx - wtlx) / wWidth
                wScaleY = float(wbry - wtly) / wHeight
                
                imtlx, imbrx, imtly, imbry = self.scanwindow
                if imbrx <= imtlx or imbry <= imtly:
                    return
                imScaleX = float(imWidth)  / (imbrx - imtlx)
                imScaleY = float(imHeight) / (imbry - imtly)
                
                a = imScaleX * wScaleX
                c = imScaleX * (wtlx - imtlx)
                e = imScaleY * wScaleY
                f = imScaleY * (wtly - imtly)
                self.map = (a, 0, c, 0, e, f)
                
                self.scaledImage = self.image.transform((wWidth, wHeight),
                                                        Image.AFFINE,
                                                        self.map,
                                                        Image.BILINEAR)
                
            gc = self.style.black_gc
            
            mode = self.image.mode
            dispWidth, dispHeight = self.scaledImage.size
            if mode == "1":
                data = self.scaledImage.convert("L").tostring("raw", "L")
                self.window.draw_gray_image(gc, 0, 0, 
                                            dispWidth, dispHeight,
                                            gtk.gdk.RGB_DITHER_NONE, data)
            elif mode == "L":
                data = self.scaledImage.tostring("raw", "L")
                self.window.draw_gray_image(gc, 0, 0, 
                                            dispWidth, dispHeight,
                                            gtk.gdk.RGB_DITHER_NONE, data)
            elif mode == "RGB":
                data = self.scaledImage.tostring("raw", "RGB")
                self.window.draw_rgb_image(gc, 0, 0, 
                                            dispWidth, dispHeight,
                                           gtk.gdk.RGB_DITHER_NONE, data)
            else:
                raise SaneError("unexpected image format: %" % mode)
        
        if not self.limitDisplay:
            self.draw_scanwindow()
        return
    
    def setInitImage(self, img):
        # want something to display in the preview area...
        # we use the image as a repeatable tile
        # let's assume a 75 dpi scan
        # moreover, we limit the image width to 600 pixel
        
        startwidth = 600
        sx1, sx2, sy1, sy2 = self.device.getMaxScanArea()
        w = sx2 - sx1
        h = sy2 - sy1
        r = float(h) / w
        startheight = int(r * startwidth)
        initImg = Image.new("RGB", (startwidth, startheight))
        tilewidth, tileheight = img.size
        
        y = 0
        while y < startheight:
            x = 0
            while x < startwidth:
                initImg.paste(img, (x,y))
                x += tilewidth
            y += tileheight
        self.setImage(initImg, self.device.getMaxScanArea())
            

