import sys
import base64
import requests
import json

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from remy.remarkable.constants import *
from remy.remarkable.render import BarePageScene, IGNORE_ERASER

from remy.utils import log


try:

  from simplification.cutil import simplify_coords

  def simpl(stroke):
    return simplify_coords([[s.x, s.y] for s in stroke.segments], 2.0)

except Exception:
  simpl = None

DEFAULT_TEXT_TOOLS = [BALLPOINT_TOOL, FINELINER_TOOL, MECH_PENCIL_TOOL]

ARTISTIC_TOOLS = set([BRUSH_TOOL, PENCIL_TOOL, HIGHLIGHTER_TOOL, ERASER_TOOL, ERASE_AREA_TOOL])

class MathPixError(Exception):

  def __init__(self, result):
    Exception.__init__(self, result.get("error"))
    self.result = result


def mathpixRaster(page, app_id, app_key, scale=.5, **opt):
  s = BarePageScene(page, **opt)
  img = QImage(scale * WIDTH, scale * HEIGHT, QImage.Format_RGB32)
  img.fill(Qt.white)
  painter = QPainter(img)
  painter.setRenderHint(QPainter.Antialiasing)
  s.render(painter)
  painter.end()
  temp = QTemporaryFile(QDir.tempPath() + "/XXXXXX.jpg")
  img.save(temp)
  ## debug:
  # QDesktopServices.openUrl(QUrl("file://" + temp.fileName()))
  r = requests.post("https://api.mathpix.com/v3/text",
      files={"file": open(temp.fileName(), "rb")},
      data={
        "options_json": json.dumps({
          "formats": ["text"],
          "math_inline_delimiters": ["$", "$"],
        })
      },
      headers={"app_id": app_id, "app_key": app_key})
  result = r.json()
  if "error" in result:
    i = result["error_info"]["id"]
    if i == "image_no_content":
      return {"text": ""}
    raise MathPixError(result)
  return result

DEFAULT_EXCLUDE_TOOLS = set([BRUSH_TOOL, PENCIL_TOOL, HIGHLIGHTER_TOOL, ERASER_TOOL, ERASE_AREA_TOOL])

def mathpixStrokes(page, app_id, app_key, simplify=True, exclude_tools=DEFAULT_EXCLUDE_TOOLS):
  if simpl is None:
    simplify = False
    log.warning("Simplification parameters ignored since the simplification library is not installed")
  x = []
  y = []
  for l in page.layers:
    for k in l.strokes:
      if TOOL_ID.get(k.pen) not in tools:
        if simplify:
          s = simpl(k)
          x.append([p[0] for p in s])
          y.append([p[1] for p in s])
        else:
          x.append([s.x for s in k.segments])
          y.append([s.y for s in k.segments])
  data = json.dumps({"strokes": {"strokes": {"x": x, "y": y}}})
  if len(data) > 512000:
    log.warning("Mathpix: too many strokes for a single request: %dKb  (max 512Kb).", len(data) // 1000)
  r = requests.post("https://api.mathpix.com/v3/strokes",
      data=data,
      headers={"app_id": app_id, "app_key": app_key,
               "Content-type": "application/json"})
  result = r.json()
  if "error" in result:
    raise MathPixError(result)
  return result


### TODO: Use rendered output since Max request size is 5mb for images and 512kb for strokes
