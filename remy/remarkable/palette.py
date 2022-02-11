from remy.remarkable.constants import *
from PyQt5.QtGui import QColor

# DEFAULT_COLORS = {
#   0: Qt.black,
#   1: QColor('#bbbbbb'),
#   2: Qt.white,
#   6: QColor('#0062cc'),
#   7: QColor('#d90707'),
# }
# DEFAULT_HIGHLIGHT = {
#   1: QColor(255,235,147),
#   3: QColor(254,253,96),
#   4: QColor(169,250,92),
#   5: QColor(255,85,207),
# }
# ALPHA_HIGHLIGHT = {
#   1: QColor(255,235,147, 127),
#   3: QColor(254,253,96, 127),
#   4: QColor(169,250,92, 127),
#   5: QColor(255,85,207, 127),
# }

class Palette():

  def __init__(self, colors={}, name=None):
    # super(Palette, self).__init__()
    self._palette = {}
    self._name = name
    for cname, color in COLORS.items():
      self._palette[cname] = QColor(colors.get(cname, color))

  def name(self):
    return self._name

  def title(self):
    return self._name.capitalize().replace('_', ' ')

  def get(self, name):
    return self._palette.get(name)

  def set(self, name, color):
    self._palette[name] = QColor(color)

  def color(self, i):
    return self._palette.get(COLOR_CODES.get(i))

  def highlight(self, i):
    return self._palette.get(HIGHLIGHTER_CODES.get(i))

  def colorFor(self, tool, i):
    if HIGHLIGHTER_TOOL == TOOL_ID.get(tool):
      return self.highlight(i)
    return self.color(i)

  def setColors(self, colors):
    for cname, color in colors.items():
      self._palette[cname] = QColor(color)

  def opacityBased(self):
    p = Palette(self._palette)
    for c in ['highlight', 'yellow', 'green', 'pink']:
      p._palette[c].setAlpha(127)
    return p

  def toDict(self):
    return {col: qcol.name() for col, qcol in self._palette.items()}


class PalettePresets():

  def __init__(self, palettes={}):
    self._palettes = {}
    for name, pal in palettes.items():
      self._palettes[name] = Palette(pal, name)
    if 'default' not in self._palettes:
      self._palettes['default'] = Palette(name='default')

  def items(self):
    yield from self._palettes.items()

  def get(self, pal):
    if isinstance(pal, dict):
      return Palette(pal)
    elif pal in self._palettes:
      return self._palettes[pal]
    else:
      return self._palettes['default']

  def toDict(self):
    return {name: pal.toDict() for name, pal in self._palettes.items()}
