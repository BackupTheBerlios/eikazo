from distutils.core import setup, Extension
import os

dir = os.path.split(__file__)[0]
if dir:
    os.chdir(dir)

mofiles = []
for dir in os.listdir('Eikazo/mo'):
    mf = os.path.join('mo', dir, 'LC_MESSAGES', '*.mo')
    mofiles.append(mf)


setup(name='Eikazo',
           version='0.3',
           author='Abel Deuring',
           author_email='adeuring@gmx.net',
           license = 'GPL',
           packages=['Eikazo', 
                     'Eikazo/output',
                     'Eikazo/devices',
                     'Eikazo/postprocessing',
                    ],
           package_data={'Eikazo': ['version.txt',
                                     'doc/*.rst', 
                                     'doc/*.html',
                                     'doc/*.css',
                                     'doc/images/*'] + mofiles},
           scripts=['eikazo'],
           ext_modules = [Extension('_meanFilter',
                                    ['cext/MeanFilter.c'],
                                    extra_compile_args=['-Wall'],
                                   )
                         ]
     )