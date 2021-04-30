import sys
import os
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from remy.remarkable.metadata import *
from remy.gui.pagerender import ThumbnailWorker
import remy.gui.resources
from remy.gui.notebookview import *

import logging
log = logging.getLogger('remy')

from remy.gui.export import webUIExport, exportDocument


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
    self.thumbs = {}
    layout = self.layout = QVBoxLayout()
    icon = self.icon = QLabel()
    title = self.title = QLabel()
    tf = QFont()
    tf.setBold(True)
    tf.setPointSize(30)
    title.setFont(tf)
    details = self.details = QFormLayout()
    layout.addWidget(icon)
    layout.addWidget(title)
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


class PinnedDelegate(QStyledItemDelegate):

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


class DocTreeItem(QTreeWidgetItem):
  def __init__(self, entry, *a, **kw):
    super().__init__(*a, **kw)
    self._entry = entry
    icon = self.treeWidget()._icon
    if isinstance(entry, Document):
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
      self.setText(0, entry.visibleName)
      self.setIcon(0, icon['trash'])
      self.setText(3, "Trash Bin")
      self.setText(2, "")
    else:
      self.setText(0, entry.visibleName)
      self.setIcon(0, icon['folder'])
      self.setText(3, "Folder")
      self.setText(2, "1" if entry.pinned else "")


  def entry(self):
    return self._entry

  def __lt__(self, other):
    if self.treeWidget().sortColumn() == 0:
      return (self.text(3)[0] + self.text(0)) < (other.text(3)[0] + other.text(0))
    return QTreeWidgetItem.__lt__(self, other)

class DocTree(QTreeWidget):

  contextMenu = pyqtSignal(QTreeWidgetItem,QContextMenuEvent)

  def __init__(self, index, *a, uid=None, show_trash=True, **kw):
    super(DocTree, self).__init__(*a, **kw)
    self.setMinimumWidth(400)
    self.setIconSize(QSize(24,24))
    # self.setColumnCount(4)
    self.setHeaderLabels(["Name", "Updated", "", "Type"])
    self.setUniformRowHeights(True)
    self.header().setStretchLastSection(False)
    self.header().setSectionResizeMode(0, QHeaderView.Stretch)
    self.setSortingEnabled(True)
    self.setItemDelegateForColumn(2, PinnedDelegate())
    # self.setDragEnabled(not index.isReadOnly())
    # self.setAcceptDrops(True)
    # self.setDragDropMode(self.DropOnly)
    # self.setDropIndicatorShown(True)

    index.listen(self.indexUpdated)

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
    else:
      return cur.entry()

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

  def indexUpdated(self, success, action, entries, index, extra):
    if success:
      if action == index.ADD:
        for uid in entries:
          # we only handle direct descendants of items, more todo
          d = index.get(uid)
          p = self._nodes[d.parent]
          self._nodes[uid] = DocTreeItem(d, p)
      elif action == index.DEL:
        pass
      elif action == index.UPD:
        pass
    else:
      log.error(str(extra['reason']))
      QMessageBox.critical(self, "Error", "Something went wrong:\n\n" % e)




class FileBrowser(QMainWindow):

  def __init__(self, index, *args, **kwargs):
    # self.bar = QMenuBar()
    super().__init__(*args, **kwargs)
    self.index = index

    splitter = self.splitter = QSplitter()
    splitter.setHandleWidth(0)
    self.setCentralWidget(splitter)

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

    splitter.setStretchFactor(0,2)
    splitter.setStretchFactor(1,1)

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
      uid = self.index.newPDFDoc(pdf, metadata={'parent': p}, content=cont)
      log.info("Saved %s as %s", pdf, uid)
    i = self.tree.itemOf(uid)
    self.tree.scrollToItem(i)
    self.tree.setCurrentItem(i) #, 0, QItemSelectionModel.ClearAndSelect)
    # self.info.setEntry(uid)

  # @pyqtSlot()
  # def selClear(self):
  #   print(self.tree.currentItem())
  #   self.info.setEntry(self.index.root())

  @pyqtSlot(QTreeWidgetItem,QTreeWidgetItem)
  def entrySelected(self, cur, prev):
    entry = self.tree.currentEntry()
    self.info.setEntry(entry)


  @pyqtSlot(QTreeWidgetItem,QContextMenuEvent)
  def contextMenu(self, item, event):
    entry = self.tree.currentEntry()
    if isinstance(entry, Folder):
      if not isinstance(entry, TrashBin):
        self.folderMenu.popup(self.tree.mapToGlobal(event.pos()))
    else:
      self.documentMenu.popup(self.tree.mapToGlobal(event.pos()))


  @pyqtSlot()
  def openCurrentEntry(self):
    item = self.tree.currentItem()
    if item:
      self.openEntry(item, 0)

  @pyqtSlot(QTreeWidgetItem,int)
  def openEntry(self, item, col=0):
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
