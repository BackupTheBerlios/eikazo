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

    we use at least two long running threads. This means
    that we must catch signals in order to shut down these
    threads properly.
    
    Also, we watch all uncaught exceptions in order to shut down threads
    properly, if any thread has raised an exception
"""
import threading, sys, time, signal
import traceback
import gtk

DEBUG=1
def showErrorInfo(error, where):
    # error: What is returned by sys.exc_info()
    # error type, error value, traceback
    # FIXME: write to stderr!
    klass, value, tb = error
    sys.stderr.write("error in %s\n" % where)
    sys.stderr.write("%s: %s\n" % (str(klass), str(value)))
    traceback.print_tb(tb)


def install_handlers():
    """
      ScanManager is a long running thread, hence we must install
      signal handlers in the main thread so that a scan manager
      thread can be told to terminate, if a signal is sent to the main 
      thread
      
      Override this method, if you need a more specialized singal handling
      
      This handler lets all signals except SIGPIPE, SIGCHLD, SIGKILL,
      SIGSTOP terminate the thread
    """
    signames = signal.__dict__.keys()
    signames = [x for x in signames if x[:3] == 'SIG']
    signames = [x for x in signames if x[3] != '_']
    signames = [x for x in signames if not x in ('SIGCHLD', 'SIGCLD',
                                                 'SIGPIPE', 'SIGKILL',
                                                 'SIGSTOP')]
    
    for name in signames:
        sig = signal.__dict__[name]
        # more than one signal name may map to the same signal number,
        # so we must ignore duplicates in order to create a recursive
        # call of "our" handler
        print "signal", name, sig
        if not _lasthandler.has_key(sig):
            _lasthandler[sig] = signal.getsignal(sig)
            signal.signal(sig, thrdhandler)

def thrdhandler(sig, frame):
    print "caught signal", sig, frame
    for thread in threads:
        thread.abort = 1
    l = _lasthandler[sig]
    if l == signal.SIG_DFL:
        # FIXME: this leads to a misleading exception/error message.
        # Unfortnately,I don't know any simple way to invoke the "real" 
        # default signal handler
        signal.default_int_handler(sig, frame)
    elif l != signal.SIG_IGN:
        l(sig, frame)

def abort_threads():
    for thread in _threads:
        thread.abort = 1

def excepthook(typ, value, tb):
    for thread in _threads:
        thread.abort = 1
        print "exception caught: thread aborted", thread
    return _old_excepthook(typ, value, tb)



class Thread(threading.Thread):
    def __init__(self, *args, **kw):
        threading.Thread.__init__(self, *args, **kw)
        _threads.append(self)
        self.abort = 0

_threads = []
_lasthandler = {}
_old_excepthook = sys.excepthook
sys.excepthook = excepthook
gtk.gdk.threads_init()
mainthread = threading.currentThread()
