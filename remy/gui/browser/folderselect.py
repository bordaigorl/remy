from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

class FolderSelectDialog(QDialog):

  @staticmethod
  def getDestinationFolder(*args, **kwargs):
    d = FolderSelectDialog(*args, **kwargs)
    res = d.exec_()
    if res == QDialog.Accepted:
      return d.selectedFolder()
    else:
      return None

  def __init__(self, index, uid=None, exclude=set(), **kwargs):
    super(FolderSelectDialog, self).__init__(**kwargs)
    self._icon = QIcon(QPixmap(":assets/24/folder.svg"))
    tree = self.tree = QTreeWidget()
    # tree.setMinimumWidth(400)
    tree.setIconSize(QSize(24,24))
    # tree.setColumnCount(4)
    tree.setHeaderLabels(["Name"])
    # tree.setUniformRowHeights(False)
    # tree.header().setStretchLastSection(False)
    # tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
    tree.setSortingEnabled(True)

    nodes = self._nodes = {}
    if uid is None:
      uid = index.root().uid
    self._rootEntry = index.get(uid)
    p = nodes[uid] = QTreeWidgetItem(tree) #tree.invisibleRootItem()
    p.setText(0, self._rootEntry.visibleName)
    p.setIcon(0, self._icon)
    p.setData(0, Qt.UserRole, uid)

    for f in index.scanFolders(uid):
      p = nodes[f.uid]
      for d in f.folders:
        d = index.get(d)
        c = nodes[d.uid] = QTreeWidgetItem(p)
        c.setIcon(0, self._icon)
        c.setText(0, d.visibleName)
        c.setData(0, Qt.UserRole, d.uid)

    # hide excluded
    for i in exclude:
      if i in nodes:
        nodes[i].setHidden(True)

    nodes[uid].setExpanded(True)
    tree.setCurrentItem(nodes[uid])

    buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttonBox.accepted.connect(self.accept)
    buttonBox.rejected.connect(self.reject)

    layout = QVBoxLayout()
    layout.setContentsMargins(0,13,0,0)
    layout.addWidget(QLabel("Select a destination folder:"))
    layout.addWidget(tree)
    layout.addWidget(buttonBox)
    self.setWindowTitle("Destination folder")
    self.setLayout(layout)

  def selectedFolder(self):
    return self.tree.currentItem().data(0, Qt.UserRole)