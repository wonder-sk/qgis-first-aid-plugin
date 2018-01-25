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

from builtins import range
import sys

from PyQt5.Qsci import QsciCommand
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QApplication
from PyQt5.Qsci import QsciScintilla, QsciLexerPython


fontName = 'Courier'
fontSize = 10
caretBackground = QColor("#e4e4ff")

# based on code from
# http://eli.thegreenplace.net/2011/04/01/sample-using-qscintilla-with-pyqt

class SourceView(QsciScintilla):

    def __init__(self, parent=None):
        QsciScintilla.__init__(self, parent)

        # Set the default font
        font = QFont()
        font.setFamily(fontName)
        font.setFixedPitch(True)
        font.setPointSize(fontSize)
        fontmetrics = QFontMetrics(font)

        # Margin 0 is used for line numbers
        self.setMarginsFont(font)
        self.setMarginWidth(1, fontmetrics.width("00000"))
        self.setMarginLineNumbers(1, True)
        #self.setMarginsBackgroundColor(QColor("#cccccc"))

        # Brace matching: enable for a brace immediately before or after the current position
        self.setBraceMatching(QsciScintilla.SloppyBraceMatch)

        # Current line visible with special background color
        self.setCaretLineVisible(True)
        #self.setCaretLineBackgroundColor(caretBackground)

        # Set Python lexer
        self.setLexer(QsciLexerPython())
        # override style settings to the same font and size
        # (python lexer has styles 0 ... 15)
        for i in range(16):
          #self.SendScintilla(QsciScintilla.SCI_STYLESETFONT, i, fontName)
          self.SendScintilla(QsciScintilla.SCI_STYLESETSIZE, i, fontSize)

        # make the source read-only
        self.SendScintilla(QsciScintilla.SCI_SETREADONLY, True)



    def openFile(self, filename):

        self.setText(open(filename).read())

    def jumpToLine(self, line_number):

        self.setCursorPosition(line_number-1,0)
        self.standardCommands().find(QsciCommand.VerticalCentreCaret).execute()

    #def resizeEvent(self, event):
        #QsciScintilla.resizeEvent(self, event)
        #print "RESIZE"

    def showEvent(self, event):
        QsciScintilla.showEvent(self, event)
        # prevent issues with initially invisible cursor / caret line
        self.setFocus()
        #self.jumpToLine(0)
        # prevent issues with incorrect initial scroll position
        self.standardCommands().find(QsciCommand.VerticalCentreCaret).execute()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = SourceView()
    editor.openFile(sys.argv[0])
    editor.jumpToLine(35)
    editor.show()
    app.exec_()
