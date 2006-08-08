#define COPYRIGHT "\
Averaging filters for the Python Imaging Library\n\
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
meanFilter(PyObject* self, PyObject *args)
{
#ifdef WITH_THREAD
    PyThreadState *_save;
#endif
    long idIn, idOut;
    Imaging im, imOut;
    int size;
    int x, y, xmax, ymax, xsize, ysize, size2;

    if (!PyArg_ParseTuple(args, "lli", &idIn, &idOut, &size)) {
        PyErr_SetString(PyExc_TypeError, "invalid arguments");
        return NULL;
    }
    
    im = (Imaging) idIn;
    imOut = (Imaging) idOut;
    

    if (!im || im->bands != 1 || im->type == IMAGING_TYPE_SPECIAL) {
	PyErr_SetString(PyExc_ValueError, "invalid image mode");
        return NULL;
    }

    xsize = im->xsize;
    ysize = im->ysize;

    if (!(size & 1)) {
	PyErr_SetString(PyExc_ValueError, "bad filter size");
        return NULL;
    }

    if ((size > xsize) || (size > ysize) || (size < 0)) {
	PyErr_SetString(PyExc_ValueError, "bad filter size");
        return NULL;
    }

    Py_UNBLOCK_THREADS
    
    size2 = xsize * ysize;
    
    /* Calculate first a sum over 2*size+1 neighboring horizontal pixels.
       In the second step, these sums will again be summed up vertically.
    */
#define MEAN_BODY(type, sumtype, data)  { \
    type *lineptr, *lineptr2, **dstimg, **srcimg; \
    sumtype *buf, *sumbuf; \
    register sumtype *bufptr, *bufptr2, *sumptr; \
    register sumtype sum; \
    register sumtype divisor; \
 \
    divisor = size * size; \
    size = size / 2; \
 \
    buf = malloc(size2 * sizeof(sumtype)); \
    if (!buf) \
        goto nomemory; \
 \
    sumbuf = malloc(xsize * sizeof(sumtype)); \
    if (!sumbuf) { \
        free(buf); \
        goto nomemory; \
    } \
 \
    /* causes a segfault \
    srcimg = &IMAGING_PIXEL_##type(im, 0, 0); */ \
    srcimg = im->data; \
    bufptr = buf; \
    for (y = 0; y < ysize; y++) { \
        /* "extend" the border pixel to the left */ \
        lineptr = lineptr2 = srcimg[y]; \
        sum = size * (*lineptr); \
        for (x = 0; x < size; x++) { \
            sum += *lineptr++; \
        } \
 \
        for (x = 0; x < size; x++) { \
            sum += *lineptr++; \
            *bufptr = sum; \
            bufptr++; \
            sum -= (*lineptr2); \
        } \
 \
        xmax = xsize - size; \
        for (x = size; x < xmax; x++) { \
            sum += *lineptr++; \
            *bufptr = sum; \
            bufptr++; \
            sum -= *lineptr2++; \
        } \
 \
        lineptr--; \
        for (x = xmax; x < xsize; x++) { \
            sum += *lineptr; \
            *bufptr = sum; \
            bufptr++; \
            sum -= *lineptr2++; \
        } \
    } \
 \
    sumptr = sumbuf; \
    bufptr = bufptr2 = buf; \
    /* causes a segfault \
    dstimg = &IMAGING_PIXEL_##type(imOut, 0, 0); */ \
    dstimg = imOut->data; \
 \
    for (x = 0; x < xsize; x++) { \
        *sumptr++ = size * *bufptr++; \
    } \
 \
    bufptr = buf; \
    for (y = 0; y < size; y++) { \
        sumptr = sumbuf; \
        for (x = 0; x < xsize; x++) { \
            *sumptr++ += *bufptr++; \
        } \
    } \
 \
    for (y = 0; y < size; y++) { \
        sumptr = sumbuf; \
        bufptr2 = buf; \
        lineptr = dstimg[y]; \
        for (x = 0; x < xsize; x++) { \
            *sumptr += *bufptr++; \
            *lineptr++ = *sumptr / divisor; \
            *sumptr++ -= *bufptr2++; \
        } \
    } \
 \
    ymax = ysize - size; \
    bufptr2 = buf; \
 \
    for (y = size; y < ymax; y++) { \
        sumptr = sumbuf; \
        lineptr = dstimg[y]; \
        for (x = 0; x < xsize; x++) { \
            *sumptr += *bufptr++; \
            *lineptr++ = *sumptr / divisor; \
            *sumptr++ -= *bufptr2++; \
        } \
    } \
 \
    for (y = ymax; y < ysize; y++) { \
        sumptr = sumbuf; \
        bufptr = buf + (ysize-1) * xsize; \
        lineptr = dstimg[y]; \
        for (x = 0; x < xsize; x++) { \
            *sumptr += *bufptr++; \
            *lineptr++ = *sumptr / divisor; \
            *sumptr++ -= *bufptr2++; \
        } \
    } \
 \
 \
    free(buf); \
    free(sumbuf); \
  }

    if (im->image8)
        MEAN_BODY(UINT8, INT32, image8)
    else if (im->type == IMAGING_TYPE_INT32)
        MEAN_BODY(INT32, INT32, image32)
    else if (im->type == IMAGING_TYPE_FLOAT32)
        MEAN_BODY(FLOAT32, FLOAT32, image32)
    else {
        /* safety net (we shouldn't end up here) */
	Py_BLOCK_THREADS
	PyErr_SetString(PyExc_ValueError, "invalid image mode");
        return NULL;
    }
    
    Py_BLOCK_THREADS
    Py_INCREF(Py_None);
    return Py_None;

nomemory:
    Py_BLOCK_THREADS
    PyErr_SetString(PyExc_MemoryError, "cannot allocate output image");
    return NULL;
}


static PyObject*
adaptiveThresholdFilter(PyObject* self, PyObject *args)
{
#ifdef WITH_THREAD
    PyThreadState *_save;
#endif
    long idIn, idOut;
    Imaging im, imOut;
    int size, x, y, xmax, ymax, xsize, ysize, size2;
    float offset;

    if (!PyArg_ParseTuple(args, "llif", &idIn, &idOut, &size, &offset)) {
        PyErr_SetString(PyExc_TypeError, "invalid arguments");
        return NULL;
    }
    
    im = (Imaging) idIn;
    imOut = (Imaging) idOut;

    if (!im || im->bands != 1 || im->type == IMAGING_TYPE_SPECIAL) {
	PyErr_SetString(PyExc_ValueError, "invalid image mode");
	return NULL;
    }

    xsize = im->xsize;
    ysize = im->ysize;

    if (!(size & 1)) {
	PyErr_SetString(PyExc_ValueError, "bad filter size");
	return NULL;
    }

    if ((size > xsize) || (size > ysize) || (size < 0)){
	PyErr_SetString(PyExc_ValueError, "bad filter size");
	return NULL;
    }

    Py_UNBLOCK_THREADS
    
    size2 = xsize * ysize;

    /* Calculate first a sum over 2*size+1 neighboring horizontal pixels.
       In the second step, these sums will again be summed up vertically.
    */
#define MEAN_AD_THRSHLD_BODY(type, sumtype, data, max)  { \
    type *lineptr, *lineptr2, **dstimg, **srcimg; \
    sumtype *buf, *sumbuf; \
    register sumtype *bufptr, *bufptr2, *sumptr; \
    register sumtype sum; \
    register sumtype divisor, _offset; \
 \
    divisor = size * size; \
    size = size / 2; \
    _offset = offset * divisor; \
 \
    buf = malloc(size2 * sizeof(sumtype)); \
    if (!buf) \
        goto nomemory; \
 \
    sumbuf = malloc(xsize * sizeof(sumtype)); \
    if (!sumbuf) { \
        free(buf); \
        goto nomemory; \
    } \
 \
    srcimg = im->data; \
    bufptr = buf; \
    for (y = 0; y < ysize; y++) { \
        /* "extend" the border pixel to the left */ \
        lineptr = lineptr2 = srcimg[y]; \
        sum = size * (*lineptr); \
        for (x = 0; x < size; x++) { \
            sum += *lineptr++; \
        } \
 \
        for (x = 0; x < size; x++) { \
            sum += *lineptr++; \
            *bufptr = sum; \
            bufptr++; \
            sum -= (*lineptr2); \
        } \
 \
        xmax = xsize - size; \
        for (x = size; x < xmax; x++) { \
            sum += *lineptr++; \
            *bufptr = sum; \
            bufptr++; \
            sum -= *lineptr2++; \
        } \
 \
        lineptr--; \
        for (x = xmax; x < xsize; x++) { \
            sum += *lineptr; \
            *bufptr = sum; \
            bufptr++; \
            sum -= *lineptr2++; \
        } \
    } \
 \
    sumptr = sumbuf; \
    bufptr = bufptr2 = buf; \
    dstimg = imOut->data; \
    srcimg = im->data; \
 \
    for (x = 0; x < xsize; x++) { \
        *sumptr++ = size * *bufptr++; \
    } \
 \
    bufptr = buf; \
    for (y = 0; y < size; y++) { \
        sumptr = sumbuf; \
        for (x = 0; x < xsize; x++) { \
            *sumptr++ += *bufptr++; \
        } \
    } \
 \
    for (y = 0; y < size; y++) { \
        sumptr = sumbuf; \
        bufptr2 = buf; \
        lineptr = dstimg[y]; \
        lineptr2 = srcimg[y]; \
        for (x = 0; x < xsize; x++) { \
            *sumptr += *bufptr++; \
            *lineptr++ = *lineptr2++ * divisor < *sumptr + _offset ? 0 : max; \
            *sumptr++ -= *bufptr2++; \
        } \
    } \
 \
    ymax = ysize - size; \
    bufptr2 = buf; \
 \
    for (y = size; y < ymax; y++) { \
        sumptr = sumbuf; \
        lineptr = dstimg[y]; \
        lineptr2 = srcimg[y]; \
        for (x = 0; x < xsize; x++) { \
            *sumptr += *bufptr++; \
            *lineptr++ = *lineptr2++ * divisor < *sumptr + _offset ? 0 : max; \
            *sumptr++ -= *bufptr2++; \
        } \
    } \
 \
    for (y = ymax; y < ysize; y++) { \
        sumptr = sumbuf; \
        bufptr = buf + (ysize-1) * xsize; \
        lineptr = dstimg[y]; \
        lineptr2 = srcimg[y]; \
        for (x = 0; x < xsize; x++) { \
            *sumptr += *bufptr++; \
            *lineptr++ = *lineptr2++ * divisor < *sumptr + _offset ? 0 : max; \
            *sumptr++ -= *bufptr2++; \
        } \
    } \
 \
 \
    free(buf); \
    free(sumbuf); \
  }

    /* FIXME: What are the max values for int32 and float?? */
    if (im->image8)
        MEAN_AD_THRSHLD_BODY(UINT8, INT32, image8, 255)
    else if (im->type == IMAGING_TYPE_INT32)
        MEAN_AD_THRSHLD_BODY(INT32, INT32, image32, 255)
    else if (im->type == IMAGING_TYPE_FLOAT32)
        MEAN_AD_THRSHLD_BODY(FLOAT32, FLOAT32, image32, 1.0)
    else {
        /* safety net (we shouldn't end up here) */
	Py_BLOCK_THREADS
	PyErr_SetString(PyExc_ValueError, "invalid image mode");
        return NULL;
    }
    
    Py_BLOCK_THREADS
    Py_INCREF(Py_None);
    return Py_None;

nomemory:
    Py_BLOCK_THREADS
    PyErr_SetString(PyExc_MemoryError, "cannot allocate output image");
    return NULL;
}


static PyObject*
fixedThresholdFilter(PyObject* self, PyObject *args)
{
#ifdef WITH_THREAD
    PyThreadState *_save;
#endif
    long idIn, idOut;
    Imaging im, imOut;
    int size, x, y, xmax, ymax, xsize, ysize, size2;
    float level;

    if (!PyArg_ParseTuple(args, "llif", &idIn, &idOut, &size, &level)) {
        PyErr_SetString(PyExc_TypeError, "invalid arguments");
        return NULL;
    }
    
    im = (Imaging) idIn;
    imOut = (Imaging) idOut;
    
    if (!im || im->bands != 1 || im->type == IMAGING_TYPE_SPECIAL){
	PyErr_SetString(PyExc_ValueError, "invalid image mode");
        return NULL;
    }

    xsize = im->xsize;
    ysize = im->ysize;

    if (!(size & 1)) {
	PyErr_SetString(PyExc_ValueError, "bad filter size");
        return NULL;
    }

    if ((size > xsize) || (size > ysize) || (size < 0)) {
	PyErr_SetString(PyExc_ValueError, "bad filter size");
        return NULL;
    }

    Py_UNBLOCK_THREADS
    size2 = xsize * ysize;

    /* Calculate first a sum over 2*size+1 neighboring horizontal pixels.
       In the second step, these sums will again be summed up vertically.
    */
#define MEAN_FIXED_THRSHLD_BODY(type, sumtype, data, max)  { \
    type *lineptr, *lineptr2, **dstimg, **srcimg; \
    sumtype *buf, *sumbuf; \
    register sumtype *bufptr, *bufptr2, *sumptr; \
    register sumtype sum; \
    register sumtype _level; \
 \
    _level = (size * size - level) * max; \
    size = size / 2; \
 \
    buf = malloc(size2 * sizeof(sumtype)); \
    if (!buf) \
        goto nomemory; \
 \
    sumbuf = malloc(xsize * sizeof(sumtype)); \
    if (!sumbuf) { \
        free(buf); \
        goto nomemory; \
    } \
 \
    srcimg = im->data; \
    bufptr = buf; \
    for (y = 0; y < ysize; y++) { \
        /* "extend" the border pixel to the left */ \
        lineptr = lineptr2 = srcimg[y]; \
        sum = size * (*lineptr); \
        for (x = 0; x < size; x++) { \
            sum += *lineptr++; \
        } \
 \
        for (x = 0; x < size; x++) { \
            sum += *lineptr++; \
            *bufptr = sum; \
            bufptr++; \
            sum -= (*lineptr2); \
        } \
 \
        xmax = xsize - size; \
        for (x = size; x < xmax; x++) { \
            sum += *lineptr++; \
            *bufptr = sum; \
            bufptr++; \
            sum -= *lineptr2++; \
        } \
 \
        lineptr--; \
        for (x = xmax; x < xsize; x++) { \
            sum += *lineptr; \
            *bufptr = sum; \
            bufptr++; \
            sum -= *lineptr2++; \
        } \
    } \
 \
    sumptr = sumbuf; \
    bufptr = bufptr2 = buf; \
    dstimg = imOut->data; \
    srcimg = im->data; \
 \
    for (x = 0; x < xsize; x++) { \
        *sumptr++ = size * *bufptr++; \
    } \
 \
    bufptr = buf; \
    for (y = 0; y < size; y++) { \
        sumptr = sumbuf; \
        for (x = 0; x < xsize; x++) { \
            *sumptr++ += *bufptr++; \
        } \
    } \
 \
    for (y = 0; y < size; y++) { \
        sumptr = sumbuf; \
        bufptr2 = buf; \
        lineptr = dstimg[y]; \
        lineptr2 = srcimg[y]; \
        for (x = 0; x < xsize; x++) { \
            *sumptr += *bufptr++; \
            *lineptr++ = *sumptr < _level ? *lineptr2 : max; \
            lineptr2++; \
            *sumptr++ -= *bufptr2++; \
        } \
    } \
 \
    ymax = ysize - size; \
    bufptr2 = buf; \
 \
    for (y = size; y < ymax; y++) { \
        sumptr = sumbuf; \
        lineptr = dstimg[y]; \
        lineptr2 = srcimg[y]; \
        for (x = 0; x < xsize; x++) { \
            *sumptr += *bufptr++; \
            *lineptr++ = *sumptr < _level ? *lineptr2 : max; \
            lineptr2++; \
            *sumptr++ -= *bufptr2++; \
        } \
    } \
 \
    for (y = ymax; y < ysize; y++) { \
        sumptr = sumbuf; \
        bufptr = buf + (ysize-1) * xsize; \
        lineptr = dstimg[y]; \
        lineptr2 = srcimg[y]; \
        for (x = 0; x < xsize; x++) { \
            *sumptr += *bufptr++; \
            *lineptr++ = *sumptr < _level ? *lineptr2 : max; \
            lineptr2++; \
            *sumptr++ -= *bufptr2++; \
        } \
    } \
 \
 \
    free(buf); \
    free(sumbuf); \
  }

    /* FIXME: What are the max values for int32 and float?? */
    if (im->image8)
        MEAN_FIXED_THRSHLD_BODY(UINT8, INT32, image8, 255)
    else if (im->type == IMAGING_TYPE_INT32)
        MEAN_FIXED_THRSHLD_BODY(INT32, INT32, image32, 255)
    else if (im->type == IMAGING_TYPE_FLOAT32)
        MEAN_FIXED_THRSHLD_BODY(FLOAT32, FLOAT32, image32, 1.0)
    else {
        /* safety net (we shouldn't end up here) */
	Py_BLOCK_THREADS
	PyErr_SetString(PyExc_ValueError, "invalid image mode");
        return NULL;
    }
    
    Py_BLOCK_THREADS
    Py_INCREF(Py_None);
    return Py_None;

nomemory:
    Py_BLOCK_THREADS
    PyErr_SetString(PyExc_MemoryError, "cannot allocate output image");
    return NULL;
}



static PyMethodDef MeanFilter_methods[] = {
  {"copyright", copyright, 1, ".copyright"},
  {"meanFilter", meanFilter, 1, ".meanFilter(imIn.im.id, imOut.im.id, size)"},
  {"adaptiveThresholdFilter", adaptiveThresholdFilter, 1, 
             ".adaptiveThresholdFilter(imIn.im.id, imOut.im.id, size, offset)"},
  {"fixedThresholdFilter", fixedThresholdFilter, 1,
             ".fixedThresholdFilter(imIn.im.id, imOut.im.id, size, threshold)"}
};

void init_meanFilter() {
    Py_InitModule("_meanFilter", MeanFilter_methods);
}
