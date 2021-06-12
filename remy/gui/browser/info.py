from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from remy.gui.qmetadata import *
from remy.gui.pagerender import ThumbnailWorker
import remy.gui.resources

import logging
log = logging.getLogger('remy')

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
    self.setDefaultInfo(title="Click on item to see metadata")
    # title.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
    # title.setMaximumWidth(self.window().width() * .4)
    self.setLayout(layout)
    self.setEntry()


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

  def setIcon(self, pixmap):
    self.icon.setPixmap(pixmap)
    m = (THUMB_HEIGHT-pixmap.height()) / 2
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
      self.details.addRow(name, detail)

  def setEntry(self, entry=None):
    if entry is None:
      self.setInfo(**self._defaults)
      self.entry = None
      return
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

InfoPanel.thumbs = {}