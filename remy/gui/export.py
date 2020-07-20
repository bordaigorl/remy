from remy import *

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtPrintSupport import *

import remy.remarkable.constants as rm

from PyPDF2 import PdfFileReader, PdfFileWriter
from PyPDF2.pdf import PageObject
from PyPDF2.utils import PdfReadError
from PyPDF2.generic import NullObject



class TolerantPdfWriter(PdfFileWriter):
# This is needed to make the PDF exporter more tolerant to errors in PDFs.
# pdftk may leave some orphan obj references for example
# and that would make the writer choke.
# Instead here we tolerate such missing refs and just produce empty objects for them

  def _sweepIndirectReferences(self, externMap, data):
    try:
      return super(TolerantPdfWriter, self)._sweepIndirectReferences(externMap, data)
    except PdfReadError:
     return NullObject()


import logging
log = logging.getLogger('remy')


def _progress(p, i, t):
  if callable(p):
    p(i, t)

def scenesPdf(scenes, outputPath, progress=None):
  printer = QPrinter(QPrinter.HighResolution)
  printer.setOutputFormat(QPrinter.PdfFormat)
  # printer.setPageSize(QPrinter.A4)
  printer.setOutputFileName(outputPath)
  printer.setPaperSize(QSizeF(HEIGHT_MM,WIDTH_MM), QPrinter.Millimeter)
  printer.setPageMargins(0,0,0,0, QPrinter.Millimeter)
  p=QPainter()
  p.begin(printer)
  _progress(progress, 0, len(scenes))
  for i in range(len(scenes)):
    if i > 0:
      printer.newPage()
    scenes[i].render(p)
    _progress(progress, i, len(scenes))
  p.end()


def pdfmerge(scenes, basePath, outputPath, progress=None):
  baseReader = PdfFileReader(basePath, strict=False)
  pageNum = min(baseReader.getNumPages(), len(scenes))

  writer = TolerantPdfWriter()
  annotReader = PdfFileReader(outputPath, strict=False)
  _progress(progress, 0, pageNum + 1)
  for page in range(pageNum):
    bp = baseReader.getPage(page)
    ap = annotReader.getPage(page)

    s = ap.cropBox or ap.artBox
    aw, ah = s.upperRight[0] - s.upperLeft[0], s.upperLeft[1] - s.lowerLeft[1]
    s = bp.cropBox or bp.artBox
    w, h = s.upperRight[0] - s.upperLeft[0], s.upperLeft[1] - s.lowerLeft[1]

    np = PageObject.createBlankPage(writer, aw, ah)
    if w <= h:
      ratio = min(aw / w, ah / h)
      tx = 0
      ty = ah - ( h * ratio )
      rot = 0
    else:
      w, h = h, w
      ratio = min(aw / w, ah / h)
      tx = w * ratio
      ty = ah - ( h * ratio )
      rot = 90
    np.mergeRotatedScaledTranslatedPage(bp, rot, ratio, tx, ty)
    np.mergePage(ap)

    writer.addPage(np)
    _progress(progress, page, pageNum + 1)

  with open(outputPath, 'wb') as out:
    writer.write(out)

  _progress(progress, pageNum + 1, pageNum + 1)
  log.info("Export of %s is done", outputPath)