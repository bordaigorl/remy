import sys
import os
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

from pathlib import Path

class DropBox(QLabel):

  _dropping = False
  onFilesDropped = pyqtSignal(list, list)


  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.setAlignment(Qt.AlignCenter)
    self.setWordWrap(True)
    self._dropInProgress(False)
    pen = QPen()
    pen.setWidth(3)
    pen.setColor(Qt.gray)
    pen.setStyle(Qt.DashLine)
    self.pen = pen
    self.accepting()

  def accepting(self, extensions=[], folders=False, action='import'):
    folders=False # disabled for the moment until supported
    self.accept_ext = extensions
    self.accept_dirs = folders
    self.accept_action = action
    if extensions or folders:
      self.setAcceptDrops(True)
    else:
      self.setAcceptDrops(False)

  def _dropInProgress(self, b, msg="Drop here to import"):
    self._dropping = b
    # if b:
    #   self.setText(msg)
    if not b:
      self.setText("")
    self.repaint()

  def paintEvent(self, e):
    if self._dropping:
      painter = QPainter(self)
      painter.setPen(self.pen)
      painter.drawRoundedRect(15,15,self.width()-30, self.height()-30,15,15)
    super().paintEvent(e)

  def _importablePaths(self, urls):
    dirs = []
    files = []
    for url in urls:
      filename = url.toLocalFile()
      if filename:
        if os.path.isdir(filename) and self.accept_dirs:
          dirs.append(filename)
        elif os.path.isfile(filename) and os.path.splitext(filename)[1] in self.accept_ext:
          files.append(filename)
    return (dirs, files)

  def _cannotImportMsg(self):
    msg = ', '.join([e.lstrip('.').upper() for e in self.accept_ext])
    if msg:
      msg = " " + msg + " files"
    if self.accept_dirs:
      if msg:
        msg += " and"
      msg += " folders"
    return "Cannot " + self.accept_action + " anything other than local" + msg

  def _dropToImportMsg(self, dirs, files):
    msg = ""
    if len(files):
      msg += " %d file" % len(files) + ("s" if len(files)>1 else "")
    if len(dirs):
      if msg:
        msg += " and"
      msg += " %d folder" % len(dirs) + ("s" if len(dirs)>1 else "")
    return "Drop to " + self.accept_action + msg

  def dragEnterEvent(self, event):
    self._dropInProgress(True)
    data = event.mimeData()
    urls = data.urls()
    dirs, files = self._importablePaths(urls)
    if len(files) + len(dirs) == 0:
      self.setText(self._cannotImportMsg())
      event.accept()
    else:
      self.setText(self._dropToImportMsg(dirs, files))
      event.setDropAction(Qt.CopyAction)
      event.accept()

  def dragLeaveEvent(self, event):
    self._dropInProgress(False)

  def dragMoveEvent(self, event):
    self._dropInProgress(True)
    data = event.mimeData()
    urls = data.urls()
    dirs, files = self._importablePaths(urls)
    if len(files) + len(dirs) == 0:
      self.setText(self._cannotImportMsg())
      # event.ignore()
      event.accept()
    else:
      self.setText(self._dropToImportMsg(dirs, files))
      event.setDropAction(Qt.CopyAction)
      event.accept()

  def dropEvent(self, event):
    self._dropInProgress(False)
    data = event.mimeData()
    urls = data.urls()
    dirs, files = self._importablePaths(urls)
    if len(files) + len(dirs) == 0:
      self.setText("")
      event.ignore()
    else:
      self.onFilesDropped.emit(dirs, files)
      event.accept()


class InfoPanel(QWidget):

  uploadRequest = pyqtSignal(str, list, list)

  def __init__(self, index, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.entry = None
    self.index = index
    self.rootName = index.fsource.name
    self.readOnly = index.isReadOnly()
    layout = self.layout = QVBoxLayout()
    icon = self.icon = QLabel()
    title = self.title = QLabel()
    tf = QFont()
    tf.setBold(True)
    tf.setPointSize(30)
    title.setFont(tf)
    details = self.details = QFormLayout()
    layout.addWidget(icon, alignment=Qt.AlignHCenter)
    # layout.addWidget(title, alignment=Qt.AlignHCenter)
    titlebox = QHBoxLayout() # this is just to disable title shrinking when wrapping text
    titlebox.addWidget(title)
    layout.addLayout(titlebox)
    layout.addLayout(details)
    if self.readOnly:
      self.drop = None
      layout.addStretch(1)
    else:
      drop = self.drop = DropBox()
      drop.onFilesDropped.connect(self._onDropped)
      layout.addWidget(drop, 1)
    title.setMargin(10)
    icon.setMargin(10)
    title.setAlignment(Qt.AlignCenter)
    icon.setAlignment(Qt.AlignCenter)
    title.setTextInteractionFlags(Qt.TextSelectableByMouse)
    title.setWordWrap(True)
    title.setText("Click on item to see metadata")
    # title.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
    # title.setMaximumWidth(self.window().width() * .4)
    self.setLayout(layout)


  @pyqtSlot(list,list)
  def _onDropped(self, dirs, files):
    self.uploadRequest.emit(self.entry.uid if self.entry else '', dirs, files)

  def _drops(self, enabled, folders=True, action='import'):
    if self.drop:
      if enabled:
        self.drop.accepting([".pdf"], folders, action)
      else:
        self.drop.accepting()


  def _resetDetails(self):
    while self.details.rowCount() > 0:
      self.details.removeRow(0)

  @pyqtSlot(str,QImage)
  def _onThumb(self, uid, img):
    self.thumbs[uid] = img
    if uid == self.entry.uid:
      self.icon.setPixmap(QPixmap.fromImage(img))

  def setEntry(self, entry):
    if not isinstance(entry, Entry):
      entry = self.index.get(entry)
    self.entry = entry
    self._resetDetails()
    # DETAILS
    if isinstance(entry, Folder):
      self.details.addRow("%d" % len(entry.folders), QLabel("Folders"))
      self.details.addRow("%d" % len(entry.files), QLabel("Files"))
    elif isinstance(entry, Document):
      self.details.addRow("Updated", QLabel(entry.updatedOn()))
      if entry.pageCount:
        self.details.addRow("Pages", QLabel("%d" % entry.pageCount))
      uidlbl = QLabel(entry.uid)
      uidlbl.setMinimumSize(100, uidlbl.minimumSize().height())
      # uidlbl.setWordWrap(True)
      uidlbl.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
      self.details.addRow("UID", uidlbl)

    # ICONS & TITLE
    if isinstance(entry, RootFolder):
      self._drops(True)
      self.title.setText(self.rootName or "Home")
      if entry.fsource.isReadOnly():
        self.icon.setPixmap(QPixmap(":assets/128/backup.svg"))
      else:
        self.icon.setPixmap(QPixmap(":assets/128/tablet.svg"))
    elif isinstance(entry, TrashBin):
      self._drops(False)
      self.title.setText("Trash")
      self.icon.setPixmap(QPixmap(":assets/128/trash.svg"))
    elif isinstance(entry, Folder):
      self._drops(True)
      self.title.setText(entry.visibleName)
      self.icon.setPixmap(QPixmap(":assets/128/folder-open.svg"))
    else:
      self.title.setText(entry.visibleName)
      if isinstance(entry, PDFDoc):
        # self._drops(True, False, 'replace')
        self.icon.setPixmap(QPixmap(":assets/128/pdf.svg"))
      elif isinstance(entry, Notebook):
        self._drops(False)
        self.icon.setPixmap(QPixmap(":assets/128/notebook.svg"))
      elif isinstance(entry, EPub):
        self._drops(False)
        self.icon.setPixmap(QPixmap(":assets/128/epub.svg"))
      else:
        self._drops(False)
        print(entry)
        self.title.setText("Unknown item")

      if entry.uid in self.thumbs:
        self.icon.setPixmap(QPixmap.fromImage(self.thumbs[entry.uid]))
      else:
        tgen = ThumbnailWorker(self.index, entry.uid)
        tgen.signals.thumbReady.connect(self._onThumb)
        QThreadPool.globalInstance().start(tgen)

InfoPanel.thumbs = {}

class NoEditDelegate(QStyledItemDelegate):

  def createEditor(self, parent, option, index):
    return None

class PinnedDelegate(NoEditDelegate):

  def __init__(self, *a, **kw):
    super().__init__(*a, **kw)
    if not hasattr(PinnedDelegate, "_icon"):
      PinnedDelegate._icon = QPixmap(":assets/bookmark.svg")

  def paint(self, painter, style, i):
    QStyledItemDelegate.paint(self, painter, style, QModelIndex())
    if i.data():
      p = style.rect.center()
      painter.drawPixmap(p.x()-8,p.y()-8, PinnedDelegate._icon)

  def sizeHint(self, style, i):
    return QSize(16,24)


DOCTYPE = {
  PDF: 'pdf',
  FOLDER: 'folder',
  EPUB: 'epub'
}


class DocTreeItem(QTreeWidgetItem):

  class UploadingItem(QWidget):

    def __init__(self, title, cancel=False, parent=None, tree=None):
      QWidget.__init__(self, parent=parent)
      layout = QHBoxLayout(self)
      layout.setContentsMargins(5, 5, 0, 0)
      # layout.addStrut(24)
      self.label = QLabel(title)
      self.progress = QProgressBar()
      self.progress.setRange(0, 0)
      # self.progress.setValue(3)
      layout.addWidget(self.label)
      layout.addWidget(self.progress)
      if cancel:
        self.cancelBtn = QPushButton("Cancel")
        if tree:
          self.cancelBtn.setMinimumWidth(tree.columnWidth(3))
        layout.addWidget(self.cancelBtn)

  class ErrorItem(QWidget):

    def __init__(self, title, msg, parent=None, tree=None):
      QWidget.__init__(self, parent=parent)
      layout = QHBoxLayout(self)
      layout.setContentsMargins(5, 5, 0, 0)
      # layout.addStrut(24)
      self.label = QLabel(title)
      msg = msg.strip()
      self.msg = msg
      if len(msg) > 30:
        msg = msg[:30] + '…  <a href="#">More info</a>'
      self.message = QLabel('<font color="Red">%s</font>' % msg)
      self.message.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
      self.message.linkActivated.connect(self.showMsg)
      bla = QLabel("Bla")
      layout.addWidget(self.label)
      layout.addSpacing(10)
      layout.addWidget(self.message,2)
      self.dismissBtn = QPushButton("Dismiss")
      if tree:
        self.dismissBtn.setMinimumWidth(tree.columnWidth(3))
      layout.addWidget(self.dismissBtn)

    @pyqtSlot(str)
    def showMsg(self, href):
      QMessageBox.critical(self.window(), "Error", "Something went wrong:\n\n" + self.msg)


  def __init__(self, entry=None, parent=None, **kw):
    super().__init__(parent)
    if entry is None:
      self.uploading(**kw)
    else:
      self.setEntry(entry)

  def uploading(self, uid=None, etype=None, metadata=None, path=None, cancel=False):
    self._entry = None
    self.setFirstColumnSpanned(True)
    title = metadata.get('visibleName', path.stem)
    doctype = DOCTYPE.get(etype)
    self.uploadingWidget = self.UploadingItem(title, cancel, tree=self.treeWidget())
    if self.treeWidget():
      self.treeWidget().setItemWidget(self, 0, self.uploadingWidget)
    if doctype is not None:
      self.setIcon(0, self.treeWidget()._icon[doctype])
    self._sortdata = doctype[0].upper() + title

  @property
  def cancelled(self):
    if isinstance(self.uploadingWidget, self.UploadingItem):
      return self.uploadingWidget.cancelBtn.clicked
    return None

  @property
  def dismissed(self):
    if isinstance(self.uploadingWidget, self.ErrorItem):
      return self.uploadingWidget.dismissBtn.clicked
    return None

  def setProgress(self, x, tot):
    if self.uploadingWidget:
      self.uploadingWidget.progress.setMaximum(tot)
      self.uploadingWidget.progress.setValue(x)

  def failure(self, uid=None, etype=None, metadata=None, path=None, exception=None):
    self._entry = None
    self.setFirstColumnSpanned(True)
    title = metadata.get('visibleName', path.stem if path else 'Unnamed')
    doctype = DOCTYPE.get(etype)
    self.uploadingWidget = self.ErrorItem(title, str(exception), tree=self.treeWidget())
    # self.uploadingWidget.dismissBtn.clicked.connect()
    if self.treeWidget():
      self.treeWidget().setItemWidget(self, 0, self.uploadingWidget)
    if doctype is not None:
      self.setIcon(0, self.treeWidget()._icon[doctype])
    self._sortdata = doctype[0].upper() + title


  def setEntry(self, entry):
    if self.treeWidget():
      self.treeWidget().removeItemWidget(self, 0)
    self.uploadingWidget = None
    self.setFirstColumnSpanned(False)
    self._entry = entry
    icon = self.treeWidget()._icon
    flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
    # commented flag settings should be uncommented once move/rename are implemented
    if isinstance(entry, Document):
      flags |= Qt.ItemNeverHasChildren #| Qt.ItemIsDragEnabled
      # if not entry.index.isReadOnly() and not entry.isDeleted():
      #   flags |= Qt.ItemIsEditable
      self.setText(0, entry.visibleName)
      if isinstance(entry, Notebook):
        self.setIcon(0, icon['notebook'])
        self.setText(3, "Notebook")
      elif isinstance(entry, PDFDoc):
        self.setIcon(0, icon['pdf'])
        self.setText(3, "PDF")
      elif isinstance(entry, EBook):
        self.setIcon(0, icon['epub'])
        self.setText(3, "EBook")
      self.setText(1, entry.updatedOn())
      self.setText(2, "1" if entry.pinned else "")
    elif isinstance(entry, TrashBin):
      # flags |= Qt.ItemIsDropEnabled
      self.setText(0, entry.visibleName)
      self.setIcon(0, icon['trash'])
      self.setText(3, "Trash Bin")
      self.setText(2, "")
    else:
      # flags |= Qt.ItemIsDropEnabled | Qt.ItemIsDragEnabled
      # if not entry.index.isReadOnly() and not entry.isDeleted():
      #   flags |= Qt.ItemIsEditable
      self.setText(0, entry.visibleName)
      self.setIcon(0, icon['folder'])
      self.setText(3, "Folder")
      self.setText(2, "1" if entry.pinned else "")
    self.setFlags(flags)
    self._sortdata = self.text(3)[0] + self.text(0)

  def entry(self):
    return self._entry

  def __lt__(self, other):
    if self.treeWidget().sortColumn() == 0:
      try:
        return self._sortdata < other._sortdata
      except Exception:
        pass
    return QTreeWidgetItem.__lt__(self, other)


class DocTree(QTreeWidget):

  contextMenu = pyqtSignal(QTreeWidgetItem,QContextMenuEvent)

  def __init__(self, index, *a, uid=None, show_trash=True, **kw):
    super(DocTree, self).__init__(*a, **kw)
    self.setMinimumWidth(400)
    self.setIconSize(QSize(24,24))
    # self.setColumnCount(4)
    self.setHeaderLabels(["Name", "Updated", "", "Type"])
    self.setUniformRowHeights(False)
    self.header().setStretchLastSection(False)
    self.header().setSectionResizeMode(0, QHeaderView.Stretch)
    self.setSortingEnabled(True)
    self._noeditDelegate = NoEditDelegate()
    self.setItemDelegateForColumn(1, self._noeditDelegate)
    self.setItemDelegateForColumn(3, self._noeditDelegate)
    self._pinnedDelegate = PinnedDelegate()
    self.setItemDelegateForColumn(2, self._pinnedDelegate)

    self.setEditTriggers(self.SelectedClicked | self.EditKeyPressed)
    self.setSelectionMode(self.ExtendedSelection)
    self.setDragDropMode(self.InternalMove)
    self.setDragEnabled(not index.isReadOnly())

    index.signals.newEntryPrepare.connect(self.newEntryPrepare)
    index.signals.newEntryProgress.connect(self.newEntryProgress)
    index.signals.newEntryComplete.connect(self.newEntryComplete)
    index.signals.newEntryError.connect(self.newEntryError)
    index.signals.updateEntryPrepare.connect(self.updateEntryPrepare)
    index.signals.updateEntryComplete.connect(self.updateEntryComplete)
    index.signals.updateEntryError.connect(self.updateEntryError)
    self.index = index

    self._icon = {
      "trash": QIcon(QPixmap(":assets/24/trash.svg")),
      "folder": QIcon(QPixmap(":assets/24/folder.svg")),
      "pdf": QIcon(QPixmap(":assets/24/pdf.svg")),
      "epub": QIcon(QPixmap(":assets/24/epub.svg")),
      "notebook": QIcon(QPixmap(":assets/24/notebook.svg")),
      "pinned": QIcon(QPixmap(":assets/bookmark.svg"))
    }

    nodes = self._nodes = {}
    if uid is None:
      uid = index.root().uid
    self._rootEntry = index.get(uid)
    p = nodes[uid] = self.invisibleRootItem()
    for f in index.scanFolders(uid):
      p = nodes[f.uid]
      for d in f.files:
        d = index.get(d)
        c = nodes[d.uid] = DocTreeItem(d, p)
      for d in f.folders:
        d = index.get(d)
        c = nodes[d.uid] = DocTreeItem(d, p)
    if show_trash:
      d = index.trash
      p = nodes[d.uid] = DocTreeItem(d, self)
      for i in index.trash.files:
        d = index.get(i)
        nodes[d.uid] = DocTreeItem(d, p)

    self.sortItems(0, Qt.AscendingOrder)
    self.resizeColumnToContents(2)

  def itemOf(self, uid):
    if isinstance(uid, Entry):
      uid = uid.uid
    return self._nodes.get(uid)

  def currentEntry(self):
    cur = self.currentItem()
    if cur is None:
      return self._rootEntry
    elif isinstance(cur,DocTreeItem):
      return cur.entry()
    else:
      return None

  def mouseReleaseEvent(self, event):
    i = self.indexAt(event.pos())
    QTreeView.mouseReleaseEvent(self, event)
    if not i.isValid():
      self.setCurrentItem(self.invisibleRootItem())

  def contextMenuEvent(self, event):
    i = self.indexAt(event.pos())
    if i.isValid():
      item = self.itemFromIndex(i)
    else:
      item = self.invisibleRootItem()
    self.setCurrentItem(item)
    self.contextMenu.emit(item, event)

  _pending_item = {}

  @pyqtSlot(str, int, dict, Path)
  def newEntryPrepare(self, uid, etype, meta, path):
    op = NewEntryWorker.getWorkerFor(uid)
    item = self.itemOf(meta.get('parent', ROOT_ID))
    i = DocTreeItem(uid=uid, etype=etype, metadata=meta, path=path, cancel=op is not None, parent=item)
    self._pending_item[uid] = i
    if op and i.cancelled:
      i.cancelled.connect(op.cancel)
    self.setSortingEnabled(True)
    self.scrollToItem(i)


  @pyqtSlot(str, int, int)
  def newEntryProgress(self, uid, done, tot):
    self._pending_item[uid].setProgress(done, tot)

  @pyqtSlot(str, int, dict, Path)
  def newEntryComplete(self, uid, etype, meta, path):
    self._nodes[uid] = i = self._pending_item[uid]
    del self._pending_item[uid]
    i.setEntry(self.index.get(uid))

  @pyqtSlot(str, int, dict, Path, Exception)
  def newEntryError(self, uid, etype, meta, path, exception):
    log.debug('New entry error: %s', exception)
    # TODO: if exception is NewEntryCancelled then remove,
    #       otherwise, show an error message in the item widget
    i = self._pending_item.get(uid)
    if i:
      i.failure(uid, etype, meta, path, exception)
      def rem():
        if i.parent():
          i.parent().removeChild(i)
        else:
          self.invisibleRootItem().removeChild(i)
        del self._pending_item[uid]
      i.dismissed.connect(rem)


  @pyqtSlot(str, int, dict)
  def updateEntryPrepare(self, uid, etype, new_meta):
    pass

  @pyqtSlot(str, int, dict)
  def updateEntryComplete(self, uid, etype, new_meta):
    pass

  @pyqtSlot(str, int, dict, Exception)
  def updateEntryError(self, uid, etype, new_meta, exception):
    pass

  # def indexUpdated(self, success, action, entries, index, extra):
  #   if success:
  #     if action == index.ADD:
  #       for uid in entries:
  #         # we only handle direct descendants of items, more todo
  #         d = index.get(uid)
  #         p = self._nodes[d.parent]
  #         self._nodes[uid] = DocTreeItem(d, p)
  #     elif action == index.DEL:
  #       pass
  #     elif action == index.UPD:
  #       pass
  #   else:
  #     log.error(str(extra['reason']))
  #     QMessageBox.critical(self, "Error", "Something went wrong:\n\n" % e)




class FileBrowser(QMainWindow):

  def __init__(self, index, *args, **kwargs):
    # self.bar = QMenuBar()
    super().__init__(*args, **kwargs)
    self.index = index

    splitter = self.splitter = QSplitter()
    splitter.setHandleWidth(0)

    tree = self.tree = DocTree(index, splitter)
    info = self.info = InfoPanel(index, splitter)
    # info.setEntry(index.root())
    info.uploadRequest.connect(self._import)
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

    self.setWindowTitle("ReMy")
    self.show()
    dg = QApplication.desktop().availableGeometry(self)
    self.resize(dg.size() * 0.5)
    fg = self.frameGeometry()
    fg.moveCenter(dg.center())
    self.move(fg.topLeft())

    splitter.setStretchFactor(0,3)
    splitter.setStretchFactor(1,2)

    self.setCentralWidget(splitter)
    # Todo: actions fields, menu per entry type (folder, pdf, nb, epub)
    self.documentMenu = QMenu(self)
    self.folderMenu = QMenu(self)
    ###
    self.previewAction = QAction('Preview', self.tree)
    self.previewAction.setShortcut("Enter")
    self.previewAction.triggered.connect(self.openCurrentEntry)
    #
    self.exportAction = QAction('Export...', self.tree)
    self.exportAction.setShortcut(QKeySequence.Save)
    self.exportAction.triggered.connect(self.exportCurrentEntry)
    # #
    # self.deleteAction = QAction('Move to Trash', self.tree)
    # self.deleteAction.setShortcut(QKeySequence.Delete)
    # self.deleteAction.triggered.connect(self.deleteEntry)
    #
    self.testAction = QAction('Test', self.tree)
    self.testAction.triggered.connect(self.test)
    self.folderMenu.addAction(self.testAction)
    #
    self.importAction = QAction('&Import...', self.tree)
    self.importAction.setShortcut("Ctrl+I")
    self.importAction.triggered.connect(self.importIntoCurrentEntry)
    ###
    self.documentMenu.addAction(self.previewAction)
    # self.documentMenu.addSeparator()
    self.documentMenu.addAction(self.exportAction)
    # self.documentMenu.addAction(self.deleteAction)
    ###
    if not index.isReadOnly():
      self.folderMenu.addAction(self.importAction)

    rootitem = self.tree.invisibleRootItem()
    self.tree.setCurrentItem(rootitem)
    self.entrySelected(rootitem,rootitem)

  @pyqtSlot(str, list,list)
  def _import(self, p, dirs, files):
    cont = QApplication.instance().config.get("import").get("default_options")
    e = self.index.get(p)
    for pdf in files:
      log.info("Uploading %s to %s", pdf, e.visibleName if e else "root")
      op = UploadWorker(self.index, pdf=pdf, metadata={'parent': p}, content=cont)
      QThreadPool.globalInstance().start(op)

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
    entry = self.tree.currentEntry()
    if entry:
      if isinstance(entry, Folder):
        if not isinstance(entry, TrashBin):
          self.folderMenu.popup(self.tree.mapToGlobal(event.pos()))
      else:
        self.documentMenu.popup(self.tree.mapToGlobal(event.pos()))

  @pyqtSlot()
  def test(self):
    item = self.tree.currentItem() or self.tree.invisibleRootItem()
    p = self.tree.currentEntry()
    op = TestWorker(self.index, metadata={'parent': p.uid, 'visibleName': "Test Note"})
    QThreadPool.globalInstance().start(op)


  @pyqtSlot()
  def openCurrentEntry(self):
    item = self.tree.currentItem()
    self.openEntry(item, 0)

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
  def exportCurrentEntry(self):
    entry = self.tree.currentEntry()
    if entry:
      exportDocument(entry, self)

  @pyqtSlot()
  def importIntoCurrentEntry(self):
    entry = self.tree.currentEntry()
    if entry and not entry.index.isReadOnly():
      filenames, ok = QFileDialog.getOpenFileNames(self, "Select files to import")
      if ok and filenames:
        self._import(entry.uid, [], filenames)



class NewEntryCancelled(Exception):
  pass

class NewEntryWorker(QRunnable):

  def __init__(self, index, **args):
    QRunnable.__init__(self)
    self.index   = index
    self.uid     = index.reserveUid()
    NewEntryWorker._pending[self.uid] = self
    self._args   = args
    self._cancel = False

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

NewEntryWorker._pending = {}

class UploadWorker(NewEntryWorker):

  def do(self):
    self.index.newPDFDoc(uid=self.uid, progress=self._progress, **self._args)

class NewFolderWorker(NewEntryWorker):

  def do(self):
    self.index.newFolder(uid=self.uid, progress=self._progress, **self._args)


class TestWorker(NewEntryWorker):

  def do(self):
    log.debug("Starting fake upload")
    self.index.test('Test.pdf', uid=self.uid, progress=self._progress, **self._args)
    log.debug("Stopping fake upload")

