from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from remy.gui.qmetadata import *
from remy.gui.thumbnail import ThumbnailWorker
import remy.gui.resources

from remy.utils import log

THUMB_HEIGHT = 150


class InfoPanel(QWidget):

  # uploadRequest = pyqtSignal(str, list, list)

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
    title.setAlignment(Qt.AlignCenter)
    icon.setAlignment(Qt.AlignCenter)
    title.setTextInteractionFlags(Qt.TextSelectableByMouse)
    title.setWordWrap(True)
    self.setDefaultInfo(title="Click on item to see metadata")
    ## title.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
    ## title.setMaximumWidth(self.window().width() * .4)
    details.horizontalHeader().setMinimumSectionSize(100)
    self.setLayout(layout)
    self.setEntry()

  def _addDetailRow(self, title, data, kerning=True):
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
      if not kerning:
        f = QFont(); f.setKerning(False)
        t.setFont(f)
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
    self._addDetailRow("Updated", entry.updatedFullDate(None))
    if isinstance(entry, Folder):
      self._addDetailRow("Folders", "%d" % len(entry.folders))
      self._addDetailRow("Files", "%d" % len(entry.files))
    elif isinstance(entry, Document):
      self._addDetailRow("Opened", entry.openedFullDate(None))
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

    self._addDetailRow("Path", entry.fullPath(), kerning=False)

    # ICONS & TITLE
    if isinstance(entry, RootFolder):
      self.title.setText(self.rootName or "Home")
      if entry.fsource.isReadOnly():
        self.setIcon(QPixmap(":assets/128/backup.svg"))
      else:
        self.setIcon(QPixmap(":assets/128/tablet.svg"))
    elif isinstance(entry, TrashBin):
      self.title.setText("Trash")
      self.setIcon(QPixmap(":assets/128/trash.svg"))
    elif isinstance(entry, Folder):
      self.title.setText(entry.visibleName)
      self.setIcon(QPixmap(":assets/128/folder-open.svg"))
    else:
      self.title.setText(entry.visibleName)
      if isinstance(entry, PDFDoc):
        self.setIcon(QPixmap(":assets/128/pdf.svg"))
      elif isinstance(entry, Notebook):
        self.setIcon(QPixmap(":assets/128/notebook.svg"))
      elif isinstance(entry, EBook):
        self.setIcon(QPixmap(":assets/128/epub.svg"))
      else:
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
