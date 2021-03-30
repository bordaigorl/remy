from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from remy.remarkable.metadata import *
from remy.remarkable.filesource import *

from pathlib import Path

from time import sleep


class QRemarkableIndexSignals(QObject):
  newEntryPrepare     = pyqtSignal(str, int, dict, Path)
  newEntryProgress    = pyqtSignal(str, int, int)
  newEntryComplete    = pyqtSignal(str, int, dict, Path)
  newEntryError       = pyqtSignal(str, int, dict, Path, Exception)
  updateEntryPrepare  = pyqtSignal(str, int, dict)
  updateEntryComplete = pyqtSignal(str, int, dict)
  updateEntryError    = pyqtSignal(str, int, dict, Exception)


class QRemarkableIndex(RemarkableIndex):

  signals = QRemarkableIndexSignals()

  def _new_entry_prepare(self, uid, etype, meta, path=None):
    self.signals.newEntryPrepare.emit(uid, etype, meta, path)

  def _new_entry_progress(self, uid, done, tot):
    self.signals.newEntryProgress.emit(uid, done, tot)

  def _new_entry_complete(self, uid, etype, meta, path=None):
    self.signals.newEntryComplete.emit(uid, etype, meta, path)

  def _new_entry_error(self, uid, etype, meta, path=None, exception=None):
    self.signals.newEntryError.emit(uid, etype, meta, path, exception)

  def _update_entry_prepare(self, uid, etype, new_meta):
    self.signals.updateEntryPrepare.emit(uid, etype, new_meta)

  def _update_entry_complete(self, uid, etype, new_meta):
    self.signals.updateEntryComplete.emit(uid, etype, new_meta)

  def _update_entry_error(self, uid, etype, new_meta, exception):
    self.signals.updateEntryError.emit(uid, etype, new_meta, exception)


  def test(self, pdf, uid=None, metadata={}, content={}, progress=None):
    try:

      log.debug("TEST uid=%s", uid)
      if not uid:
        uid = self.reserveUid()
      pdf = Path(pdf)
      log.debug("TEST uid=%s, path=%s", uid, pdf)

      self._new_entry_prepare(uid, PDF, metadata, pdf)

      totBytes = 1400
      if callable(progress):
        def p(x):
          progress(x, totBytes)
          self._new_entry_progress(uid, x, totBytes)
        def up(x, t):
          p(300+x)
      else:
        def p(x,t=0): pass
        up = None

      meta = PDF_BASE_METADATA.copy()
      meta.setdefault('visibleName', pdf.stem)
      meta.setdefault('lastModified', str(arrow.utcnow().int_timestamp * 1000))
      meta.update(metadata)
      if not self.isFolder(meta["parent"]):
        raise RemarkableError("Cannot find parent %s" % meta["parent"])
      log.debug("TEST meta=%s", meta)

      cont = PDF_BASE_CONTENT.copy()
      cont.update(content)
      log.debug("TEST cont=%s", cont)

      # imaginary 100bytes per json file
      # totBytes = 400 + stat(pdf).st_size

      p(0)
      sleep(.1)
      p(200)
      sleep(.1)
      p(200)
      sleep(.1)
      p(300)
      sleep(.1)
      for i in range(totBytes-300):
        p(300+i+1)
        sleep(.003)

      self.index[uid] = d = PDFDoc(self, uid, meta, cont)
      self.index[d.parent].files.append(uid)

      p(totBytes)
      self._new_entry_complete(uid, PDF, metadata, pdf)

      return uid

    except Exception as e:
      self._new_entry_error(uid, PDF, metadata, pdf, e)
      raise e
