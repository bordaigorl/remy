from remy import *

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtPrintSupport import *

from PyPDF2 import PdfFileReader, PdfFileWriter
from PyPDF2.pdf import PageObject
from PyPDF2.utils import PdfReadError
from PyPDF2.generic import NullObject

from remy.remarkable.metadata import PDFBasedDoc
from remy.remarkable.render import BarePageScene, Palette

import logging
log = logging.getLogger('remy')



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


def _progress(p, i, t):
  if callable(p):
    p(i, t)

def scenesPdf(scenes, pages, outputPath, progress=None, tot=0):
  printer = QPrinter(QPrinter.HighResolution)
  printer.setOutputFormat(QPrinter.PdfFormat)
  # printer.setPageSize(QPrinter.A4)
  printer.setOutputFileName(outputPath)
  printer.setPaperSize(QSizeF(HEIGHT_MM,WIDTH_MM), QPrinter.Millimeter)
  printer.setPageMargins(0,0,0,0, QPrinter.Millimeter)
  printer.setCreator('Remy')
  p=QPainter()
  p.begin(printer)
  try:
    _progress(progress, 0, tot)
    for (i,scene) in enumerate(scenes(pages)):
      if i > 0:
        printer.newPage()
      scene.render(p)
      _progress(progress, i+1, tot)
  except Exception as e:
    raise e
  finally:
    p.end()


def pdfrotate(outputPath, rotate=0):
  reader = PdfFileReader(outputPath, strict=False)
  writer = TolerantPdfWriter()
  for pageNum in range(reader.numPages):
    page = reader.getPage(pageNum)
    page.rotateClockwise(90)
    writer.addPage(page)
  with open(outputPath, 'wb') as out:
    writer.write(out)


def pdfmerge(basePath, outputPath, pdfRanges=None, rotate=0, progress=None):
  if isinstance(basePath, PdfFileReader):
    baseReader = basePath
  else:
    baseReader = PdfFileReader(basePath, strict=False)
  annotReader = PdfFileReader(outputPath, strict=False)
  if pdfRanges is None:
    pageNum = min(baseReader.getNumPages(), annotReader.getNumPages())
    pdfRanges = range(pageNum)
  else:
    pageNum = sum(len(r) for r in pdfRanges)
    pdfRanges = chain(*pdfRanges)
  writer = TolerantPdfWriter()
  _progress(progress, 0, pageNum + 1)
  for apage, page in enumerate(pdfRanges):
    bp = baseReader.getPage(page)
    ap = annotReader.getPage(apage)

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
    if rotate:
      np.rotateCounterClockwise(rotate)

    writer.addPage(np)
    _progress(progress, page, pageNum + 1)

  writer.removeLinks() # until we implement transformations on annotations
  with open(outputPath, 'wb') as out:
    writer.write(out)

  _progress(progress, pageNum + 1, pageNum + 1)



def _pageint(i):
  i = int(i)
  return (i if i < 0 else i-1)

def parsePageRange(s):
  s = [i.strip() for i in s.split(':')]
  if len(s) > 3:
    raise Exception("Could not parse page range")
  r = []
  if len(s) == 1:
    if len(s[0]) == 0:
      return [None]
    i = -1 if s[0] == "end" or len(s[0]) == 0 else _pageint(s[0])
    j = None if i == -1 else i+1
    return [i, j]
  for i in range(3):
    if i >= len(s):
      r.append(None)
    elif s[i] == "end" or len(s[i]) == 0:
      r.append(-1 if i == 0 else None)
    elif i < 2:
      r.append(_pageint(s[i]))
    else:
      r.append(int(s[i]))
  return r

def validatePageRanges(whichPages):
  try:
    if whichPages.strip() == "marked":
      return True
    for s in whichPages.split(','):
      parsePageRange(s)
    return True
  except:
    return False


def parsePageRanges(whichPages, document=None):
  if whichPages.strip() == "marked":
    if isinstance(document, PDFBasedDoc):
      return [slice(i,i+1) for i in document.markedPages()]
    else:
      return [slice(None)]
  return [slice(*parsePageRange(s)) for s in whichPages.split(',')]


import json

def parseExcludeLayers(exclude_layers):
  return set(json.loads('[%s]' % exclude_layers))

def validateExcludeLayers(exclude_layers):
  try:
    json.loads('[%s]' % exclude_layers)
    return True
  except Exception:
    return False

from itertools import chain

class CancelledExporter(Exception):
  pass

class Exporter(QThread):

  onError = pyqtSignal(Exception)
  onStart = pyqtSignal(int)
  onNewPhase = pyqtSignal(str)
  onProgress = pyqtSignal()
  onSuccess = pyqtSignal()

  _cancel = False

  def __init__(self, filename, document, whichPages=[slice(None)], parent=None, **options):
    super().__init__(parent=parent)
    self.filename   = filename
    self.document   = document
    if isinstance(whichPages, str):
      whichPages = parsePageRanges(whichPages, document)
    self.whichPages = whichPages
    self.options    = options
    # we are disabling highlight customisation for the moment
    # and using opacity instead of 'darken' composition mode
    # since the latter is not supported by the PDF export of Qt
    pal = self.options.get('palette')
    self.options['palette'] = pal.opacityBased()

  def cancel(self):
    self._cancel = True

  def _progress(self, i=1, t=1):
    if self._cancel:
      raise CancelledExporter("Export was cancelled")
    # QCoreApplication.processEvents()
    if i > 0:
      self.onProgress.emit()

  def __del__(self):
    self._cancel = True
    self.wait()

  def run(self):
    try:
      scenes = []
      totPages = self.document.pageCount or 0
      pdf = None
      if isinstance(self.document, PDFBasedDoc) and self.options.get('include_base_layer', True):
        pdf = self.document.retrieveBaseDocument()
        baseReader = PdfFileReader(pdf, strict=False)
        totPages = baseReader.getNumPages()

      rot = self.options.get("orientation", "auto")
      if rot == "auto":
        rot = self.document.orientation != "portrait"
      else:
        rot = rot == "landscape"

      ranges = [range(*s.indices(totPages)) for s in self.whichPages]
      steps = sum(len(r) for r in ranges)
      if steps == 0:
        raise Exception("No pages to export!")
      if pdf:
        self.onStart.emit(steps * 3 + 1)
      else:
        self.onStart.emit(steps * 2)

      pages = chain(*ranges)

      # self.onNewPhase.emit("Rendering lines")
      # self._progress()
      # def pr(*a):
      #   if self._cancel:
      #     raise CancelledExporter("Export was cancelled")
      # for i in pages:
      #   scenes.append(BarePageScene(self.document.getPage(i), progress=pr, **self.options))
      #   self._progress()
      self.onNewPhase.emit("Generating PDF of lines")
      scenesPdf(self.genScenes, pages, self.filename, progress=self._progress, tot=steps)
      if pdf:
        self.onNewPhase.emit("Merging with original PDF")
        pdfmerge(pdf, self.filename, pdfRanges=ranges, rotate=90 if rot else 0, progress=self._progress)
      elif rot:
        pdfrotate(self.filename, 90)

      self.onSuccess.emit()
    except Exception as e:
      log.warning("Exception on exporting: %s", e)
      self.onError.emit(e)
      import traceback
      traceback.print_exc()

  def genScenes(self, pages):
    def pr(*a):
      if self._cancel:
        raise CancelledExporter("Export was cancelled")
    # ---
    for i in pages:
      yield BarePageScene(self.document.getPage(i), progress=pr, **self.options)
