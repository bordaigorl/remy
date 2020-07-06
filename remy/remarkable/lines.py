from collections import namedtuple
import struct

from remy.remarkable.constants import *

import json
import os.path


Layer = namedtuple('Layer', ['strokes', 'name'])

Stroke = namedtuple(
  'Stroke',
  ['pen', 'color', 'unk1', 'width', 'unk2', 'segments']
)
Segment = namedtuple(
  'Segment',
  ['x', 'y', 'speed', 'direction', 'width', 'pressure']
)

HEADER_START = b'reMarkable .lines file, version='
S_HEADER_PAGE = struct.Struct('<{}ss10s'.format(len(HEADER_START)))
S_PAGE = struct.Struct('<BBH')  # TODO: might be 'I'
S_LAYER = struct.Struct('<I')
S_STROKE_V3 = struct.Struct('<IIIfI')
S_STROKE_V5 = struct.Struct('<IIIfII')
S_SEGMENT = struct.Struct('<ffffff')


class UnsupportedVersion(Exception):
  pass
class InvalidFormat(Exception):
  pass

def readStruct(fmt, source):
  buff = source.read(fmt.size)
  return fmt.unpack(buff)

def readStroke3(source):
  pen, color, unk1, width, n_segments = readStruct(S_STROKE_V3, source)
  return (pen, color, unk1, width, 0, n_segments)

def readStroke5(source):
  return readStruct(S_STROKE_V5, source)

# source is a filedescriptor from which we can .read(N)
def readLines(source):
  try:

    header, ver, *_ = readStruct(S_HEADER_PAGE, source)
    if not header.startswith(HEADER_START):
      raise InvalidFormat("Header is invalid")
    ver = int(ver)
    if ver == 3:
      readStroke = readStroke3
    elif ver == 5:
      readStroke = readStroke5
    else:
      raise UnsupportedVersion("Remy supports notebooks in the version 3 and 5 format only")
    n_layers, _, _ = readStruct(S_PAGE, source)
    layers = []
    for l in range(n_layers):
      n_strokes, = readStruct(S_LAYER, source)
      strokes = []
      for s in range(n_strokes):
        pen, color, unk1, width, unk2, n_segments = readStroke(source)
        segments = []
        for i in range(n_segments):
          x, y, speed, direction, width, pressure = readStruct(S_SEGMENT, source)
          segments.append(Segment(x, y, speed, direction, width, pressure))
        strokes.append(Stroke(pen, color, unk1, width, unk2, segments))
      layers.append(strokes)

    return (ver, layers)

  except struct.error:
    raise InvalidFormat("Error while reading page")
