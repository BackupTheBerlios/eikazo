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

Averaging filters for the Python Imaging Library

"""


import _meanFilter, Image

def meanFilter(im, size):
    """ for each pixel, calculate the average of all pixel values
        in a square area around the pixel.
        The pixel value in the result image is set to the average.
        size is the size of the square; must be a positive odd number, and
        may not be larger than the image dimensions
    """
    im.load()
    imOut = Image.new(im.mode, im.size, None)
    _meanFilter.meanFilter(im.im.id, imOut.im.id, size)
    return imOut

def adaptiveThresholdFilter(im, size, offset):
    """ for each pixel, calculate the average of all pixel values
        in a square area around the pixel.
        If the value of center pixel is less than average plus offset,
        set the value in the result image to "black", else to "white"
    """
    im.load()
    imOut = Image.new(im.mode, im.size, None)
    _meanFilter.adaptiveThresholdFilter(im.im.id, imOut.im.id, size, offset)
    return imOut

def fixedThresholdFilter(im, size, offset):
    """ for each pixel, calculate the average of all pixel values
        in a square area around the pixel.
        size is the size of the square; must be a positive odd number, and
        may not be larger than the image dimensions
    """
    im.load()
    imOut = Image.new(im.mode, im.size, None)
    _meanFilter.fixedThresholdFilter(im.im.id, imOut.im.id, size, offset)
    return imOut

