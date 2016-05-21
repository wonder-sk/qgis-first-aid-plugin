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

# TODO:
# - debugging of any file
# - load files
# - breakpoints in any file

import sip
sip.setapi('QVariant', 2)
sip.setapi('QString', 2)

from PyQt4.QtCore import *
from PyQt4.QtGui import *
import sys
import bdb
import traceback

from variablesview import VariablesView
from framesview import FramesView

input_filename = 'test_script.py'

def format_frame(frame):
    return "<FRAME %s:%d :: %s>" % (frame.f_code.co_filename, frame.f_lineno, frame.f_code.co_name)

def format_frames(frame):
    if frame.f_back is not None:
        ret = format_frames(frame.f_back) + "\n"
    else:
        ret = ""
    ret += format_frame(frame)
    return ret

class Debugger(object):

    def __init__(self, main_widget):

        self.active = False
        self.ev_loop = QEventLoop()
        self.main_widget = main_widget
        self.lineno = -1
        self.stepping = False

    def trace_function(self, frame, event, arg):
        """ to be used for sys.trace """
        if event == 'call':   # arg is always None
            # we need to return tracing function for this frame - either None or this function...

            if frame.f_code.co_filename != input_filename:
                # only trace the test script
                return None
            return self.trace_function

        elif event == 'line':  # arg is always None
            print "++ line", format_frame(frame)

            if self.stepping or frame.f_lineno-1 in self.main_widget.breakpoints:
                self.lineno = frame.f_lineno
                self.main_widget.vars_view.setVariables(frame.f_locals)
                self.main_widget.frames_view.setTraceback(traceback.extract_stack(frame))
                self.main_widget.update_highlight()
                self.ev_loop.exec_()

        elif event == 'return':  # arg is return value
            pass
            #print "++ return", arg

        else:
            print "trace", format_frames(frame), " | ", event, arg




class DebuggerWidget(QWidget):
    def __init__(self, exc_info, parent=None):
        QWidget.__init__(self, parent)

        self.text_edit = QTextEdit()
        self.toolbar = QToolBar()

        self.action_debugging = self.toolbar.addAction("debug", self.on_debug)
        self.action_debugging.setCheckable(True)
        self.action_run = self.toolbar.addAction("run (Ctrl+R)", self.on_run)
        self.action_run.setShortcut("Ctrl+R")
        #self.action_stop = self.toolbar.addAction("stop (Shift+F5)", self.on_stop)
        #self.action_stop.setShortcut("Shift+F5")
        self.action_bp = self.toolbar.addAction("breakpoint (F9)", self.on_toggle_breakpoint)
        self.action_bp.setShortcut("F9")
        self.action_step = self.toolbar.addAction("step (F10)", self.on_step)
        self.action_step.setShortcut("F10")
        self.action_continue = self.toolbar.addAction("continue (F5)", self.on_continue)
        self.action_continue.setShortcut("F5")

        self.vars_view = VariablesView()
        self.frames_view = FramesView()
        self.label_status = QLabel()

        layout = QVBoxLayout()
        layout.addWidget(self.toolbar)
        layout.addWidget(self.text_edit)
        layout.addWidget(self.vars_view)
        layout.addWidget(self.frames_view)
        layout.addWidget(self.label_status)
        self.setLayout(layout)

        self.resize(800,800)

        file_content = open(input_filename).read()
        self.text_edit.setPlainText(file_content)
        self.text_edit.setFont(QFont("Courier"))
        # self.text_edit.setReadOnly(True)  # does not show cursor :(

        self.text_edit.cursorPositionChanged.connect(self.on_pos_changed)
        self.on_pos_changed()

        self.breakpoints = []
        self.debugger = Debugger(self)

        self.update_buttons()

    def on_pos_changed(self):
        c = self.text_edit.textCursor()
        line = c.blockNumber() + 1
        col = c.positionInBlock() + 1
        self.label_status.setText("%d:%d" % (line, col))

    def on_run(self):
        globals = None
        locals = None
        if globals is None:
            import __main__
            globals = __main__.__dict__
        if locals is None:
            locals = globals
        execfile(input_filename, globals, locals)

    def on_toggle_breakpoint(self):
        line_no = self.text_edit.textCursor().blockNumber()
        if line_no in self.breakpoints:
            self.breakpoints.remove(line_no)
        else:
            self.breakpoints.append(line_no)
        self.update_highlight()

    def update_buttons(self):
        active = self.debugger.active
        #self.action_run.setEnabled(active)
        #self.action_stop.setEnabled(active)
        self.action_step.setEnabled(active)
        self.action_continue.setEnabled(active)

    def update_highlight(self):

        def _highlight(line_no, color):
            block = self.text_edit.document().findBlockByLineNumber(line_no)
            highlight = QTextEdit.ExtraSelection()
            highlight.cursor = QTextCursor(block)
            highlight.format.setProperty(QTextFormat.FullWidthSelection, True)
            highlight.format.setBackground(color)
            return highlight

        sel = []

        # breakpoints
        for bp_line_no in self.breakpoints:
            sel.append(_highlight(bp_line_no, QColor(255,180,180)))

        # debug line
        if self.debugger.lineno != -1:
            sel.append(_highlight(self.debugger.lineno-1, QColor(180,255,255)))
            # also scroll to the line
            block = self.text_edit.document().findBlockByLineNumber(self.debugger.lineno-1)
            self.text_edit.setTextCursor(QTextCursor(block))
            self.text_edit.ensureCursorVisible()

        self.text_edit.setExtraSelections(sel)


    """
    def on_stop(self):
        self.dbg.set_quit()
        self.dbg.e.exit(0)
    """

    def on_step(self):
        self.debugger.stepping = True
        self.debugger.ev_loop.exit(0)

    def on_continue(self):
        self.debugger.stepping = False
        self.debugger.lineno = -1
        self.update_highlight()
        self.vars_view.setVariables({})
        self.frames_view.setTraceback(None)
        self.debugger.ev_loop.exit(0)

    def on_debug(self):
        self.debugger.active  =self.action_debugging.isChecked()
        if self.debugger.active:
            sys.settrace(self.debugger.trace_function)
        else:
            sys.settrace(None)
        self.update_buttons()


if __name__ == '__main__':
    a = QApplication(sys.argv)
    w = DebuggerWidget(sys.exc_info())
    w.show()
    a.exec_()
