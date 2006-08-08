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

information and management of running scan jobs
"""


DEBUG=1

import gtk, gobject
from SaneError import SaneError
import  I18n

t = I18n.get_translation('eikazo')
if t:
    _ = t.gettext
else:
    _ = lambda x: x


class InfoManager:
    def __init__(self, notify_hub):
        """ construct view and model for job display
        """
        self.jobinfo = JobinfoStore(notify_hub)
        self.jobinfoWid = JobinfoView(self.jobinfo)
        
        jobinfoWidC1 = gtk.TreeViewColumn(_('Job No'))
        cell = gtk.CellRendererText()
        jobinfoWidC1.pack_start(cell, True)
        jobinfoWidC1.add_attribute(cell, 'text', 0)
        
        jobinfoWidC2 = gtk.TreeViewColumn('File')
        cell = gtk.CellRendererText()
        jobinfoWidC2.pack_start(cell, True)
        jobinfoWidC2.add_attribute(cell, 'text', 1)
        
        jobinfoWidC3 = gtk.TreeViewColumn(_('Status'))
        cell = gtk.CellRendererText()
        jobinfoWidC3.pack_start(cell, True)
        jobinfoWidC3.add_attribute(cell, 'text', 2)
        
        self.jobinfoWid.view.append_column(jobinfoWidC1)
        self.jobinfoWid.view.append_column(jobinfoWidC2)
        self.jobinfoWid.view.append_column(jobinfoWidC3)
        
        self.selection_obj = self.jobinfoWid.view.get_selection()
        self.selection_obj.connect("changed", self.jobinfoWidSelection)
        
        self.delete_buttons = []
        self.retry_buttons = []
        self.edit_buttons = []

    
    def selected_job(self):
        store, iter = self.selection_obj.get_selected()
        if iter:
            return self.jobinfo.jobdata(iter)
        else:
            print "warning: can't find the job selected for retry"
    
    def get_widget(self):
        return self.jobinfoWid
    
    def jobinfoWidSelection(self, selection):
        store, iter = selection.get_selected()
        if iter:
            job, processor = store.jobdata(iter)
            buttons_enable = job.has_error() and not job.is_active()
        else:
            buttons_enable = False
        for b in self.delete_buttons:
            b.set_sensitive(buttons_enable)
        for b in self.retry_buttons:
            b.set_sensitive(buttons_enable and processor.can_retry(job))
        for b in self.edit_buttons:
            b.set_sensitive(buttons_enable and processor.can_edit(job))
    
    def add_deleteButton(self, b):
        self.delete_buttons.append(b)
        b.connect("clicked", self.delete_job)
        b.set_sensitive(False)

    def add_retryButton(self, b):
        self.retry_buttons.append(b)
        b.connect("clicked", self.retry_job)
        b.set_sensitive(False)

    def add_editButton(self, b):
        self.edit_buttons.append(b)
        b.connect("clicked", self.edit_job)
        b.set_sensitive(False)
    
    def delete_job(self, w):
        res = self.selected_job()
        if res:
            job, processor =res
            processor.delete_job(job)

    def retry_job(self, w):
        res = self.selected_job()
        if res:
            job, processor =res
            processor.retry_job(job)

    def edit_job(self, w):
        raise "FIXME: not yet implemented"


class JobinfoView(gtk.Table):
    """ - allocate a minimal size request in the realize callback
        - wrap the treeview in a table providing a scrollbar
    """
    def __init__(self, store):
        gtk.Table.__init__(self, 1, 2)
        self.view = _JobinfoView(store)
        self.attach(self.view, 0, 1, 0, 1, gtk.EXPAND|gtk.FILL, gtk.EXPAND|gtk.FILL)
        self.vscrollbar = gtk.VScrollbar(self.view.get_vadjustment())
        self.attach(self.vscrollbar, 1, 2, 0, 1, gtk.FILL, gtk.EXPAND|gtk.FILL)
        self.view.show()
        self.vscrollbar.show()
        

class _JobinfoView(gtk.TreeView):
    """ - allocate a minimal size request in the realize callback
        - wrap the treeview in a table providing a scrollbar
    """
    def __init__(self, store):
        gtk.TreeView.__init__(self, store)
        self._rcb = self.connect("realize", self.cb_realize)
        i1 = store.append(('x', 'x', 'x'))
        i2 = store.append(('x', 'x', 'x'))
        i3 = store.append(('x', 'x', 'x'))
        i4 = store.append(('x', 'x', 'x'))
        self._dummylines = (i1, i2, i3, i4)
        self.set_vadjustment(self.get_vadjustment())
    
    def cb_realize(self, w):
        m = self.get_model()
        alloc = self.get_allocation()
        self.set_size_request(*tuple(alloc)[2:])
        for line in self._dummylines:
            m.remove(line)
        self.disconnect(self._rcb)
        del self._dummylines
        del self._rcb
    

class JobinfoStore(gtk.ListStore):
    """ store for job status info. Updates automatically.
        provides the columns:
        0	job number
        1	file name
        2	status
    """
    def __init__(self, notify_hub):
        gtk.ListStore.__init__(self, str, str, str)
        self.joblist = []
        notify_hub.connect('sane-jobinfo', self.notify_display)
        
    
    def notify_display(self, widget, what, job, processor):
        self._displayaction[what](self, job, processor)
    
    def _newjob(self, job, processor):
        iter = self.append(self.rowdata(job))
        self.joblist.append((iter, job, processor))
    
    def _statusChanged(self, job, processor):
        for i in xrange(len(self.joblist)):
            iter, test = self.joblist[i][:2]
            # FIXME: raise an error, if not found!
            if job == test:
                newdata = self.rowdata(job)
                for j in range(len(newdata)):
                    self.set_value(iter, j, newdata[j])
                t = self.joblist[i]
                self.joblist[i] = self.joblist[i][:2] + (processor,)
                break
    
    def _inDisplay(self, job):
        # mark the job somehow in the job list
        pass
    
    def _removed(self, job, processor):
        for i in range(len(self.joblist)):
            # FIXME: raise an error, if not found!
            iter, test, processor = self.joblist[i]
            if job == test:
                self.remove(iter)
                self.joblist.pop(i)
                break
    
    _displayaction = {'new job':        _newjob,
                      'status changed': _statusChanged,
                      'in display':     _inDisplay,
                      'removed':        _removed,
                     }
    
    def rowdata(self, job):
        # the data to be stored in this store for a job
        jobno = '%i(%i)' % (job.id, job.orig_id)
        status = job.status
        
        err = getattr(job, 'error', None)
        if err:
            # FIXME add i18n stuff, esp. for the error string
            info = 'error: %s, %s' % err[:2]
        else:
            info = []
            # FIXME: reliably sorted infos would be better!
            for k in status.keys():
                info.append(status[k])
            info = ' / '.join(info)
            
        return (jobno, 'NOFILE', info)
    
    def jobdata(self, iter):
        # return the job object for GtkTreeIter iter
        ipath = self.get_path(iter)
        for test, job, processor in self.joblist:
            if ipath == self.get_path(test):
                return job, processor
        return None
    
