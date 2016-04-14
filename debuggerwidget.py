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

import sip
sip.setapi('QVariant', 2)
sip.setapi('QString', 2)

from PyQt4.QtCore import *
from PyQt4.QtGui import *
import sys

input_filename = 'test_script.py'

class DebuggerWidget(QWidget):
    def __init__(self, exc_info, parent=None):
        QWidget.__init__(self, parent)

        self.text_edit = QTextEdit()
        self.toolbar = QToolBar()
        self.toolbar.addAction("Run", self.on_run)
        self.toolbar.addAction("BP", self.on_toggle_breakpoint)
        self.label_status = QLabel()
        layout = QVBoxLayout()
        layout.addWidget(self.toolbar)
        layout.addWidget(self.text_edit)
        layout.addWidget(self.label_status)
        self.setLayout(layout)

        self.resize(800,600)

        file_content = open(input_filename).read()
        self.text_edit.setPlainText(file_content)
        self.text_edit.setFont(QFont("Courier"))
        # self.text_edit.setReadOnly(True)  # does not show cursor :(

        self.text_edit.cursorPositionChanged.connect(self.on_pos_changed)
        self.on_pos_changed()

        self.breakpoints = []


    def on_pos_changed(self):
        c = self.text_edit.textCursor()
        line = c.blockNumber() + 1
        col = c.positionInBlock() + 1
        self.label_status.setText("%d:%d" % (line, col))

    def on_run(self):
        gl = {}
        execfile(input_filename, gl)

    def on_toggle_breakpoint(self):
        line_no = self.text_edit.textCursor().blockNumber()
        if line_no in self.breakpoints:
            self.breakpoints.remove(line_no)
        else:
            self.breakpoints.append(line_no)
        self._update_breakpoints_highlight()

    def _update_breakpoints_highlight(self):
        sel = []
        for bp_line_no in self.breakpoints:
            block = self.text_edit.document().findBlockByLineNumber(bp_line_no)
            highlight = QTextEdit.ExtraSelection()
            highlight.cursor = QTextCursor(block)
            highlight.format.setProperty(QTextFormat.FullWidthSelection, True)
            highlight.format.setBackground(QColor(255,180,180))
            sel.append(highlight)
        self.text_edit.setExtraSelections(sel)


if __name__ == '__main__':
    a = QApplication(sys.argv)
    w = DebuggerWidget(sys.exc_info())
    w.show()
    a.exec_()
