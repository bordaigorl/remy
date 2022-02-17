# from remy import *

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
# from PyQt5.QtPrintSupport import *

from remy.remarkable.constants import *
from remy.gui.hwr import HWRResults

from remy.gui.notebookview.view import *
from remy.gui.export import webUIExport, exportDocument

# from os import path

# import time
import logging
log = logging.getLogger('remy')



# class PageThumbItem(QListWidgetItem):

#   def __init__(self, document, i, parent=None):
#     QListWidgetItem.__init__(self, parent=parent)
#     self.setText("Page %s" % (i+1))
#     self.document = document
#     self.pageNum = i


class NotebookViewer(QMainWindow):

  def __init__(self, document):
    QMainWindow.__init__(self)

    self.view = NotebookView(document)

    self.actionWebUI = QAction('PDF from WebUI...', self)
    self.actionWebUI.setIcon(QIcon(":assets/16/webui.svg"))
    self.actionWebUI.triggered.connect(self.webUIExport)
    self.actionTextRec = QAction('Convert page with Mathpix...', self)
    self.actionTextRec.setIcon(QIcon(":assets/16/text.svg"))
    self.actionTextRec.triggered.connect(self.mathpix)

    self.setCentralWidget(self.view)
    self.setUnifiedTitleAndToolBarOnMac(True)
    tb = QToolBar("Preview")
    a = self.view.actions
    tb.addAction(a.export)
    tb.addAction(self.actionWebUI)
    tb.addSeparator()
    tb.addAction(self.actionTextRec)
    tb.addSeparator()
    tb.addAction(a.firstPage)
    tb.addAction(a.prevPage)
    self.pageNumEdit = QLineEdit()
    self.pageNumEdit.setText("1")
    # self.pageNumEdit.setValidator(QIntValidator(0,100))
    self.pageNumEdit.setFixedWidth(50)
    self.pageNumEdit.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
    self.pageNumEdit.editingFinished.connect(self._pageNumEdited)
    tb.addWidget(self.pageNumEdit)
    tb.addAction(a.nextPage)
    tb.addAction(a.lastPage)
    tb.addSeparator()
    tb.addAction(a.zoomIn)
    tb.addAction(a.fitToView)
    tb.addAction(a.actualSize)
    tb.addAction(a.zoomOut)
    tb.addSeparator()
    tb.addAction(a.rotateCW)
    tb.addAction(a.rotateCCW)

    # self.view.menu.addAction(self.actionWebUI)
    # self.view.menu.addAction(self.actionTextRec)


    tb.setIconSize(QSize(16,16))
    tb.setFloatable(False)
    tb.setMovable(False)
    self.addToolBar(tb)

    self.view.pageChanged.connect(self._onPageChange)
    self._onPageChange(self.view.currentPageNum(), self.view.currentPageNum())

  def _onPageChange(self, old, new):
    self.pageNumEdit.setText(str(new))
    self.setWindowTitle("%s - Page %d of %d" % (self.view.document().visibleName, self.view.currentPageNum(), self.view.maximumPageNum()))

  def _pageNumEdited(self):
    p = int(self.pageNumEdit.text())
    if not self.view.setCurrentPageNum(p):
      self.pageNumEdit.setText(str(self.view.currentPageNum()))


  def _onResetSize(self, ratio):
    dg = QApplication.desktop().availableGeometry(self.window())
    ds = dg.size() * 0.6
    if ds.width() * ratio > ds.height():
      ds.setWidth(int(ds.height() / ratio))
    else:
      ds.setHeight(int(ds.width() * ratio))
    self.window().resize(ds)

  def webUIExport(self, filename=None):
    webUIExport(self.view.document(), filename, self)

  def mathpix(self):
    page = self.view.currentPage()
    pageNum = self.view.currentPageNum()
    opt = QApplication.instance().config.mathpix
    w = HWRResults(page, opt)
    w.setParent(self, Qt.Window)
    w.setWindowTitle("Handwriting recongition for page %d of %s" % (pageNum, self.view.document().visibleName))
    w.show()
