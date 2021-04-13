import sys
import os
import shutil
import json

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from remy.remarkable.metadata import *
from remy.remarkable.filesource import (
  LocalFileSource,
  LiveFileSourceSSH,
  LiveFileSourceRsync,
  fileSourceFromSSH
)
import remy.gui.resources
from remy.gui.notebookview import *
from remy.gui.filebrowser import *

import time
import logging
logging.basicConfig(format='%(message)s')

def main():
  log = logging.getLogger('remy')
  log.setLevel(logging.INFO)
  log.info("Started")
  source = None
  if len(sys.argv) > 1:
    source = sys.argv[1]

  confpath = QStandardPaths.standardLocations(QStandardPaths.ConfigLocation)[0]
  if not os.path.isdir(confpath):
    os.makedirs(confpath)
  confpath = os.path.join(confpath, 'remy.json')

  QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
  app = QApplication(sys.argv)
  app.setWindowIcon(QIcon(':/assets/remy.svg'))

  if os.path.isfile(confpath):
    try:
      with open(confpath) as f:
        config = app.config = json.load(f)
    except:
      log.fatal("Could not read configuration from '%s'!", confpath)
      sys.exit(1)
  else:
    log.fatal("Configuration file '%s' not found, please create it first.", confpath)
    sys.exit(1)
  log.info("Configuration loaded from '%s'.", confpath)

  sources = config.get('sources', {})

  if source is None:
    source = config.get('default_source')
    if not source:
      source, ok = QInputDialog.getItem(
        None, "Source selection", "Source:",
        [s for s in sorted(sources) if not sources[s].get("hidden", False)],
        editable=False,
      )
      if not ok:
        log.error("Sorry, I need a source to work.")
        sys.exit()

  if source not in sources:
    log.fatal("Invalid source %s (available: %s)", source, ', '.join(sources))
    sys.exit(1)
  src = app.source = sources[source]
  config.update(src.get("settings", {}))
  src.pop("settings", None)
  if src.get("use_banner") and src.get("enable_webui_export"):
    src.pop("use_banner")
    log.warning("The `use_banner` setting is incompatible with `enable_webui_export`: the latter is overriding the former.")
  stype = src.get('type', 'ssh')
  if stype == 'ssh':
    if 'cache_dir' not in src:
      cache = QStandardPaths.standardLocations(QStandardPaths.CacheLocation)
      if len(cache) == 0:
        log.error("Sorry, I need a cache to work properly!")
        sys.exit(1)
      src['cache_dir'] = cache[0]
    fsource = fileSourceFromSSH(LiveFileSourceSSH,  **src)
  elif stype == 'rsync':
    fsource = fileSourceFromSSH(LiveFileSourceRsync,  **src)
  else:
    fsource = LocalFileSource(src.get('name', source), src.get('documents'), src.get('templates'))

  if fsource is None:
    log.fatal("Could not find the reMarkable data!")
    sys.exit(1)

  T0 = time.perf_counter()
  fsource.prefetchMetadata()
  index = RemarkableIndex(fsource)
  log.info('LOAD TIME: %f', time.perf_counter() - T0)

  # sourcesPanel = QTreeWidget(splitter)
  # p = QPalette( sourcesPanel.palette() )
  # p.setColor( QPalette.Base, p.window().color() )
  # sourcesPanel.setPalette( p )
  # sourcesPanel.setHeaderHidden(True)
  # sourcesPanel.setColumnCount(1)
  # for s in config['sources'].keys():
  #   sit = QTreeWidgetItem(sourcesPanel, [s])
  #   f = sit.font(0)
  #   f.setBold(True)
  #   sit.setFont(0, f)

  tree = FileBrowser(index)

  @pyqtSlot()
  def cleanup():
    fsource.cleanup()

  app.aboutToQuit.connect(cleanup)

  return app.exec_()
