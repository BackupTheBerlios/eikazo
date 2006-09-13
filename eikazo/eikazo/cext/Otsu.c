#define COPYRIGHT "\
Otsu Threshold\n\
\n\
Copyright (c) Abel Deuring 2006 <adeuring@gmx.net>\n\
\n\
This program is free software; you can redistribute it and/or modify\n\
it under the terms of the GNU General Public License as published by\n\
the Free Software Foundation; either version 2 of the License, or\n\
(at your option) any later version.\n\
\n\
This program is distributed in the hope that it will be useful,\n\
but WITHOUT ANY WARRANTY; without even the implied warranty of\n\
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n\
GNU General Public License for more details.\n\
\n\
You should have received a copy of the GNU General Public License\n\
along with this program; if not, write to the Free Software\n\
Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.\n\
"

#include "Imaging.h"
#include <Python.h>

static PyObject* 
copyright(PyObject* self, PyObject *args) 
{
    return Py_BuildValue("s", COPYRIGHT);
}

static PyObject*
otsu(PyObject* self, PyObject *args)
{
#ifdef WITH_THREAD
    PyThreadState *_save;
#endif
    PyObject *pyHist, *elem;
    int i, j, histsize, maxpos;
    double *cHist = NULL, *mu=NULL, *p=NULL;
    double sum, musum, test;

    if (!PyArg_ParseTuple(args, "O", &pyHist)) {
        PyErr_SetString(PyExc_TypeError, "invalid arguments");
        return NULL;
    }
    
    if (!PySequence_Check(pyHist)) {
        PyErr_SetString(PyExc_TypeError, "argument of otsu() must be a list of numbers");
        return NULL;
    }
    
    histsize = PySequence_Length(pyHist);
    if (histsize == 0) {
        PyErr_SetString(PyExc_TypeError, "otsu(): histogram may not be an empty sequence");
        return NULL;
    }
    
    cHist = malloc(sizeof(double) * histsize);
    if (!cHist) {
        PyErr_SetString(PyExc_MemoryError, "otsu(): out of memory");
        goto error2;
    }
    
    sum = 0.0;
    for (i = 0; i < histsize; i++) {
        elem = PySequence_ITEM(pyHist, i);
        if (!PyNumber_Check(elem)) {
            PyErr_SetString(PyExc_TypeError, "argument of otsu() must be a list of numbers");
            goto error2;
        }
        sum += cHist[i] = PyFloat_AsDouble(elem);
    }
    
    if (sum == 0.0) {
        PyErr_SetString(PyExc_ValueError, "otsu(); histogram sum is zero");
        goto error2;
    }
    
    Py_UNBLOCK_THREADS

    sum = 1.0 / sum;
    for (i=0; i<histsize; i++) {
        cHist[i] *= sum;
    }
    
    mu = malloc(sizeof(double) * histsize);
    if (!mu) {
        PyErr_SetString(PyExc_MemoryError, "otsu(): out of memory");
        goto error1;
    }
    
    p = malloc(sizeof(double) * histsize);
    if (!p) {
        PyErr_SetString(PyExc_MemoryError, "otsu(): out of memory");
        goto error1;
    }
    
    musum = sum = 0.0;
    for (i = 0; i < histsize; i++) {
        double x;
        x = cHist[i];
        musum += i * x;
        mu[i] = musum;
        sum += x;
        p[i] = sum;
    }
    
    test = 0.0;
    maxpos = 127; /* default */

    for (i = 0; i < histsize; i++) {
        double sigma_f, sigma_b, x, y, z, zminus, t;

        sigma_f = 0.0;
        for (j = 0; j <=i; j++) {
            x = j - mu[i];
            sigma_f += x * x * cHist[j];
        }
        
        sigma_b = 0;
        for (j=i+1; j < histsize; j++) {
            x = j - musum + mu[i];
            sigma_b += x * x * cHist[j];
        }
        
        z = p[i];
        zminus = 1.0 - z;
        t = 2.0*mu[i] - musum;
        x = z * zminus * t * t;
        y = z * sigma_f + zminus * sigma_b;
        x = x / y;
        if (x > test) {
            maxpos = i;
            test = x;
        }
    }
    
    free(cHist);
    free(mu);
    free(p);
    
    Py_BLOCK_THREADS
    
    return PyInt_FromLong(maxpos);

  error1:
    Py_UNBLOCK_THREADS
  error2:
    if (cHist) free(cHist);
    if (mu)    free(mu);
    if (p)     free(p);
    
    return NULL;
}



static PyMethodDef MeanFilter_methods[] = {
  {"copyright", copyright, 1, ".copyright"},
  {"otsu", otsu, 1, ".meanFilter(histogram)"},
};

void initotsu() {
    Py_InitModule("otsu", MeanFilter_methods);
}
