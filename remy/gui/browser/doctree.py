from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from remy.gui.qmetadata import *
# from remy.gui.pagerender import ThumbnailWorker
# import remy.gui.resources
# from remy.gui.notebookview import *

import logging
log = logging.getLogger('remy')

# from remy.gui.export import webUIExport, exportDocument
# from remy.gui.browser.info import InfoPanel
from remy.gui.browser.delegates import *
from remy.gui.browser.workers import NewEntryWorker, NewEntryCancelled

from pathlib import Path


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
    self.setData(0, Qt.UserRole, entry.uid)
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
