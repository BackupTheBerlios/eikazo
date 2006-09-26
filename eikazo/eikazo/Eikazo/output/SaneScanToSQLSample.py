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

Write scan data to a file; store additionally some information
in an SQL database. This module is intended to be an example of a custom 
plugin, than being directly a useful.
"""
import sys, os, time, traceback, re
import gtk
from Eikazo.SaneError import SaneError
from Eikazo import I18n, Config, Processor, Plugins
import outputinfo, SaneScanToFile

DEBUG = 0

t = I18n.get_translation('eikazo')
if t:
    _ = t.gettext
else:
    _ = lambda x: x
        
N_ = lambda x: x

enable_plugin = os.getenv("EIKAZO_SQLSAMPLE")

if enable_plugin:
    try:
        import MySQLdb, _mysql_exceptions
        have_mysql = 1
        mysql_import = ''
    except ImportError, val:
        have_mysql = 0
        mysql_import = str(val)
    
    plg_detail = "enabled"
    adapters = 0
    if have_mysql:
        adapters += 1
        plg_detail = plg_detail + '\nFound MySQLdb module'
    
    if adapters == 0:
        plg_detail = plg_detail + '\nNo database modules found. Please ' \
                   + 'install at least one of the following database ' \
                   + 'modules: MySQLdb, psycopg, PyGreSQL'
    if mysql_import:
        plg_detail = plg_detail \
                     + '\n mysql module import error: %s' % mysql_import
    
    
    try:
        import pgdb, pg
        have_pg = 1
        pg_import = ''
    except ImportError, val:
        have_pg = 0
        pg_import = str(val)
    
    if not have_pg and 0: # FIXME: not yet tested
        try:
            import psycopg as pgdb
            have_pg = 1
        except ImportError, val:
            pg_import += str(val)
    if have_pg:
        adapters += 1
    
else:
    adapters = 0
    plg_detail = "disabled. Set the enviroment variable EIKAZO_SQLSAMPLE to 1, " + \
                 "if you want to use this plugin"
    

Plugins.Plugin('SQL Sample', plg_detail, 'output', None)

    
if enable_plugin and adapters:

    class SQLAdapter(Config.ConfigAware):
        """ derived classes must provide the methods __init__, get_widget,
            save, get_jobdata and the attribute name
            
        """
        # Theoretically, it would be reasonable to provide
        # a connection object and a cursor object and to use a generic
        # save method, but we are mostly interested in unique IDs, and
        # mySQL does not provide sequences, so we need to circumvent 
        # this limit anyway in the few required SQL statements. In other
        # words: at least right now there is no need for a decent
        # inheritance hierarchy..

        def __init__(self, sqlmain, config):
            raise SaneError("SQLAdapter.__init__ must be overloaded")
        
        def get_widget(self):
            """return a widget containing a button "configure adapter",
               status info etc
            """
            raise SaneError("SQLAdapter.build_widget must be overloaded")
        
        def generic_setup(self, title):
            sqlparm = gtk.Table(3,4)
            sqlparm.set_col_spacing(1, 20)
            sqlparm.set_col_spacing(0, 5)
            sqlparm.set_col_spacing(2, 5)
            
            label = gtk.Label("hostname:")
            label.set_alignment(0, 0.5)
            sqlparm.attach(label, 0, 1, 0, 1, xoptions=gtk.FILL)
            label.show()
            
            whostname = gtk.Entry()
            whostname.set_text(self.hostname)
            sqlparm.attach(whostname, 1, 2, 0, 1, xoptions=0)
            whostname.show()
            
            label = gtk.Label("database name:")
            label.set_alignment(0, 0.5)
            sqlparm.attach(label, 2, 3, 0, 1, xoptions=gtk.FILL)
            label.show()
            
            wdbname = gtk.Entry()
            wdbname.set_text(self.dbname)
            sqlparm.attach(wdbname, 3, 4, 0, 1, xoptions=0)
            wdbname.show()
            
            label = gtk.Label("user name:")
            label.set_alignment(0, 0.5)
            sqlparm.attach(label, 0, 1, 1, 2, xoptions=gtk.FILL)
            label.show()
            
            wusername = gtk.Entry()
            wusername.set_text(self.username)
            sqlparm.attach(wusername, 1, 2, 1, 2, xoptions=0)
            wusername.show()
            
            label = gtk.Label("password:")
            label.set_alignment(0, 0.5)
            sqlparm.attach(label, 2, 3, 1, 2, xoptions=gtk.FILL)
            label.show()
            
            wpassword = gtk.Entry()
            wpassword.set_text(self.password)
            sqlparm.attach(wpassword, 3, 4, 1, 2, xoptions=0)
            wpassword.set_visibility(False)
            wpassword.show()
            
            label = gtk.Label("port:")
            label.set_alignment(0, 0.5)
            sqlparm.attach(label, 0, 1, 2, 3, xoptions=gtk.FILL)
            label.show()
            
            wport = gtk.Entry()
            wport.set_text('%i' % self.port)
            wport.connect('insert-text', self._int_check)
            sqlparm.attach(wport, 1, 2, 2, 3, xoptions=0)
            wport.show()
            
            dlg = gtk.Dialog(title,
                             flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                             buttons=(gtk.STOCK_OK, gtk.RESPONSE_ACCEPT,
                                      gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT)
                            )
            dlg.vbox.pack_start(sqlparm)
            sqlparm.show()
            
            res = dlg.run()

            if res == gtk.RESPONSE_ACCEPT:
                self.hostname = whostname.get_text()
                self.dbname = wdbname.get_text()
                self.username = wusername.get_text()
                self.password = wpassword.get_text()
                
                porttext = wport.get_text()
                if porttext:
                    self.mysql_port = int(wport.get_text())
                self.connect()
                
            
            dlg.destroy()
            
        # FIXME: this should be moved to a "generic tools" module
        _int_re = re.compile('^[0-9]*$')
        def _int_check(self, w, new_text, textlen, pos):
            if not self._int_re.match(new_text):
                w.stop_emission('insert-text')
            
        
    if have_mysql:
        class MySQLAdapter(SQLAdapter):
            name = "MySQLAdapter"
            def __init__(self, sqlmain, config):
                Config.ConfigAware.__init__(self, config)
                
                self.sqlmain = sqlmain
                
                self.hostname = ''
                self.dbname   = ''
                self.username = ''
                self.password = ''
                self.port = 3306
        
                self.widget = gtk.HBox()
                
                self.setupbtn = gtk.Button("Setup MySQL connection parameters")
                self.widget.pack_start(self.setupbtn, expand=False, 
                                          fill=False)
                self.setupbtn.show()
                self.setupbtn.connect("clicked", self.setup)
                
                self.create_tblbtn = gtk.Button("Create SQL table 'scaninfo'")
                self.create_tblbtn.connect("clicked", self.create_table)
                self.widget.pack_start(self.create_tblbtn, expand=False,
                                          fill=False, padding=5)
                
                self.connstatus = gtk.Label()
                self.connstatus.set_alignment(0, 0.5)
                self.widget.pack_start(self.connstatus, expand=True,
                                          fill=False, padding=5)
                self.connstatus.show()
                
                self.readConfig()
            
                self.connection = self.connect()
            
            
            def get_widget(self):
                return self.widget
            
            def connect(self):
                try:
                    self.connection = MySQLdb.connect(host=self.hostname,
                                                      user=self.username,
                                                      passwd=self.password,
                                                      db=self.dbname,
                                                      port=self.port)
                except _mysql_exceptions.OperationalError, val:
                    self.connstatus.set_text("Connection Status: %s" % val)
                    self.connection = None
                else:
                    self.connstatus.set_text("Connection Status: connected")
                    # check, if a database is selected and if the scandemo 
                    # table exists
                    c = self.connection.cursor()
                    try:
                        try:
                            c.execute("select count(*) from scaninfo")
                        except _mysql_exceptions.OperationalError, val:
                            self.connstatus.set_text("Connection Status: %s" % val)
                            self.connection = None
                        except _mysql_exceptions.ProgrammingError, val:
                            self.connstatus.set_text("Connection Status: %s" % val)
                            self.connection = None
                            # table does not exist: show button to create the table
                            self.create_tblbtn.show()
                        else:
                            self.connstatus.set_text("Connection Status: connected")
                            self.create_tblbtn.hide()
                    finally:
                        c.close()
                if self.connection:
                    self.cursor = self.connection.cursor()
                else:
                    self.cursor = None
                self.sqlmain.activate(self.connection != None)
                
            def create_table(self, w):
                connection = MySQLdb.connect(host=self.hostname,
                                             user=self.username,
                                             passwd=self.password,
                                             db=self.dbname,
                                             port=self.port)
                c = connection.cursor()
                # imgtype: RGB/Gray scale / lineart
                # id is also used as a number when
                c.execute("""create table scaninfo 
                               (id int not null auto_increment primary key,
                                resolution int,
                                tlx int,
                                tly int,
                                brx int,
                                bry int,
                                imgtype varchar(10),
                                filename varchar(1000)
                               )
                          """)
                c.close()
                connection.commit()
                self.connect()
            
            def setup(self, w):
                self.generic_setup("MySQL connection parameters")
                return
                
            def get_jobid(self):
                # insert a new row into the table, get back its ID
                # real data will be filled in later: we need the ID
                # to generate the filename
                self.cursor.execute("insert into scaninfo () values ()")

                # MySQL can be a PITA... select LAST_INSERT_ID() returns every 
                # time 1; the advice in 
                # http://mail.zope.org/pipermail/zope-dev/2001-January/008733.html
                # does not work:
                # id = self.cursor.execute("select conv(LAST_INSERT_ID(), 10, 10)")
                # the cursor object has no method insert_id despite being 
                # documented in the MySQLdb user guide:
                # id = self.cursor.insert_id()
                # ...but the cursor should have the attribute lastrowid.
                # Hopefully, this is not too dependent on the version of the
                # MySQLdb module
                return self.cursor.lastrowid
                
            def save(self, job):
                # FIXME: if the update and commit calls below fail, the image
                # should be deleted. But this is a sample application, so
                # I don't bother that much about this
                sw = job.scanwindow
                self.cursor.execute(
                    """update scaninfo
                         set resolution = %i,
                             tlx        = %i,
                             tly        = %i,
                             brx        = %i,
                             bry        = %i,
                             imgtype    = '%s',
                             filename   = '%s'
                             where id = %i
                    """ % (job.resolution,
                           sw[0],
                           sw[2],
                           sw[1],
                           sw[3],
                           job.img.mode,
                           job.filename,
                           job.sqlid
                           ))
                # may or may not be necessary...
                self.connection.commit()

            def rollback(self, job):
                # if we have a mysql table that does not support transactions,
                # "manual" cleanup is reasonable
                if hasattr(job, 'sqlid'):
                    self.cursor.execute(
                        "delete from scaninfo where id=%i" % job.sqlid)
                # may or may not work...
                self.connection.rollback()
            
            def readConfig(self):
                print "FIXME: MySQLAdapter.readConfig not yet implemented"
    
            def writeConfig(self):
                print "FIXME: MySQLAdapter.writeConfig not yet implemented"
    
    if have_pg:
        class PGSQLAdapter(SQLAdapter):
            name = "PostgreSQLAdapter"
            def __init__(self, sqlmain, config):
                Config.ConfigAware.__init__(self, config)
                
                self.sqlmain = sqlmain
                
                self.hostname = ''
                self.dbname   = ''
                self.username = ''
                self.password = ''
                self.port = 5432
        
                self.widget = gtk.HBox()
                
                self.setupbtn = gtk.Button("Setup PostgreSQL connection parameters")
                self.widget.pack_start(self.setupbtn, expand=False, 
                                          fill=False)
                self.setupbtn.show()
                self.setupbtn.connect("clicked", self.setup)
                
                self.create_tblbtn = gtk.Button("Create SQL table 'scaninfo'")
                self.create_tblbtn.connect("clicked", self.create_table)
                self.widget.pack_start(self.create_tblbtn, expand=False,
                                          fill=False, padding=5)
                
                self.connstatus = gtk.Label()
                self.connstatus.set_alignment(0, 0.5)
                self.widget.pack_start(self.connstatus, expand=True,
                                          fill=False, padding=5)
                self.connstatus.show()
                
                self.readConfig()
            
                self.connect()
            
            
            def get_widget(self):
                return self.widget
            
            def connect(self):
                try:
                    if self.port:
                        hn = '%s:%s' % (self.hostname, self.port)
                    else:
                        hn = self.hostname
                    self.connection = pgdb.connect(host=hn,
                                                   user=self.username,
                                                   password=self.password,
                                                   database=self.dbname)
                except pgdb.InternalError, val:
                    self.connstatus.set_text("Connection Status: %s" % val)
                    self.connection = None
                else:
                    # check, if a database is selected and if the scaninfo 
                    # table exists
                    c = self.connection.cursor()
                    try:
                        try:
                            c.execute("select count(*) from scaninfo")
                        except pg.DatabaseError, val:
                            self.connstatus.set_text("Connection Status: %s" % val)
                            self.connection = None
                            # table does not exist: show button to create the table
                            self.create_tblbtn.show()
                        else:
                            self.connstatus.set_text("Connection Status: connected")
                            self.create_tblbtn.hide()
                    finally:
                        c.close()
                if self.connection:
                    self.cursor = self.connection.cursor()
                else:
                    self.cursor = None
                self.sqlmain.activate(self.connection != None)
                
            def create_table(self, w):
                if self.port:
                    hn = '%s:%s' % (self.hostname, self.port)
                else:
                    hn = self.hostname
                connection = pgdb.connect(host=hn,
                                          user=self.username,
                                          password=self.password,
                                          database=self.dbname)
                c = connection.cursor()
                # imgtype: RGB/Gray scale / lineart
                # id is also used as a number when
                c.execute("""create sequence scanid;
                             create table scaninfo 
                               (id int primary key,
                                resolution int,
                                tlx int,
                                tly int,
                                brx int,
                                bry int,
                                imgtype varchar(10),
                                filename varchar(1000)
                               )
                          """)
                c.close()
                connection.commit()
                self.connect()
            
            def setup(self, w):
                self.generic_setup("PostgreSQL connection parameters")
                return
                
            def get_jobid(self):
                self.cursor.execute("select nextval('scanid')")
                return self.cursor.fetchone()[0]
                
            def save(self, job):
                # FIXME: if the update and commit calls below fail, the image
                # should be deleted. But this is a sample application, so
                # I don't bother that much about this
                sw = job.scanwindow
                self.cursor.execute(
                    """insert into scaninfo
                        (id, resolution, tlx, tly, brx, bry, imgtype, filename)
                       values (%i, %i, %i, %i, %i, %i, '%s', '%s')
                    """ % (job.sqlid,
                           job.resolution,
                           sw[0],
                           sw[2],
                           sw[1],
                           sw[3],
                           job.img.mode,
                           job.filename,
                          ))
                self.connection.commit()

            def rollback(self, job):
                self.connection.rollback()
            
            def readConfig(self):
                print "FIXME: PostgreSQLAdapter.readConfig not yet implemented"
    
            def writeConfig(self):
                print "FIXME: PostgreAdapter.writeConfig not yet implemented"
    
    class ScanToSQL(SaneScanToFile.ScanToFile):
        name = N_("SQL Sample")
        connectlabel = N_("Enable SQL Sample")

        def __init__(self, notify_hub, config):
            global have_mysql, have_pg
            self.adapters = []
            self.active = 0 # index of the active SQL adapter
            SaneScanToFile.ScanToFile.__init__(self, notify_hub, config)
            
            if have_pg:
                self.adapters.append(PGSQLAdapter(self, config))

            if have_mysql:
                self.adapters.append(MySQLAdapter(self, config))
            
            # ugly patch: remove the unnecessary widgets from file output
            self.hboxfnum.remove(self.fcfield)
            self.hboxfnum.remove(self.fcinclabel)
            self.hboxfnum.remove(self.fcincfield)
        
            self.sqlwidget = gtk.HBox()
            self.widget.pack_start(self.sqlwidget, expand=False, fill=False)
            self.widget.reorder_child(self.sqlwidget, 0)
            self.sqlwidget.show()

            if len(self.adapters) > 1:
                self.adapter_select_box = gtk.combo_box_new_text()
                for a in self.adapters:
                    self.adapter_select_box.append_text(a.name)
                self.adapter_select_box.set_active(self.active)
                label = gtk.Label("Select SQL Adapter")
                self.sqlwidget.pack_start(label, expand=False, fill=False)
                label.show()
                self.sqlwidget.pack_start(self.adapter_select_box,
                                expand=False, fill=False, padding=5)
                self.adapter_select_box.show()
                self.adapter_select_box.connect("changed", self.cb_adapter)
                
            for index in range(len(self.adapters)):
                w = self.adapters[index].get_widget()
                self.sqlwidget.pack_start(w, expand=False)
                if index == self.active:
                    w.show()
            
            self.activate(self.adapters[self.active].connection != None)                
        
        def cb_adapter(self, w):
            self.adapters[self.active].get_widget().hide()
            self.active = w.get_active()
            a = self.adapters[self.active]
            a.get_widget().show()
            self.activate(a.connection != None)

        def set_filename(self, filename):
            """ returns 0, if the filename is "useful", or an error
                message, if integers could 
            """
            if filename.find('%') >= 0:
                try:
                    filename % 1
                    self.filename = filename
                    return 0
                except:
                    self.fnfield.set_text(self.filename)
                    return _("can't insert a file number into the file name")
            return 0
            
        def fnbrowse_click(self, w):
            self._fnbrowse_click(w, True)

        def get_jobdata(self, job):
            job.sqlid = self.adapters[self.active].get_jobid()
            res = self.filename % job.sqlid
            job.filename = res
            return res
            
        def save(self, job):
            try:
                SaneScanToFile.ScanToFile.save(self, job)
            except:
                self.adapters[self.active].rollback(job)
                raise
            else:
                self.adapters[self.active].save(job)
        
        def readConfig(self):
            outputinfo.OutputProvider.readConfig(self)
            val = self.config.get('output', 'sqlsample-filename')
            if val != None:
                self.filename = val
                self.fnfield.set_text(val)
            
            val = self.config.get('output', 'sqlsample-format')
            if val != None:
                self.set_fileformat(val)
                for i in xrange(len(_fileformats)):
                    if _fileformats[i].name == val:
                        self.fmt.set_active(i)
                        break
        
        def writeConfig(self):
            outputinfo.OutputProvider.writeConfig(self)
            self.config.set('output', 'sqlsample-filename', self.filename)
            self.config.set('output', 'sqlsample-format', self.format)
    
def register():
    if enable_plugin and adapters:
        return [ScanToSQL]
    else:
        return []
