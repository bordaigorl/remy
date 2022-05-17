from remy import *

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtPrintSupport import *

from remy.remarkable.palette import Palette
from remy.remarkable.export import validatePageRanges, parseExcludeLayers, validateExcludeLayers
from remy.gui.export.palette import PaletteSelector

from os import path
import time

from remy.utils import log


class ExportDialog(QDialog):

  FileExport = 0
  FolderExport = 1

  @staticmethod
  def getFileExportOptions(parent=None, options={}, **kwargs):
    d = ExportDialog(mode=ExportDialog.FileExport, options=options, parent=parent, **kwargs)
    res = d.exec_()
    if res == QDialog.Accepted:
      return (*d.getOptions(), True)
    else:
      return (None, "", options, False)

  def __init__(self, filename=None, options={}, mode=None, **kwargs):
    super(ExportDialog, self).__init__(**kwargs)
    self.mode = ExportDialog.FileExport if mode is None else mode
    self.options = options
    self.filename = filename

    self.setWindowTitle("Export")
    self.setWindowModality(Qt.WindowModal)

    buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset)
    buttonBox.accepted.connect(self.accept)
    buttonBox.rejected.connect(self.reject)
    reset = buttonBox.button(QDialogButtonBox.Reset)
    reset.clicked.connect(self.reset)

    form = QFormLayout()
    form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

    # PATH SELECTION
    pathsel = self.pathsel = QLineEdit()
    pathsel.textChanged.connect(self.validatePath)

    act = pathsel.addAction(QIcon(":assets/symbolic/folder.svg"), QLineEdit.TrailingPosition)
    act.setToolTip("Change...")
    act.triggered.connect(self.selectPath)

    act = pathsel.addAction(QIcon(":assets/symbolic/warning.svg"), QLineEdit.TrailingPosition)
    self.replaceWarning = act
    act.setToolTip("A file or folder with the same name already exists.\nBy exporting to this location, you will overwrite its current contents.")
    act.setVisible(False)

    form.addRow("Export to:", pathsel)

    # OPEN EXPORTED
    self.openExp = QCheckBox("Open file on completion")
    form.addRow("", self.openExp)

    # ORIENTATION
    orient = self.orientation = QComboBox()
    orient.addItem("Auto", "auto")
    orient.addItem("Portrait", "portrait")
    orient.addItem("Landscape", "landscape")
    form.addRow("Orientation:", orient)

    # PAGE RANGES
    pageRanges = self.pageRanges = QLineEdit()
    pageRanges.setPlaceholderText("all")
    act = pageRanges.addAction(QIcon(":assets/symbolic/info.svg"), QLineEdit.TrailingPosition)
    act.setToolTip("Examples:\nList of pages: 1,12,3\nRange: 3:end\nMixed: 5,1:3,end\nReverse order: end:1:-1\nSkipping even pages: 1:end:2")
    act = pageRanges.addAction(QIcon(":assets/symbolic/error.svg"), QLineEdit.TrailingPosition)
    self.pageRangeInvalid = act
    act.setToolTip("Page range is invalid")
    act.triggered.connect(self.pageRanges.clear)
    act.setVisible(False)
    pageRanges.textChanged.connect(self.validatePageRanges)
    form.addRow("Page Ranges:", pageRanges)

    # INCLUDE BASE LAYER
    includeBase = self.includeBase = QCheckBox("Include template/base document")
    form.addRow("", includeBase)

    # EXCLUDE LAYERS
    exclLayers = self.exclLayers = QLineEdit()
    exclLayers.setPlaceholderText("none")
    act = exclLayers.addAction(QIcon(":assets/symbolic/info.svg"), QLineEdit.TrailingPosition)
    act.setToolTip('Examples:\nBy layer number: 1,5\nBy layer name: "guides","grid"\nMixed: 1,"guides"\nOnly highlights of a layer: "1/highlights","annot/highlights"')
    act = exclLayers.addAction(QIcon(":assets/symbolic/error.svg"), QLineEdit.TrailingPosition)
    self.exclLayersInvalid = act
    act.setToolTip("List of excluded layers is invalid")
    act.triggered.connect(self.exclLayers.clear)
    act.setVisible(False)
    exclLayers.textChanged.connect(self.validateExcludeLayers)
    form.addRow("Exclude layers:", exclLayers)

    # ERASER MODE
    emode = self.eraserMode = QComboBox()
    emode.addItem("Auto", "auto")
    emode.addItem("Accurate", "accurate")
    emode.addItem("Ignore", "ignore")
    emode.addItem("Quick & Dirty", "quick")
    form.addRow("Eraser mode:", emode)

    # Stroke width scaling
    # thickn = QHBoxLayout()
    thickness = self.thickness = QDoubleSpinBox()
    thickness.setMinimum(0)
    thickness.setSingleStep(0.05)
    # thickArtistic = self.thickArtistic = QCheckBox("Artistic brushes")
    # thickn.addWidget(thickness)
    # thickn.addWidget(thickArtistic)
    form.addRow("Thickness:", thickness)

    # Simplification TOLERANCE & smoothening
    simplsm = QHBoxLayout()
    tolerance = self.tolerance = QDoubleSpinBox()
    tolerance.setMinimum(0)
    tolerance.setSingleStep(0.5)
    smoothen = self.smoothen = QCheckBox("Smoothen")
    simplsm.addWidget(tolerance)
    simplsm.addWidget(smoothen)
    form.addRow("Simplification:", simplsm)

    # COLOR SELECTION
    self.colorsel = PaletteSelector(palette=self.options.get('palette', 'default'))
    form.addRow("Colors:", self.colorsel)

    # pencilRes = self.pencilRes = QDoubleSpinBox()
    # pencilRes.setMinimum(0)
    # pencilRes.setSingleStep(0.5)
    # form.addRow("Pencil scale:", pencilRes)
    pencilMode = self.pencilMode = QComboBox()
    pencilMode.addItem("Textured", 1)
    pencilMode.addItem("Grayscale", 0)
    pencilMode.addItem("Solid black", -1)
    form.addRow("Pencil mode:", pencilMode)

    layout = QVBoxLayout()
    layout.addLayout(form)
    layout.addWidget(buttonBox)
    self.setLayout(layout)
    self.reset()

  @pyqtSlot(bool)
  def selectPath(self, *args):
    if self.mode == ExportDialog.FileExport:
      filename, ok = QFileDialog.getSaveFileName(self, "Export PDF...", self.pathsel.text(), "PDF (*.pdf)")
    else:
      filename, ok = QFileDialog.getExistingDirectory(self, "Export PDF...", self.pathsel.text())
    if ok and filename:
      self.pathsel.setText(filename)

  @pyqtSlot(str)
  def validatePath(self, p):
    if self.mode == ExportDialog.FileExport:
      self.replaceWarning.setVisible(path.isfile(p))
    else:
      self.replaceWarning.setVisible(path.isdir(p))

  @pyqtSlot(str)
  def validatePageRanges(self, text):
    v = not validatePageRanges(text)
    self.pageRangeInvalid.setVisible(v)

  @pyqtSlot(str)
  def validateExcludeLayers(self, text):
    v = not validateExcludeLayers(text)
    self.exclLayersInvalid.setVisible(v)

  @pyqtSlot(bool)
  def reset(self, *args):
    self.pathsel.setText(self.filename or "Document.pdf")
    self.openExp.setChecked(self.options.get("open_exported", False))
    self.pageRanges.clear()
    self.exclLayers.clear() # makes little sense to get it from args

    emi = self.eraserMode.findData(self.options.get("eraser_mode", "ignore"))
    if emi < 0: emi = 1
    self.eraserMode.setCurrentIndex(emi)

    o = self.orientation.findData(self.options.get("orientation", "auto"))
    if o < 0: o = 0
    self.orientation.setCurrentIndex(o)

    self.includeBase.setChecked(self.options.get("include_base_layer", True))

    self.thickness.setValue(self.options.get("thickness_scale", 1))
    # self.thickArtistic.setChecked(self.options.get("thickness_scale_artistic", False))

    self.smoothen.setChecked(self.options.get("smoothen", False))
    self.tolerance.setValue(self.options.get("simplify", 0))
    # colors = self.options.get("colors", {})
    # self.black.setColor(QColor(colors.get("black", DEFAULT_COLORS[0])))
    # self.gray.setColor(QColor(colors.get("gray", DEFAULT_COLORS[1])))
    # self.white.setColor(QColor(colors.get("white", DEFAULT_COLORS[2])))
    # self.highlight.setColor(QColor(colors.get("highlight", DEFAULT_HIGHLIGHT)))
    # self.pencilRes.setValue(self.options.get("pencil_resolution", 0.4))

    pmi = self.pencilMode.findData(self.options.get("pencil_resolution", 1))
    if pmi < 0: pmi = 0
    self.pencilMode.setCurrentIndex(pmi)

  def getOptions(self):
    return (
      self.pathsel.text(),
      self.pageRanges.text(),
      {
        'eraser_mode': self.eraserMode.currentData(),
        'orientation': self.orientation.currentData(),
        'open_exported': self.openExp.isChecked(),
        'include_base_layer': self.includeBase.isChecked(),
        'thickness_scale': self.thickness.value(),
        # 'thickness_scale_artistic': self.thickArtistic.isChecked(),
        'simplify': self.tolerance.value(),
        'smoothen': self.smoothen.isChecked(),
        'palette': self.colorsel.getPalette(),
        'exclude_layers': parseExcludeLayers(self.exclLayers.text()),
        'pencil_resolution': self.pencilMode.currentData(),
      }
    )
