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

print scans

Disabled for now. See the comment at line 110
"""
import os, sys, traceback, subprocess, time
import gtk, gobject
from Eikazo.SaneError import SaneError
from Eikazo import Processor, I18n
import outputinfo

DEBUG = 0

t = I18n.get_translation('eikazo')
if t:
    _ = t.gettext
else:
    _ = lambda x: x

N_ = lambda x: x
        
providers = []

class ScanJobFilePrinter(Processor.SaneThreadingQueueingProcessor):
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

# disable this printing variant for now: Too many problems with gnomeprint
# Aside from the two problems mentioned below (threading and creating a
# printer configuration from an XML file, we can get page size hassles:
# On Suse 9.3, the typical setup - CUPS, foomatic and a PCL printer - does not 
# "see" the definition of A4 paper size, while a real Postscript printer
# uses this paper size. The Problem is this part of the Postscript header
# produced by gnomeprint:
#
# <<
# /PageSize [595 842]
# /ImagingBBox null
# /Duplex false
# /Tumble false
# /NumCopies 1
# /Policies <<
# /PolicyNotFound 1
# /PageSize 3
# >>
# >> setpagedevice
#
# The line /PageSize [595 842] defines an A4 page, but the dict /Policies
# defines the fallback policy, what to do, if the requested page size is
# not availabe. /PageSize 3 means "select the nearest available medium".
# Works fine for a real Postscript printer, but for Ghostscript/foomatic
# this results in the page size being set to letter or whatever else:
# If A4 is requested, the printed page has too large blank margins at the
# top of a printed page. In short: Crap. Though this is probably not
# strictly a problem of gnomeprint, it can be a showstopper from the user
# perspective.
#
# Moreover, I think that an application _library_ like gnomeprint should
# anyway not make assuptions, what to do in the case that a certain
# paper size is not available in a devide. It might sometimes be
# preferable to abort printing, if the a paper size is not supported by
# a device is selected. The decision what to do with a wrong paper size
# should be left to the user and/or an application.


if 0:
    try:
        import gnomeprint, gnomeprint.ui
        

        """ two problems with gnomeprint and gnomeprint.ui

        (1) older versions of Gnome's print dialog are not thread safe:
            http://bugzilla.gnome.org/show_bug.cgi?id=311410
            
            This could be fixed by upgrading to a more recent Gnome library,
            but not everybody will want to such complex work.
            
            Hence the print dialog is started in a forked program, and the
            result is passed as an XML description to the main program

        (2) On startup, libgnomeprint does not collect information about 
            available printers. Probably a decision to speed up the start, but
            this has a serious consequence: A call to gnomeprint.config_from_string
            silently returns the default config (silently from Python's perspective 
            -- we get a warning on stdout or stderr), if a printer dialog has not 
            been created and run before. There seems to be no other way to 
            initialize libgnomeprint's internal printer list.
            
            This means that we can't load a printer configuration from an XML
            description without running first a dialog. In other words, we can't 
            load some printing details from Eikazo's config file. Moreover, it
            seems that libgnomeprint's default page size is letter -- not very useful
            in some parts of the world.
            
            The two problems combined are especially nasty: Eikazo relies
            heavily on threading, so we even can't create a printer dialog 
            the usual way on some installations, hence we even can't try to
            set printer details in our own dialog: a gnomeprint.Config instance
            will always represent the default setup.
            
            So let's use a really ugly workaround: create a printer dialog
            during startup, hide it immediately, wait a few seconds until
            the dialog has collected information about installed printers
            and then delete it. That's acrazy, but I don't see another way
            to get printing properly working.
        """

        _idle_first = True
        def _idle_dlg():
            global _idle_first
            if _idle_first:
                _d.iconify()
                _idle_first = False
            if time.time() < _ready:
                return True
            _d.emit("delete-event", gtk.gdk.Event(gtk.gdk.DELETE))

        # give dthe dialog 8 seconds to collect printer information from Cups etc.
        _ready = time.time() + 8

        _c = gnomeprint.config_default()
        _j = gnomeprint.Job(_c)
        _d = gnomeprint.ui.Dialog(_j, "please ignore this...")
        gobject.idle_add(_idle_dlg)
        _d.run()
        

        
        printerdlg = """
    import sys, gnomeprint, gnomeprint.ui
    x = gnomeprint.config_default()
    j = gnomeprint.Job(x)
    cfg = sys.stdin.read()
    sys.stderr.write("--------- dlg read ------------\\\n%s\\\n" % cfg)
    cfg = gnomeprint.config_from_string(cfg, 0)
    sys.stderr.write("--------- dlg internal ---------\\\n")
    sys.stderr.write(cfg.to_string(0))
    job = gnomeprint.Job(cfg)
    dlg = gnomeprint.ui.Dialog(job, "Printer Setup", 0)
    res = dlg.run()
    if res == gnomeprint.ui.DIALOG_RESPONSE_PRINT:
        sys.stdout.write(cfg.to_string())
    """
        
        # FIXME: at present, we don't save the configuration. Problem is, that
        # gnomeprint does not know about most printers, before a print selection
        # dialog is shown. See 
        # http://mail.gnome.org/archives/gnome-print-list/2004-August/msg00026.html
        # This patch is obviously not yet integrated...
        class ScanToPrint(outputinfo.OutputProvider):
            name = N_("Copier")
            connectlabel = N_("Enable Copier")
            def __init__(self, notify_hub, config):
                outputinfo.OutputProvider.__init__(self, notify_hub, config)
                
                self.printconfig = gnomeprint.config_default()
                self.printjob = gnomeprint.Job(self.printconfig)
                
                self.build_widget()
                self.processor = ScanJobFilePrinter(self, self.processor_input,
                                                    notify_hub, 2)
            
            def build_widget(self):
                self.widget = gtk.VBox()
                
                hbox = gtk.HBox()
                self.widget.pack_start(hbox, expand=False)
                hbox.show()
                
                printoptbtn = gtk.Button(_("Print Options"))
                hbox.pack_start(printoptbtn, expand=False)
                printoptbtn.show()
                printoptbtn.connect("clicked", self.printoptions)
        
            def printoptions(self, widget):
                # problem: The print dialog wants to acquire a lock
                # in older GTK versions.
                # Hence the dialog is shown in a sub-process. 
                
                cmd = ["python", "-c", "exec(%s)" % repr(printerdlg)]
                cfg = self.printconfig.to_string(0)
                p = subprocess.Popen(cmd, 
                                     stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,
                                     close_fds=True)
                # writing the current config to the dialog process is pointless:
                # We'll only get the error message "model not found", because
                # of the problem described above... Hell, what a mess
                # We could create a long running process, but that would
                # require to shut it down properly and whatever else -- just to
                # to work around a crazy Gnome bug
                res, err = p.communicate(input=cfg)
                #res, err = p.communicate(input="")
                
                if res:
                    print "-------------------------------------"
                    print res
                    print "-------------------------------------"
                    self.printconfig = gnomeprint.config_from_string(res, 0)
                    self.printjob = gnomeprint.Job(self.printconfig)
                    self.printconfig.dump()
            
            def save(self, job):
                # FIXME: add: centering the image, optional scaling etc
                img = job.img
                xres = job.resolution
                yres = job.y_resolution
                gpc = self.printjob.get_context()
                
                gpc.beginpage("1")
                
                mode = img.mode
                data = img.tostring("raw", mode)
                
                w,h = img.size
                
                # for now, only 100% zoom. The methods gpc.grayimage
                # and gpc.rgbimage paint in the the square (0,0) (1,1)
                # in the current coordinate system, so we just need to
                # set the scale to the size of the image in point
                
                if yres == None:
                    yres = xres
                
                iw = float(w) * 72 / xres
                ih = float(h) * 72 / yres
                
                gpc.scale(iw, ih)
                
                if mode in ('1', 'L'):
                    data = img.tostring("raw", 'L')
                    gpc.grayimage(data, w, h, w)
                elif mode == "RGB":
                    gpc.rgbimage(data, w, h, w)
                else:
                    raise SaneError("Unsupported PIL image mode: %s" % mode)
                gpc.showpage()
                self.printjob.close()
                self.printjob.print_()
                
                self.printjob = gnomeprint.Job(self.printconfig)
        
        
        providers.append(ScanToPrint)
            
    except ImportError, val:
        print "warning: could not import module gnomeprint:", str(val)
        print "         Print output disabled"
        

def register():
    return providers