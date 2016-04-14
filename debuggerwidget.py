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
import bdb
import traceback

from variablesview import VariablesView
from framesview import FramesView

input_filename = 'test_script.py'


class MyDbg(bdb.Bdb):

    def __init__(self, widget, skip=None):
        bdb.Bdb.__init__(self, skip)

        self.e = QEventLoop()
        self.widget = widget
        self.lineno = -1
        self.starting = False
        self.is_active = False

    def user_call(self, frame, argument_list):
        """This method is called from dispatch_call() when there is the possibility
        that a break might be necessary anywhere inside the called function."""
        print "call", frame, argument_list

    def user_line(self, frame):
        """This method is called from dispatch_line() when either stop_here()
        or break_here() yields True."""
        if self.starting:
            # initially keep running - do not stop with first line!
            self.starting = False
            self.set_continue()
            return
        #print "line", frame, frame.f_code.co_filename, frame.f_lineno
        self.lineno = frame.f_lineno
        self.widget.vars_view.setVariables(frame.f_locals)
        self.widget.frames_view.setTraceback(traceback.extract_stack(frame))
        self.widget.update_highlight()
        self.e.exec_()

    def user_return(self, frame, return_value):
        """This method is called from dispatch_return() when stop_here() yields True."""
        print "return", frame, return_value

    def user_exception(self, frame, exc_info):
        """This method is called from dispatch_exception() when stop_here() yields True."""
        print "exception", frame, exc_info

    def do_clear(self, arg):
        """Handle how a breakpoint must be removed when it is a temporary one."""
        # TODO: clear temporary breakpoint
        print "do_clear", arg

    def runfile(self, filename, globals=None, locals=None):

        # GUI update
        self.is_active = True
        self.starting = True
        self.widget.update_buttons()

        if globals is None:
            import __main__
            globals = __main__.__dict__
        if locals is None:
            locals = globals
        self.reset()
        sys.settrace(self.trace_dispatch)
        try:
            execfile(filename, globals, locals)
        except bdb.BdbQuit:
            pass
        finally:
            self.quitting = 1
            sys.settrace(None)

            # GUI cleanup
            self.is_active = False
            self.lineno = -1
            self.widget.update_highlight()
            self.widget.update_buttons()
            self.widget.vars_view.setVariables({})


class DebuggerWidget(QWidget):
    def __init__(self, exc_info, parent=None):
        QWidget.__init__(self, parent)

        self.text_edit = QTextEdit()
        self.toolbar = QToolBar()

        self.action_run = self.toolbar.addAction("run (F5)", self.on_run)
        self.action_run.setShortcut("F5")
        self.action_stop = self.toolbar.addAction("stop (Shift+F5)", self.on_stop)
        self.action_stop.setShortcut("Shift+F5")
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
        self.dbg = MyDbg(self)

        self.update_buttons()

    def on_pos_changed(self):
        c = self.text_edit.textCursor()
        line = c.blockNumber() + 1
        col = c.positionInBlock() + 1
        self.label_status.setText("%d:%d" % (line, col))

    def on_run(self):
        self.dbg.runfile(input_filename)

    def on_toggle_breakpoint(self):
        line_no = self.text_edit.textCursor().blockNumber()
        if line_no in self.breakpoints:
            self.breakpoints.remove(line_no)
            self.dbg.clear_break(input_filename, line_no+1)
        else:
            self.breakpoints.append(line_no)
            self.dbg.set_break(input_filename, line_no+1)
        self.update_highlight()

    def update_buttons(self):
        active = self.dbg.is_active
        self.action_run.setEnabled(not active)
        self.action_stop.setEnabled(active)
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
        if self.dbg.lineno != -1:
            sel.append(_highlight(self.dbg.lineno-1, QColor(180,255,255)))

        self.text_edit.setExtraSelections(sel)

    def on_stop(self):
        self.dbg.set_quit()
        self.dbg.e.exit(0)

    def on_step(self):
        self.dbg.set_step()
        self.dbg.e.exit(0)

    def on_continue(self):
        self.dbg.set_continue()
        self.dbg.e.exit(0)

if __name__ == '__main__':
    a = QApplication(sys.argv)
    w = DebuggerWidget(sys.exc_info())
    w.show()
    a.exec_()
