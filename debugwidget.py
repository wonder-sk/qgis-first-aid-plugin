# -----------------------------------------------------------
#  Copyright (C) 2015 Martin Dobias
# -----------------------------------------------------------
#  Licensed under the terms of GNU GPL 2
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
# ---------------------------------------------------------------------

import code
import os
import traceback
from traceback import FrameSummary
import sys
import json

from qgis.core import Qgis, QgsApplication
from contextlib import contextmanager
from future import standard_library
standard_library.install_aliases()

from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QMessageBox,
    QSplitter,
    QApplication,
    QLabel,
    QDialog,
    QDialogButtonBox,
    QPushButton,
    QFileDialog,
    QHBoxLayout
)
from qgis.PyQt.Qsci import QsciScintilla
from qgis.PyQt.QtCore import (
    pyqtSignal,
    Qt,
    QSettings,
    QCoreApplication
)
from qgis.PyQt.QtGui import (
    QFontMetrics
)

from qgis.gui import (
    QgsGui,
    QgsCodeEditorPython
)

from .variablesview import VariablesView
from .sourceview import SourceView
from .framesview import FramesView


def frame_from_traceback(tb, index):
    while index > 0:
        # print vindex, tb
        tb = tb.tb_next
        index -= 1
    return tb.tb_frame


@contextmanager
def stdout_redirected(new_stdout):
    save_stdout = sys.stdout
    sys.stdout = new_stdout
    try:
        yield None
    finally:
        sys.stdout = save_stdout


class ConsoleInput(QgsCodeEditorPython, code.InteractiveInterpreter):

    execLine = pyqtSignal(str)

    def __init__(self, parent=None):
        super(QgsCodeEditorPython, self).__init__(parent)
        code.InteractiveInterpreter.__init__(self, locals=None)



        self.history = self.load_history()
        self.history_index = 0

        self.displayPrompt()

        self.refreshSettingsShell()

        # Don't want to see the horizontal scrollbar at all
        # Use raw message to Scintilla here (all messages are documented
        # here: http://www.scintilla.org/ScintillaDoc.html)
        self.SendScintilla(QsciScintilla.SCI_SETHSCROLLBAR, 0)

        self.setWrapMode(QsciScintilla.WrapCharacter)
        self.SendScintilla(QsciScintilla.SCI_EMPTYUNDOBUFFER)

    def load_history(self):
        history = []
        try:
            with open(os.path.join(QgsApplication.qgisSettingsDirPath(), "first_aid_history.txt")) as f:
                for command in f:
                    history.append(command.strip("\n"))
        except FileNotFoundError:
            pass
        return history

    def initializeLexer(self):
        super().initializeLexer()
        self.setCaretLineVisible(False)
        self.setLineNumbersVisible(False)  # NO linenumbers for the input line
        self.setFoldingVisible(False)
        # Margin 1 is used for the '>>>' prompt (console input)
        self.setMarginLineNumbers(1, True)
        self.setMarginWidth(1, "00000")
        self.setMarginType(1, 5)  # TextMarginRightJustified=5

        try:
            from qgis.gui import QgsCodeEditorColorScheme
            self.setMarginsBackgroundColor(self.color(QgsCodeEditorColorScheme.ColorRole.Background))
        except ImportError:
            QgsCodeEditorColorScheme = None

        self.setEdgeMode(QsciScintilla.EdgeNone)

    def _setMinimumHeight(self):
        font = self.lexer().defaultFont(0)
        fm = QFontMetrics(font)

        self.setMinimumHeight(fm.height() + 10)

    def displayPrompt(self, more=False):
        self.SendScintilla(QsciScintilla.SCI_MARGINSETTEXT, 0, str.encode("..." if more else ">>>"))

    def refreshSettingsShell(self):
        # Set Python lexer
        self.initializeLexer()

        # Sets minimum height for input area based of font metric
        self._setMinimumHeight()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            self.history_index = max(self.history_index - 1, -len(self.history))
            self.setText(self.history[self.history_index])
            self.displayPrompt()
        elif event.key() == Qt.Key_Down:
            if self.history_index == 0:
                return
            elif self.history_index == -1:
                self.history_index = 0
                self.clear()
            else:
                self.history_index += 1
                self.setText(self.history[self.history_index])
            self.displayPrompt()
        elif event.key() == Qt.Key_Return:
            self.history_index = 0

            cmd = self.text()
            self.history.append(cmd)

            # prevents commands with more lines to break the console
            # in the case they have a eol different from '\n'
            self.setText('')
            self.move_cursor_to_end()

            self.execLine.emit(cmd)
        else:
            super().keyPressEvent(event)

    def get_end_pos(self):
        """Return (line, index) position of the last character"""
        line = self.lines() - 1
        return line, len(self.text(line))

    def insert_text(self, text):
        cur_pos = self.getCursorPosition()
        self.insert(text)
        self.setCursorPosition(cur_pos[0], cur_pos[1] + len(text))

    def move_cursor_to_end(self):
        """Move cursor to end of text"""
        line, index = self.get_end_pos()
        self.setCursorPosition(line, index)
        self.ensureCursorVisible()
        self.ensureLineVisible(line)
        self.displayPrompt()


class ShellOutputScintilla(QgsCodeEditorPython):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.refreshSettingsOutput()

        self.setMinimumHeight(120)

        self.setWrapMode(QsciScintilla.WrapCharacter)
        self.SendScintilla(QsciScintilla.SCI_SETHSCROLLBAR, 0)

    def initializeLexer(self):
        super().initializeLexer()
        self.setFoldingVisible(False)
        self.setEdgeMode(QsciScintilla.EdgeNone)

    def refreshSettingsOutput(self):
        # Set Python lexer
        self.initializeLexer()
        self.setReadOnly(True)

        self.setCaretWidth(0)  # NO (blinking) caret in the output

    def get_end_pos(self):
        """Return (line, index) position of the last character"""
        line = self.lines() - 1
        return line, len(self.text(line))

    def move_cursor_to_end(self):
        line, index = self.get_end_pos()
        self.setCursorPosition(line, index)
        self.ensureCursorVisible()
        self.ensureLineVisible(line)


class ConsoleWidget(QWidget):
    def __init__(self, exc_info, parent=None):
        QWidget.__init__(self, parent)

        self.compiler = code.CommandCompiler()  # for console

        self.tb = exc_info[2]
        self.entries = traceback.extract_tb(self.tb)

        self.console = ConsoleInput()
        self.console.execLine.connect(self.exec_console)

        self.console_out = ShellOutputScintilla()
        self.console_out.setVisible(False)  # initially hidden

        self.console_outs = ['']*len(self.entries)

        self.frame_vars = [None]*len(self.entries)

        l = QVBoxLayout()
        l.addWidget(self.console_out)
        l.addWidget(self.console)
        l.setContentsMargins(0, 0, 0, 0)
        self.setLayout(l)

        self.setFocusProxy(self.console)

    def go_to_frame(self, index):
        self.console_out.setText(self.console_outs[index])
        self.current_frame_index = index

    def exec_console(self, line):
        index = self.current_frame_index
        if index < 0:
            return

        # cache frame variables (globals and locals)
        # because every time we ask for frame.f_locals, a new dict instance
        # is created - we keep our local cache that may contain some changes
        if self.frame_vars[index] is None:
            # print "init", index
            frame = frame_from_traceback(self.tb, index)
            self.frame_vars[index] = (dict(frame.f_globals), dict(frame.f_locals))

        frame_vars = self.frame_vars[index]
        # print frame_vars[1]

        try:
            c = self.compiler(line, "<console>", "single")
        except (OverflowError, SyntaxError, ValueError) as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        if c is None:
            QMessageBox.critical(self, "Error", "Code not complete")
            return

        import io
        io = io.StringIO() if sys.version_info.major >= 3 else io.BytesIO()
        try:
            with stdout_redirected(io):
                exec(c, frame_vars[0], frame_vars[1])
        except:
            etype, value, tb = sys.exc_info()
            QMessageBox.critical(self, "Error", etype.__name__ + "\n" + str(value))
            return

        stuff = self.console_outs[index]
        stuff += ">>> " + line + "\n"
        stuff += io.getvalue()
        self.console_outs[index] = stuff

        self.console_out.setText(stuff)
        self.console_out.setVisible(True)
        # make sure we are at the end
        self.console_out.move_cursor_to_end()

        self.console.setText('')

    def insert_text(self, text):
        self.console.insert_text(text)

class DebugWidget(QWidget):
    def __init__(self, exc_info, parent=None):
        QWidget.__init__(self, parent)

        etype, value, tb = exc_info

        self.tb = tb
        self.entries = traceback.extract_tb(tb)
        self.etype:Exception = etype # For use in copy traceback
        self.evalue:str = value

        self.setWindowTitle('Python Error')

        msg = str(value).replace("\n", "<br>").replace(" ", "&nbsp;")
        self.error = QLabel("<h1>"+etype.__name__+"</h1><b>"+msg+"</b>")
        self.error.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.frames = FramesView()
        self.frames.setTraceback(tb)
        self.frames.selectionModel().currentChanged.connect(self.current_frame_changed)

        self.source = SourceView()

        self.splitterSrc = QSplitter(Qt.Horizontal)
        self.splitterSrc.addWidget(self.frames)
        self.splitterSrc.addWidget(self.source)
        self.splitterSrc.setStretchFactor(0, 1)
        self.splitterSrc.setStretchFactor(1, 2)
        self.splitterSrc.setCollapsible(0, False)
        self.splitterSrc.setCollapsible(1, False)

        self.variables = VariablesView()

        self.variables.object_picked.connect(self.on_view_object_picked)

        self.console = ConsoleWidget(exc_info)

        self.splitterMain = QSplitter(Qt.Vertical)
        self.splitterMain.addWidget(self.splitterSrc)

        self.splitterMain.addWidget(self.variables)
        self.splitterMain.addWidget(self.console)
        self.splitterMain.setCollapsible(0, False)
        self.splitterMain.setCollapsible(1, False)
        self.splitterMain.setCollapsible(2, False)

        l = QVBoxLayout()
        l.addWidget(self.error)
        l.addWidget(self.splitterMain)
        l.setContentsMargins(0, 0, 0, 0)
        self.setLayout(l)

        self.resize(800, 600)

        s = QSettings()
        self.splitterSrc.restoreState(s.value("/FirstAid/splitterSrc", b""))
        self.splitterMain.restoreState(s.value("/FirstAid/splitterMain", b""))

        # select the last frame
        self.frames.setCurrentIndex(self.frames.model().index(len(self.entries)-1))

    def save_state(self):
        s = QSettings()
        s.setValue("/FirstAid/splitterSrc", self.splitterSrc.saveState())
        s.setValue("/FirstAid/splitterMain", self.splitterMain.saveState())

        with open(os.path.join(QgsApplication.qgisSettingsDirPath(), "first_aid_history.txt"), "w+") as f:
            for command in self.console.console.history[-100:]:
                f.write("{}\n".format(command))

    def current_frame_changed(self, current, previous):
        row = current.row()
        if row >= 0 and row < len(self.entries):
            self.go_to_frame(row)

    def go_to_frame(self, index):

        filename = self.entries[index][0]
        lineno = self.entries[index][1]

        self.source.openFile(filename)
        self.source.jumpToLine(lineno)

        local_vars = frame_from_traceback(self.tb, index).f_locals
        self.variables.setVariables(local_vars)

        self.console.go_to_frame(index)

    def on_view_object_picked(self, name):
        self.console.insert_text(name)
        self.console.setFocus()

class DebugDialog(QDialog):

    def __init__(self, exc_info, parent=None):
        QDialog.__init__(self, parent)

        self.setObjectName('FirstAidDebugDialog')
        self.setWindowTitle('Python Error')

        self.debug_widget = DebugWidget(exc_info)
        layout = QVBoxLayout()
        layout.addWidget(self.debug_widget, 1)

        self.horz_layout = QHBoxLayout()

        self.button_box = QDialogButtonBox(QDialogButtonBox.Close)
        self.button_box.rejected.connect(self.reject)

        self.clear_history_button = QPushButton("Clear History")
        self.clear_history_button.clicked.connect(self.clear_console_history)


        self.save_output_button = QPushButton("Copy Details")
        self.save_output_button.clicked.connect(self.save_output)

        self.horz_layout.addWidget(self.clear_history_button)
        self.horz_layout.addWidget(self.save_output_button)
        self.horz_layout.addWidget(self.button_box)

        layout.addLayout(self.horz_layout)

        self.setLayout(layout)

        QgsGui.enableAutoGeometryRestore(self)

    def clear_console_history(self):
        self.debug_widget.console.console.history = []

    def save_output(self):
        dict = {}
        dict["ExceptionDetails"] = {'Type': self.debug_widget.etype.__name__,'Message':str(self.debug_widget.evalue)}
        dict["Environment"] = {'Qgis Version':Qgis.QGIS_VERSION, 'Operating System': QgsApplication.osName(),
                               'Locale':QgsApplication.locale()}
        dict["Trace"] = []
        i = 0
        tb:FrameSummary
        for tb in self.debug_widget.console.entries:
            entry = "{}[{}:{}]".format(tb.name, tb.filename.split("/")[-1], tb.lineno)
            local_vars = frame_from_traceback(self.debug_widget.console.tb, i).f_locals
            local_vars = {k:str(v) for k, v in local_vars.items()}
            dict["Trace"].append({'Name':tb.name, 'Filename':tb.filename.split("/")[-1],
                                  'LineNo': tb.lineno, 'Variables': local_vars})
            i+=1

        jsonStr = json.dumps(dict, indent=2)
        cb = QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText(jsonStr, mode=cb.Clipboard)

    def reject(self):
        self.debug_widget.save_state()
        super().reject()


#####################################
# test

def err_here(a,b):
    c = a+b
    c += d


def call_err():
    a = 1
    b = 2
    err_here(a,b)


if __name__ == '__main__':
    a = QApplication(sys.argv)
    QCoreApplication.setOrganizationName("Test")
    QCoreApplication.setApplicationName("Test App")
    try:
        call_err()
    except Exception as e:
        w = DebugWidget(sys.exc_info())
        w.show()
    a.exec_()

