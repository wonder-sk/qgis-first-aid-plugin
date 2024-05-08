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
# TODO:
# - keep list of breakpoints between sessions
# - list of breakpoints in dock
# - handle stepping out of traced file (exit event loop)


import os
import sys
import traceback

from qgis.PyQt.QtCore import QEventLoop, QSize, Qt, QRect, QSettings
from qgis.PyQt.QtWidgets import (
    QWidget,
    QPlainTextEdit,
    QTextEdit,
    QMainWindow,
    QTabWidget,
    QDockWidget,
    QFileDialog,
    QApplication,
)
from qgis.PyQt.QtGui import (
    QFontDatabase,
    QPainter,
    QTextCursor,
    QTextFormat,
    QColor,
    QIcon,
)

from .variablesview import VariablesView
from .framesview import FramesView
from .highlighter import PythonHighlighter


def format_frame(frame):
    return "<FRAME %s:%d :: %s>" % (
        frame.f_code.co_filename,
        frame.f_lineno,
        frame.f_code.co_name,
    )


def format_frames(frame):
    if frame.f_back is not None:
        ret = format_frames(frame.f_back) + "\n"
    else:
        ret = ""
    ret += format_frame(frame)
    return ret


def frame_depth(frame):
    depth = 0
    while frame is not None:
        depth += 1
        frame = frame.f_back
    return depth


def _is_deeper_frame(f0_filename, f0_lineno, f1):
    """whether f1 has been called from f0_filename:f0_lineno (directly or indirectly)"""
    while f1 is not None:
        if f1.f_code.co_filename == f0_filename and f1.f_lineno == f0_lineno:
            return True
        f1 = f1.f_back
    return False


class Debugger:
    def __init__(self, main_widget):
        self.ev_loop = QEventLoop()
        self.main_widget = main_widget
        self.stepping = False
        self.next_step = (
            None  # None = stop always, ('over', file, line), ('at', file, line)
        )
        self.current_frame = None
        self.stopped = False

    def trace_function(self, frame, event, arg):
        """to be used for sys.trace"""
        if event == "call":  # arg is always None
            filename = os.path.normpath(os.path.realpath(frame.f_code.co_filename))

            # we need to return tracing function for this frame - either None or this function...

            if filename not in self.main_widget.text_edits:
                # ignore files from this directory (so we do not debug the debugger!)
                if os.path.dirname(filename) == os.path.dirname(
                    os.path.realpath(__file__)
                ):
                    return None  # do not trace this file
            return self.trace_function

        elif event == "line":  # arg is always None
            # print "++ line", format_frame(frame)
            filename = os.path.normpath(os.path.realpath(frame.f_code.co_filename))

            if filename in self.main_widget.text_edits:
                text_edit = self.main_widget.text_edits[filename]
                breakpoints = text_edit.breakpoints
            else:
                text_edit = None
                breakpoints = []

            if self.stepping or frame.f_lineno - 1 in breakpoints:
                if isinstance(self.next_step, tuple):
                    if self.next_step[0] == "over":
                        prev_filename = self.next_step[1]
                        prev_lineno = self.next_step[2]
                        if _is_deeper_frame(prev_filename, prev_lineno, frame):
                            return  # in a function deeper inside or the same line
                    elif self.next_step[0] == "at":
                        if (
                            filename != self.next_step[1]
                            or frame.f_lineno != self.next_step[2]
                        ):
                            return  # only stop at the particular line of code
                    elif self.next_step[0] == "out":
                        if frame_depth(frame) >= self.next_step[1]:
                            return  # only stop when in lower frame
                self.stopped = True
                self.current_frame = frame
                self.main_widget.vars_view.setVariables(frame.f_locals)
                self.main_widget.frames_view.setTraceback(
                    traceback.extract_stack(frame)
                )
                if text_edit is None:  # ensure it is loaded
                    self.main_widget.load_file(filename)
                    text_edit = self.main_widget.text_edits[filename]
                self.main_widget.tab_widget.setCurrentWidget(text_edit)
                text_edit.debug_line = frame.f_lineno
                text_edit.update_highlight()
                self.main_widget.update_buttons()
                self.main_widget.raise_()
                self.main_widget.activateWindow()
                self.ev_loop.exec()  # this will halt execution here for some time
                self.stopped = False
                self.main_widget.update_buttons()

        elif event == "return":  # arg is return value
            pass
            # print "++ return", arg

        else:
            pass
            # print "trace", format_frames(frame), " | ", event, arg


class LineNumberArea(QWidget):
    def __init__(self, editor):
        QWidget.__init__(self, editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.editor.lineNumberAreaPaintEvent(event)


class SourceWidget(QPlainTextEdit):
    def __init__(self, filename, parent=None):
        super().__init__(parent)

        with open(filename, encoding="utf-8") as f:
            file_content = f.read()
        self.setPlainText(file_content)

        # this should use the default monospaced font as set in the system
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.setFont(font)

        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.setReadOnly(True)
        self.setTextInteractionFlags(
            self.textInteractionFlags()
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )

        self.highlighter = PythonHighlighter(self.document())

        # line numbers support
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.updateLineNumberAreaWidth(0)

        self.filename = filename
        self.breakpoints = []
        self.debug_line = -1

    # support for line numbers - start

    def lineNumberAreaWidth(self):
        digits = 1
        max_digit = max(1, self.blockCount())
        while max_digit >= 10:
            max_digit /= 10
            digits += 1
        return self.fontMetrics().horizontalAdvance("9") * (digits + 2)

    def updateLineNumberAreaWidth(self, newBlockCount):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(
                0, rect.y(), self.lineNumberArea.width(), rect.height()
            )

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, e):
        QPlainTextEdit.resizeEvent(self, e)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(
            QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height())
        )

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), Qt.GlobalColor.white)
        painter.fillRect(
            QRect(
                event.rect().right() - 1, event.rect().top(), 1, event.rect().height()
            ),
            Qt.GlobalColor.lightGray,
        )
        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(Qt.GlobalColor.black)
                painter.drawText(
                    0,
                    int(top),
                    self.lineNumberArea.width()
                    - self.fontMetrics().horizontalAdvance("9"),
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    str(blockNumber + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1

    # support for line numbers - finish

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
            highlight.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            highlight.format.setBackground(color)
            return highlight

        sel = []

        # breakpoints
        for bp_line_no in self.breakpoints:
            sel.append(_highlight(bp_line_no, QColor(255, 180, 180)))

        # debug line
        if self.debug_line != -1:
            sel.append(_highlight(self.debug_line - 1, QColor(180, 255, 255)))
            # also scroll to the line
            block = self.document().findBlockByLineNumber(self.debug_line - 1)
            self.setTextCursor(QTextCursor(block))
            self.ensureCursorVisible()

        self.setExtraSelections(sel)


class DebuggerWidget(QMainWindow):
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)

        self.setWindowTitle("First Aid - Debugger")

        self.text_edits = {}  # fully expanded path of the file -> associated SourceWidget
        self.toolbar = self.addToolBar("General")
        self.toolbar.setObjectName("ToolbarGeneral")

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.on_tab_close_requested)
        self.tab_widget.currentChanged.connect(self.on_pos_changed)

        self.setCentralWidget(self.tab_widget)

        def _icon(x):
            return QIcon(os.path.join(os.path.dirname(__file__), "icons", x + ".svg"))

        self.action_load = self.toolbar.addAction(
            _icon("folder-outline"), "Load Python file (Ctrl+O)", self.on_load
        )
        self.action_load.setShortcut("Ctrl+O")
        self.action_run = self.toolbar.addAction(
            _icon("run"), "Run Python file (Ctrl+R)", self.on_run
        )
        self.action_run.setShortcut("Ctrl+R")
        self.action_bp = self.toolbar.addAction(
            _icon("record"), "Toggle breakpoint (F9)", self.on_toggle_breakpoint
        )
        self.action_bp.setShortcut("F9")
        self.toolbar.addSeparator()
        self.action_continue = self.toolbar.addAction(
            _icon("play"), "Continue (F5)", self.on_continue
        )
        self.action_continue.setShortcut("F5")
        self.action_step_into = self.toolbar.addAction(
            _icon("debug-step-into"), "Step into (F11)", self.on_step_into
        )
        self.action_step_into.setShortcut("F11")
        self.action_step_over = self.toolbar.addAction(
            _icon("debug-step-over"), "Step over (F10)", self.on_step_over
        )
        self.action_step_over.setShortcut("F10")
        self.action_step_out = self.toolbar.addAction(
            _icon("debug-step-out"), "Step out (Shift+F11)", self.on_step_out
        )
        self.action_step_out.setShortcut("Shift+F11")
        self.action_run_to_cursor = self.toolbar.addAction(
            _icon("cursor-default-outline"),
            "Run to cursor (Ctrl+F10)",
            self.on_run_to_cursor,
        )
        self.action_run_to_cursor.setShortcut("Ctrl+F10")

        self.vars_view = VariablesView()
        self.frames_view = FramesView()

        self.dock_frames = QDockWidget("Frames", self)
        self.dock_frames.setObjectName("DockFrames")
        self.dock_frames.setWidget(self.frames_view)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock_frames)

        self.dock_vars = QDockWidget("Variables", self)
        self.dock_vars.setObjectName("DockVariables")
        self.dock_vars.setWidget(self.vars_view)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock_vars)

        self.resize(800, 800)

        self.debugger = Debugger(self)

        self.update_buttons()

        settings = QSettings()
        self.restoreGeometry(settings.value("/plugins/firstaid/debugger-geometry", b""))
        self.restoreState(settings.value("/plugins/firstaid/debugger-windowstate", b""))

        filenames = settings.value("/plugins/firstaid/debugger-files", [])
        if filenames is None:
            filenames = []

        # load files from previous session
        for filename in filenames:
            self.load_file(filename)

        if self.tab_widget.count() > 1:
            self.tab_widget.setCurrentIndex(0)

        # start tracing
        self.start_tracing()

    def start_tracing(self):
        """called from constructor or when the debugger window is opened again"""
        sys.settrace(self.debugger.trace_function)

    def closeEvent(self, event):
        # disable tracing
        sys.settrace(None)

        settings = QSettings()
        settings.setValue("/plugins/firstaid/debugger-geometry", self.saveGeometry())
        settings.setValue("/plugins/firstaid/debugger-windowstate", self.saveState())

        filenames = list(self.text_edits.keys())
        settings.setValue("/plugins/firstaid/debugger-files", filenames)

        QMainWindow.closeEvent(self, event)

    def load_file(self, filename):
        filename = os.path.normpath(os.path.realpath(filename))

        if filename in self.text_edits:
            self.switch_to_file(filename)
            return  # already there...
        try:
            self.text_edits[filename] = SourceWidget(filename)
        except OSError:
            # TODO: display warning we failed to read the file
            return
        tab_text = os.path.basename(filename)
        self.tab_widget.addTab(self.text_edits[filename], tab_text)
        self.tab_widget.setTabToolTip(self.tab_widget.count() - 1, filename)
        self.tab_widget.setCurrentWidget(self.text_edits[filename])
        self.text_edits[filename].cursorPositionChanged.connect(self.on_pos_changed)
        self.on_pos_changed()

    def switch_to_file(self, filename):
        if filename in self.text_edits:
            self.tab_widget.setCurrentWidget(self.text_edits[filename])

    def unload_file(self, filename):
        for index in range(self.tab_widget.count()):
            if self.text_edits[filename] == self.tab_widget.widget(index):
                self.tab_widget.removeTab(index)
                del self.text_edits[filename]
                break

    def get_file_name(self, args):
        if isinstance(args, tuple):
            return args[0]
        elif isinstance(args, str):
            return args

        return ""

    def on_load(self):
        settings = QSettings()
        folder = settings.value("firstaid/lastFolder", "")

        args = QFileDialog.getOpenFileName(self, "Load", folder, "Python files (*.py)")
        filename = self.get_file_name(args)
        if not filename:
            return

        settings.setValue("firstaid/lastFolder", os.path.dirname(filename))
        self.load_file(filename)

    def on_tab_close_requested(self, index):
        self.unload_file(self.tab_widget.widget(index).filename)

    def on_pos_changed(self):
        if not self.current_text_edit():
            self.statusBar().showMessage("[no file]")
            return
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
        with open(self.tab_widget.currentWidget().filename, "r") as f:
            code = f.read()
            exec(code, globals, locals)

    def current_text_edit(self):
        return self.tab_widget.currentWidget()

    def on_toggle_breakpoint(self):
        if self.current_text_edit():
            self.current_text_edit().toggle_breakpoint()

    def update_buttons(self):
        active = self.debugger.stopped
        self.action_step_into.setEnabled(active)
        self.action_step_over.setEnabled(active)
        self.action_step_out.setEnabled(active)
        self.action_run_to_cursor.setEnabled(active)
        self.action_continue.setEnabled(active)

    def on_step_into(self):
        self.debugger.stepping = True
        self.debugger.next_step = None
        self.debugger.ev_loop.exit(0)

    def on_step_over(self):
        self.debugger.stepping = True
        self.debugger.next_step = (
            "over",
            self.debugger.current_frame.f_code.co_filename,
            self.debugger.current_frame.f_lineno,
        )
        self.debugger.ev_loop.exit(0)

    def on_step_out(self):
        self.debugger.stepping = True
        self.debugger.next_step = ("out", frame_depth(self.debugger.current_frame))
        self.debugger.ev_loop.exit(0)

    def on_run_to_cursor(self):
        self.debugger.stepping = True
        filename = self.tab_widget.currentWidget().filename
        line_no = self.tab_widget.currentWidget().textCursor().blockNumber() + 1
        self.debugger.next_step = ("at", filename, line_no)
        self.debugger.ev_loop.exit(0)

    def on_continue(self):
        self.debugger.stepping = False
        self.current_text_edit().debug_line = -1
        self.current_text_edit().update_highlight()
        self.vars_view.setVariables({})
        self.frames_view.setTraceback(None)
        self.debugger.ev_loop.exit(0)


if __name__ == "__main__":
    a = QApplication(sys.argv)
    w = DebuggerWidget()
    w.load_file("test_script.py")
    w.show()
    a.exec()
