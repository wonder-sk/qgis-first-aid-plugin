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
# - keep list of breakpoints between sessions
# - list of breakpoints in dock
# - open file when stepping into it
# - handle stepping out of traced file (exit event loop)

import sip
sip.setapi('QVariant', 2)
sip.setapi('QString', 2)

from PyQt4.QtCore import *
from PyQt4.QtGui import *
import os
import sys
import bdb
import traceback

from variablesview import VariablesView
from framesview import FramesView


def format_frame(frame):
    return "<FRAME %s:%d :: %s>" % (frame.f_code.co_filename, frame.f_lineno, frame.f_code.co_name)

def format_frames(frame):
    if frame.f_back is not None:
        ret = format_frames(frame.f_back) + "\n"
    else:
        ret = ""
    ret += format_frame(frame)
    return ret

def _is_deeper_frame(f0_filename, f0_lineno, f1):
    """whether f1 has been called from f0_filename:f0_lineno (directly or indirectly)"""
    while f1 is not None:
        if f1.f_code.co_filename == f0_filename and f1.f_lineno == f0_lineno:
            return True
        f1 = f1.f_back
    return False

class Debugger(object):

    def __init__(self, main_widget):

        self.active = False
        self.ev_loop = QEventLoop()
        self.main_widget = main_widget
        self.stepping = False
        self.next_step = None  # None = stop always, ('over', file, line), ('at', file, line)
        self.current_frame = None

    def trace_function(self, frame, event, arg):
        """ to be used for sys.trace """
        if event == 'call':   # arg is always None
            # we need to return tracing function for this frame - either None or this function...

            if frame.f_code.co_filename not in self.main_widget.text_edits:
                # only trace the loaded files
                return None
            return self.trace_function

        elif event == 'line':  # arg is always None
            print "++ line", format_frame(frame)

            text_edit = self.main_widget.text_edits[frame.f_code.co_filename]
            if self.stepping or frame.f_lineno-1 in text_edit.breakpoints:
                if isinstance(self.next_step, tuple):
                    if self.next_step[0] == 'over':
                        prev_filename = self.next_step[1]
                        prev_lineno = self.next_step[2]
                        if _is_deeper_frame(prev_filename, prev_lineno, frame):
                            return  # in a function deeper inside or the same line
                    elif self.next_step[0] == 'at':
                        if frame.f_code.co_filename != self.next_step[1] or frame.f_lineno != self.next_step[2]:
                            return  # only stop at the particular line of code
                self.current_frame = frame
                self.main_widget.vars_view.setVariables(frame.f_locals)
                self.main_widget.frames_view.setTraceback(traceback.extract_stack(frame))
                self.main_widget.tab_widget.setCurrentWidget(text_edit)
                text_edit.debug_line = frame.f_lineno
                text_edit.update_highlight()
                self.main_widget.raise_()
                self.main_widget.activateWindow()
                self.ev_loop.exec_()

        elif event == 'return':  # arg is return value
            pass
            #print "++ return", arg

        else:
            print "trace", format_frames(frame), " | ", event, arg


class SourceWidget(QTextEdit):
    def __init__(self, filename, parent=None):
        QTextEdit.__init__(self, parent)

        file_content = open(filename).read()
        self.setPlainText(file_content)
        self.setFont(QFont("Courier"))
        # self.setReadOnly(True)  # does not show cursor :(

        self.filename = filename
        self.breakpoints = []
        self.debug_line = -1

    def toggle_breakpoint(self):
        line_no = self.textCursor().blockNumber()
        if line_no in self.breakpoints:
            self.breakpoints.remove(line_no)
        else:
            self.breakpoints.append(line_no)
        self.update_highlight()

    def update_highlight(self):

        def _highlight(line_no, color):
            block = self.document().findBlockByLineNumber(line_no)
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
        if self.debug_line != -1:
            sel.append(_highlight(self.debug_line-1, QColor(180,255,255)))
            # also scroll to the line
            block = self.document().findBlockByLineNumber(self.debug_line-1)
            self.setTextCursor(QTextCursor(block))
            self.ensureCursorVisible()

        self.setExtraSelections(sel)


class DebuggerWidget(QMainWindow):
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)

        self.setWindowTitle("First Aid - Debugger")

        self.text_edits = {}
        self.toolbar = self.addToolBar("General")
        self.toolbar.setObjectName("ToolbarGeneral")

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.on_tab_close_requested)
        self.tab_widget.currentChanged.connect(self.on_pos_changed)

        self.setCentralWidget(self.tab_widget)

        self.action_load = self.toolbar.addAction(self.style().standardIcon(QStyle.SP_DirOpenIcon), "load", self.on_load)
        self.action_debugging = self.toolbar.addAction("debug", self.on_debug)
        self.action_debugging.setCheckable(True)
        self.action_run = self.toolbar.addAction("run script (Ctrl+R)", self.on_run)
        self.action_run.setShortcut("Ctrl+R")
        self.action_bp = self.toolbar.addAction("breakpoint (F9)", self.on_toggle_breakpoint)
        self.action_bp.setShortcut("F9")
        self.action_step_into = self.toolbar.addAction("step into (F11)", self.on_step_into)
        self.action_step_into.setShortcut("F11")
        self.action_step_over = self.toolbar.addAction("step over (F10)", self.on_step_over)
        self.action_step_over.setShortcut("F10")
        self.action_run_to_cursor = self.toolbar.addAction("run to cursor (Ctrl+F10)", self.on_run_to_cursor)
        self.action_run_to_cursor.setShortcut("Ctrl+F10")
        self.action_continue = self.toolbar.addAction("continue (F5)", self.on_continue)
        self.action_continue.setShortcut("F5")

        self.vars_view = VariablesView()
        self.frames_view = FramesView()

        self.dock_frames = QDockWidget("Frames", self)
        self.dock_frames.setObjectName("DockFrames")
        self.dock_frames.setWidget(self.frames_view)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_frames)

        self.dock_vars = QDockWidget("Variables", self)
        self.dock_vars.setObjectName("DockVariables")
        self.dock_vars.setWidget(self.vars_view)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_vars)

        self.resize(800,800)

        self.debugger = Debugger(self)

        self.update_buttons()

        settings = QSettings()
        self.restoreGeometry(settings.value("/plugins/firstaid/debugger-geometry", ''))
        self.restoreState(settings.value("/plugins/firstaid/debugger-windowstate", ''))

        # load files from previous session
        for filename in settings.value("/plugins/firstaid/debugger-files", []):
            self.load_file(filename)

    def closeEvent(self, event):
        settings = QSettings()
        settings.setValue("/plugins/firstaid/debugger-geometry", self.saveGeometry())
        settings.setValue("/plugins/firstaid/debugger-windowstate", self.saveState())

        filenames = self.text_edits.keys()
        settings.setValue("/plugins/firstaid/debugger-files", filenames)

        QMainWindow.closeEvent(self, event)


    def load_file(self, filename):
        if filename in self.text_edits:
            return   # already there...
        try:
            self.text_edits[filename] = SourceWidget(filename)
        except IOError:
            # TODO: display warning we failed to read the file
            return
        tab_text = os.path.basename(filename)
        self.tab_widget.addTab(self.text_edits[filename], tab_text)
        self.tab_widget.setCurrentWidget(self.text_edits[filename])
        self.text_edits[filename].cursorPositionChanged.connect(self.on_pos_changed)
        self.on_pos_changed()

    def switch_to_file(self, filename):
        if filename in self.text_edits:
            self.tab_widget.setCurrentWidget(self.text_edits[filename])

    def unload_file(self, filename):
        for index in xrange(self.tab_widget.count()):
            if self.text_edits[filename] == self.tab_widget.widget(index):
                self.tab_widget.removeTab(index)
                del self.text_edits[filename]
                break

    def on_load(self):
        filename = QFileDialog.getOpenFileName(self, "Load")
        if filename == '':
            return

        self.load_file(filename)

    def on_tab_close_requested(self):
        self.unload_file(self.tab_widget.currentWidget().filename)

    def on_pos_changed(self):
        if not self.current_text_edit():
            self.statusBar().showMessage("[no file]")
        c = self.current_text_edit().textCursor()
        line = c.blockNumber() + 1
        col = c.positionInBlock() + 1
        self.statusBar().showMessage("%d:%d" % (line, col))

    def on_run(self):
        globals = None
        locals = None
        if globals is None:
            import __main__
            globals = __main__.__dict__
        if locals is None:
            locals = globals
        execfile(self.tab_widget.currentWidget().filename, globals, locals)

    def current_text_edit(self):
        return self.tab_widget.currentWidget()

    def on_toggle_breakpoint(self):
        if self.current_text_edit():
            self.current_text_edit().toggle_breakpoint()

    def update_buttons(self):
        active = self.debugger.active
        #self.action_run.setEnabled(active)
        self.action_step_into.setEnabled(active)
        self.action_step_over.setEnabled(active)
        self.action_run_to_cursor.setEnabled(active)
        self.action_continue.setEnabled(active)


    def on_step_into(self):
        self.debugger.stepping = True
        self.debugger.next_step = None
        self.debugger.ev_loop.exit(0)

    def on_step_over(self):
        self.debugger.stepping = True
        self.debugger.next_step = ('over', self.debugger.current_frame.f_code.co_filename, self.debugger.current_frame.f_lineno)
        self.debugger.ev_loop.exit(0)

    def on_run_to_cursor(self):
        self.debugger.stepping = True
        filename = self.tab_widget.currentWidget().filename
        line_no = self.tab_widget.currentWidget().textCursor().blockNumber() + 1
        self.debugger.next_step = ('at', filename, line_no)
        self.debugger.ev_loop.exit(0)

    def on_continue(self):
        self.debugger.stepping = False
        self.current_text_edit().debug_line = -1
        self.current_text_edit().update_highlight()
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
    w = DebuggerWidget()
    w.load_file('test_script.py')
    w.show()
    a.exec_()
