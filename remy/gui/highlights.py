from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from remy.utils import log

from textwrap import TextWrapper
import json

HCOL = {
  0: "#ffeb93",
  1: "#ffeb93",
  3: "#fefd60",
  4: "#a9fa5c",
  5: "#ff55cf",
  8: "#A5A5A5",
}

HCODES = {
  0: "yellow",
  1: "yellow",
  3: "yellow",
  4: "green",
  5: "pink",
  8: "gray",
}


class CancelledHighlightsGen(Exception):
  pass

class HighlightsGen(QThread):

  onError = pyqtSignal(Exception)
  onStart = pyqtSignal(int)
  onProgress = pyqtSignal(str)
  onSuccess = pyqtSignal(list)

  _cancel = False

  def __init__(self, entries, parent=None, **kwargs):
    super().__init__(parent=parent)
    self.entries = entries

  def cancel(self):
    self._cancel = True

  def _progress(self, txt="", i=1):
    if self._cancel:
      raise CancelledHighlightsGen("Highlights generation was cancelled")
    # QCoreApplication.processEvents()
    if i > 0:
      self.onProgress.emit(txt)

  # def __del__(self):
  #   self._cancel = True
  #   self.wait()

  def run(self):
    try:
      docs = []
      entries = self.entries
      while len(entries) > 0:
        entry = entries.pop()
        if entry.isFolder():
          docs.extend([entry.index.get(uid) for uid in entry.files])
          entries.extend([entry.index.get(uid) for uid in entry.folders])
        else:
          docs.append(entry)
        self._progress(i=0)
      self.onStart.emit(len(docs)+1)
      results = []
      for doc in docs:
        self._progress(doc.name())
        h = [
          {
            "pageNum": hp.get("pageNum", 0),
            "highlights": list(
              sorted(
                  (
                    {
                      "text": clip.get("text", ""),
                      "start": clip.get("start", 0),
                      "color": clip.get("color", 0),
                      "layer": l+1,
                    }
                    for l, hlayer in enumerate(hp.get("highlights", []))
                    for clip in hlayer
                  ),
                  key=lambda c: c.get("start", 0),
              )
            ),
          }
          for hp in doc.highlights()
        ]
        if len(h) > 0:
          results.append((doc, h))
      self._progress("Done")
      self.onSuccess.emit(results)
    except Exception as e:
      log.warning("Exception on highlights generation: %s", e)
      self.onError.emit(e)
      import traceback
      traceback.print_exc()



class HighlightsViewer(QMainWindow):

  _result = []

  def __init__(self, entries, parent=None, **kwargs):
    super().__init__(parent=parent)
    self.txtbox = QTextEdit()
    self.setCentralWidget(self.txtbox)
    self.dialog = QProgressDialog(parent=self.parent())
    self.dialog.setWindowTitle("Generating Highlights")
    self.dialog.setLabelText("Initialising...")
    self.dialog.setMinimumDuration(500)
    self.dialog.setAutoClose(True)
    exporter = HighlightsGen(entries, parent=self, **kwargs)
    exporter.onError.connect(self.onError)
    exporter.onStart.connect(self.onStart)
    exporter.onProgress.connect(self.onProgress)
    exporter.onSuccess.connect(self.onSuccess)
    self.dialog.canceled.connect(exporter.cancel)
    exporter.start()
    self.resize(QDesktopWidget().availableGeometry(self).size() * 0.4)
    self.setUnifiedTitleAndToolBarOnMac(True)
    tb = self.addToolBar("Export")
    tb.setIconSize(QSize(16, 16))
    tb.setFloatable(False)
    tb.setMovable(False)
    tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    b1 = tb.addAction(QIcon(":/assets/16/export.svg"), "Export")
    b1.triggered.connect(self.export)
    tb.addSeparator()
    self.colorBtn = {}
    b = self.colorBtn["pink"] = tb.addAction(QIcon(":/assets/16/hl-pink.svg"), "Pink")
    b.setCheckable(True)
    b.setChecked(True)
    b.toggled.connect(self._refreshResults)
    b = self.colorBtn["yellow"] = tb.addAction(QIcon(":/assets/16/hl-yellow.svg"), "Yellow")
    b.setCheckable(True)
    b.setChecked(True)
    b.toggled.connect(self._refreshResults)
    b = self.colorBtn["green"] = tb.addAction(QIcon(":/assets/16/hl-green.svg"), "Green")
    b.setCheckable(True)
    b.setChecked(True)
    b.toggled.connect(self._refreshResults)
    b = self.colorBtn["gray"] = tb.addAction(QIcon(":/assets/16/hl-gray.svg"), "Gray")
    b.setCheckable(True)
    b.setChecked(True)
    b.toggled.connect(self._refreshResults)
    self.refreshResults(defaultMsg="Loading highlights...")

  @pyqtSlot(Exception)
  def onError(self, e):
    self.dialog.close()
    if not isinstance(e, CancelledHighlightsGen):
      QMessageBox.critical(self.parent(), "Error", "Something went wrong while exporting.\n\n" + str(e))
    self.close()

  @pyqtSlot(int)
  def onStart(self, total):
    self.dialog.setMaximum(total)

  @pyqtSlot(str)
  def onProgress(self, s):
    self.dialog.setLabelText(f"Generating Highlights: {s}...")
    self.dialog.setValue(self.dialog.value()+1)

  @pyqtSlot(list)
  def onSuccess(self, result):
    self.dialog.setValue(self.dialog.maximum())
    self._result = result
    self.refreshResults()

  def _refreshResults(self, checked=True):
    self.refreshResults()

  def refreshResults(self, defaultMsg="No highlights found."):
    if self._result:
      txt = "&nbsp;<div style='margin: 30px; margin-top: 15px'>"
      for entry, highlights in self._result:
        txt += f"<h2>{entry.name()}</h2>"
        for h in highlights:
          clips = [clip for clip in h.get("highlights", []) if self.colorBtn.get(HCODES.get(clip.get("color", 1), "yellow")).isChecked()]
          if len(clips) > 0:
            txt += f"""
              <div>
              <b>Page {h.get('pageNum', '?')}</b>
              """
            for clip in clips:
              # if self.colorBtn.get(HCODES.get(clip.get("color", 1), "yellow")).isChecked():
              txt += f"""
              <table cellspacing=0 width='100%' style='margin:12px'>
              <tr>
                <td width=8 bgcolor='{HCOL.get(clip.get("color", 1), "")}'/>
                <td style='padding: 0 12px;'>
                {clip.get("text", "")}
                </td>
              </tr>
              </table>
              """
            txt += "</div>"
      txt += "</div>&nbsp;"
    else:
      txt = defaultMsg
    self.txtbox.setHtml(txt)

  def export(self, **kwargs):
    if self._result:
      filename, ok = QFileDialog.getSaveFileName(
          self, "Export highlights", "highlights.md",
          "Markdown (*.md);;Plain text (*.txt);;JSON (*.json)"
      )
      if ok:
        if filename.endswith('.md'):
          wrapper = TextWrapper(initial_indent=' > ', subsequent_indent='   ')
          with open(filename, "w") as out:
            for entry, highlights in self._result:
              out.write(f"## {entry.name()}\n\n")
              for h in highlights:
                clips = [clip for clip in h.get("highlights", []) if self.colorBtn.get(HCODES.get(clip.get("color", 1), "yellow")).isChecked()]
                if len(clips) > 0:
                  out.write(f"Page {h.get('pageNum', '?')}\n\n")
                  for clip in clips:
                    out.write(wrapper.fill(clip.get("text", "")))
                    out.write("\n\n")
          QDesktopServices.openUrl(QUrl("file://" + filename))
        elif filename.endswith('.txt'):
          with open(filename, "w") as out:
            out.write(self.txtbox.toPlainText())
          QDesktopServices.openUrl(QUrl("file://" + filename))
        elif filename.endswith('.json'):
          with open(filename, "w") as out:
            json.dump(
              [
                {
                  "title": d.name(),
                  "path": "/" + d.path(delim="/"),
                  "uid": d.uid,
                  "pages": h,
                }
                for d, h in self._result
              ],
              out,
              indent=4,
            )



