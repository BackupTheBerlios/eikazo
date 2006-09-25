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


Processors are classes that implement some sort of processing:
  - scanning itself is done by a processor
  - saving to a file
  - printing
  - displaying scan data in a widget
  - image manipulation: deskewing, gray -> bi-level, addition of an
    ICC profile etc etc

- Every processor has exactly one input, connected to exactly
  input producer
- processors may produce output for other processors. In this case,
  their output may be fed to more than one processor. (example
  application: simultaneous printing and saving of scans)

- Every processor takes a class Scanjob instance as its input
- Error handling: If an error occurs, processors may "reject"
  a job. In this case, the job data must not be modified, and the
  job is passed back to the input processor
  
  This file contains mostly interface definitions
  
  All processors must be "threading-aware". I.e. they must maintain 
  a state; all methods may be called from another thread.

  Trivial processors can simply do all processing in their append()
  method  
"""  

import sys, time, traceback, weakref
from SaneError import SaneError
import threading, SaneThread
import gobject
import I18n
DEBUG = 1

t = I18n.get_translation('eikazo')
if t:
    _ = t.gettext
else:
    _ = lambda x: x

# "serial number" for jobs.
_jobid = 0
# paranoia check: which attributes may be set for a SaneScanJob
# instance. This ensures that attributes are not lost in SaneScanJob.copy
#
# attributes we don't want:
# 'error'
# attributes that need a "deep copy"
_deepcopyattr = ('img', )
# attributes that may be copied using sequence oprators
_seqattr = ('scanwindow',)
# attributes that are copied by value or reference, in the constructor call
_refattr = ('orig_id', 'copies', 'owner')
# attributes thay may exist and that can be copied by value:
_simpleattr = ('resolution', 'y_resolution', 'duplex_status_backside')
# unique/independed attributes
_uniqattr = ('id', 'status', 'active', 'deleted')
_jobattr = _deepcopyattr + _seqattr + _refattr + _simpleattr + _uniqattr
_joblist = []
class SaneScanJob:
    def __init__(self, owner, orig_id=None, copies=None):
        """ container for job data. Initially quite dumb,
            but instances of this class will become "better populated"
            with attributes later on. The scan processor for example
            adds the image data and scan parameters
        """
        # status: a dict, where processors can put display
        # informations about the scan status
        global _jobid
        self.id = _jobid
        _jobid += 1
        self.owner = owner
        
        self.orig_id = orig_id or self.id
        
        self.status = {}
        self.active = False
        if copies is None:
            self.copies = []
        else:
            self.copies = copies
        self.copies.append(weakref.ref(self))
        self.deleted = False
        add_joblist(self)
    
    def copy(self):
        """return a copy of self. called by processsors
           which have more than one output.
        """ 
        res = SaneScanJob(self.owner, self.orig_id, self.copies)
        
        # check that we know about all attributes
        test = self.__dict__.keys()
        test = [x for x in test if not x in _jobattr]
        if test:
            raise SaneError("SaneScanJob.copy: unexpected attributes: %s" % \
                            repr(test))
        if hasattr(self, 'img'):
            res.img = self.img.copy()
        
        for name in _seqattr:
            if hasattr(self, name):
                setattr(res, name, getattr(self, name)[:])
        for name in _simpleattr:
            if hasattr(self, name):
                setattr(res, name, getattr(self, name))
        
        return res
    
    def has_error(self):
        return hasattr(self, 'error')
    
    def set_active(self, v):
        self.active = v
    
    def is_active(self):
        return self.active



def add_joblist(job):
    for i in xrange(len(_joblist)-1, -1, -1):
        test = _joblist[i]()
        if test is None:
            _joblist.pop(i)
    _joblist.append(weakref.ref(job))

def mark_deleted(min_id):
    for i in xrange(len(_joblist)-1, -1, -1):
        job = _joblist[i]()
        if job is None:
            _joblist.pop(i)
        elif job.id >= min_id:
            job.deleted += 1

class SaneInputProducer:
    def __init__(self):
        pass
    
    def next_job(self):
    	""" called by the processor, when it has finished a job and
    	    is ready to accept a new job.
    	"""
    	raise SaneError("SaneInputProducer.next_job must be overloaded")


class SaneProcessorNotifyHub(gobject.GObject):
    """ We have several more or less independently working processors,
        without any own display, but these processors must be able
        to notify a display widget about a scan job.
        
        This class provides a "signal emitter", to which display
        widgets can connect.
        
        The signal name is "sane-jobinfo"
        
        We must also be aware of threading. Hence this class 
        uses (obviously thread-safe) function gobject.idle_add to emit 
        a signal, instead of emitting it directly.
    """
    def __init__(self):
        gobject.GObject.__init__(self)
    
    def notify(self, msg, job, proc):
        gobject.idle_add(_Notify(self, msg, job, proc))
    

class _Notify:
    def __init__(self, hub, msg, job, proc):
        self.hub = hub
        self.msg = msg
        self.job = job
        self.proc = proc

    def __call__(self):
        self.hub.emit('sane-jobinfo', self.msg, self.job, self.proc)

# parameters:
# 1: info type, string, from _displayaction.keys()
# 2: SaneScanJob instance
# 3: processor emitting the signal
gobject.signal_new('sane-jobinfo', SaneProcessorNotifyHub,
                   gobject.SIGNAL_RUN_FIRST | gobject.SIGNAL_ACTION,
                   gobject.TYPE_NONE,
                   (gobject.TYPE_PYOBJECT,
                    gobject.TYPE_PYOBJECT,
                    gobject.TYPE_PYOBJECT, ))


class SaneProcessor(gobject.GObject):
    def __init__(self, input_producer, notify_hub):
        """ input_producer: an instance of class InputProducer
            abstract base class
        """
        gobject.GObject.__init__(self)
        self.input_producer = input_producer
        self.output = []
        self.notify_hub = notify_hub
        self.errorjobs = []
        
    def append(self, job):
        """ called by the input processor to append a new job.
            raises an exception, if jobs cannot be appended
        """
    	raise SaneError("SaneProcessor.append must be overloaded")
    
    def can_append(self, job):
    	""" True, if jobs can be appended, else false
    	"""
    	raise SaneError("SaneProcessor.can_append must be overloaded")
    
    def numjobs(self, cascade):
        """ return the number of jobs queued in the instance.
            If cascade is true, add the number of all jobs in 
            following processors
        """
    	raise SaneError("SaneProcessor.jobs must be overloaded")
    
    def delete_job(self, job):
        """ delete a queued job, and all job which a farther 
            back in the queued (i.e., those with larger IDs)
        """
        raise SaneError("SaneProcessor.delete_job must be overloaded")
    
    def delete_from_id(self, id):
        """ delete a queued job, and all job which a farther 
            back in the queued (i.e., those with larger IDs)
        """
        raise SaneError("SaneProcessor.delete_from_id must be overloaded")

    def retry_job(self):
        """ retry a job which resulted in an error
        """
        raise SaneError("SaneProcessor.delete_jobs must be overloaded")
    
    def add_output(self, processor):
        """ add an output instance. processor is a SaneProcessor instance
        """
        self.output.append(processor)
    
    def remove_output(self, processor):
        """ remove a processor from the list of outputs. If the processor
            is not listed in the output list, silently ignore it
        """
        for i in range(len(self.output)-1, -1, -1):
            if self.output[i] == processor:
                self.output.pop(i)
    
    def get_output(self):
        """ return a copy of the list of outputs
        """
        return self.output[:]
        
    def set_notify_hub(self, notify_hub):
        self.notify_hub = notify_hub
    
    def notify(self, msg, job):
        if self.notify_hub:
            self.notify_hub.notify(msg, job, self)
    
    def can_retry(self, job):
        """ check, if a job in error status can be re-queued
            Should be overloaded by derived classes
        """
        return False

    def retry_job(self, job):
        """ retry a job. If successful, return True, else False
        """
        return False
    
    def can_edit(self, job):
        """ check, if a job in error status can be edited
            Should be overloaded by derived classes
        """
        return False

    def edit_job(self, job):
        """ edit a job. If successful, return True, else False
        """
        return False
    
    def set_input(self, input):
        if self.input_producer:
            self.input_producer.remove_output(self)
        self.input_producer = input
        if input:
            input.add_output(self)

    def send_toOutput(self, job):
        """ send the job to all defined outputs
        """
        raise SaneError("SaneProcessor.send_toOutput must be overloaded")
    	
class SaneQueueingProcessor(SaneProcessor):
    """ variant of SaneProcessor which implements "real" queueing
    """
    def __init__(self, input_producer, notify_hub, queue_length):
        SaneProcessor.__init__(self, input_producer, notify_hub)
        self.queue = []
        self.queue_length = queue_length
    
    def append(self, job):
        if self.can_append(job):
            self.queue.append(job)
            job.owner = self
            return
        raise SaneError("SaneQueueingProcessor.append: queue full")
    
    def can_append(self, job):
        return len(self.queue) < self.queue_length
    
    def numjobs(self, cascade):
        res = len(self.queue)
        if cascade:
            for o in self.output:
                res += o.numjobs(True)
        return res

    def send_toOutput(self, job):
        res = True
        if self.output:
            olist = self.output[:]
            # try for 60 seconds to queue the job
            for i in xrange(1200):
                if job.deleted:
                    self.notify('removed', job)
                    res = False
                    olist = []
                    break
                for j in xrange(len(olist)-1, -1, -1):
                    o = olist[j]
                    if o.can_append(job):
                        if len(olist) > 1:
                            newjob = job.copy()
                            self.notify('new job', newjob)
                            o.append(newjob)
                            # appending can fail. Example: No output enabled.
                            # The we must notify the job deletion here
                            if newjob.owner == self:
                                self.notify('removed', newjob)
                        else:
                            o.append(job)
                        olist.pop(j)
                if not olist:
                    break
                time.sleep(0.05)
            if olist:
                raise SaneError('output queue(s) blocked')
        return res
    

class SaneThreadingQueueingProcessor(SaneQueueingProcessor, SaneThread.Thread):
    """ SaneQueueingProcessor with threading support. The thread
        NOT automatically started!
    """
    def __init__(self, input_producer, notify_hub, queue_length):
        SaneQueueingProcessor.__init__(self, input_producer, notify_hub,
                                       queue_length)
        SaneThread.Thread.__init__(self)
        self.queuelock = threading.RLock()
    
    def append(self, job, blocking=1):
        if self.queuelock.acquire(blocking):
            try:
                SaneQueueingProcessor.append(self, job)
            finally:
                self.queuelock.release()
    
    def can_append(self, job):
        return (len(self.queue) < self.queue_length)

    def delete_from_id(self, id):
        # delete all jobs with a job ID >= id
        # Start with the largest ID
        self.input_producer.delete_from_id(id)
        self.queuelock.acquire()
        queue = self.queue
        dellist = [(x, queue) for x in queue if x.id >= id]
        errlist = self.errorjobs
        dellist += [(x, errlist) for x in errlist if x.id >= id]
        dellist.sort(lambda x,y: cmp(y[0].id, x[0].id))
        for j,l in dellist:
            i = l.index(j)
            l.pop(i)
            self.notify('removed', j)
        self.queuelock.release()
    
    def delete_job(self, job):
        for j in job.copies:
            j = j()
            if j is not None:
                mark_deleted(j.id)
                j.owner.delete_from_id(j.orig_id)

    def numjobs(self, cascade):
        self.queuelock.acquire()
        res = len(self.queue) + len(self.errorjobs)
        self.queuelock.release()
        if cascade:
            for o in self.output:
                res += o.numjobs(True)
        return res
    


class SaneScannerControl(SaneThreadingQueueingProcessor, SaneInputProducer):
    def __init__(self, device, input_producer, notify_hub, queue_length):
        """ device: gtkWidgets.SaneDevice instance
        """
        SaneThreadingQueueingProcessor.__init__(self, input_producer, 
                                                notify_hub, queue_length)
        SaneInputProducer.__init__(self)
        self.device = device
        self.output = []
        self.errorjobs = []
        self.start()
        self.status = 0 # idle
        # track the "duplex status": We must know, if the next
        # scan will be a backside duplex scan
        self.duplex_scanner_status_backside = False
        # ... and if the next queued job will be a backside scan
        self.duplex_input_backside = False
        # debugging: check, if restarting a backside scan in duplex
        # mode works. Set to True for to force an error
        self.TEST = False
    
    def can_append(self, job):
        return SaneThreadingQueueingProcessor.can_append(self, job) and not self.errorjobs
    
    def append(self, job):
        job.duplex_status_backside = self.duplex_input_backside
        SaneThreadingQueueingProcessor.append(self, job)
        if self.device.duplex_mode():
            self.duplex_input_backside = not self.duplex_input_backside
        job.status['scan'] = _('waiting for scan')
        self.notify('new job', job)
    
    def reset_duplex(self, input):
        """ reset the duplex status. If input is True, reset both
            duplex_input_backside and duplex_scanner_status_backside,
            else only duplex_scanner_status_backside
        """
        self.duplex_scanner_status_backside = False
        if input:
            self.duplex_input_backside = False
    
    def run(self):
        while not self.abort:
            if len(self.queue) and not self.errorjobs:
                if DEBUG:
                    print "starting scan", self.queue[0].id
                self.queuelock.acquire()
                job = self.queue.pop(0)
                self.status = 1 # scanning
                self.queuelock.release()
                job.set_active(True)
                try:
                    job.status['scan'] = _('scanning')
                    self.notify('status changed', job)
                    # collect relevant scan information
                    job.scanwindow = (self.device.tl_x, self.device.br_x,
                                           self.device.tl_y, self.device.br_y)
                    job.resolution = self.device._device.resolution
                    if 'y_resolution' in self.device.getOptionNames():
                        job.y_resolution = self.device._device.y_resolution
                    else:
                        job.y_resolution = self.device._device.resolution
                    
                    if self.TEST and self.duplex_scanner_status_backside:
                        # xxx test: force an error to see, if requeueing a
                        # a backside job works as expected
                        self.TEST = False
                        raise "duplex requeueing test"
                        
                    # paranoia: make sure that the duplex status of the scanner
                    # stays synchronous with the status as "thought of" by this
                    # class. Unfortunately, the Sane standard has no way to
                    # tell for duplex scanners, if the next start()/snap() calls
                    # will deliver front side or back side data, neither 
                    # provides any backend for duplex scanners an option 
                    # that would allow to get the actual scanner status.
                    # So let's "reset" the backend before each frontside 
                    # scan. A sane_cancel flushes possibly buffered 
                    # "back side data"
                    if not self.duplex_scanner_status_backside:
                        self.device._device.cancel()
                    
                        # now we may have the (admittedly unlikely) situation
                        # that a job for backside data is requeued, without the
                        # corresponding front side job being requeued. Not all
                        # backends for duplex scanners support backside-only
                        # scans, so we start the frontside scan too, but omit 
                        # the data
                        if job.duplex_status_backside:
                            print "dropping front side data"
                            self.device._device.start()
                            self.duplex_scanner_status_backside = \
                                not self.duplex_scanner_status_backside
                            # no check, if no_cancel is supported:
                            # duplex scans are reasonable only for PIL.sane
                            # version that DO support this mode.
                            junk = self.device._device.snap(no_cancel=1)
                            junk.save('TEST.tif')
                    
                    # we must call this before sane_start, because 
                    # not all backends allow to read an option AFTER
                    # a scan has been started.
                    in_duplex_mode = self.device.duplex_mode()

                    self.device._device.start()

                    if in_duplex_mode:
                        self.duplex_scanner_status_backside = \
                            not self.duplex_scanner_status_backside
                    # FIXME: terrible workaround...
                    # We want to use the no_cancel option, but it is
                    # no everywhere available: a quite recent bugfix
                    # -> "enforce" usage of sufficiently recent version
                    # of the sane module??
                    try:
                        img = self.device._device.snap(no_cancel=1)
                    except TypeError, val:
                        if str(val) == "snap() got an unexpected keyword argument 'no_cancel'":
                            img = self.device._device.snap()
                        else:
                            raise
                    # the sane module delivers a gray scale image even for
                    # lineart scans. 
                    if self.device._device.mode.lower() in ('lineart',
                                                            'halftone'):
                        img = img.convert('1')
                    job.img = img
                    job.status['scan'] = _("scanned")
                    self.notify('status changed', job)
                    queue_ok = self.send_toOutput(job)
                    if job.owner == self:
                        self.notify('removed', job)

                    if self.can_append(None) and queue_ok:
                        self.input_producer.next_job()
                        
                except:
                    job.error = sys.exc_info()
                    job.set_active(False)
                    job.status['scan'] = _('scan error')
                    self.notify('status changed', job)
                    self.queuelock.acquire()
                    self.errorjobs.append(job)
                    self.queuelock.release()
                    if DEBUG:
                        print str(job.error[0]), str(job.error[1])
                        traceback.print_tb(job.error[2])
                self.status = 0 # idle
                if DEBUG:
                    print "scan finished", job.id
            else:
                time.sleep(0.1)

    def numjobs(self, cascade):
        self.queuelock.acquire()
        res = len(self.queue) + len(self.errorjobs)
        if self.status != 0:
            res += 1
        self.queuelock.release()
        if cascade:
            for o in self.output:
                res += o.numjobs(True)
        return res
    
    def retry_job(self, job):
        res = False
        self.queuelock.acquire()
        for i in xrange(len(self.errorjobs)):
            if job == self.errorjobs[i]:
                self.errorjobs.pop(i)
                del job.error 
                # scan jobs should be processed in the sequence of their
                # job ids
                self.queue.append(job)
                self.queue.sort(lambda x,y: cmp(x.id, y.id))
                res = True
                break
        self.queuelock.release()
        self.reset_duplex(False)
        return res
    
    def delete_job(self, job):
        # reset the duplex status. Otherwise, the duplex logic will
        # out of sync
        self.reset_duplex(True)
        SaneThreadingQueueingProcessor.delete_job(self, job)
    
    def can_retry(self, job):
        """ check, if a job in error status can be re-queued
            Should be overloaded by derived classes
        """
        return job in self.errorjobs


