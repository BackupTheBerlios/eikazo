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

print scans, using a command line tool like lpr

"""
import os, sys, traceback, subprocess, time, threading
import PSDraw
import gtk, gobject
from Eikazo.SaneError import SaneError
from Eikazo import Processor, I18n, Config, Plugins
import outputinfo

DEBUG = 1

t = I18n.get_translation('eikazo')
if t:
    _ = t.gettext
else:
    _ = lambda x: x

N_ = lambda x: x
        
providers = []

Plugins.Plugin('Copier', 'send print data to a printer', 'output', None)

class ScanJobPrinter(Processor.SaneThreadingQueueingProcessor):
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
        job.status['print'] = _('waiting to be printed')
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
                    job.status['print'] = _('printing')
                    self.notify('status changed', job)
                    self.paramsadm.save(job)
                    del job.status['print']
                    self.notify('removed', job)
                except:
                    job.error = sys.exc_info()
                    job.status['print'] = _('print error')
                    if DEBUG:
                        print str(job.error[0]), str(job.error[1])
                        traceback.print_tb(job.error[2])
                    self.notify('status changed', job)
                    self.errorjobs.append(job)
                job.set_active(False)
                self.status = 0 # idle
                if DEBUG:
                    print "printing finished", job.id
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


class ExtPSDraw(PSDraw.PSDraw):
    """ fixes imcomplete page setup
    """
    # FIXME: read Adobe's DSC specs to see, if everything needed is
    # is there and correct
    _psHeader = """\
%%!PS-Adobe-3.0
%%%%Creator: Eikazo
%%%%LanguageLevel: 2
%%%%BoundingBox: 0 0 %i %i
%%%%Pages: 1
%%%%BeginProlog
"""
    _psHeader2 = """\
%%EndProlog
%%BeginSetup
<<
/PageSize [%i %i]
>> setpagedevice
%%EndSetup
%%BeginDocument
save
"""

    _psFooter = """\
showpage restore
%%EndDocument
"""
    def begin_document(self, pagesize):
        self.fp.write(self._psHeader % tuple(pagesize))
        self.fp.write(PSDraw.EDROFF_PS)
        self.fp.write(PSDraw.VDI_PS)
        self.fp.write(self._psHeader2 % tuple(pagesize))
    
    def end_document(self):
        self.fp.write(self._psFooter)
        

class ScanToLpr(outputinfo.OutputProvider, Config.ConfigAware):
    name = N_("Copier (lpr)")
    connectlabel = N_("Enable Copier")
    pagesizes = ['Letter', 'Legal', 'A3', 'A4', 'A5']
    pagedimension = {'Letter': (612, 792), 
                     'Legal':  (612, 1008), 
                     'A3':     (842, 1191), 
                     'A4':     (595, 842), 
                     'A5':     (421, 595), 
                    }
    horPosList = [N_('Left'), N_('Center'), N_('Right')]
    vertPosList = [N_('Top'), N_('Center'), N_('Bottom')]
    
    def __init__(self, notify_hub, config):
        Config.ConfigAware.__init__(self, config)
        outputinfo.OutputProvider.__init__(self, notify_hub, config)
        
        self.build_widget()
        self.readConfig()
        self.processor = ScanJobPrinter(self, self.processor_input,
                                        notify_hub, 2)
    
    def build_widget(self):
        self.widget = gtk.Table(12, 4)
        
        row = 0
        lbl = gtk.Label(_('Page size'))
        self.widget.attach(lbl, 0, 1, row, row+1, gtk.FILL, 0)
        lbl.set_alignment(0, 0.5)
        lbl.show()
        
        self.pagesizeW = gtk.combo_box_new_text()
        for name in self.pagesizes:
            self.pagesizeW.append_text(name)
        self.widget.attach(self.pagesizeW, 1, 2, row, row+1, gtk.FILL, 0)
        self.pagesizeW.show()
        row += 1
        
        self.customPageSize = gtk.CheckButton(_('custom page size'))
        self.widget.attach(self.customPageSize, 1, 2, row, row+1, gtk.FILL, 0)
        self.customPageSize.show()
        row += 1
        
        lbl = gtk.Label(_("page width [mm]"))
        self.widget.attach(lbl, 1, 2, row, row+1, gtk.FILL, 0)
        lbl.set_alignment(1.0, 0.5)
        lbl.show()
        
        self.customWidthW = gtk.SpinButton()
        self.customWidthW.set_increments(1, 10)
        self.customWidthW.set_range(1, 1000)
        self.customWidthW.set_digits(1)
        self.customWidthW.set_alignment(1.0)
        self.widget.attach(self.customWidthW, 2, 3, row, row+1, 0, 0)
        self.customWidthW.show()
        row += 1
        
        lbl = gtk.Label(_("page height [mm]"))
        self.widget.attach(lbl, 1, 2, row, row+1, gtk.FILL, 0)
        lbl.set_alignment(1.0, 0.5)
        lbl.show()
        
        self.customHeightW = gtk.SpinButton()
        self.customHeightW.set_increments(1, 10)
        self.customHeightW.set_range(1, 1000)
        self.customHeightW.set_digits(1)
        self.customHeightW.set_alignment(1.0)
        self.widget.attach(self.customHeightW, 2, 3, row, row+1, 0, 0)
        self.customHeightW.show()
        row += 1
        
        lbl = gtk.Label(_('Margins'))
        self.widget.attach(lbl, 0, 1, row, row+1, gtk.FILL, 0)
        lbl.set_alignment(0, 0.5)
        lbl.show()
        
        lbl = gtk.Label(_("top [mm]"))
        self.widget.attach(lbl, 1, 2, row, row+1, gtk.FILL, 0)
        lbl.set_alignment(1.0, 0.5)
        lbl.show()
        
        self.marginTopW = gtk.SpinButton()
        self.marginTopW.set_increments(1, 10)
        self.marginTopW.set_range(1, 1000)
        self.marginTopW.set_digits(1)
        self.marginTopW.set_alignment(1.0)
        self.widget.attach(self.marginTopW, 2, 3, row, row+1, 0, 0)
        self.marginTopW.show()
        row += 1
        
        lbl = gtk.Label(_("left [mm]"))
        self.widget.attach(lbl, 1, 2, row, row+1, gtk.FILL, 0)
        lbl.set_alignment(1.0, 0.5)
        lbl.show()
        
        self.marginLeftW = gtk.SpinButton()
        self.marginLeftW.set_increments(1, 10)
        self.marginLeftW.set_range(1, 1000)
        self.marginLeftW.set_digits(1)
        self.marginLeftW.set_alignment(1.0)
        self.widget.attach(self.marginLeftW, 2, 3, row, row+1, 0, 0)
        self.marginLeftW.show()
        row += 1
        
        lbl = gtk.Label(_("right [mm]"))
        self.widget.attach(lbl, 1, 2, row, row+1, gtk.FILL, 0)
        lbl.set_alignment(1.0, 0.5)
        lbl.show()
        
        self.marginRightW = gtk.SpinButton()
        self.marginRightW.set_increments(1, 10)
        self.marginRightW.set_range(1, 1000)
        self.marginRightW.set_digits(1)
        self.marginRightW.set_alignment(1.0)
        self.widget.attach(self.marginRightW, 2, 3, row, row+1, 0, 0)
        self.marginRightW.show()
        row += 1
        
        lbl = gtk.Label(_("bottom [mm]"))
        self.widget.attach(lbl, 1, 2, row, row+1, gtk.FILL, 0)
        lbl.set_alignment(1.0, 0.5)
        lbl.show()
        
        self.marginBottomW = gtk.SpinButton()
        self.marginBottomW.set_increments(1, 10)
        self.marginBottomW.set_range(1, 1000)
        self.marginBottomW.set_digits(1)
        self.marginBottomW.set_alignment(1.0)
        self.widget.attach(self.marginBottomW, 2, 3, row, row+1, 0, 0)
        self.marginBottomW.show()
        row += 1
        
        lbl = gtk.Label(_('Zoom'))
        self.widget.attach(lbl, 0, 1, row, row+1, gtk.FILL, 0)
        lbl.set_alignment(0, 0.5)
        lbl.show()
        
        self.zoomFitW = gtk.RadioButton(None, "fit")
        self.widget.attach(self.zoomFitW, 1, 2, row, row+1, gtk.FILL, 0)
        self.zoomFitW.show()
        row += 1
        
        self.zoomScaleW = gtk.RadioButton(self.zoomFitW, "percentage")
        self.widget.attach(self.zoomScaleW, 1, 2, row, row+1, gtk.FILL, 0)
        self.zoomScaleW.show()
        
        self.zoomValueW = gtk.SpinButton()
        self.zoomValueW.set_increments(1, 10)
        self.zoomValueW.set_range(1, 800)
        self.zoomValueW.set_digits(1)
        self.zoomValueW.set_alignment(1.0)
        self.widget.attach(self.zoomValueW, 2, 3, row, row+1, 0, 0)
        self.zoomValueW.show()
        row += 1
        
        lbl = gtk.Label(_('Horizontal Position'))
        self.widget.attach(lbl, 0, 1, row, row+1, gtk.FILL, 0)
        lbl.set_alignment(0, 0.5)
        lbl.show()
        
        self.horPosW = gtk.combo_box_new_text()
        for name in self.horPosList:
            self.horPosW.append_text(_(name))
        self.widget.attach(self.horPosW, 1, 2, row, row+1, gtk.FILL, 0)
        self.horPosW.show()
        row += 1
        
        self.vertPosW = gtk.combo_box_new_text()
        for name in self.vertPosList:
            self.vertPosW.append_text(_(name))
        self.widget.attach(self.vertPosW, 1, 2, row, row+1, gtk.FILL, 0)
        self.vertPosW.show()
        row += 1
        
        lbl = gtk.Label(_('Print command'))
        self.widget.attach(lbl, 0, 1, row, row+1, gtk.FILL, 0)
        lbl.set_alignment(0, 0.5)
        lbl.show()
        
        self.cmdW = gtk.Entry()
        self.widget.attach(self.cmdW, 1, 4, row, row+1, gtk.FILL|gtk.EXPAND, 0)
        self.cmdW.show()
        
    def readConfig(self):
        val = self.config.get('output', 'lpr-pagesize')
        if val != None and val in self.pagesizes:
            pos = self.pagesizes.index(val)
        else:
            # europe-centric....
            pos = self.pagesizes.index('A4')
        self.pagesizeW.set_active(pos)
        
        val = self.config.getboolean('output', 'lpr-custompagesize')
        if val == None:
            val = False
        self.customPageSize.set_active(val)
        
        val = self.config.getfloat('output', 'lpr-custompagewidth')
        if val == None:
            val = 210.0
        self.customWidthW.set_value(val)
        
        val = self.config.getfloat('output', 'lpr-custompageheight')
        if val == None:
            val = 297.0
        self.customHeightW.set_value(val)
        
        val = self.config.getfloat('output', 'lpr-margintop')
        if val == None:
            val = 7.0
        self.marginTopW.set_value(val)
        
        val = self.config.getfloat('output', 'lpr-marginleft')
        if val == None:
            val = 7.0
        self.marginLeftW.set_value(val)
        
        val = self.config.getfloat('output', 'lpr-marginright')
        if val == None:
            val = 7.0
        self.marginRightW.set_value(val)
        
        val = self.config.getfloat('output', 'lpr-marginbottom')
        if val == None:
            val = 7.0
        self.marginBottomW.set_value(val)
        
        val = self.config.getboolean('output', 'lpr-zoom-fit')
        if val == None:
            val = False
        if val:
            self.zoomFitW.set_active(True)
        else:
            self.zoomScaleW.set_active(True)
        
        val = self.config.getfloat('output', 'lpr-zoomvalue')
        if val == None:
            val = 100.0
        self.zoomValueW.set_value(val)
        
        val = self.config.get('output', 'lpr-horpos')
        if val != None and val in self.horPosList:
            pos = self.horPosList.index(val)
        else:
            pos = self.horPosList.index('Center')
        self.horPosW.set_active(pos)
        
        val = self.config.get('output', 'lpr-vertpos')
        if val != None and val in self.horPosList:
            pos = self.vertPosList.index(val)
        else:
            pos = self.vertPosList.index('Center')
        self.vertPosW.set_active(pos)
        
        val = self.config.get('output', 'lpr-cmd')
        if val == None:
            val = 'lpr'
        self.cmdW.set_text(val)
        
        
    def writeConfig(self):
        # FIXME: we must not use get_active_text, because the
        # text may be translated! we must rely on get_value
        self.config.set('output', 'lpr-pagesize', 
                        self.pagesizeW.get_active_text())
        self.config.set('output', 'lpr-custompagesize', 
                        str(self.customPageSize.get_active()))
        self.config.set('output', 'lpr-custompagewidth',
                        str(self.customWidthW.get_value()))
        self.config.set('output', 'lpr-custompageheight',
                        str(self.customHeightW.get_value()))
        self.config.set('output', 'lpr-margintop',
                        str(self.marginTopW.get_value()))
        self.config.set('output', 'lpr-marginleft',
                        str(self.marginLeftW.get_value()))
        self.config.set('output', 'lpr-marginright',
                        str(self.marginRightW.get_value()))
        self.config.set('output', 'lpr-marginbottom',
                        str(self.marginBottomW.get_value()))
        self.config.set('output', 'lpr-zoom-fit',
                        str(self.zoomFitW.get_active()))
        self.config.set('output', 'lpr-zoomvalue',
                        str(self.zoomValueW.get_value()))
        # FIXME: we must not use get_active_text, because the
        # text may be translated! we must rely on get_value
        self.config.set('output', 'lpr-horpos', 
                        self.horPosW.get_active_text())
        self.config.set('output', 'lpr-vertpos', 
                        self.vertPosW.get_active_text())
        self.config.set('output', 'lpr-cmd',
                        self.cmdW.get_text())
        
    # threading concept shamelessly stolen from Python's
    # subprocess.communicate
    def _readerthread(self, fh, buffer):
        buffer.append(fh.read())
    
    def save(self, job):
        # FIXME: add: centering the image, optional scaling etc
        img = job.img
        xres = job.resolution
        yres = job.y_resolution
        
        imgWidth, imgHeight = img.size
        # for Postscript, we want the image size in point
        # FIXME: PSDraw.PSDraw can't deal with different
        # X und Y resolutions. Hence let's for now assume
        # that x_resolution == y_resolution
        imgWidth = float(imgWidth) * 72 / xres
        imgHeight = float(imgHeight) * 72 / xres
        
        if self.customPageSize.get_active():
            pageWidth = self.customWidthW.get_value() * 72.0 / 25.4
            pageHeight = self.customHeightW.get_value() * 72.0 / 25.4
            pageSize = (pageWidth, pageHeight)
        else:
            pos = self.pagesizeW.get_active()
            name = self.pagesizes[pos]
            pageSize = self.pagedimension[name]
            pageWidth, pageHeight = pageSize
        
        marginLeft = float(self.marginLeftW.get_value()) * 72.0 / 25.4
        marginRight = float(self.marginRightW.get_value()) * 72.0 / 25.4
        marginTop = float(self.marginTopW.get_value()) * 72.0 / 25.4
        marginBottom = float(self.marginBottomW.get_value()) * 72.0 / 25.4
        
        
        printWidth = pageWidth - marginLeft - marginRight
        printHeight = pageHeight - marginTop - marginBottom
        
        # first check, if anything needs to be done.
        # If the effective print dimension are zero or negative,
        # or if the image size is zero, simply return.
        # FIXME: The former case should be checked with GUI-
        # callbacks!
        test = min(imgWidth, imgHeight, printWidth, printHeight)
        if test <= 0:
            return
        
        if self.zoomFitW.get_active():
            # scale to fit
            scalex = printWidth / imgWidth
            scaley = printHeight / imgHeight
            if scalex < scaley:
                z = scalex
            else:
                z = scaley
            scaledWidth = imgWidth * z
            scaledHeight = imgHeight * z
        else:
            # absolute zoom definition
            z = self.zoomValueW.get_value() / 100.0
            scaledWidth = imgWidth * z
            scaledHeight = imgHeight * z
        
        scaledResX = xres / z
        scaledResY = yres / z
        
        hpos = self.horPosW.get_active()
        
        if hpos == 0:
            # left adjust
            bbox_x = marginLeft
        elif hpos == 1:
            # centered
            bbox_x = (pageWidth + marginLeft - marginRight - scaledWidth) / 2.0
        else:
            # right adjust
            bbox_x = pageWidth - marginRight - scaledWidth
        
        vpos = self.vertPosW.get_active()
        if vpos == 0:
            # top adjust
            bbox_y = pageHeight - marginTop - scaledHeight
        elif vpos == 1:
            # centered
            bbox_y = (pageHeight + marginBottom - marginTop - scaledHeight) / 2.0
        else:
            # bottom adjust
            bbox_y = marginBottom
        
        bbox = (int(bbox_x), int(bbox_y), 
                int(bbox_x + scaledWidth), int(bbox_y + scaledHeight))
        
        # FIXME: add parsing for "..." and '...' in the command line
        # FIXME: allow to insert parameters, i.e., consider cmdline
        # to be a format string, where we "apply" something like
        # cmd % {'resolution': value, 'tl_x': value...}
        cmd = self.cmdW.get_text().strip()
        cmd = cmd.split(' ')
        pipe = subprocess.Popen(cmd, 
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        
        pipe = subprocess.Popen(cmd, 
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        
        stdout = []
        stdoutThread = threading.Thread(target=self._readerthread,
                                        args=(pipe.stdout, stdout))
        stdoutThread.start()
        
        stderr = []
        stderrThread = threading.Thread(target=self._readerthread,
                                        args=(pipe.stderr, stderr))
        stderrThread.start()
        
        try:
            pswriter = ExtPSDraw(pipe.stdin)
            pswriter.begin_document(pageSize)
            if img.mode == '1':
                img = img.convert('L')
            pswriter.image(bbox, img, scaledResX)
            pswriter.end_document()
        
        finally:
            pipe.stdin.close()
            stdoutThread.join()
            stderrThread.join()
        
            pipe.wait()
            stderr = stderr[0]
            stdout = stdout[0]
            if DEBUG and (stdout or stderr):
                print "output from subprocess:"
                print stdout
                print stderr
            # FIXME: should non-empty stdout optionally be considered an error?
            if stderr:
                raise SaneError("print error: %s" % stderr)
            

providers.append(ScanToLpr)
    

def register():
    return providers