from remy import *

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtPrintSupport import *

import remy.remarkable.constants as rm

from simplification.cutil import simplify_coords

import time
import logging
log = logging.getLogger('remy')


def simpl(stroke, tolerance=10.0):
  return simplify_coords([[s.x, s.y] for s in stroke.segments], tolerance)

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

def _progress(p, i, t):
  if callable(p):
    p(i, t)


DEFAULT_COLORS = [Qt.black, Qt.gray, Qt.white]
DEFAULT_HIGHLIGHT = QColor(255,235,147, 80)

QUICK_ERASER    = 0
IGNORE_ERASER   = 1
ACCURATE_ERASER = 2

ERASER_MODE = {
  "quick": QUICK_ERASER,
  "ignore": IGNORE_ERASER,
  "accurate": ACCURATE_ERASER,
}


def bezierInterpolation(K, coord):
  n = len(K)-1
  p1=[0.]*n
  p2=[0.]*n

  a=[0.]*n
  b=[0.]*n
  c=[0.]*n
  r=[0.]*n

  a[0]=0.
  b[0]=2.
  c[0]=1.
  r[0] = K[0][coord]+2.*K[1][coord]

  for i in range(1,n-1):
    a[i]=1.
    b[i]=4.
    c[i]=1.
    r[i] = 4. * K[i][coord] + 2. * K[i+1][coord]

  a[n-1]=2.
  b[n-1]=7.
  c[n-1]=0.
  r[n-1] = 8. *K[n-1][coord] + K[n][coord]

  # Thomas algorithm
  for i in range(1,n):
    m = a[i]/b[i-1]
    b[i] = b[i] - m * c[i - 1]
    r[i] = r[i] - m * r[i-1]

  p1[n-1] = r[n-1]/b[n-1]
  for i in range(n-2,-1,-1):
    p1[i] = (r[i] - c[i] * p1[i+1]) / b[i]

  for i in range(n-1):
    p2[i]=2.*K[i+1][coord]-p1[i+1]

  p2[n-1]=0.5*(K[n][coord]+p1[n-1])

  return (p1,p2)



class PageGraphicsItem(QGraphicsRectItem):

  def __init__(
      self,
      page,
      scene=None,
      colors=DEFAULT_COLORS,
      highlight=DEFAULT_HIGHLIGHT,
      simplify=0,
      smoothen=False,
      eraser_mode=ACCURATE_ERASER,
      parent=None,
      progress=None,
  ):
    super().__init__(0,0,rm.WIDTH,rm.HEIGHT,parent)

    if isinstance(eraser_mode, str):
      eraser_mode = ERASER_MODE.get(eraser_mode, ACCURATE_ERASER)
    if isinstance(colors, dict):
      highlight = colors.get('highlight', highlight)
      colors = [
        QColor(colors.get('black', DEFAULT_COLORS[0])),
        QColor(colors.get('gray', DEFAULT_COLORS[1])),
        QColor(colors.get('white', DEFAULT_COLORS[2])),
      ]

    noPen = QPen(Qt.NoPen)
    noPen.setWidth(0)
    self.setPen(noPen)
    eraserStroker = QPainterPathStroker()
    eraserStroker.setCapStyle(Qt.RoundCap)
    eraserStroker.setJoinStyle(Qt.RoundJoin)

    pen = QPen()
    pen.setWidth(1)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    pbrush = QBrush(Qt.Dense3Pattern)

    totalStrokes = sum(len(l.strokes) for l in page.layers)
    curStroke = 0
    _progress(progress,curStroke,totalStrokes); curStroke += 1

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
          pbrush.setColor(colors[k.color])
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
          pass
        elif k.pen == 6 and eraser_mode == IGNORE_ERASER:
          pass
        elif k.pen == 6 and eraser_mode == ACCURATE_ERASER:
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
          log.debug('B: %f', time.perf_counter() - T1); T1 = time.perf_counter()
          # area = fullPageClip.subtracted(subarea)  # this alternative is also expensive
          area.addPath(subarea)
          group.setFlag(QGraphicsItem.ItemClipsChildrenToShape)
          group.setPath(area)
          ### good for testing:
          # group.setPen(Qt.red)
          # group.setBrush(QBrush(QColor(255,0,0,50)))
          newgroup = QGraphicsPathItem()
          newgroup.setPen(noPen)
          group.setParentItem(newgroup)
          group = newgroup
        else:
          if (simplify > 0 or smoothen) and (k.pen == 4 or k.pen == 17):
            pen.setWidthF(k.width)
            if simplify > 0:
              sk = simpl(k, simplify)
            else:
              sk = k.segments
            path = QPainterPath(QPointF(sk[0][0], sk[0][1]))
            if len(sk) == 2:
              path.lineTo(sk[1][0],sk[1][1])
            elif smoothen:
              px1, px2 = bezierInterpolation(sk, 0)
              py1, py2 = bezierInterpolation(sk, 1)
              for i in range(1,len(sk)):
                path.cubicTo(px1[i-1],py1[i-1],px2[i-1],py2[i-1],sk[i][0],sk[i][1])
            else:
              for i in range(1,len(sk)):
                path.lineTo(sk[i][0],sk[i][1])
          else:
            # STANDARD
            for s in k.segments:
              w = calcwidth(k, s)
              if w == pen.widthF() and path:
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

        _progress(progress,curStroke,totalStrokes); curStroke += 1

      group.setParentItem(self)


_TEMPLATE_CACHE = {}

def pixmapOfBackground(bg):
  if bg and bg.name not in _TEMPLATE_CACHE:
    bgf = bg.retrieve()
    if bgf:
      _TEMPLATE_CACHE[bg.name] = QPixmap.fromImage(QImage(bgf))
    else:
      return None
  return _TEMPLATE_CACHE[bg.name]


class BarePageScene(QGraphicsScene):

  def __init__(self, page, parent=None, **kw):
    super().__init__(parent=parent)
    r = self.addRect(0,0,rm.WIDTH, rm.HEIGHT)
    r.setFlag(QGraphicsItem.ItemClipsChildrenToShape)
    if page.background and page.background.name != "Blank":
      img = pixmapOfBackground(page.background)
      if img:
        QGraphicsPixmapItem(img, r)
    PageGraphicsItem(page, parent=r, **kw)
    self.setSceneRect(r.rect())
