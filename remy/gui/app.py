import sys
from pathlib import Path
import shutil
import json
import signal

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from remy.remarkable.config import *
from remy.remarkable.metadata import *
from remy.remarkable.filesource import (
  LocalFileSource,
  LiveFileSourceSSH,
  LiveFileSourceRsync
)
import remy.gui.resources
from remy.gui.notebookview import *
from remy.gui.filebrowser import *
from remy.connect import connect, BadHostKeyException, UnknownHostKeyException

import time
import logging
logging.basicConfig(format='[%(levelname).1s] %(message)s')

def _mkIcon(fn):
  icon = QPixmap(fn)
  icon.setDevicePixelRatio(QApplication.instance().devicePixelRatio())
  return icon


class RemyApp(QApplication):

  _rootWindows = [] # this is a place to store top level windows
                    # to avoid them being collected for going out of scope

  def __init__(self, args):
    QApplication.__init__(self, args)
    log = logging.getLogger('remy')
    self.setQuitOnLastWindowClosed(False)

    self.setOrganizationDomain('emanueledosualdo.com')
    self.setApplicationName('remy')
    self.setApplicationDisplayName('Remy')
    self.setWindowIcon(QIcon(':/assets/remy.svg'))

    self._makeAppPaths()
    config = self.config = RemyConfig(argv=sys.argv, paths=self.paths)

    log.setLevel(config.logLevel())

    log.info("Configuration loaded from %s.", config.path() or 'defaults')
    log.debug("Cache at '%s'", self.paths.cache_dir)
    log.debug("Known hosts at '%s'", self.paths.known_hosts)

    sources = config.get('sources')
    source = config.selectedSource()

    if len(sources) > 0 and source is None:
      source = config.get('default_source')
      if not source:
        source, ok = self.sourceSelectionBox()
        if not ok:
          log.error("Sorry, I need a source to work.")
          sys.exit(2)
      config.selectSource(source)

  def sourceSelectionBox(self):
    sources = self.config.get('sources')
    return QInputDialog.getItem(
              None, "Source selection", "Source:",
              [s for s in sorted(sources) if not sources[s].get("hidden", False)],
              editable=False,
            )

  def _makeAppPaths(self):
    conf_dir = Path(QStandardPaths.standardLocations(QStandardPaths.ConfigLocation)[0])
    old = conf_dir / 'remy.json'
    conf_dir = conf_dir / 'remy'
    conf_file = conf_dir / 'config.json'
    conf_dir.mkdir(parents=True, exist_ok=True)
    if old.is_file(): # migrate
      log.warning("Old configuration file '%s' moved to '%s'.", old, conf_file)
      old.rename(conf_file)
    try:
      cache_dir = Path(QStandardPaths.standardLocations(QStandardPaths.CacheLocation)[0])
    except Exception:
      cache_dir = None

    self._paths = AppPaths(conf_dir, conf_file, conf_dir / 'known_hosts', cache_dir)

  @property
  def paths(self):
    return self._paths

  _init = None
  initDialog = None
  def requestInit(self, **overrides):
    self.setQuitOnLastWindowClosed(False)
    self.initDialog = RemyProgressDialog(label="Loading: ")
    init = RemyInitWorker(*self.config.connectionArgs(**overrides))
    self.initDialog.canceled.connect(init.signals.cancelInit)
    init.signals.success.connect(self.initialised)
    init.signals.error.connect(self.retryInit)
    init.signals.canceled.connect(self.canceledInit)
    init.signals.progress.connect(self.initDialog.onProgress)
    QThreadPool.globalInstance().start(init)


  @pyqtSlot(Exception)
  def retryInit(self, e):
    log.error('RETRY? [%s]', e)
    mbox = QMessageBox(QMessageBox.NoIcon, 'Connection error', "Connection attempt failed")
    mbox.addButton("Settings…", QMessageBox.ResetRole)
    mbox.addButton(QMessageBox.Cancel)
    if isinstance(e, BadHostKeyException):
      mbox.setIconPixmap(_mkIcon(":/assets/128/security-low.svg"))
      mbox.setDetailedText(str(e))
      mbox.setInformativeText(
        "<big>The host at %s has the wrong key.<br>"
        "This usually happens just after a software update on the tablet.</big><br><br>"
        "You have three options to fix this permanently:"
        "<ol><li>"
        "Press Update to replace the old key with the new."
        "<br></li><li>"
        "Change your <code>~/.ssh/known_hosts</code> file to match the new fingerprint.<br>"
        "The easiest way to do this is connecting manually via ssh and follow the instructions."
        "<br></li><li>"
        "Set <code>\"host_key_policy\": \"ignore_new\"</code> in the appropriate source of Remy\'s settings.<br>"
        "This is not recommended unless you are in a trusted network."
        "<br></li><ol>" % (e.hostname)
      )
      mbox.addButton("Ignore", QMessageBox.NoRole)
      mbox.addButton("Update", QMessageBox.YesRole)
    elif isinstance(e, UnknownHostKeyException):
      mbox.setIconPixmap(_mkIcon(":/assets/128/security-high.svg"))
      mbox.setDetailedText(str(e))
      mbox.setInformativeText(
        "<big>The host at %s is unknown.<br>"
        "This usually happens if this is the first time you use ssh with your tablet.</big><br><br>"
        "You have three options to fix this permanently:"
        "<ol><li>"
        "Press Add to add the key to the known hosts."
        "<br></li><li>"
        "Change your <code>~/.ssh/known_hosts</code> file to match the new fingerprint.<br>"
        "The easiest way to do this is connecting manually via ssh and follow the instructions."
        "<br></li><li>"
        "Set <code>\"host_key_policy\": \"ignore_new\"</code> in the appropriate source of Remy\'s settings.<br>"
        "This is not recommended unless you are in a trusted network."
        "<br></li><ol>" % (e.hostname)
      )
      mbox.addButton("Ignore", QMessageBox.NoRole)
      mbox.addButton("Add", QMessageBox.YesRole)
    else:
      mbox.setIconPixmap(_mkIcon(":/assets/dead.svg"))
      mbox.setInformativeText("I could not connect to the reMarkable at %s:\n%s." % (self.config.get('host', '[no source selected]'), e))
      d=mbox.addButton(QMessageBox.Discard)
      d.setText("Source…")
      mbox.addButton(QMessageBox.Retry)
      mbox.setDefaultButton(QMessageBox.Retry)
    answer = mbox.exec()
    log.info(answer)
    if answer == QMessageBox.Retry:
      self.requestInit()
    elif answer == QMessageBox.Cancel:
      self.quit()
    elif answer == QMessageBox.Discard: # Sources selection
      source, ok = self.sourceSelectionBox()
      if not ok:
        self.quit()
      else:
        self.config.selectSource(source)
        self.requestInit()
    elif answer == 1: # Ignore
      self.requestInit(host_key_policy="ignore_all")
    elif answer == 2: # Add/Update
      local_kh = self.paths.known_hosts
      if not local_kh.is_file():
        open(local_kh, 'a').close()
      from paramiko import HostKeys
      hk = HostKeys(local_kh)
      hk.add(e.hostname, e.key.get_name(), e.key)
      hk.save(local_kh)
      log.info("Saved host key in %s", local_kh)
      self.requestInit()
    else:
      self.openSettings(prompt=False)
      self.quit()


  @pyqtSlot()
  def canceledInit(self, ):
    log.fatal("Canceled")
    self.retryInit(RemyInitCancel("Canceled initialisation"))

  @pyqtSlot(RemarkableIndex)
  def initialised(self, index):
    self._init = None
    self.initDialog = None
    self.tree = FileBrowser(index)
    self.setQuitOnLastWindowClosed(True)
    log.info("Initialised, launching browser")

  @pyqtSlot()
  def openSettings(self, prompt=True):
    if self.paths.config is None:
      QMessageBox.critical("Configuration", "No configuration found")
      self.quit()
      return
    if prompt:
      ans = QMessageBox.information(
              None,
              "Opening Settings",
              'To load the new settings you need to relaunch Remy.',
              buttons=(QMessageBox.Ok | QMessageBox.Cancel),
              defaultButton=QMessageBox.Ok
            )
      if ans == QMessageBox.Cancel:
        return

    confpath = self.paths.config
    if confpath.is_file():
      confpath = confpath.resolve()
      confpath.parent.mkdir(exist_ok=True)
      with open(confpath, "w") as f:
        self.config.dump(f)
    QDesktopServices.openUrl(QUrl(confpath.as_uri()))
    self.quit()



class RemyProgressDialog(QProgressDialog):

  def __init__(self, title="", label="", parent=None):
    QProgressDialog.__init__(self, parent)
    self.label = label
    self.setWindowTitle(title)
    self.setMinimumWidth(300)
    self.setLabelText(label)
    self.setMinimumDuration(500)
    self.setAutoClose(True)

  @pyqtSlot(int,int,str)
  def onProgress(self, x, tot, txt):
    self.setMaximum(tot)
    self.setValue(x)
    lbl = self.label + txt
    if len(lbl) > 35:
      lbl = lbl[:35] + '…'
    self.setLabelText(lbl)

  @pyqtSlot()
  @pyqtSlot(Exception)
  def calledOff(self, e=None):
    self.close()


class RemyInitCancel(Exception):
  pass

class RemyInitSignals(QObject):

  success = pyqtSignal(RemarkableIndex)
  error = pyqtSignal(Exception)
  canceled = pyqtSignal()
  progress = pyqtSignal(int,int,str)
  _cancel = False

  @pyqtSlot()
  def cancelInit(self):
    log.info("Cancel initialisation requested")
    self._cancel = True


class RemyInitWorker(QRunnable):

  _cancel = False

  def __init__(self, stype, args):
    QRunnable.__init__(self)
    self.signals = RemyInitSignals()
    self.stype = stype
    self.args = args


  # @pyqtSlot(int,int,str)
  def _progress(self, x, tot, txt="Initialising"):
    if self.signals._cancel:
      self.signals.progress.emit(1, 1, "Error")
      # self.signals.progress.disconnect()
      raise RemyInitCancel("Canceled initialisation")
    self.signals.progress.emit(x, tot, txt)

  def run(self):
    args = self.args
    app = QApplication.instance()
    fsource = None
    try:
      if self.stype == 'local':
        self._progress(0,0,"Initialising...")
        fsource = LocalFileSource(args.get('name'), args.get('documents'), args.get('templates'))
      else:
        self._progress(0,0,"Connecting...")
        ssh = connect(**args)
        if self.stype == 'ssh':
          if app.paths.cache_dir is None:
            self.signals.error.emit(Exception("Error locating the cache folder"))
            return
          fsource = LiveFileSourceSSH(ssh, **args)
        elif self.stype == 'rsync':
          fsource = LiveFileSourceRsync(ssh, **args)

      if fsource is None:
        self.signals.error.emit(Exception("Could not find the reMarkable data!"))
        return

      T0 = time.perf_counter()
      self._progress(0,0,"Fetching metadata")
      fsource.prefetchMetadata(progress=self._progress)
      self._progress(0,0,"Building index")
      index = RemarkableIndex(fsource, progress=self._progress)
      self._progress(4,4,"Done")
      log.info('LOAD TIME: %f', time.perf_counter() - T0)
      self.signals.success.emit(index)
    except RemyInitCancel:
      self.signals.canceled.emit()
    except Exception as e:
      self.signals.error.emit(e)



def main():
  QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
  log.setLevel(logging.INFO)
  log.info("STARTING: %s", time.asctime())
  try:
    app = RemyApp(sys.argv)
  except RemyConfigException as e:
    log.fatal("Misconfiguration: %s", str(e))
    sys.exit(1)

  app.requestInit()

  signal.signal(signal.SIGINT, lambda *args: app.quit())
  ecode = app.exec_()
  log.info("QUITTING: %s", time.asctime())
  sys.exit(ecode)

# THE APP IS EXITING BECAUSE IT NEEDS OPEN DIALOGS TO STAY ALIVE
# Either handle autoclosing manually
# or keep some dialog always open...