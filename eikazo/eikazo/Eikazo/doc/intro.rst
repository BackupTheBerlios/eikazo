+-------------------------------+--------------------------------------+
| `up: Contents <index.html>`_  | `next: User Interface <gui.html>`_   |
+-------------------------------+--------------------------------------+

======================================================================
Introduction
======================================================================

Eikazo -- a GTK and Python based frontend for SANE

features
========

- designed to be fast. If a scanner has a document feeder and if if the 
  ADF is enabled, a new scan is started, before the data of a previous
  scan has been written to a disk file or printed. The processing time
  for a scan image is typically below one second, so that fast
  document scanners are well supported.
- more than one output per scan is possible. You can simultaneously 
  save the scanned image into a file and print it.
- the image of every scan is displayed in a preview window.
- plugin mechanisms for device specific features, for scan filters
  and for output generation. This allows the easy addition of special
  purpose scan filters or of a database integration.

  At present, the following filters are available:

  - adaptive lineart thresholding, allowing reliable generation of lineart
    images from documents with varying background color or 
  - some filters provided by ImageMagick

  planned:
  
  - deskewing (in combination with an appropriate device plugin)
  

