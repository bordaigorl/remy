from remy.remarkable.constants import *
from threading import RLock

from remy.utils import log

from PyQt5.QtGui import QImage

import time

NO_RENDERER = 0
MUPDF       = 1
POPPLER     = 2

# PyMuPDF is the preferred rendering method.
# Use popplerqt5 as a fallback if PyMuPDF is not found
# and gracefully degrade if neither are installed

try:
  import fitz
  RENDERER = MUPDF
except ImportError:
  try:
    from popplerqt5 import Poppler
    RENDERER = POPPLER
  except ImportError:
    RENDERER = NO_RENDERER

# The direct dependencies on Qt and the renderer are ugly:
# the metadata module should be standalone.
# Since we are not using metadata as standalone, here we compromise.


class _PDFBase():
  _pdfDoc = None

  # ABSTRACT
  def _loadPdf(self):
    pass

  def _originalPage(self, i):
    return None

  def toImage(self, i, scale=1):
    return QImage()
  # END ABSTRACT

  def __init__(self, entry):
    self._entry = entry

  def canRender(self):
    return False

  def _pdf(self):
    self._loadPdf()
    return self._pdfDoc

  def path(self):
    return self._entry.retrieveBaseDocument()

  def found(self):
    return self.path() is not None

  def originalPageNum(self, i):
    pmap = self._entry.redirectionPageMap
    if pmap and i < len(pmap):
      i = pmap[i]
      if i < 0: i = None
    return i

  def _page(self, i):
    return self._originalPage(self.originalPageNum(i))

  def pageCount(self):
    return 0


if RENDERER == MUPDF:

  class PDFBase(_PDFBase):

    def canRender(self):
      return True

    def _loadPdf(self):
      if self._pdfDoc is None:
        doc = self._entry.retrieveBaseDocument()
        if doc is None:
          log.warning("Base document for %s could not be found", self._entry.uid)
        else:
          self._pdfDoc = fitz.open(doc)

    def _originalPage(self, i):
      if i is not None:
        pdf = self._pdf()
        if pdf:
          return pdf[i]
      return None

    def toImage(self, i, scale=1):
      pdf = self._pdf()
      if pdf:
        page = self._page(i)
        if page:
          sz = page.mediabox
          w, h = sz.width, sz.height
          if w <= h:
            ratio = min(WIDTH / w, HEIGHT / h) / 72
          else:
            ratio = min(HEIGHT / w, WIDTH / h) / 72
          m = fitz.Matrix(scale*ratio, scale*ratio)
          if w > h:
            m.prerotate(270)
          pix = page.get_pixmap(alpha=False, matrix=m)
          return QImage(pix.samples,
                        pix.width, pix.height,
                        pix.stride, # length of one image line in bytes
                        QImage.Format_RGB888)
      return QImage()

    def pageCount(self):
      pdf = self._pdf()
      return len(pdf) if pdf else 0


elif RENDERER == POPPLER:

  class PDFBase(_PDFBase):
    lock = RLock()

    def canRender(self):
      return True

    def _loadPdf(self):
      with self.lock:
        if self._pdfDoc is None:
          doc = self._entry.retrieveBaseDocument()
          if doc is None:
            log.warning("Base document for %s could not be found", self._entry.uid)
          else:
            self._pdfDoc = Poppler.Document.load(doc)
            self._pdfDoc.setRenderHint(Poppler.Document.Antialiasing)
            self._pdfDoc.setRenderHint(Poppler.Document.TextAntialiasing)
            try:
              self._pdfDoc.setRenderHint(Poppler.Document.HideAnnotations)
            except Exception:
              pass

    def _originalPage(self, i):
      if i is not None:
        pdf = self._pdf()
        if pdf:
          return pdf.page(i)
      return None

    def toImage(self, i, scale=1):
      pdf = self._pdf()
      if pdf:
        with self.lock:
          page = self._page(i)
          if page:
            sz = page.pageSize()
            w, h = sz.width(), sz.height()
            if w <= h:
              ratio = min(WIDTH / w, HEIGHT / h)
            else:
              ratio = min(HEIGHT / w, WIDTH / h)
            xres = scale * ratio
            yres = scale * ratio
            if w <= h:
              return page.renderToImage(xres, yres)
            else:
              return page.renderToImage(xres, yres, -1,-1,-1,-1, page.Rotate270)
      return QImage()

    def pageCount(self):
      pdf = self._pdf()
      if pdf:
        with self.lock:
          return pdf.numPages()
      return 0

else:

  class PDFBase(_PDFBase):
    pass

