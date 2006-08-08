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

a bit of internationalisation

"""
import gettext, sys, os
import Plugins

_tdomains = {}

_plugin_info = Plugins.Plugin('I18n', 'Internationalisation', 'other', None)
_i18ndirs = ['/usr/local/share/locale', '/usr/share/locale']
_p = os.path.split(__file__)[0]
_p = os.path.join(_p, 'mo')
_i18ndirs.insert(0, _p)


def get_translation(domain):
    """ find a translation file for a domain
    """
    if _tdomains.has_key(domain):
        return _tdomains[domain]
    t = None
    for d in _i18ndirs:
        try:
            t = gettext.translation(domain, d)
            _ = t.gettext
            break
        except IOError:
            pass
    if t:
        domaintext = "Translation for domain %s found" % domain
    else:
        domaintext = "Translation for domain %s not found" % domain
    _plugin_info.details = '%s\n    %s' % (_plugin_info.details, domaintext)
    
    _tdomains[domain] = t
    if t == None:
        sys.stderr.write("warning: could not find translation file for domain %s\n" % domain)
    return t
