from remy import *

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtPrintSupport import *

import remy.remarkable.constants as rm
from remy.ocr.mathpix import mathpix

from remy.gui.pagerender import PageGraphicsItem
from remy.gui.export import scenesPdf, pdfmerge

from os import path

import time
import logging
log = logging.getLogger('remy')



class NotebookViewer(QGraphicsView):

  zoomInFactor = 1.25
  zoomOutFactor = 1 / zoomInFactor

  def __init__(self, document):
    QGraphicsView.__init__(self)
    # self.setAttribute(Qt.WA_OpaquePaintEvent, True)

    self.document = document
    self.options = QApplication.instance().config.get('preview', {})
    # document.prefetch()
    # self.uid = uid

    # self.scene = QGraphicsScene()
    # self.setScene(self.scene)

    self.setBackgroundBrush(QColor(230,230,230))
    self.aspectRatioMode = Qt.KeepAspectRatio
    self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    self.setAlignment(Qt.AlignCenter)

    self.menu = QMenu(self)
    ###
    act = QAction('Export document...', self)
    act.triggered.connect(lambda: self.export())
    self.menu.addAction(act)
    ###
    self.menu.addSeparator() # --------------------------
    ###
    act = QAction('Convert page with Mathpix...', self)
    act.triggered.connect(lambda: self.mathpix())
    self.menu.addAction(act)
    ###
    self.menu.addSeparator() # --------------------------
    ###
    act = QAction('Fit to view', self, checkable=True)
    self.fitAction = act
    act.triggered.connect(lambda: self.setFit(True))
    self.menu.addAction(act)
    ###
    act = QAction('Actual Size', self)
    act.triggered.connect(lambda: self.actualSize())
    self.menu.addAction(act)
    ###
    act = QAction('Zoom In', self)
    act.triggered.connect(self.zoomIn)
    self.menu.addAction(act)
    ###
    act = QAction('Zoom Out', self)
    act.triggered.connect(self.zoomOut)
    self.menu.addAction(act)
    ###
    self.menu.addSeparator() # --------------------------
    ###
    act = QAction('Rotate clockwise', self)
    act.triggered.connect(self.rotateCW)
    self.menu.addAction(act)
    ###
    act = QAction('Rotate counter-clockwise', self)
    act.triggered.connect(self.rotateCCW)
    self.menu.addAction(act)

    self._fit = True
    self._rotation = 0 # used to produce a rotated screenshot

    self._page_cache = {}
    self._page = 0
    self._templates = {}
    # we only support pdfs for the forseable future
    if isinstance(document, PDFDoc):
      self._maxPage = document.baseDocument().numPages() - 1
    else:
      self._maxPage = document.pageCount - 1
    self.loadPage(document.lastOpenedPage or 0)

    self.show()
    if document.orientation == "landscape":
      self.rotateCW()
      self.resetSize(WIDTH / HEIGHT)
    else:
      self.resetSize(HEIGHT / WIDTH)

  def imageOfBasePdf(self, i, mult=1):
    pdf = self.document.baseDocument()
    if pdf:
      page = pdf.page(i)
      s = page.pageSize()
      w, h = s.width(), s.height()
      if w <= h:
        ratio = min(WIDTH / w, HEIGHT / h)
      else:
        ratio = min(HEIGHT / w, WIDTH / h)
      xres = 72.0 * ratio * mult
      yres = 72.0 * ratio * mult
      if w <= h:
        return page.renderToImage(xres, yres)
      else:
        return page.renderToImage(xres, yres, -1,-1,-1,-1, page.Rotate270)
    else:
      return QImage()

  def pixmapOfBackground(self, bg):
    if bg and bg.name not in self._templates:
      bgf = bg.retrieve()
      if bgf:
        self._templates[bg.name] = QPixmap.fromImage(QImage(bgf))
      else:
        return None
    return self._templates[bg.name]

  def makePageScene(self, i, forViewing=True, simplify=0, eraserMode="ignore"):
    page = self.document.getPage(i)
    scene = QGraphicsScene()
    r = scene.addRect(0,0,rm.WIDTH, rm.HEIGHT)
    r.setFlag(QGraphicsItem.ItemClipsChildrenToShape)
    if forViewing:
      r.setBrush(Qt.white)
    # try:
    if page.background and page.background.name != "Blank":
      img = self.pixmapOfBackground(page.background)
      if img:
        scene.baseItem = QGraphicsPixmapItem(img, r)
    # if isinstance(page.background, PDFDocPage) and page.background.path() != self.document.baseDocument():
    #   print("Not supported for the moment") # narrow usecase
    elif forViewing and self.document.baseDocument():
      # todo: adapt the oversampling based on QGraphicsView scale
      img = self.imageOfBasePdf(i, 2)
      img = QGraphicsPixmapItem(QPixmap(img), r)
      img.setTransformationMode(Qt.SmoothTransformation)
      img.setScale(1/2)
      scene.baseItem = img
    else:
      scene.baseItem = None
    # except Exception as e:
      # print("Too bad, can't open background %s" % e)
    PageGraphicsItem(page, scene=scene, simplify=simplify, eraserMode=eraserMode, parent=r)
    scene.setSceneRect(r.rect())
    if forViewing:
      r=scene.addRect(0,0,rm.WIDTH, rm.HEIGHT)
      r.setPen(Qt.black)
    return scene

  def loadPage(self, i):
    T0 = time.perf_counter()
    ermode = self.options.get("eraser_mode")
    if i not in self._page_cache:
      self._page_cache[i] = self.makePageScene(i, eraserMode=ermode)
    self.setScene(self._page_cache[i])
    self._page = i
    self.refreshTitle()
    log.debug('LOAD PAGE %d: %f', i, time.perf_counter() - T0)

  def resetSize(self, ratio):
    dg = QApplication.desktop().availableGeometry(self)
    ds = dg.size() * 0.6
    if ds.width() * ratio > ds.height():
      ds.setWidth(int(ds.height() / ratio))
    else:
      ds.setHeight(int(ds.width() * ratio))
    self.resize(ds)

  def nextPage(self):
    if self._page < self._maxPage:
      self.loadPage(self._page + 1)

  def prevPage(self):
    if self._page > 0:
      self.loadPage(self._page - 1)

  def refreshTitle(self):
    self.setWindowTitle("%s - Page %d of %d" % (self.document.visibleName, self._page + 1, self._maxPage +1))

  def contextMenuEvent(self, event):
    self.fitAction.setChecked(self._fit)
    self.menu.exec_(self.mapToGlobal(event.pos()))

  def updateViewer(self):
    if self._fit:
      self.fitInView(self.sceneRect(), self.aspectRatioMode)
    # else:

  def resizeEvent(self, event):
    self.updateViewer()

  def mouseDoubleClickEvent(self, event):
    # scenePos = self.mapToScene(event.pos())
    if event.button() == Qt.LeftButton:
        self._fit=True
        self.updateViewer()
        # self.leftMouseButtonDoubleClicked.emit(scenePos.x(), scenePos.y())
    # elif event.button() == Qt.RightButton:
        # self.rightMouseButtonDoubleClicked.emit(scenePos.x(), scenePos.y())
    # super(NotebookViewer, self).mouseDoubleClickEvent(event)


  def wheelEvent(self, event):
    if event.modifiers() == Qt.NoModifier:
      QAbstractScrollArea.wheelEvent(self, event)
    else:
      self._fit = False

      self.setTransformationAnchor(QGraphicsView.NoAnchor)
      self.setResizeAnchor(QGraphicsView.NoAnchor)

      oldPos = self.mapToScene(event.pos())

      # Zoom
      if event.angleDelta().y() > 0:
          zoomFactor = self.zoomInFactor
      else:
          zoomFactor = self.zoomOutFactor
      self.scale(zoomFactor, zoomFactor)

      # Get the new position
      newPos = self.mapToScene(event.pos())

      # Move scene to old position
      delta = newPos - oldPos
      self.translate(delta.x(), delta.y())

  def rotateCW(self):
    self.rotate(90)
    self._rotation += 90
    self.updateViewer()

  def rotateCCW(self):
    self.rotate(-90)
    self._rotation -= 90
    self.updateViewer()

  def zoomIn(self):
    self._fit = False
    self.scale(self.zoomInFactor, self.zoomInFactor)

  def zoomOut(self):
    self._fit = False
    self.scale(self.zoomOutFactor, self.zoomOutFactor)

  def setFit(self, f):
    self._fit = f
    self.updateViewer()

  def actualSize(self):
    self._fit = False
    self.resetTransform()
    self.scale(1/self.devicePixelRatio(), 1/self.devicePixelRatio())
    self.rotate(self._rotation)

  def export(self, filename=None):
    ok = True
    opt = QApplication.instance().config.get("export", {})
    if filename is None:
      filename = self.document.visibleName
      if not filename.endswith(".pdf"):
        filename += ".pdf"
      filename = path.join(opt.get("default_dir", ""), filename)
      filename, ok = QFileDialog.getSaveFileName(self, "Export PDF...", filename)
    if ok and filename:
      ropt = {
        "simplify": opt.get("simplify", 0),
        "eraserMode": opt.get("eraser_mode", "accurate")
      } # this will be properly generalised at some point
      scenes = [self.makePageScene(i, forViewing=False, **ropt) for i in range(self._maxPage+1)]
      scenesPdf(scenes, filename)
      if isinstance(self.document, PDFDoc):
        pdfmerge(scenes, self.document.retrieveBaseDocument(), filename)
      if opt.get("open_exported", True):
        QDesktopServices.openUrl(QUrl("file://" + filename))


  def mathpix(self, pageNum=None, simplify=True):
    if pageNum is None:
      pageNum = self._page
    page = self.document.getPage(pageNum)
    c = QApplication.instance().config
    try:
      r = mathpix(page, c['mathpix']['app_id'], c['mathpix']['app_key'], simplify)
      txt = QPlainTextEdit(r["text"])
      txt.setParent(self, Qt.Window)
      txt.show()
    except:
      QMessageBox.critical(self, "Error",
        "Please check you properly configured your mathpix API keys "
        "in the configuration file.\n\n"
        "Instructions to obtain API keys at\n"
        "https://mathpix.com/ocr")


  _tolerance = {}

  def keyPressEvent(self, event):
    if event.matches(QKeySequence.Close):
      self.close()
    elif event.key() == Qt.Key_Left:
      if event.modifiers() & Qt.ControlModifier:
        self.rotateCCW()
      else:
        self.prevPage()
    elif event.key() == Qt.Key_Right:
      if event.modifiers() & Qt.ControlModifier:
        self.rotateCW()
      else:
        self.nextPage()
    elif event.key() == Qt.Key_F:
      self.setFit(True)
    elif event.key() == Qt.Key_1:
      self.actualSize()
    elif event.key() == Qt.Key_Plus:
      self.zoomIn()
    elif event.key() == Qt.Key_Minus:
      self.zoomOut()
    elif event.key() == Qt.Key_E:
      self.export()
    elif event.key() == Qt.Key_S:
      i = self._page
      self._tolerance.setdefault(i, .5)
      if event.modifiers() & Qt.ShiftModifier:
        if self._tolerance[i] > 0:
          self._tolerance[i] -= .5
      else:
        self._tolerance[i] += .5
      self._page_cache[i] = self.makePageScene(i, simplify=self._tolerance[i])
      self.setScene(self._page_cache[i])

