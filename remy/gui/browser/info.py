from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from remy.gui.qmetadata import *
from remy.gui.thumbnail import ThumbnailWorker
import remy.gui.resources

from remy.utils import log

THUMB_HEIGHT = 150


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
    tf.setPointSize(18)
    title.setFont(tf)
    layout.addWidget(icon, alignment=Qt.AlignHCenter)
    # layout.addWidget(title, alignment=Qt.AlignHCenter)
    titlebox = QHBoxLayout() # this is just to disable title shrinking when wrapping text
    titlebox.addWidget(title)
    layout.addLayout(titlebox)
    details = self.details = QTableWidget()
    details.setColumnCount(2)
    details.setRowCount(0)
    details.setShowGrid(False)
    pal = details.palette()
    pal.setBrush(QPalette.Base, pal.window())
    details.setPalette(pal)
    details.setFrameShape(QFrame.NoFrame)
    details.verticalHeader().setVisible(False)
    details.horizontalHeader().setVisible(False)
    details.horizontalHeader().setStretchLastSection(True)
    layout.addSpacing(20)
    layout.addWidget(details)
    # details = self.details = QFormLayout()
    # layout.addLayout(details)
    # if self.readOnly:
    #   self.drop = None
    #   layout.addStretch(1)
    # else:
    #   drop = self.drop = DropBox()
    #   drop.onFilesDropped.connect(self._onDropped)
    #   layout.addWidget(drop, 1)
    # title.setMargin(10)
    # icon.setMargin(10)
    title.setAlignment(Qt.AlignCenter)
    icon.setAlignment(Qt.AlignCenter)
    # title.setTextInteractionFlags(Qt.TextSelectableByMouse)
    # title.setWordWrap(True)
    self.setDefaultInfo(title="Click on item to see metadata")
    ## title.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
    ## title.setMaximumWidth(self.window().width() * .4)
    details.horizontalHeader().setMinimumSectionSize(100)
    self.setLayout(layout)
    self.setEntry()


  @pyqtSlot(list,list)
  def _onDropped(self, dirs, files):
    self.uploadRequest.emit(self.entry.uid if self.entry else '', dirs, files)

  def _drops(self, enabled, folders=True, action='import'):
    pass
    # if self.drop:
    #   if enabled:
    #     self.drop.accepting([".pdf", ".epub"], folders, action)
    #   else:
    #     self.drop.accepting()

  def _addDetailRow(self, title, data):
    if not data: return
    n = self.details.rowCount()
    self.details.setRowCount(n+1)
    t = QTableWidgetItem(title)
    f = QFont()
    f.setBold(True)
    t.setFont(f)
    t.setTextAlignment(Qt.AlignRight | Qt.AlignTop)
    t.setFlags(Qt.ItemIsEnabled)
    self.details.setItem(n, 0, t)
    if isinstance(data, str):
      t = QTableWidgetItem(data)
      t.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
      t.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
      self.details.setItem(n, 1, t)
    elif isinstance(data, QTableWidgetItem):
      self.details.setItem(n, 1, data)
    else:
      self.details.setCellWidget(n, 1, data)
      self.details.verticalHeader().setSectionResizeMode(n, QHeaderView.ResizeToContents)

  def _resetDetails(self):
    self.details.hide()
    self.details.setRowCount(0)

  def _finalizeDetails(self):
    self.details.resizeColumnToContents(0)
    self.details.resizeRowsToContents()
    self.details.show()

  def setIcon(self, pixmap):
    self.icon.setPixmap(pixmap)
    m = int((THUMB_HEIGHT-pixmap.height()) / 2)
    self.icon.setContentsMargins(0, m, 0, m)

  @pyqtSlot(str,QImage)
  def _onThumb(self, uid, img):
    self.thumbs[uid] = img
    if self.entry and uid == self.entry.uid:
      self.setIcon(QPixmap.fromImage(img))

  def setDefaultInfo(self, **kw):
    self._defaults = kw

  def setInfo(self, title="", icon=None, details=[]):
    self._resetDetails()
    self.title.setText(title)
    if icon is None:
      self.setIcon(QPixmap())
    elif isinstance(icon, str):
      self.setIcon(QPixmap(":assets/128/%s.svg" % icon))
    else:
      self.setIcon(icon)
    for (name, detail) in details:
      self._addDetailRow(name, detail)
    self._finalizeDetails()

  def setEntries(self, entries=None):
    if entries is None or len(entries) == 0 :
      self.setInfo(**self._defaults)
      self.entry = None
    elif len(entries) == 1:
      self.setEntry(entries[0])
    else:
      self._resetDetails()
      self.entry = None
      self.setIcon(QPixmap(":assets/128/multiple-selection.svg"))
      folders = 0
      pdfs = 0
      ebooks = 0
      notebs = 0
      for entry in entries:
        if isinstance(entry, Folder):
          folders += 1
        elif isinstance(entry, PDFDoc):
          pdfs += 1
        elif isinstance(entry, EBook):
          ebooks += 1
        elif isinstance(entry, Notebook):
          notebs += 1
      self.title.setText("%d selected items" % len(entries))
      if folders: self._addDetailRow("Folders", str(folders))
      if pdfs: self._addDetailRow("PDFs", str(pdfs))
      if ebooks: self._addDetailRow("EBooks", str(ebooks))
      if notebs: self._addDetailRow("Notebooks", str(notebs))
      self._finalizeDetails()

  def setEntry(self, entry=None):
    # Todo: Template
    if entry is None:
      self.setInfo(**self._defaults)
      self.entry = None
      return
    if not isinstance(entry, Entry):
      entry = self.index.get(entry)
    self.entry = entry
    self._resetDetails()
    # DETAILS
    self._addDetailRow("Updated", entry.updatedOn(None))
    if isinstance(entry, Folder):
      self._addDetailRow("Folders", "%d" % len(entry.folders))
      self._addDetailRow("Files", "%d" % len(entry.files))
    elif isinstance(entry, Document):
      self._addDetailRow("Opened", entry.openedOn(None))
      if entry.pageCount:
        if entry.originalPageCount and entry.originalPageCount > 0 and entry.pageCount - entry.originalPageCount > 0:
          self._addDetailRow("Pages", f"{entry.pageCount} (of which {entry.pageCount - entry.originalPageCount} of notes)")
        else:
          self._addDetailRow("Pages", str(entry.pageCount))
      self._addDetailRow("Size", entry.size())
      self._addDetailRow("Orientation", entry.orientation)

    if isinstance(entry, PDFBasedDoc):
      np = entry.numMarkedPages()
      if np: self._addDetailRow("Marked pages", str(np))
      np = entry.numHighlightedPages()
      if np: self._addDetailRow("Highl. pages", str(np))
      if entry.documentMetadata:
        self._addDetailRow("Title", entry.documentMetadata.get("title"))
        self._addDetailRow("Authors", ','.join(entry.documentMetadata.get("authors", [])))
        self._addDetailRow("Publisher", entry.documentMetadata.get("publisher"))

    self._addDetailRow("Path", entry.fullPath())

    # ICONS & TITLE
    if isinstance(entry, RootFolder):
      self._drops(True)
      self.title.setText(self.rootName or "Home")
      if entry.fsource.isReadOnly():
        self.setIcon(QPixmap(":assets/128/backup.svg"))
      else:
        self.setIcon(QPixmap(":assets/128/tablet.svg"))
    elif isinstance(entry, TrashBin):
      self._drops(False)
      self.title.setText("Trash")
      self.setIcon(QPixmap(":assets/128/trash.svg"))
    elif isinstance(entry, Folder):
      self._drops(True)
      self.title.setText(entry.visibleName)
      self.setIcon(QPixmap(":assets/128/folder-open.svg"))
    else:
      self.title.setText(entry.visibleName)
      if isinstance(entry, PDFDoc):
        # self._drops(True, False, 'replace')
        self._drops(False)
        self.setIcon(QPixmap(":assets/128/pdf.svg"))
      elif isinstance(entry, Notebook):
        self._drops(False)
        self.setIcon(QPixmap(":assets/128/notebook.svg"))
      elif isinstance(entry, EBook):
        self._drops(False)
        self.setIcon(QPixmap(":assets/128/epub.svg"))
      else:
        self._drops(False)
        self.title.setText("Unknown item")

      if entry.uid in self.thumbs:
        self.setIcon(QPixmap.fromImage(self.thumbs[entry.uid]))
      else:
        tgen = ThumbnailWorker(self.index, entry.uid, THUMB_HEIGHT)
        tgen.signals.thumbReady.connect(self._onThumb)
        QThreadPool.globalInstance().start(tgen)

    tags = entry.allDocTags()
    if tags:
      taglist = QListWidget()
      taglist.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
      for row, tag in enumerate(tags):
        i = QListWidgetItem(tag)
        i.setIcon(QIcon(":assets/16/tag.svg"))
        taglist.addItem(i)
      taglist.setFrameShape(QFrame.NoFrame)
      h = taglist.visualRect(taglist.model().index(taglist.model().rowCount() - 1, 0)).bottom()+4
      h -= taglist.visualRect(taglist.model().index(0, 0)).top()
      taglist.setMaximumHeight(h)
      self._addDetailRow("Tags", taglist)

    tags = entry.allPageTags()
    if tags:
      taglist = QListWidget()
      taglist.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
      for tag in tags:
        i = QListWidgetItem(tag)
        i.setIcon(QIcon(":assets/16/tag.svg"))
        taglist.addItem(i)
      taglist.setFrameShape(QFrame.NoFrame)
      h = taglist.visualRect(taglist.model().index(taglist.model().rowCount() - 1, 0)).bottom()+4
      h -= taglist.visualRect(taglist.model().index(0, 0)).top()
      taglist.setMaximumHeight(h)
      self._addDetailRow("Page Tags", taglist)

    self._addDetailRow("UID", entry.uid)

    self._finalizeDetails()


InfoPanel.thumbs = {}
