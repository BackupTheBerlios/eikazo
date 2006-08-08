#!/usr/bin/python

import os, subprocess

os.chdir(os.path.split(__file__)[0])

modir = os.path.join('..', 'mo')
modirs = os.listdir(modir)

for name in os.listdir('.'):
    test = name.rfind('.po')
    if test > 0 and test + 3 == len(name):
        lang = name[:-3]
        dst = os.path.join(modir, lang, 'LC_MESSAGES')
        if not lang in modirs:
            os.makedirs(dst)
        dst = os.path.join(dst, 'eikazo.mo')
        subprocess.call(['msgfmt', '-o', dst, name])

    
    