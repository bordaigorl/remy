from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from remy.remarkable.metadata import *
from remy.remarkable.filesource import *

from pathlib import Path

from time import sleep


class QRemarkableIndexSignals(QObject):
  newEntryPrepare     = pyqtSignal(str, int, dict, object)
  newEntryProgress    = pyqtSignal(str, int, int)
  newEntryComplete    = pyqtSignal(str, int, dict, object)
  newEntryError       = pyqtSignal(Exception, str, int, dict, object)
  updateEntryPrepare  = pyqtSignal(str, dict, dict)
  updateEntryComplete = pyqtSignal(str, dict, dict)
  updateEntryError    = pyqtSignal(Exception, str, dict, dict)


class QRemarkableIndex(RemarkableIndex):

  signals = QRemarkableIndexSignals()

  def _new_entry_prepare(self, uid, etype, meta, path=None):
    self.signals.newEntryPrepare.emit(uid, etype, meta, path)

  def _new_entry_progress(self, uid, done, tot):
    self.signals.newEntryProgress.emit(uid, done, tot)

  def _new_entry_complete(self, uid, etype, meta, path=None):
    self.signals.newEntryComplete.emit(uid, etype, meta, path)

  def _new_entry_error(self, exception, uid, etype, meta, path=None):
    self.signals.newEntryError.emit(exception, uid, etype, meta, path)

  def _update_entry_prepare(self, uid, new_meta, new_content):
    self.signals.updateEntryPrepare.emit(uid, new_meta, new_content)

  def _update_entry_complete(self, uid, new_meta, new_content):
    self.signals.updateEntryComplete.emit(uid, new_meta, new_content)

  def _update_entry_error(self, exception, uid, new_meta, new_content):
    self.signals.updateEntryError.emit(exception, uid, new_meta, new_content)

  _test = 0
  def test(self, pdf, uid=None, content={}, progress=None, **metadata):
    try:
      self._test += 1

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
        if self._test % 3 == 1 and i == totBytes // 2:
          raise Exception("Test error. If everithing works as expected, you should be seeing this message and being able to dismiss it.")
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
