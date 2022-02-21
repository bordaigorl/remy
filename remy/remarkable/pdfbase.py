from remy.remarkable.constants import *
from threading import RLock

from remy.utils import log


class PDFBase():
  _pdf = None
  lock = RLock()

  def __init__(self, entry):
    self._entry = entry

  def pdf(self):
    from popplerqt5 import Poppler
    with self.lock:
      if self._pdf is None:
        doc = self._entry.retrieveBaseDocument()
        if doc is None:
          log.warning("Base document for %s could not be found", self._entry.uid)
        else:
          self._pdf = Poppler.Document.load(doc)
          self._pdf.setRenderHint(Poppler.Document.Antialiasing)
          self._pdf.setRenderHint(Poppler.Document.TextAntialiasing)
          try:
            self._pdf.setRenderHint(Poppler.Document.HideAnnotations)
          except Exception:
            pass
    return self._pdf

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

  def originalPage(self, i):
    pdf = self.pdf()
    if pdf:
      return pdf.page(i)
    else:
      return None

  def page(self, i):
    pdf = self.pdf()
    j = self.originalPageNum(i)
    if pdf and j is not None:
      return pdf.page(j)
    return None

  def toImage(self, i, scale=1):
    from PyQt5.QtGui import QImage
    pdf = self.pdf()
    if pdf:
      with self.lock:
        page = self.page(i)
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
