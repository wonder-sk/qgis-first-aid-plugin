# -----------------------------------------------------------
# Copyright (C) 2015 Martin Dobias
# -----------------------------------------------------------
# Licensed under the terms of GNU GPL 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# ---------------------------------------------------------------------

import sys

from qgis.gui import QgsCodeEditorPython
from qgis.PyQt.Qsci import (
    QsciCommand,
    QsciScintilla
)
from qgis.PyQt.QtGui import (
    QColor
)
from qgis.PyQt.QtWidgets import QApplication


fontName = 'Courier'
fontSize = 10
caretBackground = QColor("#e4e4ff")

# based on code from
# http://eli.thegreenplace.net/2011/04/01/sample-using-qscintilla-with-pyqt


class SourceView(QgsCodeEditorPython):

    def __init__(self, parent=None):
        QgsCodeEditorPython.__init__(self, parent)

        # make the source read-only
        self.SendScintilla(QsciScintilla.SCI_SETREADONLY, True)

    def openFile(self, filename):

        self.setText(open(filename).read())

    def jumpToLine(self, line_number):
        self.setCursorPosition(line_number-1, 0)
        # prevent issues with initially invisible cursor / caret line
        self.setFocus()
        self.standardCommands().find(QsciCommand.Command.VerticalCentreCaret).execute()

    # def resizeEvent(self, event):
        # QsciScintilla.resizeEvent(self, event)
        # print "RESIZE"

    def showEvent(self, event):
        QsciScintilla.showEvent(self, event)
        # self.jumpToLine(0)
        # prevent issues with incorrect initial scroll position
        self.standardCommands().find(QsciCommand.Command.VerticalCentreCaret).execute()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = SourceView()
    editor.openFile(sys.argv[0])
    editor.jumpToLine(35)
    editor.show()
    app.exec()
