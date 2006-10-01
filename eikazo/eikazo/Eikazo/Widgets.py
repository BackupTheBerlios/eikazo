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

provides PyGTK based widgets which control sane backends

"""

import sys, os
import threading
import sane
import gtk, gobject
import Config, I18n, Curve

t = I18n.get_translation('sane-backends')
if t:
    T2_ = t.gettext
else:
    T2_ = lambda x: x
    
t2 = I18n.get_translation('eikazo')
if t2:
    _ = t2.gettext
else:
    _ = lambda x: x

# strings needing translations in the eikazo domain, but which
# should _not_ be replaced dynamically
def N_(x):
    return x


sane.init()

# these constants should be defined in _sane.c ...
SANE_TYPE_BOOL   = 0
SANE_TYPE_INT    = 1
SANE_TYPE_FIXED  = 2
SANE_TYPE_STRING = 3
SANE_TYPE_BUTTON = 4
SANE_TYPE_GROUP  = 5

SANE_UNIT_NONE		= 0
SANE_UNIT_PIXEL		= 1
SANE_UNIT_BIT		= 2
SANE_UNIT_MM		= 3
SANE_UNIT_DPI		= 4
SANE_UNIT_PERCENT	= 5
SANE_UNIT_MICROSECOND	= 6
 

class EikazoWidgetError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return self.value

class SaneWidgetConfig(Config.ConfigAware):
    def __init__(self, config):
        Config.ConfigAware.__init__(self, config)
        self.section = 'device'
        self.delayedConfigValue = None
        self.readConfig()
    
    def readConfig(self):
        opts = self.device.getOptions()
        opt = [x for x in opts if x[9] == self.optname][0]
        opttype = opt[4]
        optcap = opt[7]
        opt = self.device._device.opt[self.optname]
        # FIXME: check for arrays!
        
        # FIXME: can a button be settable??
        if opttype in (SANE_TYPE_BOOL, SANE_TYPE_BUTTON):
            val = self.config.getboolean(self.section, self.optname)
        elif opttype == SANE_TYPE_INT:
            # float and int options max change from backend to backend
            # so let's read floats in any case
            val = self.config.getfloat(self.section, self.optname)
            if  val != None:
                val = int(val)
        elif opttype == SANE_TYPE_FIXED:
            val = self.config.getfloat(self.section, self.optname)
        elif opttype == SANE_TYPE_STRING:
            val = self.config.get(self.section, self.optname)
        if val != None:
            if opt.is_settable():
                if opt.is_active():
                    # we may get an error, if we load a config that
                    # has been saved for device 1, and open the config
                    # for device 2. In this case, the value of an option
                    # may not be valid for device 2. 
                    # Example: The source option may have values
                    # like 'ADF' or 'ADF Front', but the selected scanner
                    # does not have an ADF installed, or a value
                    # with the same or a similar meaning is different:
                    # 'ADF' vs. 'Automatic Document Feeder'.
                    # Silently ignore these errors
                    try:
                        self.device._device.__setattr__(self.optname, val)
                    except sane._sane.error, errval:
                        if str(errval) != 'Invalid argument':
                            raise
                else:
                    # FIXME: must be updated in Reload!!!
                    self.delayedConfigValue = val
            self.Reload()
    
    def writeConfig(self):
        opts = self.device.getOptions()
        opt = [x for x in opts if x[9] == self.optname][0]
        opttype = opt[4]
        optcap = opt[7]
        opt = self.device._device.opt[self.optname]
        
        # FIXME check for arrays!
        if optcap & opt.is_settable():
            if opt.is_active():
                val = self.device._device.__getattr__(self.optname)
            elif self.delayedConfigValue != None:
                val = self.delayedConfigValue
            else:
                # inactive option: we'll use the value stored
                # in in the GUI widget
                val = self.guiValue()
            self.config.set(self.section, self.optname, str(val))

class DeviceSelectionDialog(gtk.Dialog):

    def __init__(self, title=N_("Select a Scanner"), parent=None, flags=0):
        self.devs = sane.get_devices()
        #print self.devs
        #print [x[1:4] + x[:1] for x in self.devs]
        gtk.Dialog.__init__(self, title, parent, flags, 
                            (gtk.STOCK_OK, gtk.RESPONSE_ACCEPT,
                             gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT))
        
        self.sel = gtk.combo_box_new_text()
        #print self.sel.get_property("model")
        for dev in self.devs:
            self.sel.append_text('%s %s (%s)' % (dev[1:3] + dev[:1]))
        
        self.sel.set_active(0)
      
        self.vbox.pack_start(self.sel)
        self.sel.show()
    
    def getSelectedDeviceName(self):
        return self.devs[self.GetSelection()][0]
    
    def run(self):
        """ returns None, if "cancel" has been clicked, or the Sane device
            name of the selected device
        """
        res = gtk.Dialog.run(self)
        if res == gtk.RESPONSE_ACCEPT:
            return self.devs[self.sel.get_active()][0]
        return None

def getDeviceName(parent=None):
    """ show a DeviceSelectionDialog and return None or a Sane device name
    """
    d = DeviceSelectionDialog(parent=parent)
    res = d.run()
    d.destroy()
    return res


def getDevice(parent=None):
    """ Convenience function. 
        
        If no device is availabale, return 0
        If exactly one device is available, return a SaneDevice instance
           for this scanner
        If more devices are available, open a device selection dialog,
          and return a SaneDevie instance for the selected device, or
          None, it the user aborts the selection
    """
    devs = sane.get_devices()
    l = len(devs)
    if not l:
        return 0
    if l == 1:
        return SaneDevice(devs[0][0])
    name = getDeviceName(parent)
    if name:
        return SaneDevice(name)
    return None

class SaneDevice(gobject.GObject):
    """ manages communication between a Sane device and WXWidgets.
        All widgets used to control a canner should be created via
        method of this class
    """
    
    def __init__(self, devicename):
        gobject.GObject.__init__(self)
        self._device = sane.open(devicename)
        self._widgets = {}
        self._devicelock = threading.RLock()
        self._tooltips = gtk.Tooltips()
        self.mainthread = threading.currentThread()
        self.devicename = devicename
    
    # a few very common Sane options may be read and set directly
    # This makes the synchronization with higher level widgets like
    # a preview window easier
    _deviceattrnames =  ('tl_x', 'br_x', 'tl_y', 'br_y')
    # When the device is scanning, we may not be able to access
    # the options. Some Sane backends return an error in this case.
    # Hence we cache the most important options
    _cachedattr = {}
    def __getattr__(self, key):
        if key in self._deviceattrnames:
            if self._devicelock.acquire(0):
                try:
                    # FIXME:
                    # at least with the test backend, this raises from time
                    # to time _sane.error: Invalid argument. No
                    # idea why... This is not a good workaround...
                    res = self._device.__getattr__(key)
                    self._cachedattr[key] = res
                except sane._sane.error:
                    res = self._cachedattr[key]
                self._devicelock.release()
                return res
            return self._cachedattr[key]
        d = self.__dict__
        if key in d.keys():
            return d[key]
        raise AttributeError, "no such attribute %s" % key
    
    def __setattr__(self, key, value):
        if key in self._deviceattrnames:
            if self._devicelock.acquire(0):
                self._device.__setattr__(key, value)
                self._cachedattr[key] = self._device.__getattr__(key)
                self._devicelock.release()
            else:
                # FIXME: should be impossible to change options during
                # scans. The affected widgets should be disabled
                # during scans.
                raise EikazoWidgetError("can't acquire device lock")
            if self.__dict__['_widgets'].has_key(key):
                for w in self.__dict__['_widgets'][key]:
                    w.Reload()
                return
        self.__dict__[key] = value
    
    def _registerWidget(self, name, widget):
        if self._widgets.has_key(name):
            self._widgets[name].append(widget)
        else:
            self._widgets[name] = [widget]
    
    def widgets(self, optname):
        """ return the widgets controlling the option optname
        """
        return self._widgets.get(optname, [])
    
    def getOptions(self):
        """ a trivial wrapper for Sane.SaneDev.get_options.
        Returns a list of tuples describing all the available options.
        
        A tuple consists of:
          - [0] the option number 	(integer)
          - [1] name			(string)
          - [2] title			(string)
          - [3] description		(string)
          - [4] type 			integer, with the following meaning:
                        0	SANE_TYPE_BOOL
                        1	SANE_TYPE_INT
                        2	SANE_TYPE_FIXED
                        3	SANE_TYPE_STRING
                        4	SANE_TYPE_BUTTON
                        5	SANE_TYPE_GROUP
                        (see Sane API doc, section 4.2.9.4)
          - [5] unit	integer, with the following meaning:
                    0	SANE_UNIT_NONE
                    1	SANE_UNIT_PIXEL
                    2	SANE_UNIT_BIT
                    3	SANE_UNIT_MM
                    4	SANE_UNIT_DPI
                    5	SANE_UNIT_PERCENT
                    6	SANE_UNIT_MICROSECOND
                    (see Sane API doc, section 4.2.9.5)
          - [6] size	integer, with the following meaning:
                    for SANE_TYPE_STRING options: 
                      max length of the string
                    for SANE_TYPE_INT, SANE_TYPE_FIXED:
                      "vector length": number of option values, mulptplied by
                      sizeof(SANE_Word) this should be "scaled down"
                      to the "real" vector length
                    for SANE_TYPE_BOOL options:
                      must be sizeof(SANE_Word)
                    for SANE_TYPE_BUTTON, SANE_TYPE_GROUP:
                      not used
          - [7] cap		integer
                    bitset:
                    1	SANE_CAP_SOFT_SELECT, The option value can be set by 
                        a call to sane_control_option()
                    2	SANE_CAP_HARD_SELECT.  	 The option value can be set 
                        by user-intervention (e.g., by flipping a switch). The 
                        user-interface should prompt the user to execute the 
                        appropriate action to set such an option. This 
                        capability is mutually exclusive with 
                        SANE_CAP_SOFT_SELECT (either one of them can be set, 
                        but not both simultaneously).
                    4	SANE_CAP_SOFT_DETECT The option value can be detected 
                        by software. If SANE_CAP_SOFT_SELECT is set, this 
                        capability must  be set. If SANE_CAP_HARD_SELECT is set, 
                        this capability may or may not be set. If this capability 
                        is set but neither SANE_CAP_SOFT_SELECT nor 
                        SANE_CAP_HARD_SELECT  are, then there is no way to 
                        control the option. That is, the option provides read-out
                        of the current value only. 
                    8	SANE_CAP_EMULATED. If set, this capability indicates that
                        an option is not directly supported by the device and is 
                        instead emulated in the backend. A sophisticated frontend
                        may elect to use its own (presumably better) emulation in
                        lieu of an emulated option.
                    16	SANE_CAP_AUTOMATIC.  If set, this capability indicates 
                        that the backend (or the device) is capable to picking a 
                        reasonable option value automatically. For such options, 
                        it is possible to select automatic operation by calling 
                        sane_control_option()  with an action value of 
                        SANE_ACTION_SET_AUTO.
                    32	SANE_CAP_INACTIVE. If set, this capability indicates that
                        the option is not currently active (e.g., because it's 
                        meaningful only if another option is set to some other 
                        value).
                    64	SANE_CAP_ADVANCED. If set, this capability indicates that
                        the option should be considered an ``advanced user 
                        option.'' A frontend typically displays such options in 
                        a less conspicuous way than regular options (e.g., a 
                        command line interface may list such options last or a 
                        graphical interface may make them available in a seperate
                        ``advanced settings'' dialog).
          - [8] constraint
                    None, if the option has no constraint
                    tuple of length 3 for SANE_CONSTRAINT_RANGE: min, max, quant
                      int values for SANE_TYPE_INT options
                      float values for SANE_TYPE_FIXED options 
                    list of numeric or string values.
                      numeric values are ints for SANE_TYPE_INT options and 
                      floats for SANE_TYPE_FIXED options
          - [9] python name The is the same as name, except that '-' characters
                    are replaced by '_'
        """
        res = self._device.get_options()
        res = [list(x) for x in res]
        # The Sharp backend for example does not provide option names
        # for group options, only titles.
        [x.append(x[1] and x[1].replace('-', '_') or x[1]) for x in res]
        return [tuple(x) for x in res]
          
    def getGroupedOptionNames(self):
        """ return a list of tuples ('group name', ['group member',...])
        """
        optlist = self.getOptions()
        if optlist[0][4] == SANE_TYPE_GROUP:
            groupname = optlist[0][2]
            optlist.pop(0)
        else:
            groupname = ''
        res = []
        l = []
        for opt in optlist:
            if opt[4] == SANE_TYPE_GROUP:
                res.append((groupname, l))
                groupname = opt[2]
                l = []
            else:
                l.append(opt[-1])
        res.append((groupname, l))
        return res
        
    
    def getOptionNames(self):
        """ return the list of available device options
        """
        return self._device.optlist
    
    def _showOptInfo(self, opt, optname):
        print "-----------------------"
        print "opt name", optname
        opt = self._device.opt[optname]
        print "index", opt.index
        print "type", opt.type
        print "unit", opt.unit
        print "size", opt.size
        print "cap", opt.cap
        print "constraint", opt.constraint
        print "enabled", opt.is_active()

    def createOptionWidget(self, optname, config, optwidget='default', **kw):
        """ return an appropriate widget for a device option. optnum
            is the number of the option as returned by GetOptions()
        """
        opt = self._device.opt[optname]
        if opt.type == SANE_TYPE_BOOL:
            if opt.is_settable():
                res = CheckButton(optname, self, config, **kw)
            else:
                # we can have the funny case that an option has the capability
                # SANE_CAP_HARD_SELECT, but not SANE_CAP_SOFT_DETECT,
                # i.e., that is_settable() returns false.This
                # means that the option is set by hardware, and can't be
                # read by software. In other words, it is completely
                # useless for a program ;) This is true for test backend,
                # option bool_hard_select. We'll simply ignore such an option.
                if opt.cap & sane._sane.CAP_SOFT_DETECT == 0:
                    return None
                res = BoolDisplay(optname, self, **kw)
            self._registerWidget(optname, res)
            return res
        elif opt.type in (SANE_TYPE_FIXED, SANE_TYPE_INT):
            # slider for range constraints; choicebox for list constraints,
            # textfield no non-constraint values
            # FIXME: check for arrays!!!
            
            # check, if we have a single value or an array. The value
            # of opt.size is platform dependent (quote from from the Sane
            # API doc: " The size must be a positive integer multiple of 
            # the size of a SANE_Word. The option value is a vector of length
            # size/sizeof(SANE_Word)", so we'll use the Python type
            
            constr = opt.constraint

            # FIXME: the sane module returns the option size as specified
            # by the backend, i.e., for SANE_Word, SANE_Int in multiples
            # of sizeof(SANE_Word). This is not of much value in Python:
            # here, we don't know the value of sizeof(SANE_Word).
            # we need a function in the C extension that tells us the
            # size.
            if 0:
                if opt.size > 1:
                    if type(constr) == type(()):
                        print "xxx cCURVES DISABLED"
                        return None
                        res = SaneCurve(optname, self, config, **kw)
                    elif type(constr) == type([]):
                        # FIXME: might be reasonable to build a table of
                        # choiceboxes for shorter lists
                        print "can't build a widget for a float/integer list with selection constraint"
                        return None
                    else:
                        # hrmm. What to do here?
                        print "can't build a widget for a float/integer list without constraint"
                        return None
            
            elif type(constr) == type(()):
                minValue = constr[0]
                maxValue = constr[1]
                if optwidget in ('default', 'hscale'):
                    res = HScale(optname, self, config, **kw)
                elif optwidget == 'labeled hscale':
                    res = HScalePanel(optname, self, config, **kw)
                elif optwidget == 'vscale':
                    res = VScale(optname, self, config, **kw)
                elif optwidget == 'labeled vscale':
                    res = VScalePanel(optname, self, config, **kw)
                elif optwidget == 'number field':
                    res = NumberField(optname, self, config, **kw)
                elif optwidget == 'labeled number field':
                    res = LabeledNumberField(optname, self, config, **kw)
                else:
                    raise EikazoWidgetError(
                      'invalid widget type for integer or fixed widget: %s %s' \
                      % (opt.name, optwidget))
            elif type(constr) == type([]):
                if optwidget in ('default', 'choice'):
                    res = Choice(optname, self, config, **kw)
                elif optwidget == 'labeled choice':
                    res = LabeledChoice(optname, self, config, **kw)
                else:
                    raise EikazoWidgetError(
                      'invalid widget type for integer or fixed widget: %s %s' \
                      % (opt.name, optwidget))
            else:
                res = NumberField(optname, self, config, **kw)
            self._registerWidget(optname, res)
            return res
        elif opt.type == SANE_TYPE_STRING:
            # right now, we'll support only selection lists, i.e., 
            # the constraint type must be a list
            constr = opt.constraint
            if type(constr) == type([]):
                if optwidget in ('default', 'choice'):
                    res = Choice(optname, self, config, **kw)
                elif optwidget == 'labeled choice':
                    res = LabeledChoice(optname, self, config, **kw)
                else:
                    raise EikazoWidgetError(
                      'invalid widget type for integer or fixed widget: %s %s' \
                      % (opt.name, optwidget))
                self._registerWidget(optname, res)
                return res
            res = StringOption(optname, self, config, **kw)
            self._registerWidget(optname, res)
            return res
        elif opt.type == SANE_TYPE_BUTTON:
            res = Button(optname, self, **kw)
            self._registerWidget(optname, res)
            return res
        elif opt.type == SANE_TYPE_GROUP:
            # this is a "layout hint"; should be handled externally
            return None
        # self._showOptInfo(opt, optname)
        raise EikazoWidgetError("unknown option type %i" % opt.type)
    
    def reloadOptions(self):
        # reload device options. Happens for example, if the scan mode
        # changes from bi-level to gray scale. For gray scale, setting 
        # the threshold is disabled by most backends
        for wlist in self._widgets.values():
            for w in wlist:
                w.Reload()
        self.geometryChanged()
    
    def enable_options(self, value):
        """ enable or disable the option widgets. 
            Must be called before starting a scan and after the end of
            a scan. Many backends refuse to allow the change of options
            during a scan.
        """
        if threading.currentThread() == self.mainthread:
            self._enable_options(value)
        else:
            gtk.gdk.threads_enter()
            self._enable_options(value)
            gtk.gdk.threads_leave()
        
    
    def _enable_options(self, value):
        for wlist in self._widgets.values():
            for w in wlist:
                w.enable_option(value)
    
    def getMaxScanArea(self):
        """ return the max size of the scan area (tlx, brx, tly, bry)
            The units are millemeters, if the resolution can be determined.
            Otherwise, the default unit is returned
        """
        res = getattr(self, '_scanarea', None)
        if res: return res
        found = 0
        resol = None
        for opt in self.getOptions():
            if opt[1] == 'tl-x':
                found |= 1
                tlx = opt
                if found == 31: break
            if opt[1] == 'tl-y':
                found |= 2
                tly = opt
                if found == 31: break
            if opt[1] == 'br-x':
                found |= 4
                brx = opt
                if found == 31: break
            if opt[1] == 'br-y':
                found |= 8
                bry = opt
                if found == 31: break
            elif opt[1] == 'resolution':
                found |= 16
                resol = opt
                if found == 31: break
        
        if (found & 15) != 15:
            # the backend does not provide at least some parameters
            # of the scan area. example: camera backends. This means that
            # the scan window can not be set, and the scan siz can be
            # retrieved by calling get_parameters. FIXME: This is not
            # necessarily true: A counter example would be a backend
            # which allows to set the paper size but not tl_x, br_x etc
            
            format, last_frame, (ppl, lines), depth, bpl \
                = self._device.get_parameters()
            
            self._scanarea = (0, ppl, 0, lines)
            return self._scanarea
        
        
        if resol:
            resol = self._device.resolution
        self._scanarea = (_millimeters(_getMinConstraint(tlx), tlx, resol),
                          _millimeters(_getMaxConstraint(brx), brx, resol),
                          _millimeters(_getMinConstraint(tly), tly, resol),
                          _millimeters(_getMaxConstraint(bry), bry, resol))
        return self._scanarea
    
    def geometryChanged(self):
        self.emit("sane-geometry")
    
    def reloadParams(self):
        self.emit("sane-reload-params")
    
    def adf_mode(self):
        """ check, if an ADF is available and selected
            returns or True or False
        """
        # FIXME: is the list of possible strings which "indicate" an
        # ADF complete or not??
        # FIXME: If we have an ADF scanner without a "source" option,
        # or an inactive "source" option, False will be returned. 
        # That's not, what we want... I don't see another way to detect
        # an ADF, and if it is enabled, except from the 'source' option...
        # A candidate from this case is for example the fi-5110
        # PROBLEM: We can't read inactive options...
        
        # grepping the Sane backend sources, the following ways exist
        # to select and detect an ADF:
        #
        # option source has one of the values:
        #   'ADF'                       (avision, hp, microtek2, sp15c)
        #   'ADF Rear'                  (avision)
        #   'ADF Duplex'                (avision, fujitsu)
        #   'ADF Front'                 (fujitsu)
        #   'ADF Back'                  (fujitsu)
        #   'Automatic Document Feeder' (bh, epson, mustek, nec, pixma,
        #                                sharp, umax)
        #   'Document Feeder'           (snapscan)
        #   'Filmstrip'                 (microtek2)
        #     I'm not 100% sure about Filmstrip, but it could make sense
        #     to treat it similary to an ADF
        #
        # bool option 'adf': artec, ibm
        # bool option 'noadf': canon
        # string option 'feeder-mode', value 'All Pages': matsushita
        #
        # FIXME: The backends plustek, ma1509, matsushita seem to support
        # ADFs too, but I could not figure out, how these can be detected
        # The plustek backend perhaps uses the device type string
        # 'USB sheet-fed scanner', and the matsushita backend uses the
        # device type string 'sheetfed scanner'.
        # The ma1509 describes itself as a 'flatbed scanner', so there
        # seems to be no way to dicover, if an ADF is used or installed...
        
        
        optnames = self.getOptionNames()
        try:
            if 'source' in optnames:
                source = self._device.source
                for test in ('ADF', 'Document Feeder'):
                    if source.find(test) >= 0:
                        return True
        except AttributeError, errval:
            if str(errval) == 'Inactive option: source':
                return False
            raise
        
        if 'adf' in optnames:
            try:
                return self._device.adf
            except AttributeError, errval:
                if str(errval) == 'Inactive option: adf':
                    return False
                raise
        elif 'noadf' in optnames:
            try:
                return not self._device.noadf
            except AttributeError, errval:
                if str(errval) == 'Inactive option: noadf':
                    return False
                raise
        elif 'feeder_mode' in optnames:
            try:
                return self._device.feeder_mode == 'All Pages'
            except AttributeError, errval:
                if str(errval) == 'Inactive option: adf':
                    return False
                raise
        return False

    def duplex_mode(self):
        """ returns true, if the scanner is in ADF mode and if
            duplex scans are enabled (if possible)
        """
        if not self.adf_mode():
            return False
        optnames = self.getOptionNames()
        if 'source' in optnames:
            # avision, fujitsu
            try:
                return self._device.source == 'ADF Duplex'
            except AttributeError, errval:
                if str(errval) == 'Inactive option: source':
                    return False
                raise
        elif 'duplex' in optnames:
            # bh
            try:
                return self._device.duplex
            except AttributeError, errval:
                if str(errval) == 'Inactive option: duplex':
                    return False
                raise
        elif 'adf_mode' in optnames:
            # epson
            try:
                return self._device.adf_mode == 'Duplex'
            except AttributeError, errval:
                if str(errval) == 'Inactive option: adf_mode':
                    return False
                raise
        return False
        
gobject.signal_new("sane-geometry", SaneDevice, 
                   gobject.SIGNAL_RUN_FIRST | gobject.SIGNAL_ACTION,
                   gobject.TYPE_NONE,
                   ())
gobject.signal_new("sane-reload-params", SaneDevice, 
                   gobject.SIGNAL_RUN_FIRST | gobject.SIGNAL_ACTION,
                   gobject.TYPE_NONE,
                   ())


def _millimeters(val, opt, resol):
    if opt[5] == SANE_UNIT_MM:
        return val
    elif opt[5] == SANE_UNIT_PIXEL and resol:
        # well, we don't have a warranty that the scanner provides the
        # resolution in DPI units, but everthing else would be really pointless..
        return 25.4 * val / resol
    return val

def _getMinConstraint(opt):
    constr = opt[8]
    if type(constr) == type(()):
        return constr[0]
    elif type(constr) == type([]):
        return min(constr)
    raise EikazoWidgetError("can't retrieve constraint data for option %s" % opt[1])

def _getMaxConstraint(opt):
    constr = opt[8]
    if type(constr) == type(()):
        return constr[1]
    elif type(constr) == type([]):
        return max(constr)
    raise EikazoWidgetError("can't retrieve constraint data for option %s" % opt[1])


class DeviceWidget:
    """ common stuff for the device widgets
    """
    def __init__(self, optname, device):
        self.optname = optname
        self.device = device
        self.tLabel = None
    
    def titleWidget(self):
        """ return a gtk.Label with the title of the option
        """
        if not self.tLabel:
            opt = self.device._device.opt[self.optname]
            self.tLabel = gtk.Label(T2_(opt.title))
        return self.tLabel
    
    def show(self):
        raise EikazoWidgetError("class %s: DeviceWidget.show must be overloaded" % \
                           self.__class__.__name__)
    
    def _show(self):
        if self.tLabel:
            self.tLabel.show()

    def hide(self):
        raise EikazoWidgetError("DeviceWidget.hide must be overloaded")

    def _hide(self):
        if self.tLabel:
            self.tLabel.hide()

class BoolDisplay(DeviceWidget, gtk.HBox):
    """ for options that can't be set via software. This includes
        purely "informal" data and options that can be set by a switch
        or button on the scanner.
        FIXME For now, we simply display the text "[on]" or "[off]". Something
        like a green/red LED image would look much nicer, on the other
        hand, a _pure_ red/green signel is not very useful for many
        colorblind persons...
    """
    # no need to store config data
    def __init__(self, optname, device, **kw):
        gtk.HBox.__init__(self, **kw)
        DeviceWidget.__init__(self, optname, device)
        opt = device._device.opt[optname]
        self.display = gtk.Label(_("[off]"))
        self.pack_start(self.display, expand=False, fill=False, padding=5)
        self.display.show()
        label = gtk.Label(T2_(opt.title))
        self.pack_start(label, expand=False, fill=False)
        label.show()
        # FIXME: need to add an eventbox, in order to get a tooltip??
        #if opt.desc:
        #    device._tooltips.set_tip(self.display, opt.desc)
        self.Reload()
    
    def Reload(self):
        if self.device._device.opt[self.optname].is_active():
            if self.device._device.__getattr__(self.optname):
                self.display.set_text(_("[on]"))
            else:
                self.display.set_text(_("[off]"))
    
    def enable_option(self, value):
        pass

    def show(self):
        self._show()
        gtk.HBox.show(self)

    def hide(self):
        self._hide()
        gtk.HBox.hide(self)


class CheckButton(DeviceWidget, gtk.CheckButton, SaneWidgetConfig):
    def __init__(self, optname, device, config, **kw):
        opt = device._device.opt[optname]
        gtk.CheckButton.__init__(self, label=T2_(opt.title), **kw)
        DeviceWidget.__init__(self, optname, device)
        self.set_sensitive(opt.is_active())
        if opt.is_active():
            self.set_active(device._device.__getattr__(optname))
        if opt.desc:
            device._tooltips.set_tip(self, T2_(opt.desc))
        self.connect("toggled", _DeviceEvent(device, self, optname))
        SaneWidgetConfig.__init__(self, config)
    
    def Reload(self):
        opt = self.device._device.opt[self.optname]
        self.set_sensitive(opt.is_active())
        if opt.is_active():
            if self.delayedConfigValue:
                self.device._device.__setattr__(self.optname, self.delayedConfigValue)
                self.delayedConfigValue = None
            self.set_active(self.device._device.__getattr__(self.optname))
    
    def ChangeDeviceValue(self):
        self.device._device.__setattr__(self.optname, self.get_active())

    def enable_option(self, value):
        if not value:
            self.set_sensitive(False)
        else:
            opt = self.device._device.opt[self.optname]
            self.set_sensitive(opt.is_active())
    
    def guiValue(self):
        return self.get_active()

    def show(self):
        self._show()
        gtk.CheckButton.show(self)

    def hide(self):
        self._hide()
        gtk.CheckButton.hide(self)
            
class _DeviceEvent:
    def __init__(self, device, widget, optname):
        self.optname = optname
        self.device = device
        self.widget = widget
    def __call__(self, e):
        wlist = self.device._widgets[self.optname]
        self.widget.ChangeDeviceValue()
        for w in wlist:
            if w != self.widget:
                w.Reload()
        if self.device._device.last_opt & sane.INFO_RELOAD_OPTIONS:
            self.device.reloadOptions()
        # Not all backends set the reload params flag, when
        # scan size or resolution are changed.
        if self.optname in ('tl_x', 'tl_y', 'br_x', 'br_y', 'resolution',
                            'y-resolution') or \
           self.device._device.last_opt & sane.INFO_RELOAD_PARAMS:
            self.device.reloadParams()
            
            
_geometryOptions = ('tl_x', 'tl_y', 'br_x', 'br_y')

class _SaneScale(DeviceWidget, SaneWidgetConfig):
    """mixin for HScale and VScale. Does the "real stuff": connects the 
       gtk.Adjustment instance and implements the communication with the 
       Sane device
    """
    def __init__(self, optname, device, config, **kw):
        DeviceWidget.__init__(self, optname, device)
        opt = device._device.opt[optname]
        constr = opt.constraint
        if opt.is_active():
            value = device._device.__getattr__(optname)
        else:
            value = constr[0] # min value
        if opt.desc:
            device._tooltips.set_tip(self, T2_(opt.desc))
        self.adj = gtk.Adjustment(value, constr[0], constr[1], constr[2], **kw)
        self.set_adjustment(self.adj)
        self.set_sensitive(opt.is_active())
        self.adj.connect("value-changed", _DeviceEvent(device, self, optname))
        SaneWidgetConfig.__init__(self, config)

    def Reload(self):
        opt = self.device._device.opt[self.optname]
        self.set_sensitive(opt.is_active())
        if opt.is_active():
            if self.delayedConfigValue:
                self.device._device.__setattr__(self.optname, self.delayedConfigValue)
                self.delayedConfigValue = None
            v = self.device._device.__getattr__(self.optname)
            self.adj.set_value(v)
    
    def ChangeDeviceValue(self):
        opt = self.device._device.opt[self.optname]
        constr = opt.constraint
        v = self.adj.get_value()
        if opt.type == SANE_TYPE_INT:
            v = int(round(v))
        if v < constr[0]:
            v = constr[0]
        elif v > constr[1]:
            v = constr[1]
        self.device._device.__setattr__(self.optname, v)
        # the step constraint may be violated; the backend should fix this
        # for us
        self.adj.set_value(self.device._device.__getattr__(self.optname))
        #print "opt", self.optname, self.device._device, v, self.device._device.__getattr__(self.optname)
        if self.optname in _geometryOptions:
            self.device.geometryChanged()

    def enable_option(self, value):
        if not value:
            self.set_sensitive(False)
        else:
            opt = self.device._device.opt[self.optname]
            self.set_sensitive(opt.is_active())

    def guiValue(self):
        return self.adj.get_value()

class HScalePanel(gtk.VBox):
    def __init__(self, optname, device, config, **kw):
        gtk.VBox.__init__(self, **kw)
        opt = device._device.opt[optname]
        label = gtk.Label(T2_(opt.title))
        self.add(label)
        label.show()
        self.scale = HScale(optname, device, config, **kw)
        self.add(self.scale)
        self.scale.show()
    
    def Reload(self):
        self.scale.Reload()
        
    def ChangeDeviceValue(self):
        self.scale.ChangeDeviceValue()
    
    def enable_option(self, value):
        self.scale.enable_option(value)
    
class HScale(_SaneScale, gtk.HScale):
    def __init__(self, optname, device, config, **kw):
        gtk.HScale.__init__(self, **kw)
        _SaneScale.__init__(self, optname, device, config, **kw)
        
    def show(self):
        self._show()
        gtk.HScale.show(self)

    def hide(self):
        self._hide()
        gtk.HScale.hide(self)


class VScale(_SaneScale, gtk.VScale):
    def __init__(self, optname, device, config,  **kw):
        gtk.VScale.__init__(self, **kw)
        _SaneScale.__init__(self, optname, device, config, **kw)
        
    def show(self):
        self._show()
        gtk.VScale.show(self)

    def hide(self):
        self._hide()
        gtk.VScale.hide(self)


class LabeledNumberField(gtk.VBox):
    def __init__(self, optname, device, config, **kw):
        gtk.VBox.__init__(self, **kw)
        opt = device._device.opt[optname]
        label = gtk.Label(T2_(opt.title))
        self.add(label)
        label.show()
        self.string = NumberField(optname, device, config, **kw)
        self.add(self.string)
        self.string.show()
    
    def Reload(self):
        self.string.Reload()
        
    def ChangeDeviceValue(self):
        self.string.ChangeDeviceValue()

    def enable_option(self, value):
        self.string.enable_option(value)

class NumberField(DeviceWidget, gtk.SpinButton, SaneWidgetConfig):
    """ used for integers and Sane_Fixed. 
    """
    def __init__(self, optname, device, config, **kw):
        gtk.SpinButton.__init__(self, **kw)
        DeviceWidget.__init__(self, optname, device)
        opt = device._device.opt[optname]
        if opt.is_active():
            value = device._device.__getattr__(optname)
        else:
            value = 0
        self.set_sensitive(opt.is_active())
        self.set_numeric(True)
        if opt.desc:
            device._tooltips.set_tip(self, T2_(opt.desc))
        
        constr = opt.constraint
        if type(constr) == type(()):
            adj = gtk.Adjustment(value, constr[0], constr[1], constr[2], **kw)
        else:
            if opt.type == SANE_TYPE_INT:
                adj = gtk.Adjustment(value, -2**31, 2**31-1, 1, 10, 10)
            else: # must be float
                # FIXME: seems to be buggy for values >= 32768
                adj = gtk.Adjustment(value, -100000.0, 100000.0, 1.0, 10.0, 10.0)
        
        digits = 0
        if opt.type == SANE_TYPE_FIXED:
            # FIXME: one digit is an absolutely arbitrary choice...
            # Would perhaps be better to use a simple gtk.Entry field
            digits = 1
        self.configure(adj, 1, digits)
        self.connect("value-changed", _DeviceEvent(device, self, optname))
        SaneWidgetConfig.__init__(self, config)
    
    def Reload(self):
        opt = self.device._device.opt[self.optname]
        self.set_sensitive(opt.is_active())
        if opt.is_active():
            if self.delayedConfigValue:
                self.device._device.__setattr__(self.optname, self.delayedConfigValue)
                self.delayedConfigValue = None
            self.set_value(self.device._device.__getattr__(self.optname))
        
    def ChangeDeviceValue(self):
        # FIXME: check for constraints!!
        opt = self.device._device.opt[self.optname]
        constr = opt.constraint
        v = self.get_value()
        if opt.type == SANE_TYPE_INT:
            v = int(round(v))
        if constr:
            if v < constr[0]:
                v = constr[0]
            elif v > constr[1]:
                v = constr[1]
        self.device._device.__setattr__(self.optname, v)
        # the step constraint may be violated; the backend should fix this
        # for us
        self.set_value(self.device._device.__getattr__(self.optname))
        if self.optname in _geometryOptions:
            self.device.geometryChanged()

    def enable_option(self, value):
        if not value:
            self.set_sensitive(False)
        else:
            opt = self.device._device.opt[self.optname]
            self.set_sensitive(opt.is_active())
    
    def guiValue(self):
        return self.get_value()

    def show(self):
        self._show()
        gtk.SpinButton.show(self)

    def hide(self):
        self._hide()
        gtk.SpinButton.hide(self)


class LabeledChoice(gtk.VBox):
    def __init__(self, optname, device, config, **kw):
        gtk.VBox.__init__(self, **kw)
        opt = device._device.opt[optname]
        label = gtk.Label(T2_(opt.title))
        self.add(label)
        label.show()
        self.choice = Choice(optname, device, config, **kw)
        self.add(self.choice)
        self.choice.show()
    
    def Reload(self):
        self.choice.Reload()
        
    def ChangeDeviceValue(self):
        self.choice.ChangeDeviceValue()

    def enable_option(self, value):
        self.choice.enable_option(value)

class Choice(DeviceWidget, gtk.ComboBox, SaneWidgetConfig):
    def __init__(self, optname, device, config, **kw):
        DeviceWidget.__init__(self, optname, device)
        opt = device._device.opt[optname]
        if opt.type == SANE_TYPE_INT:
            store = gtk.ListStore(gobject.TYPE_INT)
        elif opt.type == SANE_TYPE_FIXED:
            store = gtk.ListStore(gobject.TYPE_FLOAT)
        elif opt.type == SANE_TYPE_STRING:
            store = gtk.ListStore(gobject.TYPE_STRING)
        else:
            raise EikazoWidgetError("can't handle creation of comboboxes for type %s" % opt.type)
        gtk.ComboBox.__init__(self, store, **kw)
        constr = opt.constraint
        for s in constr:
            store.append([T2_(s)])
        cell = gtk.CellRendererText()
        self.pack_start(cell, True)
        self.add_attribute(cell, "text", 0)
        self.set_sensitive(opt.is_active())
        if opt.is_active():
            value = device._device.__getattr__(optname)
            pos = constr.index(value)
            self.set_active(pos)

        if opt.desc:
            # FIXME: tooltips don't show up. Need to add an eventbox?
            device._tooltips.set_tip(self, T2_(opt.desc))
        self.constraint = constr # FIXME: can this change for some backends??
        self.set_sensitive(opt.is_active())
        self.connect("changed", _DeviceEvent(device, self, optname))
        SaneWidgetConfig.__init__(self, config)

    def Reload(self):
        opt = self.device._device.opt[self.optname]
        self.set_sensitive(opt.is_active())
        if opt.is_active():
            if self.delayedConfigValue:
                self.device._device.__setattr__(self.optname, self.delayedConfigValue)
                self.delayedConfigValue = None
            value = self.device._device.__getattr__(self.optname)
            pos = opt.constraint.index(value)
            self.set_active(pos)

    def ChangeDeviceValue(self):
        i = self.get_active()
        self.device._device.__setattr__(self.optname, self.constraint[i])
        
    def enable_option(self, value):
        if not value:
            self.set_sensitive(False)
        else:
            opt = self.device._device.opt[self.optname]
            self.set_sensitive(opt.is_active())
    
    def guiValue(self):
        i = self.get_active()
        return self.constraint[i]
    
    def show(self):
        self._show()
        gtk.ComboBox.show(self)

    def hide(self):
        self._hide()
        gtk.ComboBox.hide(self)

class LabeledStringOption(gtk.VBox):
    def __init__(self, optname, device, config, **kw):
        gtk.VBox.__init__(self, **kw)
        opt = device._device.opt[optname]
        label = gtk.Label(T2_(opt.title))
        self.add(label)
        label.show()
        self.string = StringOption(optname, device, config, **kw)
        self.add(self.string)
        self.string.show()
    
    def Reload(self):
        self.string.Reload()
        
    def ChangeDeviceValue(self):
        self.string.ChangeDeviceValue()

    def enable_option(self, value):
        self.string.enable_option(value)

class StringOption(DeviceWidget, gtk.Entry, SaneWidgetConfig):
    def __init__(self, optname, device, config, **kw):
        DeviceWidget.__init__(self, optname, device)
        opt = device._device.opt[optname]
        gtk.Entry.__init__(self, opt.size-1)
        if opt.is_active():
            value = device._device.__getattr__(optname)
        else:
            value = ''
        self.set_text(value)
        self.set_sensitive(opt.is_active())
        self.optname = optname
        self.device = device
        if opt.desc:
            device._tooltips.set_tip(self, T2_(opt.desc))
        self.connect("changed", _DeviceEvent(device, self, optname))
        SaneWidgetConfig.__init__(self, config)
    
    def Reload(self):
        opt = self.device._device.opt[self.optname]
        self.set_sensitive(opt.is_active())
        if opt.is_active():
            if self.delayedConfigValue:
                self.device._device.__setattr__(self.optname, self.delayedConfigValue)
                self.delayedConfigValue = None
            self.set_text(self.device._device.__getattr__(self.optname))
        
    def ChangeDeviceValue(self):
        self.device._device.__setattr__(self.optname, self.get_text())

    def enable_option(self, value):
        if not value:
            self.set_sensitive(False)
        else:
            opt = self.device._device.opt[self.optname]
            self.set_sensitive(opt.is_active())
    
    def guiValue(self):
        return self.get_text()

    def show(self):
        self._show()
        gtk.Entry.show(self)

    def hide(self):
        self._hide()
        gtk.Entry.hide(self)


class Button(DeviceWidget, gtk.Button):
    # no need to store/load config data
    def __init__(self, optname, device, **kw):
        DeviceWidget.__init__(self, optname, device)
        opt = device._device.opt[optname]
        gtk.Button.__init__(self, label=T2_(opt.title), **kw)
        self.optname = optname
        self.device = device
        self.set_sensitive(opt.is_active())
        if opt.desc:
            device._tooltips.set_tip(self, T2_(opt.desc))
        self.connect("clicked", _DeviceEvent(device, self, optname))
    
    def Reload(self):
        opt = self.device._device.opt[self.optname]
        self.set_sensitive(opt.is_active())
        
    def ChangeDeviceValue(self):
        self.device._device.__setattr__(self.optname, 1)

    def enable_option(self, value):
        if not value:
            self.set_sensitive(False)
        else:
            opt = self.device._device.opt[self.optname]
            self.set_sensitive(opt.is_active())
    
    def titleWidget(self):
        """ no need for a "real" label: the button provides
            its own explanatory text
        """
        if not self.tLabel:
            self.tLabel = gtk.Label("")
        return self.tLabel

    def show(self):
        self._show()
        gtk.CheckButton.show(self)

    def hide(self):
        self._hide()
        gtk.CheckButton.hide(self)

class xxxCurve(DeviceWidget, gtk.Curve, SaneWidgetConfig):
    def __init__(self, optname, device, config, **kw):
        print "xxx init Curve 1"
        DeviceWidget.__init__(self, optname, device)
        opt = device._device.opt[optname]
        gtk.Curve.__init__(self)
        print "xxx init Curve 2"
        
        if type(opt.constraint) != type(()):
            raise EikazoWidgetError("Wigdets.Curve requires a min/man constraint option")
        self.optname = optname
        self.device = device
        print "xxx init Curve 3"
        self.set_sensitive(opt.is_active())
        if opt.desc:
            device._tooltips.set_tip(self, T2_(opt.desc))
        print "xxx init Curve 4"
        self.set_range(0, opt.size, opt.constraint[0], opt.constraint[1])
        print "xxx init Curve 5"
        #xxx self.set_curve_type(gtk.CURVE_TYPE_LINEAR)
        print "xxx init Curve 6"
        SaneWidgetConfig.__init__(self, config)
        print "xxx init Curve finished"
        
class SaneCurve(DeviceWidget, Curve.Curve, SaneWidgetConfig):
    def __init__(self, optname, device, config, **kw):
        opt = device._device.opt[optname]
        if type(opt.constraint) != type(()):
            raise EikazoWidgetError("Wigdets.Curve requires a min/man constraint option")

        DeviceWidget.__init__(self, optname, device)
        Curve.Curve.__init__(self, 0, opt.size-1, opt.constraint[0], opt.constraint [1])
        
        self.optname = optname
        self.device = device
        self.set_sensitive(opt.is_active())
        if opt.desc:
            device._tooltips.set_tip(self, T2_(opt.desc))
        #xxx self.curve.set_range(0, opt.size, opt.constraint[0], opt.constraint[1])
        SaneWidgetConfig.__init__(self, config)
        
    def Reload(self):
        opt = self.device._device.opt[self.optname]
        self.set_sensitive(opt.is_active())
    
    def ChangeDeviceValue(self):
        self.device._device.__setattr__(self.optname, self.gamma.get_vector())

    def enable_option(self, value):
        if not value:
            self.set_sensitive(False)
        else:
            opt = self.device._device.opt[self.optname]
            self.set_sensitive(opt.is_active())
    
    def show(self):
        self._show()
        gtk.CheckButton.show(self)

    def hide(self):
        self._hide()
        gtk.CheckButton.hide(self)
    