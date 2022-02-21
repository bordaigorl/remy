from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from remy.utils import log

from remy.gui.browser.delegates import PinnedDelegate

### This proxy can be attached to the model of a DocTree to flatten the hierarchy
# class FlatRemarkableProxyModel(QAbstractProxyModel):

#   def __init__(self, tree):
#     QAbstractProxyModel.__init__(self)
#     self._uids = list(tree.index.allUids())
#     self._rows = dict(enumerate(self._uids))
#     self._tree = tree

#   def mapFromSource(self, sourceIndex):
#     if sourceIndex.isValid():
#       item = self._tree.itemFromIndex(sourceIndex)
#       entry = item.entry
#       if entry:
#         return self.createIndex(self._rows[entry.uid], sourceIndex.column())
#     return QModelIndex()

#   def mapToSource(self, proxyIndex):
#     if proxyIndex.isValid() and proxyIndex.row() < len(self._uids):
#       uid = self._uids[proxyIndex.row()]
#       idx = self._tree.indexFromItem(self._tree.itemOf(uid))
#       return self.createIndex(idx.row(), idx.column())
#     return QModelIndex()



class FlatRemarkableIndexModel(QAbstractTableModel):

  def __init__(self, index):
    QAbstractListModel.__init__(self)
    self._index = index
    self._uids = list(index.allUids())
    index.signals.newEntryComplete.connect(self.newEntry)
    index.signals.updateEntryComplete.connect(self.updateEntry)
    self._icon = {
      "trash": QIcon(":assets/24/trash.svg"),
      "folder": QIcon(":assets/24/folder.svg"),
      "pdf": QIcon(":assets/24/pdf.svg"),
      "epub": QIcon(":assets/24/epub.svg"),
      "notebook": QIcon(":assets/24/notebook.svg"),
    }
    self._filterName = QSortFilterProxyModel()
    self._filterType = QSortFilterProxyModel()
    self._filterType.setFilterRole(Qt.UserRole + 1)
    self._filterType.setFilterCaseSensitivity(False)
    self._filterTrash = QSortFilterProxyModel()
    self._filterTrash.setFilterRole(Qt.UserRole + 2)
    self._filterPinned = QSortFilterProxyModel()
    self._filterPinned.setFilterRole(Qt.UserRole + 3)
    self._topProxy = self._filterPinned
    self.refresh()
    # self._starred = QIcon(":assets/symbolic/starred.svg")

  def refresh(self):
    self._filterName.setSourceModel(self)
    self._filterType.setSourceModel(self._filterName)
    self._filterTrash.setSourceModel(self._filterType)
    self._filterPinned.setSourceModel(self._filterTrash)

  # def parent(self, index):
  #   return QModelIndex()

  def columnCount(self, parent=None):
    return 4

  # def index(self, row, col, parent):
  #   if not parent.isValid():
  #     return self.createIndex(row, col)
  #   return QModelIndex()

  def rowCount(self, parent=None):
    return len(self._uids)

  def data(self, index, role):
    if not index.isValid():
      return None

    if index.row() >= len(self._uids):
      return None

    uid = self._uids[index.row()]
    entry = self._index.get(uid)
    if role == Qt.ToolTipRole:
      return self._index.fullPathOf(uid)
    elif role == Qt.ForegroundRole:
      if entry.isIndirectlyDeleted():
        return QBrush(Qt.gray)
    elif role == Qt.UserRole:
      return uid
    elif role == Qt.UserRole + 1:
      return entry.typeName()
    elif role == Qt.UserRole + 2:
      return "1" if entry.isIndirectlyDeleted() else "0"
    elif role == Qt.UserRole + 3:
      return "1" if entry.pinned else "0"

    if index.column() == 0: # name
      if role == Qt.DisplayRole:
        return entry.name()
      elif role == Qt.DecorationRole:
        return self._icon.get(entry.typeName())
    elif index.column() == 1: # pinned
      if role == Qt.DisplayRole:
        return "1" if entry.pinned else "0"
    elif index.column() == 2: # updated
      if role == Qt.DisplayRole:
        return entry.updatedOn()
    elif index.column() == 3: # type
      if role == Qt.DisplayRole:
        return entry.typeName().title()

    return None

  def headerData(self, section, orientation, role):
    if role == Qt.DisplayRole:
      if section == 0:
        return "Name"
      elif section == 1:
        return ""
      elif section == 2:
        return "Updated"
      elif section == 3:
        return "Type"

  def proxy(self):
    return self._topProxy

  def filterTrash(self, b):
    self._filterTrash.setFilterFixedString("0" if b else None)

  def filterPinned(self, b):
    self._filterPinned.setFilterFixedString("1" if b else None)

  def filterName(self, query):
    self._filterName.setFilterWildcard(query)

  def filterType(self, query):
    self._filterType.setFilterRegExp(query)

  def setCaseSensitivity(self, b):
    self._filterName.setFilterCaseSensitivity(b)

  @pyqtSlot(str, int, dict, object)
  def newEntry(self, uid, meta, pth):
    r = len(self._uids)
    self.beginInsertRows(QModelIndex(), r, r)
    self._uids.append(uid)
    self.endInsertRows()

  @pyqtSlot(str, dict, dict)
  def updateEntry(self, uid, meta, pth):
    i = self._uids.index(uid)
    self.dataChanged.emit(self.createIndex(i,0),self.createIndex(i,3),
                     [Qt.ToolTipRole, Qt.ForegroundRole, Qt.UserRole + 1,
                      Qt.UserRole + 2, Qt.UserRole + 3, Qt.DisplayRole])

  def entryFromIndex(self, index):
    if index.isValid():
      return self._index.get(self._uids[index.row()])

  def entryOf(self, uid):
    return self._index.get(uid)


class SearchResults(QTreeView):

  entryTypes = set()
  selected = pyqtSignal(QModelIndex)
  queryChanged = pyqtSignal(str)

  def __init__(self, index, parent=None):
    QTreeView.__init__(self, parent=parent)
    self._index_model = FlatRemarkableIndexModel(index)
    self.setModel(self._index_model.proxy())
    self._query = None
    # self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool);
    # self.setAttribute(Qt.WA_ShowWithoutActivating)
    self.setIconSize(QSize(24,24))
    self.setContextMenuPolicy(Qt.ActionsContextMenu)
    self.setItemDelegateForColumn(1, PinnedDelegate())
    self.setSortingEnabled(True)
    self.header().setStretchLastSection(False)
    self.header().setSectionResizeMode(0, QHeaderView.Stretch)
    self.header().setSectionResizeMode(1, QHeaderView.Fixed)
    self.resizeColumnToContents(1)

    self._optionsMenu = menu = QMenu()
    self._caseToggle = act = menu.addAction("Case sensitive")
    act.setCheckable(True)
    act.setIcon(QIcon(":assets/16/case.svg"))
    act.setIconVisibleInMenu(True)
    act.triggered.connect(self.setCaseSensitivity)
    # act.setChecked(True)
    # act.setChecked(False)
    menu.addSeparator()
    self._pdfToggle = act = menu.addAction("PDF")
    act.setIcon(QIcon(":assets/16/pdf.svg"))
    act.setIconVisibleInMenu(True)
    act.setCheckable(True)
    act.triggered.connect(lambda c: self.showType("pdf", c))
    # act.setChecked(True)
    self._epubToggle = act = menu.addAction("EPUB")
    act.setIcon(QIcon(":assets/16/epub.svg"))
    act.setIconVisibleInMenu(True)
    act.setCheckable(True)
    act.triggered.connect(lambda c: self.showType("epub", c))
    # act.setChecked(True)
    self._notebookToggle = act = menu.addAction("Notebook")
    act.setIcon(QIcon(":assets/16/notebook.svg"))
    act.triggered.connect(lambda c: self.showType("notebook", c))
    act.setIconVisibleInMenu(True)
    act.setCheckable(True)
    # act.setChecked(True)
    self._folderToggle = act = menu.addAction("Folder")
    act.setIcon(QIcon(":assets/16/folder.svg"))
    act.triggered.connect(lambda c: self.showType("folder", c))
    act.setIconVisibleInMenu(True)
    act.setCheckable(True)
    # act.setChecked(True)
    menu.addSeparator()
    self._pinnedToggle = act = menu.addAction("Only Favourites")
    act.setIcon(QIcon(":assets/symbolic/starred.svg"))
    act.triggered.connect(lambda c: self.showPinnedOnly(c))
    act.setIconVisibleInMenu(True)
    act.setCheckable(True)
    # act.setChecked(False)
    menu.addSeparator()
    self._trashToggle = act = menu.addAction("Trash")
    act.setCheckable(True)
    act.setIcon(QIcon(":assets/16/trash.svg"))
    act.setIconVisibleInMenu(True)
    act.triggered.connect(self.showDeleted)
    # act.setChecked(True) # to trigger change signal
    # act.setChecked(False)
    self.showDeleted(False)
    self.setCaseSensitivity(False)
    self.showPinnedOnly(False)
    self.showAllTypes()

  def uidOfItem(self, item):
    return self.model().data(item, Qt.UserRole)

  def optionsMenu(self):
    return self._optionsMenu

  def setQuery(self, txt=None):
    if not txt: txt = None
    if self._query != txt:
      log.debug("Setting query %s", txt)
      self._query = txt
      self._index_model.filterName(txt)
      self.queryChanged.emit(txt)

  def showDeleted(self, b):
    self._index_model.filterTrash(not b)
    self._trashToggle.setChecked(b)

  def showPinnedOnly(self, b):
    self._index_model.filterPinned(b)

  def setCaseSensitivity(self, b):
    self._index_model.setCaseSensitivity(b)
    self._caseToggle.setChecked(b)

  def showOnlyType(self, ty):
    self.entryTypes.clear()
    self.showType(ty, True)

  def showAllTypes(self):
    self.entryTypes.add("epub")
    self.entryTypes.add("pdf")
    self.entryTypes.add("folder")
    self.entryTypes.add("notebook")
    self._typeRefresh()

  def showType(self, ty, b):
    if b:
      self.entryTypes.add(ty)
    else:
      self.entryTypes.discard(ty)
    self._typeRefresh()

  def _typeRefresh(self):
    t = "|".join(self.entryTypes) or "none"
    self._index_model.filterType(t)
    self._epubToggle.setChecked("epub" in self.entryTypes)
    self._pdfToggle.setChecked("pdf" in self.entryTypes)
    self._folderToggle.setChecked("folder" in self.entryTypes)
    self._notebookToggle.setChecked("notebook" in self.entryTypes)

  def selectionChanged(self, sel, desel):
    QTreeView.selectionChanged(self, sel, desel)
    log.debug("SEARCH SEL: %d", len(self.selectedIndexes()))
    sel = self.selectedIndexes()
    if len(sel) > 0:
      self.selected.emit(sel[0])
    else:
      self.selected.emit(QModelIndex())

  @pyqtSlot()
  def clearSelection(self):
    QTreeView.clearSelection(self)
    self.setCurrentIndex(QModelIndex())
    self.selected.emit(QModelIndex())

  def mouseReleaseEvent(self, event):
    i = self.indexAt(event.pos())
    QTreeView.mouseReleaseEvent(self, event)
    if not i.isValid():
      self.setCurrentIndex(QModelIndex())

  # def currentChanged(self, curr, prev):
  #   QTreeView.currentChanged(self, curr, prev)
  #   log.debug("SEARCH CURR: %s -> %s", prev.row(),curr.row())
  #   self.selected.emit(curr)

  def currentEntry(self):
    sel = self.selectedIndexes()
    if len(sel) > 0:
      i = sel[0]
      if i.isValid():
        return self._index_model.entryOf(self.model().data(i, Qt.UserRole))
    return None

  def selectedEntries(self):
    # just because of the selection mode
    e = self.currentEntry()
    return [e] if e else []

  def hasPendingItems(self):
    return False



class SearchBar(QWidget):

  def __init__(self, parent=None):
    QWidget.__init__(self, parent=parent)
    self.layout = layout = QHBoxLayout(self)
    layout.setContentsMargins(5,0,5,0)
    layout.addStretch(1)
    self.search = search = QLineEdit()
    self.searchAction = search.addAction(QIcon(":assets/symbolic/search.svg"), QLineEdit.LeadingPosition)
    self.optionsAction = search.addAction(QIcon(":assets/symbolic/options.svg"), QLineEdit.TrailingPosition)
    self.optionsAction.triggered.connect(self.popupOptions)
    self.optionsAction.setVisible(False)
    self.clearAction = search.addAction(QIcon(":assets/symbolic/clear.svg"), QLineEdit.TrailingPosition)
    search.setPlaceholderText("Search")
    layout.addWidget(search, 1)
    # self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)

    self.searchAction.triggered.connect(self.obtainFocus)
    self.searchAction.setShortcut(QKeySequence.Find)
    self.searchAction.setShortcutContext(Qt.WindowShortcut)

    self.clearAction.setVisible(False)
    self.clearAction.triggered.connect(search.clear)
    self.clearAction.setShortcut(QKeySequence.Cancel)
    self.clearAction.setShortcutContext(Qt.WindowShortcut)

    search.textChanged.connect(lambda txt: self.clearAction.setVisible(len(txt) > 0))

    self.queryEdited = search.textChanged
    self.query = self.search.text
    self.clear = self.search.clear

  @pyqtSlot()
  def obtainFocus(self):
    self.search.setFocus()
    self.search.selectAll()

  def setQuery(self, txt=None):
    if self.search.text() != txt:
      self.search.setText(txt or "")

  def setOptionsMenu(self, menu=None):
    self._optionsMenu = menu
    self.optionsAction.setVisible(menu is not None)

  @pyqtSlot()
  def popupOptions(self):
    menu = self._optionsMenu
    if menu:
      pos = self.search.rect().bottomRight()
      pos = self.search.mapToGlobal(pos) - QPoint(menu.sizeHint().width(), 0)
      menu.popup(pos)
