WIDTH = 1404
HEIGHT = 1872
WIDTH_MM = 206
HEIGHT_MM = 154.5
PIXELS_NUM = WIDTH * HEIGHT
TOTAL_BYTES = PIXELS_NUM * 2

# evtype_sync = 0
e_type_key = 1
e_type_abs = 3

# evcode_stylus_distance = 25
# evcode_stylus_xtilt = 26
# evcode_stylus_ytilt = 27
e_code_stylus_xpos = 1
e_code_stylus_ypos = 0
e_code_stylus_pressure = 24
# evcode_finger_xpos = 53
# evcode_finger_ypos = 54
# evcode_finger_pressure = 58
e_code_stylus_proximity = 320

stylus_width = 15725
stylus_height = 20951

# normalised ids
BRUSH_TOOL       = 12
MECH_PENCIL_TOOL = 13
PENCIL_TOOL      = 14
BALLPOINT_TOOL   = 15
MARKER_TOOL      = 16
FINELINER_TOOL   = 17
HIGHLIGHTER_TOOL = 18
ERASER_TOOL      = 6
ERASE_AREA_TOOL  = 8
CALLIGRAPHY_TOOL = 21
UNKNOWN_TOOL     = None

# id to normalised id
TOOL_ID = {
   0: BRUSH_TOOL,
   1: PENCIL_TOOL,
   2: BALLPOINT_TOOL,
   3: MARKER_TOOL,
   4: FINELINER_TOOL,
   5: HIGHLIGHTER_TOOL,
   6: ERASER_TOOL,
   7: MECH_PENCIL_TOOL,
   8: ERASE_AREA_TOOL,
   9: CALLIGRAPHY_TOOL, # guesswork
  12: BRUSH_TOOL,
  13: MECH_PENCIL_TOOL,
  14: PENCIL_TOOL,
  15: BALLPOINT_TOOL,
  16: MARKER_TOOL,
  17: FINELINER_TOOL,
  18: HIGHLIGHTER_TOOL,
  19: ERASER_TOOL,
  21: CALLIGRAPHY_TOOL,
}

# name to normalised id
TOOL_NAME_ID = {
        "brush": BRUSH_TOOL,
  "mech_pencil": MECH_PENCIL_TOOL,
       "pencil": PENCIL_TOOL,
    "ballpoint": BALLPOINT_TOOL,
       "marker": MARKER_TOOL,
    "fineliner": FINELINER_TOOL,
  "highlighter": HIGHLIGHTER_TOOL,
       "eraser": ERASER_TOOL,
   "erase_area": ERASE_AREA_TOOL,
  "calligraphy": CALLIGRAPHY_TOOL,
}

# normalised id to name
TOOL_NAME = {
        BRUSH_TOOL: "brush",
  MECH_PENCIL_TOOL: "mech_pencil",
       PENCIL_TOOL: "pencil",
    BALLPOINT_TOOL: "ballpoint",
       MARKER_TOOL: "marker",
    FINELINER_TOOL: "fineliner",
  HIGHLIGHTER_TOOL: "highlighter",
       ERASER_TOOL: "eraser",
   ERASE_AREA_TOOL: "erase_area",
  CALLIGRAPHY_TOOL: "calligraphy",
}

TOOL_LABEL = {
        "brush": "Brush",
       "pencil": "Pencil",
    "ballpoint": "Ballpoint",
       "marker": "Marker",
    "fineliner": "Fineliner",
  "highlighter": "Highlighter",
       "eraser": "Eraser",
  "mech_pencil": "Mechanical Pencil",
   "erase_area": "Erase Area",
}



