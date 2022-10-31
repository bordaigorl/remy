from remy import *

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtPrintSupport import *

import remy.remarkable.constants as rm

from remy.remarkable.render import PageGraphicsItem
from remy.gui.export import exportDocument

from os import path

from remy.utils import log


class Actions:

  def __init__(self, parent=None):

    self.export = QAction('Export document...', parent)
    self.export.setIcon(QIcon(":assets/16/export.svg"))
    # TODO
    self.reload = QAction('Reload', parent)
    self.reload.setIcon(QIcon(":assets/16/reload.svg"))
    ###
    self.prevPage = QAction('Previous Page', parent)
    self.prevPage.setIcon(QIcon(":assets/16/go-previous.svg"))
    self.prevMarkedPage = QAction('Previous Marked Page', parent)
    self.prevMarkedPage.setIcon(QIcon(":assets/16/go-marked-previous.svg"))
    self.nextPage = QAction('Next Page', parent)
    self.nextPage.setIcon(QIcon(":assets/16/go-next.svg"))
    self.nextMarkedPage = QAction('Next Marked Page', parent)
    self.nextMarkedPage.setIcon(QIcon(":assets/16/go-marked-next.svg"))
    self.firstPage = QAction('First Page', parent)
    self.firstPage.setIcon(QIcon(":assets/16/go-first.svg"))
    self.lastPage = QAction('Last Page', parent)
    self.lastPage.setIcon(QIcon(":assets/16/go-last.svg"))
    self.fitToView = QAction('Fit to view', parent, checkable=True)
    self.fitToView.setIcon(QIcon(":assets/16/zoom-fit-best.svg"))
    self.actualSize = QAction('Actual Size', parent)
    self.actualSize.setIcon(QIcon(":assets/16/zoom-original.svg"))
    self.zoomIn = QAction('Zoom In', parent)
    self.zoomIn.setIcon(QIcon(":assets/16/zoom-in.svg"))
    self.zoomOut = QAction('Zoom Out', parent)
    self.zoomOut.setIcon(QIcon(":assets/16/zoom-out.svg"))
    self.rotateCW = QAction('Rotate clockwise', parent)
    self.rotateCW.setIcon(QIcon(":assets/16/rotate-cw.svg"))
    self.rotateCCW = QAction('Rotate counter-clockwise', parent)
    self.rotateCCW.setIcon(QIcon(":assets/16/rotate-ccw.svg"))


class NotebookView(QGraphicsView):

  zoomInFactor = 1.25
  zoomOutFactor = 1 / zoomInFactor

  pageChanged = pyqtSignal(int, int)
  resetSize = pyqtSignal(float)

  def __init__(self, document, parent=None):
    QGraphicsView.__init__(self, parent=parent)
    self.actions = Actions(self)
    self._connectActions()
    # self.setAttribute(Qt.WA_OpaquePaintEvent, True)

    self.setRenderHint(QPainter.Antialiasing)
    # self.setRenderHint(QPainter.SmoothPixmapTransform)
    # setting this^ per-pixmap now, so pencil textures are not smoothened

    self.viewport().grabGesture(Qt.PinchGesture)

    self._document = document
    self.options = QApplication.instance().config.preview
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
    a = self.actions
    self.menu.addAction(a.export)
    ###
    self.menu.addSeparator() # --------------------------
    self.menu.addAction(a.fitToView)
    self.menu.addAction(a.actualSize)
    self.menu.addAction(a.zoomIn)
    self.menu.addAction(a.zoomOut)
    self.menu.addSeparator() # --------------------------
    self.menu.addAction(a.rotateCW)
    self.menu.addAction(a.rotateCCW)

    self._fit = True
    self._rotation = 0 # used to produce a rotated screenshot

    self._page_cache = {}
    self._page = 0
    self._templates = {}
    # we only support pdfs for the forseable future
    self._maxPage = document.totalPageCount() - 1
    # if isinstance(document, PDFDoc):
    #   self._maxPage = document.baseDocument().numPages() - 1
    self._loadPage(document.lastOpenedPage or 0)

    self.show()
    if document.orientation == "landscape":
      self.rotateCW()
      self.resetSize.emit(WIDTH / HEIGHT)
    else:
      self.resetSize.emit(HEIGHT / WIDTH)

  def _connectActions(self):
    a = self.actions
    a.export.triggered.connect(lambda: self.export())
    a.fitToView.triggered.connect(lambda: self.setFit(True))
    a.actualSize.triggered.connect(lambda: self.actualSize())
    a.zoomIn.triggered.connect(self.zoomIn)
    a.zoomOut.triggered.connect(self.zoomOut)
    a.rotateCW.triggered.connect(self.rotateCW)
    a.rotateCCW.triggered.connect(self.rotateCCW)
    a.prevPage.triggered.connect(self.prevPage)
    a.prevMarkedPage.triggered.connect(self.prevMarkedPage)
    a.nextPage.triggered.connect(self.nextPage)
    a.nextMarkedPage.triggered.connect(self.nextMarkedPage)
    a.firstPage.triggered.connect(self.firstPage)
    a.lastPage.triggered.connect(self.lastPage)

  def imageOfBackground(self, bg):
    if bg and bg.name not in self._templates:
      bgf = bg.retrieve()
      if bgf:
        self._templates[bg.name] = QImage(bgf)
      else:
        return None
    return self._templates[bg.name]

  def _loadPage(self, i):
    # ermode = self.options.get("eraser_mode", "ignore")
    # pres = self.options.get("pencil_resolution", 0.4)
    # pal = self.options.get("palette", {})
    # scene = self.makePageScene(i, eraser_mode=ermode, pencil_resolution=pres, palette=pal)
    scene = self.makePageScene(i, **self.options)
    self.setScene(scene)
    old_page = self._page
    self._page = i
    # self.refreshTitle()
    self.pageChanged.emit(old_page+1, self._page+1)

  def makePageScene(self, i, replace=False, **options):
    if not replace and i in self._page_cache:
      return self._page_cache[i]

    scene = self._page_cache[i] = QGraphicsScene()
    r = scene.pageRect = scene.addRect(0,0,rm.WIDTH, rm.HEIGHT)
    r.setFlag(QGraphicsItem.ItemClipsChildrenToShape)
    r.setBrush(Qt.white)

    scene.loadingItem = QLoadingItem(r)
    # scene.loadingItem.setRotation(-scene.rotation())

    # lw = scene.loadingItem.boundingRect().width()
    # scene.loadingItem.setPos(r.rect().center() - QPointF(lw/2,12))
    scene.loadingItem.setPos(r.rect().center())


    w = AsyncPageLoad(self._document, i, **options)
    w.signals.pageReady.connect(self.pageReady)
    QThreadPool.globalInstance().start(w)
    return scene


  @pyqtSlot(Page, PageGraphicsItem, QImage)
  def pageReady(self, page, pitem, img):
    scene = self._page_cache[page.pageNum]
    if page.background and page.background.name != "Blank":
      img = self.imageOfBackground(page.background)
      if img:
        scene.baseItem = QGraphicsPixmapItem(QPixmap(img), scene.pageRect)
    elif img:
      img = QGraphicsPixmapItem(QPixmap(img), scene.pageRect)
      img.setTransformationMode(Qt.SmoothTransformation)
      img.setScale(1/2)
      scene.baseItem = img
    else:
      scene.baseItem = None
    scene.removeItem(scene.loadingItem)
    pitem.setParentItem(scene.pageRect)
    scene.setSceneRect(scene.pageRect.rect())
    r=scene.addRect(0,0,rm.WIDTH, rm.HEIGHT)
    r.setPen(Qt.black)


  # def resetSize.emit(self, ratio):
  #   dg = QApplication.desktop().availableGeometry(self.window())
  #   ds = dg.size() * 0.6
  #   if ds.width() * ratio > ds.height():
  #     ds.setWidth(int(ds.height() / ratio))
  #   else:
  #     ds.setHeight(int(ds.width() * ratio))
  #   self.window().resize(ds)

  def document(self):
    return self._document

  def currentPage(self):
    return self._document.getPage(self._page)

  def currentPageNum(self):
    return self._page+1

  def currentPageIndex(self):
    return self._page

  def maximumPageNum(self):
    return self._maxPage+1

  def setCurrentPageNum(self, p):
    p -= 1
    if p >= 0 and p <= self._maxPage:
      self._loadPage(p)
      return True
    return False

  def firstPage(self):
    self._loadPage(0)

  def lastPage(self):
    self._loadPage(self._maxPage)

  def nextPage(self):
    if self._page < self._maxPage:
      self._loadPage(self._page + 1)
      return True
    return False

  def prevPage(self):
    if self._page > 0:
      self._loadPage(self._page - 1)
      return True
    return False

  def nextMarkedPage(self):
    p = self._page
    while p < self._maxPage:
      p +=1
      if self._document.marked(p):
        self._loadPage(p)
        return True
    return False

  def prevMarkedPage(self):
    p = self._page
    while p > 0:
      p -=1
      if self._document.marked(p):
        self._loadPage(p)
        return True
    return False

  # def refreshTitle(self):
  #   self.window().setWindowTitle("%s - Page %d of %d" % (self._document.visibleName, self._page + 1, self._maxPage +1))

  def contextMenuEvent(self, event):
    self.actions.fitToView.setChecked(self._fit)
    self.menu.exec_(self.mapToGlobal(event.pos()))

  def updateViewer(self):
    if self._fit:
      self.fitInView(self.sceneRect(), self.aspectRatioMode)
    # else:

  def resizeEvent(self, event):
    self.updateViewer()

  def viewportEvent(self, event):
    if event.type() == QEvent.Gesture:
      pinch = event.gesture(Qt.PinchGesture)
      if pinch is not None:
        self._fit = False
        self.scale(pinch.scaleFactor(), pinch.scaleFactor())
        return True
    return bool(QGraphicsView.viewportEvent(self, event))

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
    elif event.modifiers() != Qt.ShiftModifier:
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

  def export(self):
    exportDocument(self._document, self)



  _tolerance = {}
  _smoothen = False

  def keyPressEvent(self, event):
    if event.matches(QKeySequence.Close):
      self.close()
    elif event.key() == Qt.Key_Left:
      if event.modifiers() & Qt.ControlModifier:
        self._loadPage(0)
      elif event.modifiers() & Qt.MetaModifier:
        self.rotateCCW()
      else:
        self.prevPage()
    elif event.key() == Qt.Key_Right:
      if event.modifiers() & Qt.ControlModifier:
        self._loadPage(self._maxPage)
      elif event.modifiers() & Qt.MetaModifier:
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
    elif event.key() == Qt.Key_S and event.modifiers() & Qt.MetaModifier:
      self._smoothen = not self._smoothen
      i = self._page
      self._tolerance.setdefault(i, 0)
      self.makePageScene(i, replace=True, simplify=self._tolerance[i], smoothen=self._smoothen)
      self.setScene(self._page_cache[i])
    elif event.key() == Qt.Key_S:
      i = self._page
      self._tolerance.setdefault(i, .5)
      if event.modifiers() & Qt.ShiftModifier:
        if self._tolerance[i] > 0:
          self._tolerance[i] -= .25
      else:
        self._tolerance[i] += .25
      log.info("Tolerance: %g", self._tolerance[i])
      self.makePageScene(i, replace=True, simplify=self._tolerance[i], smoothen=self._smoothen)
      self.setScene(self._page_cache[i])


class AsyncPageLoadSignals(QObject):
  pageReady = pyqtSignal(Page, PageGraphicsItem, QImage)

class AsyncPageLoad(QRunnable):

  def __init__(self, document, i, **kw):
    QRunnable.__init__(self)
    self.document = document
    self.pageNum = i
    self.options = kw
    self.signals = AsyncPageLoadSignals()

  def imageOfBasePdf(self, mult=1):
    pdf = self.document.baseDocument()
    if pdf:
      return pdf.toImage(self.pageNum, 72.0 * mult)
    else:
      return QImage()

  def run(self):
    page = self.document.getPage(self.pageNum)
    # try:
    if page.background and page.background.name != "Blank":
      page.background.retrieve()
      img = QImage()
      # images are cached
    else:
      # todo: adapt the oversampling based on QGraphicsView scale
      img = self.imageOfBasePdf(2)
    p = PageGraphicsItem(page, **self.options)
    self.signals.pageReady.emit(page, p, img)



class QLoadingItem(QGraphicsRectItem):

  def __init__(self, parent=None):
    QGraphicsItem.__init__(self, parent=parent)
    self.setFlag(QGraphicsItem.ItemIgnoresTransformations)
    ###
    img = QMovie(":assets/loading.gif")
    imgw = QLabel()
    imgw.setMovie(img)
    img.setScaledSize(QSize(40,40))
    spinner = self.spinner = QGraphicsProxyWidget(self)
    spinner.setWidget(imgw)
    img.start()
    ###
    font=QFont()
    font.setPointSize(14)
    lbl = QGraphicsSimpleTextItem("Loading", self)
    lbl.setFont(font)
    lbl.setBrush(Qt.gray)
    lblr = lbl.boundingRect()
    lbl.setPos(-lblr.width()/2,30)
    # lbl.setPos(-lblr.width()/2,-lblr.height()/2)
    spinner.setPos(-20,-20)
    # spinner.setPos(-lblr.width()/2-40,-15)
    lbl.setText("Loading…")

