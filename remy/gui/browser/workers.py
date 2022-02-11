import traceback
from PyQt5.QtCore import *

import logging
log = logging.getLogger('remy')


class NewEntryCancelled(Exception):
  pass

# clearly this would be better as a sort of factory
# with _pending indexed by fsource but this is good enough for now
class NewEntryWorker(QRunnable):

  def __init__(self, index, **args):
    QRunnable.__init__(self)
    self.index   = index
    self.uid     = index.reserveUid()
    NewEntryWorker._pending[self.uid] = self
    self._args   = args
    self._cancel = False

  def start(self, pool=None):
    if pool is None:
      pool = QThreadPool.globalInstance()
    pool.start(self)

  # @pyqtSlot(bool) # compatibility with clicked of button
  def cancel(self, *a):
    self._cancel = True

  def _progress(self, *a):
    if self._cancel:
      log.debug("Cancel of new entry upload requested")
      raise NewEntryCancelled("Cancelled!")

  def run(self):
    try:
      self.do()
    except Exception as e:
      import traceback
      traceback.print_exc()
    finally:
      del NewEntryWorker._pending[self.uid]

  @classmethod
  def getWorkerFor(cls, uid, default=None):
    return cls._pending.get(uid, default)

  @classmethod
  def pendingUids(cls):
    return cls._pending.keys()

  @classmethod
  def noPending(cls):
    return len(cls._pending) == 0

  @classmethod
  def cancelAll(cls):
    for op in cls._pending.values():
      op.cancel()


NewEntryWorker._pending = {}

class UploadWorker(NewEntryWorker):

  def do(self):
    self.index.newDocument(uid=self.uid, progress=self._progress, **self._args)


class NewFolderWorker(NewEntryWorker):

  def do(self):
    self.index.newFolder(uid=self.uid, progress=self._progress, **self._args)


class Worker(QRunnable):

  def __init__(self, fn, *args, **kwargs):
    QRunnable.__init__(self)
    self.fn      = fn
    self._args   = args
    self._kwargs = kwargs

  def start(self, pool=None):
    if pool is None:
      pool = QThreadPool.globalInstance()
    pool.start(self)

  def run(self):
    try:
      self.fn(*self._args, **self._kwargs)
    except Exception as e:
      traceback.print_exc()
