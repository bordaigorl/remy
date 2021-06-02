from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

class NoEditDelegate(QStyledItemDelegate):

  def createEditor(self, parent, option, index):
    return None


class PinnedDelegate(NoEditDelegate):

  def __init__(self, *a, **kw):
    super().__init__(*a, **kw)
    if not hasattr(PinnedDelegate, "_icon"):
      PinnedDelegate._icon = QPixmap(":assets/symbolic/starred.svg")

  def paint(self, painter, style, i):
    QStyledItemDelegate.paint(self, painter, style, QModelIndex())
    if i.data():
      p = style.rect.center()
      painter.drawPixmap(p.x()-8,p.y()-8, PinnedDelegate._icon)

  def sizeHint(self, style, i):
    return QSize(16,24)


class StatusDelegate(NoEditDelegate):

  def __init__(self, *a, **kw):
    super().__init__(*a, **kw)
    if not hasattr(StatusDelegate, "_icon"):
      StatusDelegate._icon = {
        '': QPixmap(":assets/symbolic/ok.svg"),
        'warning': QPixmap(":assets/symbolic/warning.svg"),
        'error': QPixmap(":assets/symbolic/error.svg"),
        'info': QPixmap(":assets/symbolic/info.svg"),
        'updating': QPixmap(":assets/symbolic/updating.svg"),
      }

  def paint(self, painter, style, i):
    QStyledItemDelegate.paint(self, painter, style, QModelIndex())
    icon = StatusDelegate._icon.get(i.data())
    if icon:
      p = style.rect.center()
      painter.drawPixmap(p.x()-8,p.y()-8, icon)

  def sizeHint(self, style, i):
    return QSize(16,24)
