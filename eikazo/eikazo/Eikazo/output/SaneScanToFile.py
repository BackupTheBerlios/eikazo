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

Write scan data to a file.
"""
import sys, os, time, traceback
import gtk
from Eikazo.SaneError import SaneError
from Eikazo import I18n, Config, Processor, Plugins
import outputinfo

DEBUG = 0

t = I18n.get_translation('eikazo')
if t:
    _ = t.gettext
else:
    _ = lambda x: x
        
N_ = lambda x: x

Plugins.Plugin('Save to File', '', 'output', None)

class FormatOptions:
    """ base class for file formats. It provides:

          - a user interface allowing to set the options
          - a format name to identify the format.
          - a file name pattern for the format. Used for gtk.FileFilter
          - a method that returns a dict with the current settings.
            Its result is intended to be used in calls of PIL.Image.save()
    """
    def __init__(self):
        gtk.HBox.__init__(self)
    
    name = None
    
    pattern = None
        
    def save_options(self, resolution, y_resolution):
        """ the options to be used in PIL.Image.save """
        raise SaneError("FormatOptions.save_options must be overridden")
    
    def save(self, img, filename, xres, yres):
        """ default implementation using PIL's file saving mechanism
        """
        # resolution and y_resolution are set by class SaneScanQueue.Scanner
        params = self.save_options(xres, yres)
        img.save(filename, self.name, **params)
    
class TiffFormatOptions(FormatOptions, gtk.HBox, Config.ConfigAware):
    """ PIL.TiffImagePlugin supports the following parameters:
          description
          resolution
          x resolution
          y resolution
          resolution unit (inch or cm)
          software
          date time
          artist
          copyright
    """

    name = "TIFF"
        
    pattern = "*.[tT][iI][fF]"

    def __init__(self, config):
        FormatOptions.__init__(self)
        gtk.HBox.__init__(self)
        Config.ConfigAware.__init__(self, config)
        self.description = ""
        self.copyright = ""
        
        self.desclabel = gtk.Label(_("Description"))
        self.pack_start(self.desclabel, expand=False)
        self.desclabel.show()
        
        self.descwidget = gtk.Entry()
        self.pack_start(self.descwidget, expand=True, fill=True)
        self.descwidget.show()
        self.descwidget.connect("focus-out-event", self.text_changed, 
                                "description")
        
        self.copylabel = gtk.Label(_("Copyright"))
        self.pack_start(self.copylabel, expand=False)
        self.copylabel.show()
        
        self.copywidget = gtk.Entry()
        self.pack_start(self.copywidget, expand=True, fill=True)
        self.copywidget.show()
        self.copywidget.connect("focus-out-event", self.text_changed, 
                                "copyright")
        self.readConfig()

    def text_changed(self, w, ev, field):
        setattr(self, field, w.get_text())
    
    def save_options(self, resolution, y_resolution):
        res = {'resolution unit': 'inch',
               'description':     self.description,
               'copyright':       self.copyright,
              }
        if y_resolution == None:
            y_resolution = resolution
        res['resolution'] = resolution
        res['y resolution'] = y_resolution
        return res
    
    def readConfig(self):
        val = self.config.get('output', 'file-tiff-description')
        if val:
            self.description = val
            self.descwidget.set_text(val)
        
        val = self.config.get('output', 'file-tiff-copyright')
        if val:
            self.copyright = val
            self.copywidget.set_text(val)
        
    def writeConfig(self):
        self.config.set('output', 'file-tiff-description', self.description)
        self.config.set('output', 'file-tiff-copyright', self.copyright)
    
class JpegFormatOptions(FormatOptions, gtk.HBox, Config.ConfigAware):
    """ PIL.JpegImagePlugin supports the following parameters:
          dpi (2-tuple for x and y direction)
          quality
          progressive
          smooth
          optimize
          streamtype
    """

    name = "JPEG"
        
    pattern = "*.[jJ][pP][gG]"
    
    PILBUG = 1
    def __init__(self, config):
        FormatOptions.__init__(self)
        gtk.HBox.__init__(self)
        Config.ConfigAware.__init__(self, config)
        
        self.quality = 75
        self.progressive = False
        self.optimize = True
        
        self.qualitylabel = gtk.Label(_("quality"))
        self.pack_start(self.qualitylabel, expand=False)
        self.qualitylabel.show()
        
        self.qualitywidget = gtk.SpinButton(digits=3)
        self.qualitywidget.set_range(0, 100)
        self.qualitywidget.set_increments(1,10)
        self.qualitywidget.set_value(self.quality)
        self.qualitywidget.set_numeric(True)
        self.pack_start(self.qualitywidget, expand=False)
        self.qualitywidget.show()
        self.qualitywidget.connect("value-changed", self.set_quality)
        
        # using the optimize and progressive options triggers a bug
        # in PIL's JPegImage plugin
        if not self.PILBUG:
            self.progressivewidget = gtk.CheckButton("progressive")
            self.progressivewidget.set_active(self.progressive)
            self.pack_start(self.progressivewidget, expand=False)
            self.progressivewidget.show()
            self.progressivewidget.connect("toggled", self.set_progressive)
            
            self.optimizewidget = gtk.CheckButton("optimize")
            self.optimizewidget.set_active(self.optimize)
            self.pack_start(self.optimizewidget, expand=False)
            self.optimizewidget.show()
            self.optimizewidget.connect("toggled", self.set_optimize)
        
        self.readConfig()
        
    def set_quality(self, w):
        self.quality = w.get_value()
    
    def set_progressive(self, w):
        self.progressive = w.get_active()
        
    def set_optimize(self, w):
        self.optimize = w.get_active()
        
        
        
    def save_options(self, resolution, y_resolution):
        if y_resolution == None:
            y_resolution = resolution
        res = {}
        return res
    
    def readConfig(self):
        val = self.config.getfloat('output', 'file-jpeg-quality')
        if val:
            self.quality = val
            self.qualitywidget.set_value(val)
        
        if not self.PILBUG:
            val = self.config.getboolean('output', 'file-jpeg-progressive')
            if val != None:
                self.progressive = val
                self.progressivewidget.set_active(val)
            val = self.config.getboolean('output', 'file-jpeg-optimize')
            if val != None:
                self.optimize = val
                self.optimizewidget.set_active(val)
        
    def writeConfig(self):
        val = self.config.set('output', 'file-jpeg-quality', 
                              str(self.quality))
        if not self.PILBUG:
            val = self.config.set('output', 'file-jpeg-progressive',
                                  str(self.progressive))
            val = self.config.eet('output', 'file-jpeg-optimize',
                                  str(self.optimize))
    
_fileformats = [TiffFormatOptions, JpegFormatOptions]


class ScanJobFileWriter(Processor.SaneThreadingQueueingProcessor):
    def __init__(self, paramsadm, input_producer, notify_hub, queue_length):
        """ input_producer, queue_length: see base classes
            paramsadm: instance of a class which can return
        """
        Processor.SaneThreadingQueueingProcessor.__init__(self, 
            input_producer, notify_hub, queue_length)
        self.errorjobs = []
        self.paramsadm = paramsadm
        self.start()
        self.status = 0
        
    def append(self, job):
        Processor.SaneThreadingQueueingProcessor.append(self, job)
        job.status['write'] = _('waiting to be written')
        self.notify('status changed', job)
    
    
    def run(self):
        while not self.abort:
            if len(self.queue) and not self.errorjobs:
                self.queuelock.acquire()
                job = self.queue.pop(0)
                self.status = 1 # writing
                self.queuelock.release()
                job.set_active(True)
                try:
                    job.status['write'] = _('writing')
                    self.notify('status changed', job)
                    self.paramsadm.save(job)
                    self.notify('removed', job)
                except:
                    job.error = sys.exc_info()
                    job.status['write'] = _('write error')
                    if DEBUG:
                        print str(job.error[0]), str(job.error[1])
                        traceback.print_tb(job.error[2])
                    self.notify('status changed', job)
                    self.errorjobs.append(job)
                job.set_active(False)
                self.status = 0 # idle
                if DEBUG:
                    print "writing finished", job.id
            else:
                time.sleep(0.1)
                
    def numjobs(self, cascade):
        self.queuelock.acquire()
        res = len(self.queue) + len(self.errorjobs)
        if self.status != 0:
            res += 1
        self.queuelock.release()
        return res

    def retry_job(self, job):
        res = False
        self.queuelock.acquire()
        for i in xrange(len(self.errorjobs)):
            if job == self.errorjobs[i]:
                self.errorjobs.pop(i)
                # scan jobs shouldprocessed in the sequence of their
                # job ids
                self.queue.append(job)
                self.queue.sort(lambda x,y: cmp(x.id, y.id))
                res = True
                break
        self.queuelock.release()
        return res
    

class ScanToFile(outputinfo.OutputProvider):
    name = N_("Save to File")
    connectlabel = N_("Enable Save to File")
    def __init__(self, notify_hub, config):
        outputinfo.OutputProvider.__init__(self, notify_hub, config)
        self.filecounter = 0
        self.incr = 1
        self.set_filename("%04i.tif")
        
        self.build_widget()
        self.readConfig()
        # start the file output "unconnected"
        self.processor = ScanJobFileWriter(self, self.processor_input, notify_hub, 2)
        self.lastfiles = []

    def build_widget(self):
        self.widget = gtk.VBox()
        
        self.hboxfname = gtk.HBox()
        self.widget.pack_start(self.hboxfname, expand=False)
        self.hboxfname.show()
        
        self.fnlabel = gtk.Label(_("file name:"))
        self.hboxfname.pack_start(self.fnlabel, expand=False)
        self.fnlabel.show()
        
        self.fnfield = gtk.Entry()
        self.hboxfname.pack_start(self.fnfield, expand=True, fill=True)
        self.fnfield.show()
        self.fnfield.set_text(self.filename)
        self.fnfield.connect("focus-out-event", self.fnchanged)
        
        self.fnbrowse = gtk.Button(_("Browse"))
        self.hboxfname.pack_start(self.fnbrowse, expand=False)
        self.fnbrowse.show()
        self.fnbrowse.connect("clicked", self.fnbrowse_click)
        
        self.hboxfnum = gtk.HBox()
        self.widget.pack_start(self.hboxfnum, expand=False)
        self.hboxfnum.show()
        
        self.fclabel = gtk.Label(_("file counter"))
        self.hboxfnum.pack_start(self.fclabel, expand=False)
        self.fclabel.show()
        
        self.fcfield = gtk.SpinButton(digits=0)
        self.hboxfnum.pack_start(self.fcfield, expand=True, fill=False)
        self.fcfield.show()
        adj = gtk.Adjustment(self.filecounter, -2**31, 2**31-1, 1, 10, 10)
        self.fcfield.configure(adj, 1, 0)
        self.fcfield.set_numeric(True)
        self.fcfield.set_increments(1,10)
        self.fcfield.connect("value-changed", self.cb_filecounter)
        
        self.fcinclabel = gtk.Label(_("file counter increment"))
        self.hboxfnum.pack_start(self.fcinclabel, expand=False)
        self.fcinclabel.show()
        
        self.fcincfield = gtk.SpinButton(digits=0)
        self.hboxfnum.pack_start(self.fcincfield, expand=True, fill=False)
        self.fcincfield.show()
        adj = gtk.Adjustment(self.incr, -2**31, 2**31-1, 1, 10, 10)
        self.fcincfield.configure(adj, 1, 0)
        self.fcincfield.set_numeric(True)
        self.fcincfield.set_increments(1,1)
        self.fcincfield.connect("value-changed", self.cb_incr)
        
        self.fmtlabel = gtk.Label(_("file format"))
        self.hboxfnum.pack_start(self.fmtlabel, expand=False)
        self.fmtlabel.show()
        
        self.filefilters = []
        for name, pattern in [(x.name, x.pattern) for x in _fileformats]:
            filter = gtk.FileFilter()
            filter.set_name(name)
            filter.add_pattern(pattern)
            self.filefilters.append(filter)
        
        self.formatwidgets = {}
        for klass in _fileformats:
            inst = klass(self.config)
            name = inst.name
            self.formatwidgets[name] = inst
            self.widget.pack_start(inst, expand=False, fill=False)
        # avoid an exception in the following method
        self.format = fileformat = "TIFF"
        self.formatwidgets[fileformat].show()
        self.set_fileformat(fileformat)

        self.fmt = gtk.combo_box_new_text()
        i = 0
        self.fmt.values = [x.name for x in _fileformats]
        for name in self.fmt.values:
            self.fmt.append_text(name)
            if name == fileformat:
                active = i
            i += 1
        self.fmt.set_active(active)
        self.hboxfnum.pack_start(self.fmt, expand=False)
        self.fmt.show()
        self.fmt.connect("changed", self.fmt_changed)
        
        self.saveInfoStore = gtk.ListStore(str, str, str, str)

        self.saveInfoFrame = gtk.Frame(_('last saved files'))
        self.widget.pack_start(self.saveInfoFrame, expand=True, fill=True)
        self.saveInfoFrame.show()
        
        self.saveViewTbl = gtk.Table(1, 2)
        self.saveInfoFrame.add(self.saveViewTbl)
        self.saveViewTbl.show()
        self.saveView = gtk.TreeView(self.saveInfoStore)
        self.saveViewTbl.attach(self.saveView, 0, 1, 0, 1, 
                                gtk.EXPAND|gtk.FILL, gtk.EXPAND|gtk.FILL)
        self.saveView.show()

        scrollbar = gtk.VScrollbar(self.saveView.get_vadjustment())
        self.saveViewTbl.attach(scrollbar, 1, 2, 0, 1, gtk.FILL, gtk.FILL)
        scrollbar.show()
        
        colno = 0
        for title in (_('mode'), _('res'), _('size'), _('file name')):
            col = gtk.TreeViewColumn(title)
            cell = gtk.CellRendererText()
            col.pack_start(cell, True)
            col.add_attribute(cell, 'text', colno)
            colno += 1
            self.saveView.append_column(col)
        
        self.readConfig()
    
    def set_filename(self, filename):
        """ returns 0, if the filename is "useful", or an error
            message, if integers could 
        """
        self.filename = filename
        self.use_number = 0
        if filename.find('%') >= 0:
            try:
                filename % 1
                self.use_number = 1
                return 0
            except:
                return _("can't insert a file number into the file name")
        return 0
        
    def filename_warning(self, msg):
        dlg = gtk.MessageDialog(None,
                gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_WARNING,
                gtk.BUTTONS_OK,
                msg)
        dlg.connect("response", lambda w, resp: w.destroy())
        dlg.show()
    
    def fnchanged(self, w, event):
        test = self.set_filename(w.get_text())
        if test:
            self.filename_warning(test)
    
    def fnbrowse_click(self, w):
        dlg = gtk.FileChooserDialog(_("Select filename..."), None, 
                  gtk.FILE_CHOOSER_ACTION_SAVE, 
                  (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, 
                   gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        dlg.set_default_response(gtk.RESPONSE_OK)
        filter = gtk.FileFilter()
        filter.set_name(_("All files"))
        filter.add_pattern("*")
        dlg.add_filter(filter)
        for filter in self.filefilters:
            dlg.add_filter(filter)
            if filter.get_name() == self.format:
                dlg.set_filter(filter)
        dlg.hide()
        path, fname = os.path.split(self.get_filename())
        dlg.set_current_folder(path)
        dlg.set_current_name(fname)

        if dlg.run() == gtk.RESPONSE_OK:
            filename = dlg.get_filename()
            test = self.set_filename(filename)
            if test:
                self.filename_warning(test)
            self.fnfield.set_text(dlg.get_filename())
            filter = dlg.get_filter()
            if filter:
                name = filter.get_name()
                for i in range(len(self.filefilters)):
                    if name == self.filefilters[i].get_name():
                        # sets also self.format via the the canged callback
                        self.fmt.set_active(i)
                    
        dlg.destroy()

    
    def fmt_changed(self, w):
        i = self.fmt.get_active()
        self.set_fileformat(_fileformats[i].name)
    
    def cb_filecounter(self, w):
        self.filecounter = int(w.get_value())
    
    def cb_incr(self, w):
        self.incr = int(w.get_value())
    
    def get_filename(self):
        return self.filename
    
    def set_fileformat(self, format):
        if not format in [x.name for x in _fileformats]:
            raise SaneError("unknown fileformat: %s" % format)
        if format != self.format:
            self.formatwidgets[self.format].hide()
            self.format = format
            self.formatwidgets[format].show()
    
    def get_fileformat(self):
        return self.format
    
    def set_filecounter(self, filecounter):
        self.filecounter = filecounter
        self.fcfield.set_value(filecounter)
        
    def get_filecounter(self):
        return self.filecounter
    
    def set_incr(self, incr):
        self.incr = incr
        self.fcincfield.set_value(incr)
    
    def get_jobdata(self):
        if self.use_number:
            res = self.filename % self.filecounter
            self.filecounter += self.incr
            self.fcfield.set_value(self.filecounter)
            return res
        return self.filename
    
    def save(self, job):
        fname = self.get_jobdata()
        format = self.formatwidgets[self.get_fileformat()]
        format.save(job.img, fname, job.resolution, job.y_resolution)

        if job.resolution == job.y_resolution:
            res = str(job.resolution)
        else:
            res = '%i x %i' % (job.resolution, job.y_resolution)
        sw = job.scanwindow
        size = '%.1f x %.1f' % (sw[1]-sw[0], sw[3]-sw[2])
        
        gtk.gdk.threads_enter()
        if len(self.lastfiles) > 20:
            iter = self.lastfiles.pop(0)
            self.saveInfoStore.remove(iter)
        self.lastfiles.append(
            self.saveInfoStore.append((job.img.mode, res, size, fname)))
        gtk.gdk.threads_leave()
    
    def get_connect_widget(self):
        return self.connect_widget
    
    def readConfig(self):
        outputinfo.OutputProvider.readConfig(self)
        val = self.config.get('output', 'file-filename')
        if val != None:
            self.filename = val
            self.fnfield.set_text(val)
        
        val = self.config.getint('output', 'file-filecounter')
        if val != None:
            self.filecounter = val
            self.fcfield.set_value(val)
        
        val = self.config.getint('output', 'file-increment')
        if val != None:
            self.incr = val
            self.fcincfield.set_value(val)
        
        val = self.config.get('output', 'file-format')
        if val != None:
            self.set_fileformat(val)
            for i in xrange(len(_fileformats)):
                if _fileformats[i].name == val:
                    self.fmt.set_active(i)
                    break
    
    def writeConfig(self):
        outputinfo.OutputProvider.writeConfig(self)
        self.config.set('output', 'file-filename', self.filename)
        self.config.set('output', 'file-filecounter', str(self.filecounter))
        self.config.set('output', 'file-increment', str(self.incr))
        self.config.set('output', 'file-format', self.format)
    
def register():
    return [ScanToFile]
