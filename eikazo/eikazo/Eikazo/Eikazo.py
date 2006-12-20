about_text=""" 
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
"""

"""
    complete Eikazo user interface.
    The main widget can laso be included in another program
"""
import os
import gtk

import SaneThread, threading
import Widgets, Config
import Preview
import ScanJob
import I18n
import Processor
import Help
import Plugins
import output, postprocessing
from SaneError import SaneError

from devices.scannerinfo import scannerinfo

t = I18n.get_translation('eikazo')
if t:
    _ = t.gettext
else:
    _ = lambda x: x

t2 = I18n.get_translation('sane-backends')
if t2:
    SB_ = t2.gettext
else:
    SB_ = lambda x: x



class ScanStarter(Processor.SaneInputProducer):
    def __init__(self, device):
        Processor.SaneInputProducer.__init__(self)
        self.device = device
        self.scanprocessor = None
    
    def set_scanprocessor(self, processor):
        self.scanprocessor = processor
    
    def set_start_button(self, button):
        self.startbutton = button
        button.connect('clicked', self.do_start)
    
    def do_start(self, widget):
        # FIXME: add bureaucracy like filename definition here, not as 
        # late as in the write processor!!
        self.scan_one()
    
    def scan_one(self):
        job = Processor.SaneScanJob(self)
        
        try:
            self.scanprocessor.append(job)
        except SaneError, value:
            if str(value) == "SaneQueueingProcessor.append: queue full":
                pending = self.scanprocessor.numjobs(True)
                # method can be called from the scan proceccor thread.
                msg = _("cannot start a new scan. %i pending scan job(s)") % pending
                if threading.currentThread() == SaneThread.mainthread:
                    self.show_errmsg(msg)
                else:
                    gtk.gdk.threads_enter()
                    self.show_errmsg()
                    gtk.gdk.threads_leave()
            else:
                raise
    
    def show_errmsg(self, msg):
        errmsg = gtk.MessageDialog(None, gtk.DIALOG_MODAL,
                     gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, msg)
        errmsg.run()
        errmsg.destroy()

    def next_job(self):
        # callback from scanprocessor: request for a new job
        if self.device.adf_mode():
            self.scan_one()
    
    def delete_from_id(self, id):
        return
    

class DeviceControl:
    """ - provides widgets which are "collections" of smaller widgets
          controlling device parameters
        - provides the scan processor
    """
    
    _nodisplayOpts = []
    _mainOpts = ['source', 'mode', 'resolution', 'y_resolution',
                 'tl_x', 'br_x', 'tl_y', 'br_y',
                 'pagewidth', 'pageheight', 'overscan'
                ]

    # The Sane option constraints are represented in the PIL Sane
    # module as:
    # None  -> no constraint;
    # tuple -> range constraint
    # list  -> selection list
    # Some scanners allow for example only a fixed list of resolutions, so 
    # we need to be able to deal with all types of constraints.
    
    
    _num_constrmap = { type(None): ('number field', ),
                      type([]):   ('choice', ),
                      type(()):   ('hscale', 'number field'),
                    }
    
    _default_map = { type(None): ('default', ),
                   }

    _mainOptWTypes = {
        Widgets.SANE_TYPE_BOOL:   _default_map,
        Widgets.SANE_TYPE_INT:    _num_constrmap,
        Widgets.SANE_TYPE_FIXED:  _num_constrmap,
        Widgets.SANE_TYPE_STRING:  { type(None): ('string field', ),
                                     type([]):   ('choice', ),
                                   },
        Widgets.SANE_TYPE_BUTTON:  _default_map,
        Widgets.SANE_TYPE_GROUP:   { type(None): (), 
                                   },
    }
    
    def __init__(self, device, config, notify_hub):
        self.device = device
        self.config = config
        self._tabs = []
        self.notify_hub = notify_hub
        
        self.scanstarter = ScanStarter(device)
        self.scanprocessor = Processor.SaneScannerControl(device, 
                                                          self.scanstarter,
                                                          notify_hub, 2)
        self.scanstarter.set_scanprocessor(self.scanprocessor)
        
        deviceinfo = scannerinfo(device.devicename)
        nodisplayOpts = self._nodisplayOpts[:]
        replacementOpts = {}
        replacementPos = []
        
        self.specialDeviceCaps = []
        # device_status: a speicel widget optionally provided by a device
        # plugin to display additional information
        self.deviceStatusWidget = None
        
        for r in deviceinfo:
            # "input elements" of the device like buttons or
            # "selectors" 
            if r['usage'] == None or r['type'] in ('button', 'selection'):
                nodisplayOpts.append(r['name'])
            elif r['type'] == 'cap':
                devcap = r['usage']()
                self.specialDeviceCaps.append(devcap)
                capOpts = devcap.widgets(device, self, self.config)
                
                # search for a status widget; this does not fit in
                # any other tab, but is useful in the "scan" tab
                for i in xrange(len(capOpts)-1, -1, -1):
                    if capOpts[i][:2] == ('status', 'gtksane_status'):
                        self.deviceStatusWidget = capOpts[i][2]
                        capOpts.pop(i)
                
                replacementPos += [x[:2] for x in capOpts]
                replacementOpts.update([(x[0], x[2]) for x in capOpts])
                
            
        
        allOpts = device.getOptionNames()
        o = device.getOptions()
        o = [(x[9], x) for x in o]
        optinfo = {}
        optinfo.update(o)
        
        mainOpts = [x for x in self._mainOpts \
                      if x in allOpts and not x in nodisplayOpts]
          
        addMain = [x[0] for x in replacementOpts \
                        if x[1] == 'main' and not x[0] in mainOpts]
        mainOpts += addMain
        
        optbox = gtk.Table(len(mainOpts), 3, homogeneous=False)
        optbox.set_col_spacing(0, 6)
        pos = 0
        for opt in mainOpts:
            hpos = 1
            if opt in replacementOpts.keys():
                # FIXME: should be possible to select, which widget types
                # we want!
                widgets = replacementOpts[opt]
                for w in widgets:
                    if hpos == 1:
                        l = w.titleWidget()
                        l.set_alignment(0, 0.5)
                        optbox.attach(l, 0, 1, pos, pos+1, 
                                      xoptions=gtk.FILL, yoptions=gtk.FILL,
                                      xpadding=0, ypadding=0)
                        l.show()
                        optbox.attach(w, hpos, hpos+1, pos, pos+1,
                                      xoptions=gtk.FILL|gtk.EXPAND, yoptions=gtk.FILL,
                                      xpadding=0, ypadding=0)
                    else:
                        optbox.attach(w, hpos, hpos+1, pos, pos+1,
                                      xoptions=gtk.FILL, yoptions=gtk.FILL,
                                      xpadding=0, ypadding=0)
                    w.show()
                    hpos += 1
            else:
                otype = optinfo[opt][4]
                constr = optinfo[opt][8]
                for t in self._mainOptWTypes[otype][type(constr)]:
                    w = device.createOptionWidget(opt, self.config, t)
                    if hpos == 1:
                        l = w.titleWidget()
                        l.set_alignment(0, 0.5)
                        optbox.attach(l, 0, 1, pos, pos+1, 
                                      xoptions=gtk.FILL, yoptions=gtk.FILL,
                                      xpadding=0, ypadding=0)
                        l.show()
                        optbox.attach(w, hpos, hpos+1, pos, pos+1,
                                      xoptions=gtk.FILL, yoptions=gtk.FILL,
                                      xpadding=0, ypadding=0)
                    else:
                        optbox.attach(w, hpos, hpos+1, pos, pos+1,
                                      xoptions=gtk.FILL|gtk.EXPAND, yoptions=gtk.FILL,
                                      xpadding=0, ypadding=0)
                    if t == 'hscale' and w.__class__ == Widgets.HScale:
                        w.set_draw_value(False)
                    w.show()
                    hpos += 1
            pos += 1
        
        self.mainOptsPane = pane = gtk.HPaned()
        pane.pack1(optbox, shrink=False, resize=True)
        optbox.show()
        self._tabs.append((_('Main Scan\nParameters'), pane))
        
        for groupname, opts in device.getGroupedOptionNames():
            opts = [x for x in opts if not x in self._mainOpts \
                                       and not x in nodisplayOpts]
            if opts:
                optbox = gtk.Table(len(opts), 2)
                optbox.set_col_spacing(0, 6)
                pos = 0
                for opt in opts:
                    if opt in replacementOpts.keys():
                        w = replacement_opts[opt]
                    else:
                        w = device.createOptionWidget(opt, self.config)
                    if w != None:
                        l = w.titleWidget()
                        l.set_alignment(0, 0.5)
                        optbox.attach(l, 0, 1, pos, pos+1, 
                                      xoptions=gtk.FILL, yoptions=gtk.FILL,
                                      xpadding=0, ypadding=0)
                        optbox.attach(w, 1, 2, pos, pos+1, 
                                      xoptions=gtk.FILL|gtk.EXPAND, yoptions=gtk.FILL,
                                      xpadding=0, ypadding=0)
                        w.show() # implies l.show()
                    else:
                        print "Warning: Could not create widget for option", opt
                    pos += 1
                self._tabs.append((SB_(groupname), optbox))
    
    def tabs(self):
        return self._tabs
    
    def set_start_button(self, button):
        self.scanstarter.set_start_button(button)
    
    def get_scanprocessor(self):
        return self.scanprocessor
    
    def insert_preview(self, preview):
        self.mainOptsPane.pack2(preview, shrink=True, resize=True)
        preview.show()
    
class ScanTab(gtk.VBox):
    def __init__(self, device, devicecontrol, config, notify_hub):
        gtk.VBox.__init__(self)
        self.tablabel = gtk.Label(_('Scan'))
        
        self.preview = Preview.SanePreview(device, config)
        self.pack_start(self.preview, expand=True, fill=True)
        self.preview.show()
        
        self.infoManager = ScanJob.InfoManager(notify_hub)
        self.jobstatus = self.infoManager.get_widget()
        self.pack_start(self.jobstatus, expand=False, fill=True)
        self.jobstatus.show()
        
        if devicecontrol.deviceStatusWidget:
            self.pack_start(devicecontrol.deviceStatusWidget,
                            expand=False, fill=True)
            devicecontrol.deviceStatusWidget.show()
        
        self.buttonbar = gtk.HBox()
        self.pack_start(self.buttonbar, expand=False, fill=True)
        self.buttonbar.show()
        self.buttonbar.set_spacing(10)
        
        self.scanbutton = gtk.Button(_('Scan'))
        self.buttonbar.pack_start(self.scanbutton, expand=False, fill=False)
        self.scanbutton.show()
        devicecontrol.set_start_button(self.scanbutton)
        
        self.delbutton = gtk.Button(_('Delete Job'))
        self.buttonbar.pack_start(self.delbutton, expand=False, fill=False)
        self.delbutton.show()
        self.infoManager.add_deleteButton(self.delbutton)
        
        self.retrybutton = gtk.Button(_('Retry Job'))
        self.buttonbar.pack_start(self.retrybutton, expand=False, fill=False)
        self.retrybutton.show()
        self.infoManager.add_retryButton(self.retrybutton)
        
        self.editbutton = gtk.Button(_('Edit Job'))
        self.buttonbar.pack_start(self.editbutton, expand=False, fill=False)
        self.editbutton.show()
        self.infoManager.add_editButton(self.editbutton)
    
    def get_previewWidget(self):
        return self.preview



class SaneMainWidget(gtk.VBox):
    def __init__(self, device, config=None):
        """ device: SaneDevice instance
              config: SaneConfig instance, or a string, providing
                    a file name of a config file
            configfile: file to read config data from, if config is None
                    If None, a default config is created
        """
        gtk.VBox.__init__(self)
        
        if config == None:
            self.config = config = Config.SaneConfig()
        elif type(config) == type(''):
            self.config = Config.SaneConfig()
            config.loadConfig(config)
            config = self.config
        else:
            self.config = config
        
        self.device = device
        self.notify_hub = Processor.SaneProcessorNotifyHub()
        self.devicecontrol = DeviceControl(device, config, self.notify_hub)
        
        self._gtkActions = gtk.ActionGroup('SaneMainActions')
        self._gtkActions.add_actions(self.action_description())
        self.mainArea = gtk.Notebook()
        self.pack_start(self.mainArea, expand=True, fill=True)
        self.mainArea.show()
        self.statusbar = gtk.Statusbar()
        self.pack_start(self.statusbar, expand=False, fill=True)
        self.statusbar.show()
        
        self.scantab = ScanTab(self.device, self.devicecontrol, config, 
            self.notify_hub)
        self.mainArea.append_page(self.scantab, self.scantab.tablabel)
        self.scantab.show()
        self.previewProcessor = \
            Preview.SanePreviewProcessor(
                self.devicecontrol.get_scanprocessor(),
                self.notify_hub,
                2,
                self.scantab.get_previewWidget())
        
        preview2 = Preview.SanePreview(device, config)
        self.previewProcessor.add_preview(preview2)
        self.devicecontrol.insert_preview(preview2)
        
        
        for title, widget in self.devicecontrol.tabs():
            l = gtk.Label(_(title))
            self.mainArea.append_page(widget, l)
            widget.show()
        
        lastfilter = self.devicecontrol.get_scanprocessor()
        self.postprocOpts = [x(self.notify_hub, False, config) \
                             for x in postprocessing.procinfo.infos]
        if self.postprocOpts:
            if len(self.postprocOpts) == 1:
                # simply show the plain output widget, but with
                # a frame for the name of the processing class
                o = self.postprocOpts[0]
                postprocwidget = gtk.Frame(_(o.get_name()))
                w = o.get_widget()
                postprocwidget.add(w)
                w.show()
                o.set_processor_input(lastfilter)
                lastfilter = o.get_processor()
            else:
                postprocwidget = gtk.Notebook()
                postprocwidget.set_tab_pos(gtk.POS_LEFT)
                for o in self.postprocOpts:
                    l = o.get_name_label()
                    w = o.get_widget()
                    c = o.get_connect_widget()
                    box = gtk.VBox()
                    box.pack_start(c, expand=False, fill=False)
                    c.show()
                    box.pack_start(w, expand=True, fill=True)
                    w.show()
                    postprocwidget.append_page(box, l)
                    box.show()
                    o.set_processor_input(lastfilter)
                    lastfilter = o.get_processor()
            l = gtk.Label(_('Postprocessing'))
            self.mainArea.append_page(postprocwidget, l)
            postprocwidget.show()
            
        
        self.outputOpts = [x(self.notify_hub, config) for x in output.outputinfo.infos]
        if not self.outputOpts:
            msg = _(\
"""Warning: Could not find any output write classes.
Please install at least one output writer.
Currently you can only view scanned images in this program.
""")
            errmsg = gtk.MessageDialog(None, gtk.DIALOG_MODAL,
                             gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, msg)
            errmsg.run()
            errmsg.destroy()
        else:
            if len(self.outputOpts) == 1:
                # simply show the plain output widget, but with
                # a frame for the name of the writer class
                o = self.outputOpts[0]
                outputwidget = gtk.Frame(_(o.get_name()))
                w = o.get_widget()
                outputwidget.add(w)
                w.show()
                o.enable_input(True)
                o.set_processor_input(lastfilter)
            else:
                outputwidget = gtk.Notebook()
                outputwidget.set_tab_pos(gtk.POS_LEFT)
                first_widget = True
                for o in self.outputOpts:
                    l = o.get_name_label()
                    w = o.get_widget()
                    c = o.get_connect_widget()
                    box = gtk.VBox()
                    box.pack_start(c, expand=False, fill=False)
                    c.show()
                    box.pack_start(w, expand=True, fill=True)
                    w.show()
                    outputwidget.append_page(box, l)
                    box.show()
                    if first_widget:
                        o.enable_input(True)
                        first_widget = False
                    o.set_processor_input(lastfilter)
            l = gtk.Label(_('Output'))
            self.mainArea.append_page(outputwidget, l)
            outputwidget.show()
        
        self.help = Help.Help()
        
    
    ############################################################
    #
    #   Menu
    #
    def ui_description(self):
        """ return an XML description of the menu structure for 
            this widget
        """
        return """<ui>
          <menubar name="Menubar">
            <menu action="FileMenu">
              <menuitem action="LoadConfig" />
              <menuitem action="SaveConfig" />
              <menuitem action="SaveConfigAs" />
            </menu>
            <menu action="HelpMenu">
              <menuitem action="About" />
              <menuitem action="Manual" />
              <menuitem action="Plugins" />
            </menu>
          </menubar>
        </ui>"""
    
    def action_description(self):
        """ return the actions needed by this widget 
        """
        return [
          # name,        stockID, label,       accelerator, tooltip, callback
          ('FileMenu',   None, _('_File')),
          ('LoadConfig', None, _('_Load Configuration'), None,  None,
                                                            self.cbLoadConfig),
          ('SaveConfig', None, _('_Save Configuration'), None,  None,
                                                            self.cbSaveConfig),
          ('SaveConfigAs', None, _('Save Configuration _As'), None, None,
                                                            self.cbSaveConfigAs),
          ('HelpMenu',   None, _('_Help')),
          ('About',      None, _('_About'),     None,       None,
                                                           self.cbHelpAbout),
          ('Manual',     None, _('_Manual'),    None,       None,
                                                           self.cbHelpManual),
          ('Plugins',    None, _('_Plugins'),   None,       None,
                                                           self.cbPluginList),
        ]
    
    def gtkActions(self):
        """ return the GTK action group for this widget
        """
        return self._gtkActions
    
    ################################################################
    #
    # Configuration
    #
    def cbLoadConfig(self, widget):
        dlg = gtk.FileChooserDialog(_("Select filename..."), None,
                  gtk.FILE_CHOOSER_ACTION_OPEN,
                  (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                   gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        dlg.set_default_response(gtk.RESPONSE_OK)
        filter = gtk.FileFilter()
        filter.set_name(_("Eikazo config files (*.eicfg)"))
        filter.add_pattern("*.eicfg")
        dlg.add_filter(filter)
        filter = gtk.FileFilter()
        filter.set_name(_("All files"))
        filter.add_pattern("*")
        dlg.add_filter(filter)

        dlg.hide()
        if dlg.run() == gtk.RESPONSE_OK:
            filename = dlg.get_filename()
            if os.access(filename, os.W_OK):
                self.config.loadConfig(filename)
            else:
                errmsg = gtk.MessageDialog(None, gtk.DIALOG_MODAL,
                              gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE,
                              _("Can't open file %s") % filename)
                errmsg.run()
                errmsg.destroy()
        dlg.destroy()
    
    def cbSaveConfig(self, widget):
        if self.config.currentFile:
            self.config.saveConfig(self.config.currentFile)
        else:
            self.cbSaveConfigAs(widget)

    def cbSaveConfigAs(self, widget):
        dlg = gtk.FileChooserDialog(_("Select filename..."), None,
                  gtk.FILE_CHOOSER_ACTION_SAVE,
                  (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                   gtk.STOCK_SAVE, gtk.RESPONSE_OK))
        dlg.set_default_response(gtk.RESPONSE_OK)
        filter = gtk.FileFilter()
        filter.set_name(_("Eikazo config files (*.eicfg)"))
        filter.add_pattern("*.eicfg")
        dlg.add_filter(filter)
        filter = gtk.FileFilter()
        filter.set_name(_("All files"))
        filter.add_pattern("*")
        dlg.add_filter(filter)

        dlg.hide()
        if self.config.currentFile:
            path, fname = os.path.split(self.config.currentFile)
            dlg.set_current_folder(path)
            dlg.set_current_name(fname)

        if dlg.run() == gtk.RESPONSE_OK:
            filename = dlg.get_filename()
            try:
                self.config.saveConfig(filename)
            except ValueError: # FIXME: Check for reasonable
                               # errors, and translate them into
                               # "end user understandable" language
                errmsg = gtk.MessageDialog(None, gtk.DIALOG_MODAL,
                             gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE,
                             _("Can't save to file %s") % filename)
                errmsg.run()
                errmsg.destroy()
        dlg.destroy()        

    def cbHelpAbout(self, widget):
        path = os.path.split(__file__)
        fname = os.path.join(path[0], 'version.txt')
        version = open(fname).read().strip()
        text = _(about_text)
        text = text.split('\n\n')
        text = [x.replace('\n', ' ') for x in text]
        text = '\n\n'.join(text)
        
        text = 'Eikazo version %s\n\n%s' % (version, text)
        
        msg = gtk.MessageDialog(None, gtk.DIALOG_MODAL,
                  gtk.MESSAGE_INFO, gtk.BUTTONS_CLOSE,
                     _(text))
        msg.run()
        msg.destroy()
        
    
    def cbHelpManual(self, widget):
        self.help.show()
    
    def cbPluginList(self, widget):
        text = Plugins.plugininfo()
        msg = gtk.MessageDialog(None, gtk.DIALOG_MODAL,
                  gtk.MESSAGE_INFO, gtk.BUTTONS_CLOSE,
                     text)
        msg.run()
        msg.destroy()
        

class SaneMainWindow(gtk.Window):
    """ simple top level window which ties together a menu bar and 
        a SaneMain widget
    """
    def __init__(self, device, type=gtk.WINDOW_TOPLEVEL):
        gtk.Window.__init__(self, type=type)
        self.exit_on_destroy = False
        
        vbox = gtk.VBox()
        self.add(vbox)
        vbox.show()
        
        self.saneWidget = SaneMainWidget(device)
        
        self.windowActionGroup = gtk.ActionGroup('WidowActions')
        self.windowActionGroup.add_actions(
          [('FileMenu', None, _('_File')),
           ('Quit',     None, _('_Quit'), '<control>q', None, self.destroy)
          ])

        
        self.uim = gtk.UIManager()
        self.uim.insert_action_group(self.saneWidget.gtkActions(), 0)
        self.uim.insert_action_group(self.windowActionGroup, 0)
        self.uim.add_ui_from_string(self.saneWidget.ui_description())
        self.uim.add_ui_from_string(self.ui_description())
        self.add_accel_group(self.uim.get_accel_group())
        
        self.menu = self.uim.get_widget('/Menubar')
        vbox.pack_start(self.menu, expand=False)
        self.menu.show()
        vbox.pack_start(self.saneWidget, expand=True, fill=True)
        self.saneWidget.show()
        
        self.connect("destroy", self.destroy)
        
    def ui_description(self):
        return """<ui>
          <menubar name="Menubar">
            <menu action="FileMenu">
              <menuitem action="Quit" />
            </menu>
          </menubar>
        </ui>"""

    
    def destroy(self, w):
        self.onExit = True
        SaneThread.abort_threads()
        if self.exit_on_destroy:
            gtk.main_quit()
        
    def main(self):
        self.show()
        self.exit_on_destroy = True
        gtk.main()
        


if __name__ == '__main__':
    dev = Widgets.getDevice()
    if not dev:
        print _("no devices found")
        sys.exit(0) 
        
    m = SaneMainWindow(dev, type=gtk.WINDOW_TOPLEVEL)
    m.main()
