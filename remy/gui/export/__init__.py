from remy import *

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtPrintSupport import *

from remy.remarkable.export import Exporter, CancelledExporter
from remy.gui.export.options import ExportDialog

from os import path

import logging
log = logging.getLogger('remy')


class ExportOperation(QObject):

  step = 0
  success = pyqtSignal()

  def run(self, filename, document, **kwargs):
    self.name = path.basename(filename)
    self.dialog = QProgressDialog(parent=self.parent())
    self.dialog.setWindowTitle("Exporting %s" % self.name)
    self.dialog.setLabelText("Initialising...")
    self.dialog.setMinimumDuration(500)
    self.dialog.setAutoClose(True)
    exporter = Exporter(filename, document, **kwargs, parent=self)
    exporter.onError.connect(self.onError)
    exporter.onNewPhase.connect(self.onNewPhase)
    exporter.onStart.connect(self.onStart)
    exporter.onProgress.connect(self.onProgress)
    exporter.onSuccess.connect(self.onSuccess)
    self.dialog.canceled.connect(exporter.cancel)
    exporter.start()

  @pyqtSlot(Exception)
  def onError(self, e):
    self.dialog.close()
    if not isinstance(e, CancelledExporter):
      QMessageBox.critical(self.parent(), "Error", "Something went wrong while exporting.\n\n" + str(e))

  @pyqtSlot(int)
  def onStart(self, total):
    self.dialog.setMaximum(total)

  @pyqtSlot(str)
  def onNewPhase(self, s):
    self.dialog.setLabelText("Exporting %s:\n%s..." % (self.name, s))

  @pyqtSlot()
  def onProgress(self):
    self.step += 1
    self.dialog.setValue(self.step)

  @pyqtSlot()
  def onSuccess(self):
    self.dialog.setValue(self.dialog.maximum())
    self.success.emit()


class WebUIExport(QObject):
  # TODO make asynchronous + progress dialog

  def run(self, filename, uid, webUIUrl="10.11.99.1"):
    import requests
    # Credit: https://github.com/LinusCDE/rmWebUiTools
    response = requests.get(
      "http://{webUIUrl}/download/{uid}/placeholder".format(
        webUIUrl=webUIUrl, uid=uid
      ),
      stream=True,
    )

    if not response.ok:
      raise Exception("Download from WebUI failed")

    response.raw.decode_content = True  # Decompress if needed
    with open(filename, "wb") as out:
      for chunk in response.iter_content(8192):
        out.write(chunk)


def exportDocument(doc, parent=None):
  ok = True
  opt = QApplication.instance().config.export
  filename = doc.visibleName
  if not filename.endswith(".pdf"):
    filename += ".pdf"
  filename = path.join(opt.get("default_dir", ""), filename)
  # filename, ok = QFileDialog.getSaveFileName(parent, "Export PDF...", filename)
  filename, whichPages, opt, ok = ExportDialog.getFileExportOptions(filename=filename, options=opt, parent=parent)
  if ok:
    op = ExportOperation(parent=parent)
    if opt.pop("open_exported", True):
      op.success.connect(lambda: QDesktopServices.openUrl(QUrl("file://" + filename)))
    op.run(filename, doc, whichPages=whichPages, **opt)
    return op
  return None


def webUIExport(doc, filename=None, parent=None):
  ok = True
  opt = QApplication.instance().config.export
  if filename is None:
    filename = doc.visibleName
    if not filename.endswith(".pdf"):
      filename += ".pdf"
    filename = path.join(opt.get("default_dir", ""), filename)
    filename, ok = QFileDialog.getSaveFileName(parent, "Export PDF...", filename)
  if ok and filename:
    try:
      op = WebUIExport(parent=parent)
      op.run(filename, doc.uid)
      if opt.pop("open_exported", True):
        QDesktopServices.openUrl(QUrl("file://" + filename))
      return True
    except:
      QMessageBox.critical(parent, "Error", "Could not download PDF from WebUI.\nThis feature only works with USB connections.")
  return False
