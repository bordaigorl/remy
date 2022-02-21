from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from remy.hwr.mathpix import mathpixRaster, MathPixError

from remy.utils import log


class HWRSignal(QObject):
  done = pyqtSignal(dict)
  error = pyqtSignal(Exception)

class HWRWorker(QRunnable):

  def __init__(self, page, **opt):
    QRunnable.__init__(self)
    self.page = page
    self.opt  = opt
    self.signals = HWRSignal()

  def run(self):
    try:
      r = mathpixRaster(self.page, **self.opt)
      self.signals.done.emit(r)
    except Exception as e:
      self.signals.error.emit(e)


class HWRResults(QWidget):

  def __init__(self, page, opt, parent=None):
    QWidget.__init__(self, parent)
    self.gif = QMovie(":assets/recognising.gif", parent=self)
    self.setLayout(QVBoxLayout())
    self.layout().setContentsMargins(0,0,0,0)
    self.textbox = QPlainTextEdit()
    self.textbox.setPlaceholderText("Loading...")
    self.layout().addWidget(self.textbox)
    # self.spinner = QLabel()
    # self.layout().addWidget(self.spinner)
    # self.spinner.setMovie(self.gif)
    # self.spinner.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
    # self.gif.start()
    self.setMinimumSize(QSize(300,250))
    worker = HWRWorker(page, **opt)
    worker.signals.done.connect(self.onDone)
    worker.signals.error.connect(self.onError)
    QThreadPool.globalInstance().start(worker)

  def onDone(self, result):
    # self.gif.stop()
    # self.spinner.hide()
    self.textbox.document().setPlainText(result.get("text", ""))
    self.layout().addWidget(self.textbox)

  def onError(self, exc):
    if isinstance(exc, MathPixError):
      log.error("Mathpix: %s", e.result)
      QMessageBox.critical(self, "MathPix Error",
        "The request to MathPix was unsuccessful:\n\n%s"
        % e.result.get('error'))
    else:
      log.error("Mathpix: %s", exc)
      QMessageBox.critical(self, "Error",
        "Please check you properly configured your mathpix API keys "
        "in the configuration file.\n\n"
        "Instructions to obtain API keys at\n"
        "https://mathpix.com/ocr")
    self.close()

