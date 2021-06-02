from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from remy.gui.qmetadata import *
from remy.gui.pagerender import ThumbnailWorker
import remy.gui.resources
from remy.gui.notebookview import *

import logging
log = logging.getLogger('remy')

from remy.gui.export import webUIExport, exportDocument
from remy.gui.browser.info import InfoPanel
from remy.gui.browser.doctree import *
from remy.gui.browser.workers import *


# I could have used QWidget.addAction to attach these to the tree/main window
# but this way I get a bit more flexibility
class Actions:

  SEPARATOR = None

  def newSep(self):
    return self.SEPARATOR
    sep = QAction()
    sep.setSeparator(True)
    return sep

  def __init__(self, parent=None, isLive=False):
    # if all non folders
    self.preview = QAction('Open in viewer', parent)
    self.preview.setShortcut("Ctrl+Enter")
    #
    # if all non folders (for now)
    self.export = QAction('Export...', parent)
    self.export.setShortcut(QKeySequence.Save)
    self.export.setIcon(QIcon(":assets/16/export.svg"))
    #
    # if single folder
    self.upload = QAction('&Upload Here...', parent)
    self.upload.setShortcut("Ctrl+U")
    self.upload.setIcon(QIcon(":assets/16/import.svg"))
    #
    # if single non root entry
    self.rename = QAction('Rename', parent)
    self.rename.setIcon(QIcon(":assets/16/rename.svg"))
    # if any unpinned
    self.addToPinned = QAction('Add to Favourites', parent)
    self.addToPinned.setIcon(QIcon(":assets/16/star-add.svg"))
    # if any pinned
    self.remFromPinned = QAction('Remove from Favourites', parent)
    self.remFromPinned.setIcon(QIcon(":assets/16/star-rem.svg"))
    #
    # if single sel
    self.newFolder = QAction('New Folder', parent)
    self.newFolder.setShortcut(QKeySequence.New)
    self.newFolder.setIcon(QIcon(":assets/16/folder-new.svg"))
    #
    # non root
    self.newFolderWith = QAction('New Folder with Selection', parent)
    self.newFolderWith.setIcon(QIcon(":assets/16/folder-with.svg"))
    #
    # non root
    self.delete = QAction('Move to Trash', parent)
    self.delete.setShortcut(QKeySequence.Delete)
    self.delete.setIcon(QIcon(":assets/16/trash.svg"))
    # if pending
    self.cancelPending = QAction('Cancel all pending', parent)
    self.cancelPending.setIcon(QIcon(":assets/16/cancel.svg"))
    self.dismissErrors = QAction('Dismiss all errors', parent)
    self.dismissErrors.setIcon(QIcon(":assets/16/clear-all.svg"))
    #
    self.test = QAction('Test', parent)
    #
    self.setLive(isLive)
    self.enableAccordingToSelection([])

  def isLive(self):
    return self._isLive

  def setLive(self, b):
    self._isLive = b
    self.upload.setVisible(b)
    self.rename.setVisible(b)
    self.addToPinned.setVisible(b)
    self.remFromPinned.setVisible(b)
    self.newFolder.setVisible(b)
    self.newFolderWith.setVisible(b)
    self.delete.setVisible(b)
    self.cancelPending.setVisible(b)
    self.dismissErrors.setVisible(b)

  def enableAccordingToSelection(self, sel, pending=False):
    allFolders = True
    anyFolders = anyPinned = anyUnpinned = anyDeleted = False
    empty = len(sel) == 0
    singleSel = len(sel) == 1
    for e in sel:
      allFolders = allFolders and e.isFolder()
      anyFolders = anyFolders or e.isFolder()
      anyPinned = anyPinned or (e.pinned == True)
      anyUnpinned = anyUnpinned or (e.pinned == False)
      anyDeleted = anyDeleted or e.isIndirectlyDeleted()
    self.preview.setEnabled(not (empty or anyFolders))
    # self.export.setEnabled(not (empty or anyFolders)) # once implemented
    self.export.setEnabled(singleSel and not anyFolders)
    self.upload.setEnabled(singleSel and allFolders and not anyDeleted)
    self.rename.setEnabled(singleSel)
    self.addToPinned.setEnabled(anyUnpinned and not anyDeleted)
    self.remFromPinned.setEnabled(anyPinned and not anyDeleted)
    self.newFolder.setEnabled(singleSel and not anyDeleted)
    self.newFolderWith.setEnabled(not (empty or anyDeleted))
    self.delete.setEnabled(not (empty or anyDeleted))
    self.cancelPending.setVisible(pending)
    self.dismissErrors.setVisible(pending)
    ### making invisible the ones not currently implemented:
    self.cancelPending.setVisible(False)
    self.dismissErrors.setVisible(False)


  def toolBarActions(self):
    return [
      self.newFolder,
      self.newSep(),
      self.upload,
      self.export,
      self.newSep(),
      self.delete,
      self.newSep(),
      self.addToPinned,
      self.remFromPinned,
    ]

  def ctxtMenuActions(self):
    return [
      self.preview,
      self.newSep(),
      self.newFolder,
      self.newFolderWith,
      # self.newSep(),
      self.rename,
      self.addToPinned,
      self.remFromPinned,
      self.newSep(),
      self.delete,
      self.newSep(),
      self.upload,
      self.export,
      # self.newSep(),
      # self.test,
    ]

  def actionsDict(self):
    return self.__dict__.copy()


class FileBrowser(QMainWindow):

  def __init__(self, index, *args, **kwargs):
    # self.bar = QMenuBar()
    super().__init__(*args, **kwargs)
    self.index = index

    splitter = self.splitter = QSplitter()
    splitter.setHandleWidth(0)

    central = QStackedWidget(splitter)
    tree = self.tree = DocTree(index)
    central.addWidget(tree)
    tree.stack = central
    # tree = self.tree = DocTree(index, splitter)
    info = self.info = InfoPanel(index, splitter)
    # info.setEntry(index.root())
    info.uploadRequest.connect(self._requestUpload)
    splitter.setCollapsible(1,True)

    # @pyqtSlot(QModelIndex,QModelIndex)
    # def onsel(cur, prev):
    #   info.setText(cur.internalPointer())

    tree.itemActivated.connect(self.openEntry)
    tree.currentItemChanged.connect(self.entrySelected)
    tree.contextMenu.connect(self.contextMenu)

    # tree.selectionCleared.connect(self.selClear)

    self.viewers = {}

    # tree.doubleClicked.connect(self.openEntry)

    self.setWindowTitle("Remy")
    self.show()
    dg = QApplication.desktop().availableGeometry(self)
    self.resize(dg.size() * 0.5)
    fg = self.frameGeometry()
    fg.moveCenter(dg.center())
    self.move(fg.topLeft())

    splitter.setStretchFactor(0,3)
    splitter.setStretchFactor(1,2)

    self.setCentralWidget(splitter)

    self.actions = Actions(self, isLive=not self.index.isReadOnly())
    self._connectActions()
    tree.itemChanged.connect(self.itemChanged)

    self.setUnifiedTitleAndToolBarOnMac(True)
    tb = QToolBar("Documents")
    sep = True
    for a in self.actions.toolBarActions():
      if a != Actions.SEPARATOR:
        tb.addAction(a)
        sep = tb.isVisible()
      elif sep:
        tb.addSeparator()
        sep = False
    tb.setIconSize(QSize(16,16))
    tb.setFloatable(False)
    tb.setMovable(False)
    self.addToolBar(tb)

    rootitem = self.tree.invisibleRootItem()
    self.tree.setCurrentItem(rootitem)
    self.entrySelected(rootitem,rootitem)

  def _connectActions(self):
    a = self.actions
    a.preview.triggered.connect(self.openSelected)
    a.export.triggered.connect(self.exportSelected)
    a.newFolder.triggered.connect(self.newFolder)
    a.newFolderWith.triggered.connect(self.newFolderWith)
    a.rename.triggered.connect(self.editCurrent)
    a.addToPinned.triggered.connect(self.pinSelected)
    a.remFromPinned.triggered.connect(self.unpinSelected)
    a.test.triggered.connect(self.test)
    a.upload.triggered.connect(self.uploadIntoCurrentEntry)
    a.delete.triggered.connect(self.deleteSelected)
    self.tree.itemSelectionChanged.connect(self.selectionChanged)

  @pyqtSlot()
  def selectionChanged(self):
    self.actions.enableAccordingToSelection([i.entry() for i in self.tree.selectedItems()], self.tree.hasPendingItems())

  @pyqtSlot(QTreeWidgetItem, int)
  def itemChanged(self, item, col):
    name = item.text(0)
    entry = item.entry()
    if col == 0 and entry and entry.name() != name:
      if name:
        log.debug('Rename %s -> %s', entry.name(), name)
        Worker(self.index.rename, entry.uid, name).start()
      else:
        item.setText(0, entry.name())

  @pyqtSlot(str, list,list)
  def _requestUpload(self, p, dirs, files):
    opt = QApplication.instance().config.get("upload")
    e = self.index.get(p)
    for doc in files:
      log.info("Uploading %s to %s", doc, e.visibleName if e else "root")
      cont = opt.get(str(doc)[-3:].lower() + "_options", {})
      UploadWorker(self.index, path=doc, parent=p, content=cont).start()

  # @pyqtSlot()
  # def selClear(self):
  #   print(self.tree.currentItem())
  #   self.info.setEntry(self.index.root())

  @pyqtSlot(QTreeWidgetItem,QTreeWidgetItem)
  def entrySelected(self, cur, prev):
    entry = self.tree.currentEntry()
    if entry:
      self.info.setEntry(entry)

  @pyqtSlot(QTreeWidgetItem,QContextMenuEvent)
  def contextMenu(self, item, event):
    items = self.tree.selectedItems()
    actions = self.actions
    # actions.enableAccordingToSelection(sel, pending)
    menu = QMenu(self)
    sep = True
    for a in actions.ctxtMenuActions():
      if a != Actions.SEPARATOR:
        if a.isEnabled():
          menu.addAction(a)
          sep = True
      elif sep:
        menu.addSeparator()
        sep = False
    menu.popup(self.tree.mapToGlobal(event.pos()))

  @pyqtSlot()
  def test(self):
    item = self.tree.currentItem() or self.tree.invisibleRootItem()
    p = self.tree.currentEntry()
    TestWorker(self.index, parent=p.uid, visibleName="Test Note").start()

  @pyqtSlot()
  def openSelected(self):
    # item = self.tree.currentItem()
    for item in self.tree.selectedItems():
      self.openEntry(item)

  @pyqtSlot(QTreeWidgetItem,int)
  def openEntry(self, item, col=0):
    if item and item.entry():
      uid = item.entry().uid
      index = self.index
      if not index.isOfType(uid, FOLDER):
        if uid not in self.viewers:
          self.viewers[uid] = NotebookViewer(index.get(uid))
        win = self.viewers[uid]
        win.show()
        win.raise_()
        win.activateWindow()

  @pyqtSlot()
  def exportSelected(self):
    # for now, later use selectedItems
    entry = self.tree.currentEntry()
    if entry:
      exportDocument(entry, self)

  @pyqtSlot()
  def editCurrent(self):
    item = self.tree.currentItem()
    if item:
      self.tree.editItem(item)

  @pyqtSlot()
  def uploadIntoCurrentEntry(self):
    entry = self.tree.currentEntry()
    if entry and not entry.index.isReadOnly():
      filenames, ok = QFileDialog.getOpenFileNames(self, "Select files to import")
      if ok and filenames:
        self._requestUpload(entry.uid, [], filenames)

  @pyqtSlot()
  def newFolder(self):
    entry = self.tree.currentEntry()
    if entry and not entry.index.isReadOnly():
      if not entry.isFolder():
        entry = entry.parentEntry()
      name, ok = QInputDialog.getText(self, "New Folder in %s" % entry.name(),
                                      "Name of new folder:", text="New Folder")
      if ok and name:
        NewFolderWorker(self.index, parent=entry.uid, visibleName=name).start()

  @pyqtSlot()
  def deleteSelected(self):
    for item in self.tree.selectedItems():
      entry = item.entry()
      if entry:
        Worker(self.index.moveToTrash, entry.uid).start()

  @pyqtSlot()
  def pinSelected(self):
    for item in self.tree.selectedItems():
      entry = item.entry()
      if entry:
        Worker(lambda: self.index.update(entry.uid, pinned=True)).start()

  @pyqtSlot()
  def unpinSelected(self):
    for item in self.tree.selectedItems():
      entry = item.entry()
      if entry:
        Worker(lambda: self.index.update(entry.uid, pinned=False)).start()

  @pyqtSlot()
  def newFolderWith(self):
    entries = [ item.entry() for item in self.tree.selectedItems() if item.entry() ]
    if entries:
      # parent of first entry is parent of new folder
      parent = entries[0].parentEntry()
      name, ok = QInputDialog.getText(self, "New Folder in %s" % parent.name(),
                                      "Name of new folder (with %d items):" % len(entries),
                                      text="New Folder")
      if ok and name:
        Worker(self.index.newFolderWith, [ e.uid for e in entries], parent=parent.uid, visibleName=name).start()

