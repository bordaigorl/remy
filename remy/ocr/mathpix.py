import sys
import base64
import requests
import json

try:

  from simplification.cutil import simplify_coords

  def simpl(stroke):
    return simplify_coords([[s.x, s.y] for s in stroke.segments], 2.0)

except Exception:
  simpl = None


def mathpix(page, app_id, app_key, simplify=True, tools = [2, 15, 4, 17, 7, 13]):
  if simpl is None:
    simplify = False
    log.warning("Simplification parameters ignored since the simplification library is not installed")
  x = []
  y = []
  for l in page.layers:
    for k in l.strokes:
      if k.pen in tools:
        if simplify:
          s = simpl(k)
          x.append([p[0] for p in s])
          y.append([p[1] for p in s])
        else:
          x.append([s.x for s in k.segments])
          y.append([s.y for s in k.segments])
  r = requests.post("https://api.mathpix.com/v3/strokes",
      data=json.dumps({"strokes": {"strokes": {"x": x, "y": y}}}),
      headers={"app_id": app_id, "app_key": app_key,
               "Content-type": "application/json"})
  r = json.loads(r.text)
  return r
