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
        self.drop.accepting([".pdf", ".epub"], folders, action)
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
        self._drops(False)
        self.icon.setPixmap(QPixmap(":assets/128/pdf.svg"))
      elif isinstance(entry, Notebook):
        self._drops(False)
        self.icon.setPixmap(QPixmap(":assets/128/notebook.svg"))
      elif isinstance(entry, EBook):
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
      PinnedDelegate._icon = QPixmap(":assets/symbolic/starred.svg")

  def paint(self, painter, style, i):
    QStyledItemDelegate.paint(self, painter, style, QModelIndex())
    if i.data():
      p = style.rect.center()
      painter.drawPixmap(p.x()-8,p.y()-8, PinnedDelegate._icon)

  def sizeHint(self, style, i):
    return QSize(16,24)


class StatusDelegate(NoEditDelegate):

  def __init__(self, *a, **kw):
    super().__init__(*a, **kw)
    if not hasattr(StatusDelegate, "_icon"):
      StatusDelegate._icon = {
        '': QPixmap(":assets/symbolic/ok.svg"),
        'warning': QPixmap(":assets/symbolic/warning.svg"),
        'error': QPixmap(":assets/symbolic/error.svg"),
        'info': QPixmap(":assets/symbolic/info.svg"),
        'updating': QPixmap(":assets/symbolic/updating.svg"),
      }

  def paint(self, painter, style, i):
    QStyledItemDelegate.paint(self, painter, style, QModelIndex())
    icon = StatusDelegate._icon.get(i.data())
    if icon:
      p = style.rect.center()
      painter.drawPixmap(p.x()-8,p.y()-8, icon)

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
    self._messages = []
    if entry is None:
      self.uploading(**kw)
    else:
      self.setEntry(entry)
      self.idle()

  def uploading(self, uid=None, etype=None, metadata=None, path=None, cancel=False):
    self._entry = None
    self.setFlags(Qt.NoItemFlags)
    self.setFirstColumnSpanned(True)
    title = metadata.get('visibleName', path.stem if path else 'Untitled')
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

  def setProgress(self, x, tot):
    if self.uploadingWidget:
      self.uploadingWidget.progress.setMaximum(tot)
      self.uploadingWidget.progress.setValue(x)

  def warning(self, msg):
    self._messages.append(('warning', msg))
    self.idle()

  def error(self, msg):
    self._messages.append(('error', msg))
    self.idle()

  def info(self, msg):
    self._messages.append(('info', msg))
    self.idle()

  def idle(self):
    if self._messages:
      self.setText(4, self._messages[-1][0])
      self.setData(4, Qt.ToolTipRole, "Click for more info")
    else:
      self.setText(4, '')
      self.setData(4, Qt.ToolTipRole, "Up to date")

  def updating(self):
    self.setText(4, 'updating')

  def showMessages(self):
    msg = ""
    for m in self._messages:
      msg += '\n' + m[0].upper() + ': ' + m[1]
    log.debug(msg)
    if msg:
      QMessageBox.information(self.treeWidget().window(), "Log", msg)
    self._messages.clear()
    self.idle()

  def failure(self, uid=None, etype=None, metadata=None, path=None, exception=None):
    self._entry = None
    self.setFlags(Qt.NoItemFlags)
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

  @property
  def dismissed(self):
    if isinstance(self.uploadingWidget, self.ErrorItem):
      return self.uploadingWidget.dismissBtn.clicked
    return None

  def status(self):
    if self.uploadingWidget is None and self._entry is not None:
      return DocTreeItem.OK
    elif isinstance(self.uploadingWidget, self.UploadingItem):
      return DocTreeItem.PROGRESS
    else:
      return DocTreeItem.ERROR

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
      if not entry.index.isReadOnly() and not entry.isDeleted():
        flags |= Qt.ItemIsEditable
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
      flags = Qt.ItemIsEnabled
      # flags |= Qt.ItemIsDropEnabled
      self.setText(0, entry.visibleName)
      self.setIcon(0, icon['trash'])
      self.setText(3, "Trash Bin")
      self.setText(2, "")
    else:
      # flags |= Qt.ItemIsDropEnabled | Qt.ItemIsDragEnabled
      if not entry.index.isReadOnly() and not entry.isDeleted():
        flags |= Qt.ItemIsEditable
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

DocTreeItem.OK = 0
DocTreeItem.PROGRESS = 1
DocTreeItem.ERROR = 2

class DocTree(QTreeWidget):

  contextMenu = pyqtSignal(QTreeWidgetItem,QContextMenuEvent)

  def __init__(self, index, *a, uid=None, show_trash=True, **kw):
    super(DocTree, self).__init__(*a, **kw)
    self.setMinimumWidth(400)
    self.setIconSize(QSize(24,24))
    # self.setColumnCount(4)
    self.setHeaderLabels(["Name", "Updated", "", "Type", ""])
    self.setUniformRowHeights(False)
    self.header().setStretchLastSection(False)
    self.header().setSectionResizeMode(0, QHeaderView.Stretch)
    self.setSortingEnabled(True)
    self._noeditDelegate = NoEditDelegate()
    self.setItemDelegateForColumn(1, self._noeditDelegate)
    self.setItemDelegateForColumn(3, self._noeditDelegate)
    self._pinnedDelegate = PinnedDelegate()
    self.setItemDelegateForColumn(2, self._pinnedDelegate)
    self.setItemDelegateForColumn(4, self._noeditDelegate)
    self.header().setSectionResizeMode(2, QHeaderView.Fixed)
    self._statusDelegate = StatusDelegate()
    self.setItemDelegateForColumn(4, self._statusDelegate)
    self.header().setSectionResizeMode(4, QHeaderView.Fixed)

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
      t = index.trash
      nodes[t.uid] = DocTreeItem(t, self)
      for f in index.scanFolders(t):
        p = nodes[f.uid]
        for d in f.files:
          d = index.get(d)
          c = nodes[d.uid] = DocTreeItem(d, p)
          if d.deleted: c.warning("Item deleted from trash but still on disk")
        for d in f.folders:
          d = index.get(d)
          c = nodes[d.uid] = DocTreeItem(d, p)
          if d.deleted: c.warning("Item deleted from trash but still on disk")

    self.sortItems(0, Qt.AscendingOrder)
    self.resizeColumnToContents(2)
    self.resizeColumnToContents(4)
    if index.isReadOnly(): self.setColumnHidden(4, True)
    self.header().moveSection(2,1)
    self.itemClicked.connect(self.showMessages)

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
    if len(self.selectedItems()) == 0:
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
    i.idle()

  @pyqtSlot(Exception, str, int, dict, Path)
  def newEntryError(self, exception, uid, etype, meta, path=None):
    log.debug('New entry error: %s', exception)
    if isinstance(exception, NewEntryCancelled):
      self._removePending(uid)
    else:
      i = self._pending_item.get(uid)
      if i:
        i.failure(uid, etype, meta, path, exception)
        i.dismissed.connect(lambda: self._removePending(uid))

  @pyqtSlot(str, dict, dict)
  def updateEntryPrepare(self, uid, new_meta, new_cont):
    item = self._nodes.get(uid)
    if item: item.updating()

  @pyqtSlot(str, dict, dict)
  def updateEntryComplete(self, uid, new_meta, new_cont):
    item = self._nodes.get(uid)
    if item:
      entry = self.index.get(uid)
      item.setEntry(entry)
      if 'parent' in new_meta:
        p = self._nodes.get(entry.parent)
        i = item.parent().indexOfChild(item)
        if p is not None and i:
          item = item.parent().takeChild(i)
          p.addChild(item)
        else:
          item.warning("Could not move to new parent folder. Try restarting Remy.")
          log.error("Something when wrong in reparenting item")
      item.idle()
      self.itemSelectionChanged.emit()

  @pyqtSlot(Exception, str, dict, dict)
  def updateEntryError(self, exception, uid, new_meta, new_cont):
    item = self._nodes.get(uid)
    if item:
      item.setEntry(self.index.get(uid))
      msg = str(exception) or exception.__class__.__name__
      item.error('Failed to update item: %s' % msg)
      self.itemSelectionChanged.emit()

  @pyqtSlot(QTreeWidgetItem, int)
  def showMessages(self, item, col):
    if col == 4:
      item.showMessages()

  def _removePending(self, uid):
    i = self._pending_item.get(uid)
    if i:
      if i.parent():
        i.parent().removeChild(i)
      else:
        self.invisibleRootItem().removeChild(i)
      del self._pending_item[uid]

  def dismissAllErrors(self, uid):
    for uid, item in self._pending_item.items():
      if item.status() == DocTreeItem.ERROR:
        self._removePending(uid)

  def cancelAllPending(self, uid):
    for uid, item in self._pending_item.items():
      if item.status() == DocTreeItem.PROGRESS:
        op = NewEntryWorker.getWorkerFor(uid)
        if op:
          op.cancel()

  def hasPendingItems(self):
    for item in self._pending_item.values():
      if item.status() != DocTreeItem.OK:
        return True
    return False

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

    tree = self.tree = DocTree(index, splitter)
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


class TestWorker(NewEntryWorker):

  def do(self):
    log.debug("Starting fake upload")
    self.index.test('Test.pdf', uid=self.uid, progress=self._progress, **self._args)
    log.debug("Stopping fake upload")


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
      import traceback
      traceback.print_exc()
