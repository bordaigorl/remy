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

from remy.gui.pagerender import BarePageScene, DEFAULT_COLORS, DEFAULT_HIGHLIGHT

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
    for s in whichPages.split(','):
      parsePageRange(s)
    return True
  except:
    return False


def parsePageRanges(whichPages):
  return [slice(*parsePageRange(s)) for s in whichPages.split(',')]


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
      whichPages = parsePageRanges(whichPages)
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

  def run(self, filename, document, **kwargs):
    self.name = path.basename(filename)
    self.dialog = QProgressDialog(parent=self.parent())
    self.dialog.setWindowTitle("Exporting %s" % self.name)
    self.dialog.setLabelText("Initialising...")
    self.dialog.setMinimumDuration(2000)
    self.dialog.setAutoClose(True)
    exporter = Exporter(filename, document, **kwargs, parent=self)
    exporter.onError.connect(self.onError)
    exporter.onNewPhase.connect(self.onNewPhase)
    exporter.onStart.connect(self.onStart)
    exporter.onProgress.connect(self.onProgress)
    exporter.onSuccess.connect(self.onSuccess)
    self.dialog.canceled.connect(exporter.cancel)
    exporter.start()

  @pyqtSlot(Exception)
  def onError(self, e):
    self.dialog.close()
    if not isinstance(e, CancelledExporter):
      QMessageBox.critical(self.parent(), "Error", "Something went wrong while exporting.\n\n" + str(e))


  @pyqtSlot(int)
  def onStart(self, total):
    self.dialog.setMaximum(total)

  @pyqtSlot(str)
  def onNewPhase(self, s):
    self.dialog.setLabelText("Exporting %s:\n%s..." % (self.name, s))

  @pyqtSlot()
  def onProgress(self):
    self.step += 1
    self.dialog.setValue(self.step)

  @pyqtSlot()
  def onSuccess(self):
    self.dialog.setValue(self.dialog.maximum())
    self.success.emit()




class WebUIExport(QObject):
  # TODO make asynchronous + progress dialog

  def run(self, filename, uid, webUIUrl="10.11.99.1"):
    import requests
    # Credit: https://github.com/LinusCDE/rmWebUiTools
    response = requests.get(
      "http://{webUIUrl}/download/{uid}/placeholder".format(
        webUIUrl=webUIUrl, uid=uid
      ),
      stream=True,
    )

    if not response.ok:
      raise Exception("Download from WebUI failed")

    response.raw.decode_content = True  # Decompress if needed
    with open(filename, "wb") as out:
      for chunk in response.iter_content(8192):
        out.write(chunk)



class ExportDialog(QDialog):

  FileExport = 0
  FolderExport = 1

  class ColorButton(QPushButton):

    def __init__(self, *args, color=None, options=QColorDialog.ColorDialogOptions(), **kwargs):
      super().__init__(*args, **kwargs)
      self.options = options
      self.setColor(color)
      self.clicked.connect(self.selectColor)

    @pyqtSlot(bool)
    def selectColor(self, *args):
      color = QColorDialog.getColor(self._color or Qt.black, self.window(), options=self.options)
      if color.isValid():
        self.setColor(color)

    def setColor(self, color):
      self._color = color
      if color is not None:
        col = QPixmap(12,12)
        col.fill(color)
        self.setIcon(QIcon(col))

    def color(self):
      return self._color

  @staticmethod
  def getFileExportOptions(parent=None, options={}, **kwargs):
    d = ExportDialog(mode=ExportDialog.FileExport, options=options, parent=parent, **kwargs)
    res = d.exec_()
    if res == QDialog.Accepted:
      return (*d.getOptions(), True)
    else:
      return (None, "", options, False)

  def __init__(self, filename=None, options={}, mode=None, **kwargs):
    super(ExportDialog, self).__init__(**kwargs)
    self.mode = ExportDialog.FileExport if mode is None else mode
    self.options = options
    self.filename = filename

    self.setWindowTitle("Export")
    self.setWindowModality(Qt.WindowModal)

    buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset)
    buttonBox.accepted.connect(self.accept)
    buttonBox.rejected.connect(self.reject)
    reset = buttonBox.button(QDialogButtonBox.Reset)
    reset.clicked.connect(self.reset)

    form = QFormLayout()
    form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

    # PATH SELECTION
    pathsel = self.pathsel = QLineEdit()
    pathsel.textChanged.connect(self.validatePath)

    act = pathsel.addAction(QIcon(":assets/symbolic/folder.svg"), QLineEdit.TrailingPosition)
    act.setToolTip("Change...")
    act.triggered.connect(self.selectPath)

    act = pathsel.addAction(QIcon(":assets/symbolic/warning.svg"), QLineEdit.TrailingPosition)
    self.replaceWarning = act
    act.setToolTip("A file or folder with the same name already exists.\nBy exporting to this location, you will overwrite its current contents.")
    act.setVisible(False)

    form.addRow("Export to:", pathsel)

    # OPEN EXPORTED
    self.openExp = QCheckBox("Open file on completion")
    form.addRow("", self.openExp)


    # PAGE RANGES
    pageRanges = self.pageRanges = QLineEdit()
    pageRanges.setPlaceholderText("all")
    act = pageRanges.addAction(QIcon(":assets/symbolic/info.svg"), QLineEdit.TrailingPosition)
    act.setToolTip("Examples:\nList of pages: 1,12,3\nRange: 3:end\nMixed: 5,1:3,end\nReverse order: end:1:-1\nSkipping even pages: 1:end:2")
    act = pageRanges.addAction(QIcon(":assets/symbolic/error.svg"), QLineEdit.TrailingPosition)
    self.pageRangeInvalid = act
    act.setToolTip("Page range is invalid")
    act.triggered.connect(self.pageRanges.clear)
    act.setVisible(False)
    pageRanges.textChanged.connect(self.validatePageRanges)
    form.addRow("Page Ranges:", pageRanges)

    # ERASER MODE
    emode = self.eraserMode = QComboBox()
    emode.addItem("Accurate", "accurate")
    emode.addItem("Ignore", "ignore")
    emode.addItem("Quick & Dirty", "quick")
    form.addRow("Eraser mode:", emode)

    # Simplification TOLERANCE & smoothening
    simplsm = QHBoxLayout()
    tolerance = self.tolerance = QDoubleSpinBox()
    tolerance.setMinimum(0)
    tolerance.setSingleStep(0.5)
    smoothen = self.smoothen = QCheckBox("Smoothen")
    simplsm.addWidget(tolerance)
    simplsm.addWidget(smoothen)
    form.addRow("Simplification:", simplsm)

    # COLOR SELECTION
    colorsel = QGridLayout()
    self.black = self.ColorButton("Black")
    self.gray = self.ColorButton("Gray")
    self.white = self.ColorButton("White")
    self.highlight = self.ColorButton("Highlight", options=QColorDialog.ShowAlphaChannel)
    colorsel.addWidget(self.black, 0, 0)
    colorsel.addWidget(self.gray, 0, 1)
    colorsel.addWidget(self.white, 1, 0)
    colorsel.addWidget(self.highlight, 1, 1)
    form.addRow("Colors:", colorsel)


    layout = QVBoxLayout()
    layout.addLayout(form)
    layout.addWidget(buttonBox)
    self.setLayout(layout)
    self.reset()

  @pyqtSlot(bool)
  def selectPath(self, *args):
    if self.mode == ExportDialog.FileExport:
      filename, ok = QFileDialog.getSaveFileName(self, "Export PDF...", self.pathsel.text(), "PDF (*.pdf)")
    else:
      filename, ok = QFileDialog.getExistingDirectory(self, "Export PDF...", self.pathsel.text())
    if ok and filename:
      self.pathsel.setText(filename)

  @pyqtSlot(str)
  def validatePath(self, p):
    if self.mode == ExportDialog.FileExport:
      self.replaceWarning.setVisible(path.isfile(p))
    else:
      self.replaceWarning.setVisible(path.isdir(p))

  @pyqtSlot(str)
  def validatePageRanges(self, text):
    v = not validatePageRanges(text)
    self.pageRangeInvalid.setVisible(v)

  @pyqtSlot(bool)
  def reset(self, *args):
    self.pathsel.setText(self.filename or "Document.pdf")
    self.openExp.setChecked(self.options.get("open_exported", False))
    self.pageRanges.clear()

    emi = self.eraserMode.findData(self.options.get("eraser_mode", "ignore"))
    if emi < 0: emi = 1
    self.eraserMode.setCurrentIndex(emi)

    self.smoothen.setChecked(self.options.get("smoothen", False))
    self.tolerance.setValue(self.options.get("simplify", 0))
    colors = self.options.get("colors", {})
    self.black.setColor(QColor(colors.get("black", DEFAULT_COLORS[0])))
    self.gray.setColor(QColor(colors.get("gray", DEFAULT_COLORS[1])))
    self.white.setColor(QColor(colors.get("white", DEFAULT_COLORS[2])))
    self.highlight.setColor(QColor(colors.get("highlight", DEFAULT_HIGHLIGHT)))

  def getOptions(self):
    return (
      self.pathsel.text(),
      self.pageRanges.text(),
      {
        'simplify': self.tolerance.value(),
        'eraser_mode': self.eraserMode.currentData(),
        'open_exported': self.openExp.isChecked(),
        'smoothen': self.smoothen.isChecked(),
        'colors': {
          'black': self.black.color(),
          'gray': self.gray.color(),
          'white': self.white.color(),
          'highlight': self.highlight.color(),
        }
      }
    )
