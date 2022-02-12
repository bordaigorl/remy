from remy import *

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtPrintSupport import *

import remy.remarkable.constants as rm
from remy.ocr.mathpix import mathpix

from remy.remarkable.render import PageGraphicsItem
from remy.gui.export import webUIExport, exportDocument

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

    self.setRenderHint(QPainter.Antialiasing)
    # self.setRenderHint(QPainter.SmoothPixmapTransform)
    # setting this^ per-pixmap now, so pencil textures are not smoothened

    self.viewport().grabGesture(Qt.PinchGesture)

    self.document = document
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
    ###
    act = QAction('Export document...', self)
    act.triggered.connect(lambda: self.export())
    self.menu.addAction(act)
    ###
    if QApplication.instance().config.get('enable_webui_export'):
      act = QAction('PDF from WebUI...', self)
      act.triggered.connect(lambda: self.webUIExport())
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
    self._maxPage = document.pageCount - 1
    # if isinstance(document, PDFDoc):
    #   self._maxPage = document.baseDocument().numPages() - 1
    self.loadPage(document.lastOpenedPage or 0)

    self.show()
    if document.orientation == "landscape":
      self.rotateCW()
      self.resetSize(WIDTH / HEIGHT)
    else:
      self.resetSize(HEIGHT / WIDTH)

  # def imageOfBasePdf(self, i, mult=1):
  #   pdf = self.document.baseDocument()
  #   if pdf:
  #     with pdf.lock:
  #       page = pdf.page(i)
  #       s = page.pageSize()
  #       w, h = s.width(), s.height()
  #       if w <= h:
  #         ratio = min(WIDTH / w, HEIGHT / h)
  #       else:
  #         ratio = min(HEIGHT / w, WIDTH / h)
  #       xres = 72.0 * ratio * mult
  #       yres = 72.0 * ratio * mult
  #       if w <= h:
  #         return page.renderToImage(xres, yres)
  #       else:
  #         return page.renderToImage(xres, yres, -1,-1,-1,-1, page.Rotate270)
  #   else:
  #     return QImage()

  def imageOfBackground(self, bg):
    if bg and bg.name not in self._templates:
      bgf = bg.retrieve()
      if bgf:
        self._templates[bg.name] = QImage(bgf)
      else:
        return None
    return self._templates[bg.name]

  def loadPage(self, i):
    # ermode = self.options.get("eraser_mode", "ignore")
    # pres = self.options.get("pencil_resolution", 0.4)
    # pal = self.options.get("palette", {})
    # scene = self.makePageScene(i, eraser_mode=ermode, pencil_resolution=pres, palette=pal)
    scene = self.makePageScene(i, **self.options)
    self.setScene(scene)
    self._page = i
    self.refreshTitle()

  def makePageScene(self, i, **options):
    if i in self._page_cache:
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


    w = AsyncPageLoad(self.document, i, **options)
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
    exportDocument(self.document, self)

  def webUIExport(self, filename=None):
    webUIExport(self.document, filename, self)

  def mathpix(self, pageNum=None, simplify=True):
    if pageNum is None:
      pageNum = self._page
    page = self.document.getPage(pageNum)
    try:
      c = QApplication.instance().config.get('mathpix')
      r = mathpix(page, c['app_id'], c['app_key'], simplify)
      txt = QPlainTextEdit(r["text"])
      txt.setParent(self, Qt.Window)
      txt.show()
    except Exception as e:
      log.error("Mathpix: %s", e)
      QMessageBox.critical(self, "Error",
        "Please check you properly configured your mathpix API keys "
        "in the configuration file.\n\n"
        "Instructions to obtain API keys at\n"
        "https://mathpix.com/ocr")


  _tolerance = {}
  _smoothen = False

  def keyPressEvent(self, event):
    if event.matches(QKeySequence.Close):
      self.close()
    elif event.key() == Qt.Key_Left:
      if event.modifiers() & Qt.ControlModifier:
        self.loadPage(0)
      elif event.modifiers() & Qt.MetaModifier:
        self.rotateCCW()
      else:
        self.prevPage()
    elif event.key() == Qt.Key_Right:
      if event.modifiers() & Qt.ControlModifier:
        self.loadPage(self._maxPage)
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
      self._page_cache[i] = self.makePageScene(i, simplify=self._tolerance[i], smoothen=self._smoothen)
      self.setScene(self._page_cache[i])
    elif event.key() == Qt.Key_S:
      i = self._page
      self._tolerance.setdefault(i, .5)
      if event.modifiers() & Qt.ShiftModifier:
        if self._tolerance[i] > 0:
          self._tolerance[i] -= .5
      else:
        self._tolerance[i] += .5
      self._page_cache[i] = self.makePageScene(i, simplify=self._tolerance[i], smoothen=self._smoothen)
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

