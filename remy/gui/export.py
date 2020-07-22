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

from remy.gui.pagerender import BarePageScene

from os import path
import time

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
  try:
    _progress(progress, 0, len(scenes))
    for i in range(len(scenes)):
      if i > 0:
        printer.newPage()
      scenes[i].render(p)
      _progress(progress, i+1, len(scenes))
  except Exception as e:
    raise e
  finally:
    p.end()


def pdfmerge(basePath, outputPath, progress=None):
  if isinstance(basePath, PdfFileReader):
    baseReader = basePath
  else:
    baseReader = PdfFileReader(basePath, strict=False)
  annotReader = PdfFileReader(outputPath, strict=False)
  pageNum = min(baseReader.getNumPages(), annotReader.getNumPages())
  writer = TolerantPdfWriter()
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

  writer.removeLinks() # until we implement transformations on annotations
  with open(outputPath, 'wb') as out:
    writer.write(out)

  _progress(progress, pageNum + 1, pageNum + 1)


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
    self.whichPages = whichPages
    self.options    = options

  def cancel(self):
    self._cancel = True

  def _progress(self, i=1, t=1):
    if self._cancel:
      raise CancelledExporter("Export was cancelled")
    # QCoreApplication.processEvents()
    if i > 0:
      self.onProgress.emit()

  def run(self):
    try:
      scenes = []
      totPages = self.document.pageCount or 0
      pdf = None
      if isinstance(self.document, PDFDoc):
        pdf = self.document.retrieveBaseDocument()
        baseReader = PdfFileReader(pdf, strict=False)
        totPages = baseReader.getNumPages()

      ranges = [range(*s.indices(totPages)) for s in self.whichPages]
      steps = sum(len(r) for r in ranges)
      if pdf:
        self.onStart.emit(steps * 3 + 1)
      else:
        self.onStart.emit(steps * 2)

      pages = chain(*ranges)

      self.onNewPhase.emit("Rendering lines")
      self._progress()
      def pr(*a):
        # QCoreApplication.processEvents()
        if self._cancel:
          raise CancelledExporter("Export was cancelled")
      for i in pages:
        scenes.append(BarePageScene(self.document.getPage(i), progress=pr, **self.options))
        self._progress()
      self.onNewPhase.emit("Generating PDF of lines")
      scenesPdf(scenes, self.filename, progress=self._progress)
      if pdf:
        self.onNewPhase.emit("Merging with original PDF")
        pdfmerge(pdf, self.filename, progress=self._progress)

      self.onSuccess.emit()
    except Exception as e:
      log.warning("Exception on exporting: %s", e)
      self.onError.emit(e)


class ExportOperation(QObject):

  step = 0
  success = pyqtSignal()

  def run(self, *args, **kwargs):
    self.t=time.perf_counter()
    self.name = path.basename(args[0])
    self.dialog = QProgressDialog(parent=self.parent())
    self.dialog.setWindowTitle("Exporting %s" % self.name)
    self.dialog.setLabelText("Initialising...")
    self.dialog.setMinimumDuration(2000)
    self.dialog.setAutoClose(True)
    exporter = Exporter(*args, parent=self, **kwargs)
    exporter.onError.connect(self.onError)
    exporter.onNewPhase.connect(self.onNewPhase)
    exporter.onStart.connect(self.onStart)
    exporter.onProgress.connect(self.onProgress)
    exporter.onSuccess.connect(self.onSuccess)
    self.dialog.canceled.connect(exporter.cancel)
    exporter.start()

  @pyqtSlot(Exception)
  def onError(self, e):
    self.dialog.hide()
    if not isinstance(e, CancelledExporter):
      QMessageBox.critical(self.parent(), "Error", "Something went wrong while exporting.\n\n" + str(e))


  @pyqtSlot(int)
  def onStart(self, total):
    log.info("Started %d steps", total)
    self.dialog.setMaximum(total)

  @pyqtSlot(str)
  def onNewPhase(self, s):
    self.dialog.setLabelText("Exporting %s:\n%s..." % (self.name, s))

  @pyqtSlot()
  def onProgress(self):
    self.step += 1
    self.t=time.perf_counter()
    self.dialog.setValue(self.step)

  @pyqtSlot()
  def onSuccess(self):
    self.dialog.setValue(self.dialog.maximum())
    self.success.emit()
