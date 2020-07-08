from remy import *

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtPrintSupport import *

import remy.remarkable.constants as rm
from remy.ocr.mathpix import mathpix

from os import path

import time
import logging
log = logging.getLogger('remy')

from simplification.cutil import simplify_coords

def simpl(stroke, tolerance=10.0):
  return simplify_coords([[s.x, s.y] for s in stroke.segments], tolerance)


# class PageScene(QGraphicsScene):

#   def __init__(self, document):

def flat_width(stroke, segment):
  return stroke.width

def dynamic_width(stroke, segment):
  return segment.width + segment.pressure

def bold_dynamic_width(stroke, segment):
  return max(segment.width * segment.pressure * .7, stroke.width * .8)

def very_dynamic_width(stroke, segment):
  return (segment.width / 2) + (segment.width / 2 * segment.pressure)

def const_width(w):
    return lambda stroke, segment: w


from PyPDF2 import PdfFileReader, PdfFileWriter
from PyPDF2.pdf import PageObject

def scenesPdf(scenes, outputPath):
  printer = QPrinter(QPrinter.HighResolution)
  printer.setOutputFormat(QPrinter.PdfFormat)
  # printer.setPageSize(QPrinter.A4)
  printer.setOutputFileName(outputPath)
  printer.setPaperSize(QSizeF(HEIGHT_MM,WIDTH_MM), QPrinter.Millimeter)
  printer.setPageMargins(0,0,0,0, QPrinter.Millimeter)
  p=QPainter()
  p.begin(printer)
  for i in range(len(scenes)):
    if i > 0:
      printer.newPage()
    scenes[i].render(p)
  p.end()


def pdfmerge(scenes, basePath, outputPath):
  baseReader = PdfFileReader(basePath, strict=False)
  pageNum = baseReader.getNumPages()
  assert(pageNum == len(scenes))

  writer = PdfFileWriter()
  annotReader = PdfFileReader(outputPath, strict=False)
  for page in range(pageNum):
    print('%d%%' % (page*100//pageNum), end='\r', flush=True)
    bp = baseReader.getPage(page)
    ap = annotReader.getPage(page)

    s = ap.cropBox or ap.artBox
    aw, ah = s.upperRight[0] - s.upperLeft[0], s.upperLeft[1] - s.lowerLeft[1]
    s = bp.cropBox or bp.artBox
    w, h = s.upperRight[0] - s.upperLeft[0], s.upperLeft[1] - s.lowerLeft[1]

    np = PageObject.createBlankPage(writer, aw, ah)
    if w <= h:
      ratio = min(aw / w, ah / h)
      tx = 0
      ty = ah - ( h * ratio )
      rot = 0
    else:
      w, h = h, w
      ratio = min(aw / w, ah / h)
      tx = w * ratio
      ty = ah - ( h * ratio )
      rot = 90
    np.mergeRotatedScaledTranslatedPage(bp, rot, ratio, tx, ty)
    np.mergePage(ap)

    writer.addPage(np)

  with open(outputPath, 'wb') as out:
    writer.write(out)

  print("Export done.")


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

  def makePageScene(self, i, forViewing=True, simplify=0, fancyEraser=False):
    page = self.document.getPage(i)
    scene = QGraphicsScene()
    noPen = QPen(Qt.NoPen)
    noPen.setWidth(0)
    eraserStroker = QPainterPathStroker()
    eraserStroker.setCapStyle(Qt.RoundCap)
    eraserStroker.setJoinStyle(Qt.RoundJoin)
    highlight = QColor(255,235,147, 120)
    colors = [Qt.black, Qt.gray, Qt.white]
    r = scene.addRect(0,0,rm.WIDTH, rm.HEIGHT)
    scene.setSceneRect(r.rect())
    r.setFlag(QGraphicsItem.ItemClipsChildrenToShape)
    if forViewing:
      r.setBrush(Qt.white)
    r.setPen(noPen)
    # r0 = r
    # r = QGraphicsRectItem(100,100,rm.WIDTH, rm.HEIGHT,r)
    # r.setPen(QPen(Qt.NoPen))
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
    pen = QPen()
    pen.setWidth(1)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    pbrush = QBrush(Qt.Dense3Pattern)

    fullPageClip = QPainterPath(QPointF(0,0))
    fullPageClip.addRect(0,0,rm.WIDTH,rm.HEIGHT)


    for l in page.layers:
      group = QGraphicsPathItem()
      group.setPen(noPen)

      for k in l.strokes:
        calcwidth = dynamic_width
        if k.pen == 0 or k.pen == 12:
          #### BRUSH             ####
          pen.setColor(colors[k.color])
        elif (k.pen == 1 or k.pen == 14):
          #### PENCIL            ####
          c = QColor(colors[k.color])
          c.setAlpha(180)
          pbrush.setColor(c)
          pen.setBrush(pbrush)
        elif (k.pen == 2 or k.pen == 15):
          #### BALLPOINT         ####
          pen.setColor(colors[k.color])
          calcwidth = very_dynamic_width
          # pen.setWidth(2)
        elif (k.pen == 3 or k.pen == 16):
          #### MARKER            ####
          pen.setColor(colors[k.color])
          calcwidth = bold_dynamic_width
        elif (k.pen == 4 or k.pen == 17):
          #### FINELINER         ####
          pen.setColor(colors[k.color])
          calcwidth = flat_width
        elif (k.pen == 5 or k.pen == 18):
          #### HIGHLIGHTER       ####
          pen.setColor(highlight)
          calcwidth = const_width(30)
        elif (k.pen == 6):
          #### ERASER            ####
          pen.setColor(Qt.white)
          calcwidth = flat_width
        elif (k.pen == 7 or k.pen == 13):
          #### MECHANICAL PENCIL ####
          pen.setColor(colors[k.color])
          pen.setBrush(pbrush)
          calcwidth = flat_width
        elif k.pen == 8:
          #### ERASE AREA        ####
          # pen.setColor(Qt.white)
          # calcwidth = const_width(0)
          pass
        else:
          log.warning("Unknown pen code %d" % k.pen)
          pen.setColor(Qt.red)
        pen.setWidthF(0)
        path = None

        if k.pen == 8:
          # ERASE AREA
          # The remarkable renderer seems to ignore these!
          # area = QPainterPath(QPointF(k.segments[0].x, k.segments[0].y))
          # area.setFillRule(Qt.WindingFill)
          # for s in k.segments[1:]:
          #   area.lineTo(s.x,s.y)
          # area = fullPageClip.subtracted(area)
          # group.setFlag(QGraphicsItem.ItemClipsChildrenToShape)
          # group.setPath(area)

          # newgroup = QGraphicsPathItem(r)
          # newgroup.setPen(noPen)
          # group.setParentItem(newgroup)
          # group = newgroup
          pass
        elif k.pen == 6 and fancyEraser:
          # ERASER
          T1 = time.perf_counter()
          eraserStroker.setWidth(k.width)
          area = QPainterPath(QPointF(0,0))
          area.moveTo(0,0)
          area.lineTo(0,rm.HEIGHT)
          area.lineTo(rm.WIDTH,rm.HEIGHT)
          area.lineTo(rm.WIDTH,0)
          area.lineTo(0,0)
          subarea = QPainterPath(QPointF(k.segments[0].x, k.segments[0].y))
          for s in k.segments[1:]:
            subarea.lineTo(s.x,s.y)
          subarea = eraserStroker.createStroke(subarea)
          log.debug('A: %f', time.perf_counter() - T1); T1 = time.perf_counter()
          subarea = subarea.simplified()  # this is expensive
          # area = fullPageClip.subtracted(subarea)  # this alternative is also expensive
          area.addPath(subarea)
          group.setFlag(QGraphicsItem.ItemClipsChildrenToShape)
          group.setPath(area)
          ### good for testing:
          # group.setPen(Qt.red)
          # group.setBrush(QBrush(QColor(255,0,0,50)))
          log.debug('B: %f', time.perf_counter() - T1); T1 = time.perf_counter()
          newgroup = QGraphicsPathItem()
          newgroup.setPen(noPen)
          group.setParentItem(newgroup)
          group = newgroup
        else:
          if simplify > 0 and (k.pen == 4 or k.pen == 17):
            # SIMPLIFIED (Test)
            pen.setWidthF(k.width)
            for s in simpl(k, simplify):
              if path:
                path.lineTo(s[0],s[1])
              else:
                path = QPainterPath(QPointF(s[0], s[1]))
            # END SIMPLIFIED
          else:
            # STANDARD
            for s in k.segments:
              w = calcwidth(k, s)
              if w == pen.width() and path:
                path.lineTo(s.x,s.y)
              else:
                if path:
                  path.lineTo(s.x,s.y)
                  item=QGraphicsPathItem(path, group)
                  item.setPen(pen)
                path = QPainterPath(QPointF(s.x, s.y))
                path.setFillRule(Qt.WindingFill)
                pen.setWidthF(w)
            # END STANDARD

          item=QGraphicsPathItem(path, group)
          item.setPen(pen)
          # if k.pen == 8:
          #   item.setBrush(Qt.white)

        # path = QPainterPath(QPointF(k.segments[0].x, k.segments[0].y))
        # QUADRATIC
        # for i in range(len(k.segments[1:])//2):
        #   s1 = k.segments[2*i+1]
        #   s2 = k.segments[2*i+2]
        #   path.quadTo(s1.x,s1.y,s2.x,s2.y)
        # CUBIC
        # segs = k.segments[1::5]
        # if (len(k.segments)-1) % 5 != 0:
        #   segs.append(k.segments[-1])
        # for j in range(len(segs)//3):
        #   s1 = segs[3*j]
        #   s2 = segs[3*j+1]
        #   s3 = segs[3*j+2]
        #   path.cubicTo(s1.x,s1.y,s2.x,s2.y,s3.x,s3.y)
        # LINEAR
        # for s in k.segments[1:]:
        #   path.lineTo(s.x,s.y)
        # item=QGraphicsPathItem(path, r)
        # pen.setWidth(k.width)
        # item.setPen(pen)

      # group.setPath(fullPageClip)
      group.setParentItem(r)

    if forViewing:
      r=scene.addRect(0,0,rm.WIDTH, rm.HEIGHT)
      r.setPen(Qt.black)
    return scene

  def loadPage(self, i):
    T0 = time.perf_counter()
    fancy = self.options.get('eraser_mode') == "accurate"
    if i not in self._page_cache:
      self._page_cache[i] = self.makePageScene(i, fancyEraser=fancy)
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
      scenes = [self.makePageScene(i, forViewing=False, simplify=.8, fancyEraser=True) for i in range(self._maxPage+1)]
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

