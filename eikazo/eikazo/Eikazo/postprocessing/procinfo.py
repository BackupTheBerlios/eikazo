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

collect information about available filter plugins

"""
import os, sys, traceback, time
import gtk
from Eikazo import I18n, Processor, Config

t = I18n.get_translation('eikazo')
if t:
    _ = t.gettext
else:
    _ = lambda x: x

N_ = lambda x: x

DEBUG = 1

# for the definition of the sort order
RGB=1
GRAY=2
BILEVEL=3

def outputinfo():
    """ return a list of known output classes
    """

# common processor class for filters
# - queue length is fixed to 1
# - if the filter is disabled, all methods call the
#   same method of the output resp. input
class ScanJobFilterProcessor(Processor.SaneThreadingQueueingProcessor):
    def __init__(self, paramsadm, input_producer, notify_hub,
                 filtername, enabled):
        """ input_producer, queue_length: see base classes
            paramsadm: instance of a class which can return
        """
        Processor.SaneThreadingQueueingProcessor.__init__(self, 
            input_producer, notify_hub, 1)
        self.errorjobs = []
        self.paramsadm = paramsadm
        self.start()
        self.status = 0
        self.filtername = filtername
        self.enabled = enabled
        
    def enable(self, v):
        self.enabled = v
    
    def append(self, job):
        if self.enabled:
            Processor.SaneThreadingQueueingProcessor.append(self, job)
            job.status[self.filtername] = _('queued by %s') % self.filtername
            job.owner = self
            self.notify('status changed', job)
        else:
            self.send_toOutput(job)
    
    def can_append(self, job):
        if self.enabled:
            return Processor.SaneThreadingQueueingProcessor.can_append(self, job)
        else:
            if self.output:
                res = [x.can_append(job) for x in self.output]
                return reduce(lambda x,y: x and y, res)
            else:
                return True
        
    def numjobs(self, cascade):
        self.queuelock.acquire()
        res = len(self.queue) + len(self.errorjobs)
        if self.status != 0:
            res += 1
        self.queuelock.release()
        return res

    def run(self):
        while not self.abort:
            if len(self.queue) and not self.errorjobs:
                self.queuelock.acquire()
                job = self.queue.pop(0)
                self.status = 1 # writing
                self.queuelock.release()
                job.set_active(True)
                try:
                    job.status[self.filtername] = _('processed by %s' % self.filtername)
                    self.notify('status changed', job)
                    self.paramsadm.filter(job)
                    del job.status[self.filtername]
                    self.send_toOutput(job)
                    if job.owner == self:
                        self.notify('removed', job)
                except:
                    job.error = sys.exc_info()
                    job.status[self.filtername] = _('filter error: %s' % self.filtername)
                    if DEBUG:
                        print str(job.error[0]), str(job.error[1])
                        traceback.print_tb(job.error[2])
                    self.notify('status changed', job)
                    self.errorjobs.append(job)
                job.set_active(False)
                self.status = 0 # idle
            else:
                time.sleep(0.1)
                


# base class for output providers

class ProcessingProvider(Config.ConfigAware):
    # derived classes must define these attributes:
    #   - name: Name of the output. Shown in a UI tab. (class attribute)
    #   - processor: A Processor.Processor instance
    #   - widget: The GUI widget for the processing provider
    #   - connectlabel: Text to show for the "enbale filter" checkbutton
    
    def __init__(self, notify_hub, enabled, config):
        Config.ConfigAware.__init__(self, config)
        
        self.processor_input = None
        self.enabled = enabled

        self.name_label = gtk.HBox()
        self.name_label_icon = gtk.Image()
        self.name_label_icon.set_from_stock(gtk.STOCK_CANCEL, 1)
        self.name_label.pack_start(self.name_label_icon, 
                                   expand=False, fill=True)
        self.name_label_icon.show()

        w = gtk.Label(_(self.name))
        self.name_label.pack_start(w, expand=False, fill=True)
        w.show()
        
        self.connect_widget = gtk.CheckButton(_(self.connectlabel))
        self.connect_widget.set_active(self.enabled)
        self.connect_widget.connect("toggled", self.cb_connect_widget)
        

    def cb_connect_widget(self, w):
        v = w.get_active()
        self.enable_filter(v)
    
    def get_widget(self):
        return self.widget
    
    def get_name(self):
        return self.name
    
    def get_name_label(self):
        return self.name_label
    
    def get_processor(self):
        return self.processor
        
    def get_connect_widget(self):
        return self.connect_widget
    
    def set_processor_input(self, input):
        self.processor_input = input
        self.processor.set_input(input)
    
    def enable_filter(self, v):
        if v != self.enabled:
            self.enabled = v
            self.connect_widget.set_active(v)
            self.processor.enable(v)
            if v:
                self.name_label_icon.set_from_stock(gtk.STOCK_OK, 1)
            else:
                self.name_label_icon.set_from_stock(gtk.STOCK_CANCEL, 1)
    
    def readConfig(self):
        val = self.config.getboolean('postprocessing', self.name + '-enable')
        if val != None:
            self.enable_filter(val)
    
    def writeConfig(self):
        self.config.set('postprocessing', self.name + '-enable', str(self.enabled))
    
def register():
    return [ScanToFile]
