from __future__ import absolute_import
#-----------------------------------------------------------
# Copyright (C) 2015 Martin Dobias
#-----------------------------------------------------------
# Licensed under the terms of GNU GPL 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#---------------------------------------------------------------------
from PyQt5.QtWidgets import QWidget, QLineEdit, QTextEdit, QVBoxLayout, QMessageBox, QSplitter, QApplication, QLabel
from future import standard_library
standard_library.install_aliases()
from builtins import str
import sip
sip.setapi('QVariant', 2)
sip.setapi('QString', 2)

from PyQt5.QtCore import *
from PyQt5.QtGui import *
import sys

from .variablesview import VariablesView
from .sourceview import SourceView
from .framesview import FramesView

import code
import traceback
from contextlib import contextmanager


def frame_from_traceback(tb, index):
    while index > 0:
      #print vindex, tb
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


class ConsoleWidget(QWidget):
    def __init__(self, exc_info, parent=None):
        QWidget.__init__(self, parent)

        self.compiler = code.CommandCompiler()  # for console

        self.tb = exc_info[2]
        self.entries = traceback.extract_tb(self.tb)

        self.console = QLineEdit()
        self.console.setPlaceholderText(">>> Python Console")
        self.console.returnPressed.connect(self.exec_console)
        self.console.setFont(QFont("Courier"))

        self.console_out = QTextEdit()
        self.console_out.setReadOnly(True)
        self.console_out.setFont(QFont("Courier"))
        self.console_out.setVisible(False)  # initially hidden

        self.console_outs = ['']*len(self.entries)

        self.frame_vars = [None]*len(self.entries)

        l = QVBoxLayout()
        l.addWidget(self.console_out)
        l.addWidget(self.console)
        l.setContentsMargins(0,0,0,0)
        self.setLayout(l)

    def go_to_frame(self, index):
        self.console_out.setPlainText(self.console_outs[index])
        self.current_frame_index = index

    def exec_console(self):

        index = self.current_frame_index
        if index < 0: return

        # cache frame variables (globals and locals)
        # because every time we ask for frame.f_locals, a new dict instance
        # is created - we keep our local cache that may contain some changes
        if self.frame_vars[index] is None:
            #print "init", index
            frame = frame_from_traceback(self.tb, index)
            self.frame_vars[index] = (dict(frame.f_globals), dict(frame.f_locals))

        frame_vars = self.frame_vars[index]
        #print frame_vars[1]

        line = self.console.text()
        try:
            c = self.compiler(line, "<console>", "single")
        except (OverflowError, SyntaxError, ValueError) as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        if c is None:
            QMessageBox.critical(self, "Error", "Code not complete")
            return

        import io
        io = io.StringIO()
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

        self.console_out.setPlainText(stuff)
        self.console_out.setVisible(True)
        # make sure we are at the end
        c = self.console_out.textCursor()
        c.movePosition(QTextCursor.End)
        self.console_out.setTextCursor(c)
        self.console_out.ensureCursorVisible()

        self.console.setText('')


class DebugWidget(QWidget):
    def __init__(self, exc_info, parent=None):
        QWidget.__init__(self, parent)

        etype, value, tb = exc_info

        self.tb = tb
        self.entries = traceback.extract_tb(tb)

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

        self.variables = VariablesView()

        self.console = ConsoleWidget(exc_info)

        self.splitterMain = QSplitter(Qt.Vertical)
        self.splitterMain.addWidget(self.splitterSrc)
        self.splitterMain.addWidget(self.variables)
        self.splitterMain.addWidget(self.console)

        l = QVBoxLayout()
        l.addWidget(self.error)
        l.addWidget(self.splitterMain)
        self.setLayout(l)

        self.resize(800,600)

        s = QSettings()
        self.splitterSrc.restoreState(s.value("/FirstAid/splitterSrc", b""))
        self.splitterMain.restoreState(s.value("/FirstAid/splitterMain", b""))
        self.restoreGeometry(s.value("/FirstAid/geometry", b""))

        # select the last frame
        self.frames.setCurrentIndex(self.frames.model().index(len(self.entries)-1))

    def closeEvent(self, event):
        s = QSettings()
        s.setValue("/FirstAid/splitterSrc", self.splitterSrc.saveState())
        s.setValue("/FirstAid/splitterMain", self.splitterMain.saveState())
        s.setValue("/FirstAid/geometry", self.saveGeometry())
        QWidget.closeEvent(self, event)

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
