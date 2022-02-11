from remy import *

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

import remy.remarkable.constants as rm
from remy.remarkable.render import BarePageScene, IGNORE_ERASER

import logging
log = logging.getLogger('remy')

class ThumbnailSignal(QObject):
  thumbReady = pyqtSignal(str, QImage)

class ThumbnailWorker(QRunnable):

  def __init__(self, index, uid, height=150):
    QRunnable.__init__(self)
    self.uid = uid
    self.index = index
    self.height = height
    self.signals = ThumbnailSignal()

  def run(self):
    painter = None
    try:
      d = self.index.get(self.uid)
      log.debug("Generating thumb for %s", d.name())
      page = d.getPage(d.cover())
      s = BarePageScene(page,
                        include_base_layer=False,
                        pencil_resolution = 1,
                        simplify=0, smoothen=False,
                        eraser_mode=IGNORE_ERASER)
      img = QImage(self.height * s.width() / s.height(), self.height ,QImage.Format_ARGB32)
      img.fill(Qt.white)
      painter = QPainter(img)
      painter.setRenderHint(QPainter.Antialiasing)
      painter.setRenderHint(QPainter.SmoothPixmapTransform)
      if page.background and page.background.name != "Blank":
        bgf = page.background.retrieve()
        if bgf:
          bg = QImage(bgf)
          painter.drawImage(img.rect(), bg)
      else:
        pdf = d.baseDocument()
        if pdf:
          with pdf.lock:
            pdf = pdf.page(d.cover())
            sz = pdf.pageSize()
            w, h = sz.width(), sz.height()
            if w <= h:
              ratio = min(rm.WIDTH / w, rm.HEIGHT / h)
            else:
              ratio = min(rm.HEIGHT / w, rm.WIDTH / h)
            xres = 5.0 * ratio
            yres = 5.0 * ratio
            if w <= h:
              pdf = pdf.renderToImage(xres, yres)
            else:
              pdf = pdf.renderToImage(xres, yres, -1,-1,-1,-1, pdf.Rotate270)
            painter.drawImage(img.rect(), pdf)
      s.render(painter)
      pen = QPen(Qt.gray)
      pen.setWidth(2)
      painter.setPen(pen)
      painter.drawRect(img.rect())
      self.signals.thumbReady.emit(self.uid, img)
    except Exception as e:
      log.warning("Could not create thumbnail for %s [%s]", self.uid, e)
    finally:
      if painter:
        painter.end()
