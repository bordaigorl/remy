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

