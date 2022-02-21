from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from remy.gui.qmetadata import *
from remy.gui.thumbnail import ThumbnailWorker
import remy.gui.resources
from remy.gui.notebookview import *

from remy.utils import log

from remy.gui.export import webUIExport, exportDocument
from remy.gui.browser.info import InfoPanel
from remy.gui.browser.doctree import *
from remy.gui.browser.workers import *
from remy.gui.browser.search import *
from remy.gui.browser.folderselect import *

# I could have used QWidget.addAction to attach these to the tree/main window
# but this way I get a bit more flexibility
class Actions:

  SEPARATOR = 0
  SPACER = 1

  def __init__(self, parent=None, isLive=False):
    # if all non folders
    self.preview = QAction('Open in viewer', parent)
    self.preview.setShortcut("Ctrl+Enter")
    # if single pdf
    self.openBaseDoc = QAction('Open base document', parent)
    self.openBaseDoc.setShortcut("Ctrl+Shift+Enter")
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
    self.moveTo = QAction('Move to…', parent)
    self.moveTo.setIcon(QIcon(":assets/symbolic/folder.svg"))
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
    self.browse = QAction('Browse folders')
    self.browse.setIcon(QIcon(":assets/16/browser.svg"))
    self.browse.setCheckable(True)
    self.listPdfs = QAction('List all PDFs')
    self.listPdfs.setIcon(QIcon(":assets/16/pdf.svg"))
    self.listPdfs.setCheckable(True)
    self.listEpubs = QAction('List all EPUBs')
    self.listEpubs.setIcon(QIcon(":assets/16/epub.svg"))
    self.listEpubs.setCheckable(True)
    self.listNotebooks = QAction('List all Notebooks')
    self.listNotebooks.setIcon(QIcon(":assets/16/notebook.svg"))
    self.listNotebooks.setCheckable(True)
    self.listPinned = QAction('List all Favourites')
    self.listPinned.setIcon(QIcon(":assets/symbolic/starred.svg"))
    self.listPinned.setCheckable(True)
    self.listResults = QAction('List search results')
    self.listResults.setIcon(QIcon(":assets/symbolic/search.svg"))
    self.listResults.setCheckable(True)
    self.listResults.setVisible(False)
    self.listResults.toggled.connect(lambda c: self.listResults.setVisible(c))
    self.listsGroup = QActionGroup(parent)
    self.listsGroup.addAction(self.browse)
    self.listsGroup.addAction(self.listPdfs)
    self.listsGroup.addAction(self.listEpubs)
    self.listsGroup.addAction(self.listNotebooks)
    self.listsGroup.addAction(self.listPinned)
    self.listsGroup.addAction(self.listResults)
    self.listsGroup.setExclusive(True)
    #
    self.setLive(isLive)
    self.enableAccordingToSelection([])

  def isLive(self):
    return self._isLive

  def setLive(self, b):
    self._isLive = b
    self.upload.setVisible(b)
    self.moveTo.setVisible(b)
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
    self.openBaseDoc.setVisible(singleSel and isinstance(e, Document))
    self.openBaseDoc.setEnabled(singleSel and isinstance(e, Document) and e.hasBaseDocument())
    # self.export.setEnabled(not (empty or anyFolders)) # once implemented
    self.export.setEnabled(singleSel and not anyFolders)
    self.upload.setEnabled(empty or (singleSel and allFolders and not anyDeleted))
    self.rename.setEnabled(singleSel)
    self.addToPinned.setEnabled(anyUnpinned and not anyDeleted)
    self.remFromPinned.setEnabled(anyPinned and not anyDeleted)
    self.newFolder.setEnabled((singleSel and not anyDeleted) or empty)
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
      self.SEPARATOR,
      self.upload,
      self.export,
      self.SEPARATOR,
      self.delete,
      self.SEPARATOR,
      self.addToPinned,
      self.remFromPinned,
      self.SEPARATOR,
      self.browse,
      self.listPdfs,
      self.listEpubs,
      self.listNotebooks,
      self.listPinned,
      self.listResults,
    ]

  def ctxtMenuActions(self):
    return [
      self.preview,
      self.openBaseDoc,
      self.SEPARATOR,
      self.newFolder,
      self.newFolderWith,
      # self.SEPARATOR,
      self.rename,
      self.moveTo,
      self.addToPinned,
      self.remFromPinned,
      self.SEPARATOR,
      self.delete,
      self.SEPARATOR,
      self.upload,
      self.export,
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

    central = self.stack = QStackedWidget(splitter)
    tree = self.tree = DocTree(index)
    results = self.results = SearchResults(tree.index)

    central.addWidget(tree)
    central.addWidget(results)

    info = self.info = InfoPanel(index, splitter)
    info.uploadRequest.connect(self._requestUpload)

    # @pyqtSlot(QModelIndex,QModelIndex)
    # def onsel(cur, prev):
    #   info.setText(cur.internalPointer())

    tree.itemActivated.connect(self.openEntry)
    tree.currentItemChanged.connect(self.treeCurrentChanged)
    self.tree.itemSelectionChanged.connect(self.selectionChanged)
    tree.contextMenu.connect(self.contextMenu)
    # tree.selectionCleared.connect(self.selClear)

    # results.selected.connect(self.resultSelected)
    results.selected.connect(self.selectionChanged)
    # results.selected.connect(self.treeCurrentChanged)
    results.activated.connect(self.resultActivated)

    self.viewers = {}

    # tree.doubleClicked.connect(self.openEntry)

    self.setWindowTitle("Remy")
    self.show()
    dg = QApplication.desktop().availableGeometry(self)
    self.resize(dg.size() * 0.7)
    fg = self.frameGeometry()
    fg.moveCenter(dg.center())
    self.move(fg.topLeft())

    splitter.setStretchFactor(0,3)
    splitter.setStretchFactor(1,2)

    self.setCentralWidget(splitter)

    self.actions = Actions(self, isLive=not self.index.isReadOnly())
    self._connectActions()
    tree.itemChanged.connect(self.itemChanged)
    self.showResAct = act = QAction("Show in enclosing folder")
    act.triggered.connect(self.resultActivated)
    results.addAction(act)
    results.addAction(self.actions.preview)
    results.addAction(self.actions.openBaseDoc)
    results.addAction(self.actions.export)
    results.queryChanged.connect(self.searchQueryChanged)

    self.setUnifiedTitleAndToolBarOnMac(True)
    tb = QToolBar("Documents")
    sep = True
    for a in self.actions.toolBarActions():
      if a == Actions.SPACER:
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
        tb.addWidget(spacer)
        sep = False
      elif a != Actions.SEPARATOR:
        tb.addAction(a)
        sep = a.isVisible()
      elif sep:
        tb.addSeparator()
        sep = False

    tb.setIconSize(QSize(16,16))
    tb.setFloatable(False)
    tb.setMovable(False)
    searchBar = self.searchBar = SearchBar()
    searchBar.queryEdited.connect(self.searchQueryEdited)
    searchBar.setOptionsMenu(results.optionsMenu())
    # spacer = QWidget()
    # spacer.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
    # tb.addWidget(spacer)
    tb.addWidget(searchBar)
    self.addToolBar(tb)

    splitter.setCollapsible(1,True)

    # rootitem = self.tree.invisibleRootItem()
    # self.tree.setCurrentItem(rootitem)
    self.selectView(self.actions.browse)
    self.treeCurrentChanged()


  def _connectActions(self):
    a = self.actions
    a.preview.triggered.connect(self.openSelected)
    a.openBaseDoc.triggered.connect(self.openBaseDoc)
    a.export.triggered.connect(self.exportSelected)
    a.newFolder.triggered.connect(self.newFolder)
    a.newFolderWith.triggered.connect(self.newFolderWith)
    a.rename.triggered.connect(self.editCurrent)
    a.moveTo.triggered.connect(self.moveCurrentTo)
    a.addToPinned.triggered.connect(self.pinSelected)
    a.remFromPinned.triggered.connect(self.unpinSelected)
    a.upload.triggered.connect(self.uploadIntoCurrentEntry)
    a.delete.triggered.connect(self.deleteSelected)
    a.listsGroup.triggered.connect(self.selectView)

  # this has to handle selection better:
  #   selection on results should not trigger selection on tree
  #   selection on results should set info as well
  #   when changing view either clearSelection or bring seletion to new view
  @pyqtSlot(QAction)
  def selectView(self, which):
    which.setChecked(True)
    if which is self.actions.browse:
      if self.currentView() is not self.tree:
        self.lastView = which
        self.results.setQuery(None)
        self.results.showDeleted(False)
        self.results.showPinnedOnly(False)
        self.results.showAllTypes()
        self.stack.setCurrentWidget(self.tree)
        e = self.results.currentEntry()
        if e:
          self.tree.setCurrentItem(self.tree.itemOf(e))
        else:
          self.tree.setCurrentItem(None)
    else:
      if which is not self.actions.listResults:
        self.lastView = which
        self.results.showDeleted(False)
        self.results.showPinnedOnly(False)
        self.results.setQuery(None)
      if which is self.actions.listPdfs:
        self.results.showOnlyType("pdf")
        self.info.setDefaultInfo(title="PDFs", icon="pdf")
      elif which is self.actions.listEpubs:
        self.results.showOnlyType("epub")
        self.info.setDefaultInfo(title="EPUBs", icon="epub")
      elif which is self.actions.listNotebooks:
        self.results.showOnlyType("notebook")
        self.info.setDefaultInfo(title="Notebooks", icon="notebook")
      elif which is self.actions.listPinned:
        self.results.showAllTypes()
        self.results.showPinnedOnly(True)
        self.info.setDefaultInfo(title="Favourites", icon="starred")
      self.stack.setCurrentWidget(self.results)
      self.results.clearSelection()

  def currentView(self):
    return self.stack.currentWidget()

  @pyqtSlot()
  def selectionChanged(self):
    v = self.currentView()
    self.actions.enableAccordingToSelection(v.selectedEntries(), v.hasPendingItems())
    self.info.setEntry(v.currentEntry())


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
    opt = QApplication.instance().config.upload
    e = self.index.get(p)
    for doc in files:
      log.info("Uploading %s to %s", doc, e.visibleName if e else "root")
      cont = opt.get(str(doc)[-3:].lower() + "_options", {})
      UploadWorker(self.index, path=doc, parent=p, content=cont).start()

  # @pyqtSlot()
  # def selClear(self):
  #   print(self.tree.currentItem())
  #   self.info.setEntry(self.index.root())

  # @pyqtSlot(QTreeWidgetItem,QTreeWidgetItem)
  def treeCurrentChanged(self, cur=None, prev=None):
    curr = self.tree.currentEntry()
    if curr and curr.isRoot():
      self.info.setEntry(curr)

  # @pyqtSlot(QTreeWidgetItem,QContextMenuEvent)
  def contextMenu(self, item, event):
    actions = self.actions
    # actions.enableAccordingToSelection(sel, pending)
    menu = QMenu(self)
    # maybe merge in the currentView().actions() too!
    for a in actions.ctxtMenuActions():
      if a != Actions.SEPARATOR:
        if a.isEnabled():
          menu.addAction(a)
      else:#if sep:
        menu.addSeparator()
    menu.popup(self.currentView().mapToGlobal(event.pos()))

  @pyqtSlot()
  def openSelected(self):
    # item = self.tree.currentItem()
    for e in self.currentView().selectedEntries():
      self.openEntry(e)

  @pyqtSlot()
  def openBaseDoc(self):
    # item = self.tree.currentItem()
    for e in self.currentView().selectedEntries():
      filename = e.retrieveBaseDocument()
      log.info("%s", filename)
      QDesktopServices.openUrl(QUrl("file://" + filename))

  def openEntry(self, entry, col=0):
    if isinstance(entry, DocTreeItem):
      entry = entry.entry()
    if entry:
      uid = entry.uid
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
    if self.currentView() is not self.tree:
      self.selectView(self.actions.browse)
    item = self.tree.currentItem()
    if item:
      self.tree.editItem(item)

  @pyqtSlot()
  def uploadIntoCurrentEntry(self):
    entry = self.currentView().currentEntry()
    if entry and not entry.index.isReadOnly():
      filenames, ok = QFileDialog.getOpenFileNames(self, "Select files to import")
      if ok and filenames:
        self._requestUpload(entry.uid, [], filenames)

  @pyqtSlot()
  def newFolder(self):
    entry = self.currentView().currentEntry()
    if entry and not entry.index.isReadOnly():
      if not entry.isFolder():
        entry = entry.parentEntry()
      name, ok = QInputDialog.getText(self, "New Folder in %s" % entry.name(),
                                      "Name of new folder:", text="New Folder")
      if ok and name:
        NewFolderWorker(self.index, parent=entry.uid, visibleName=name).start()

  @pyqtSlot()
  def moveCurrentTo(self):
    uids = set(item.entry().uid for item in self.tree.selectedItems())
    dest = FolderSelectDialog.getDestinationFolder(self.index, parent=self, exclude=uids)
    if dest:
      self.index.moveAll(uids, dest)

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


  # def resultSelected(self, item):
  #   uid = self.results.uidOfItem(item)
  #   # self.tree.setCurrentItem(self.tree.itemOf(uid))


  def resultActivated(self, item):
    if not isinstance(item, QModelIndex):
      item = self.results.currentIndex()
    uid = self.results.uidOfItem(item)
    self.selectView(self.actions.browse)
    self.tree.setCurrentItem(self.tree.itemOf(uid))
    # self.searchBar.clear()


  @pyqtSlot(str)
  def searchQueryEdited(self, txt):
    self.results.setQuery(txt)

  @pyqtSlot(str)
  def searchQueryChanged(self, txt):
    self.searchBar.setQuery(txt)
    currView = self.actions.listsGroup.checkedAction()
    if txt:
      if currView is not self.actions.listResults:
        self.selectView(self.actions.listResults)
    elif currView is not self.lastView:  #self.actions.listResults:
      self.selectView(self.lastView)
