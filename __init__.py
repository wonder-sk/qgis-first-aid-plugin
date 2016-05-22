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

import os
from PyQt4.QtGui import *
from PyQt4.QtCore import *

import qgis.utils

from debugwidget import DebugWidget
from debuggerwidget import DebuggerWidget

import handlers_qgis   # for introspection of QGIS types

dw = None

def showException(etype, value, tb, msg, *args, **kwargs):
    global dw
    if dw is not None and dw.isVisible():
        return  # pass this exception while previous is being inspected
    dw = DebugWidget((etype,value,tb))
    dw.show()


def classFactory(iface):
    return FirstAidPlugin(iface)


class FirstAidPlugin:
    def __init__(self, iface):
        self.old_show_exception = None
        self.debugger_widget = None

    def initGui(self):
        # ReportPlugin also hooks exceptions and needs to be unloaded if active
        # so qgis.utils.showException is the QGIS native one
        report_plugin = "report"
        report_plugin_active = report_plugin in qgis.utils.active_plugins
        if report_plugin_active:
            qgis.utils.unloadPlugin(report_plugin)

        # hook to exception handling
        self.old_show_exception = qgis.utils.showException
        qgis.utils.showException = showException

        icon = QIcon(os.path.join(os.path.dirname(__file__), "icons", "bug.svg"))
        self.action_debugger = QAction(icon, "Debug", qgis.utils.iface.mainWindow())
        self.action_debugger.triggered.connect(self.run_debugger)
        qgis.utils.iface.addToolBarIcon(self.action_debugger)

        # If ReportPlugin was activated, load and start it again to cooperate
        if report_plugin_active:
            qgis.utils.loadPlugin(report_plugin)
            qgis.utils.startPlugin(report_plugin)

    def unload(self):

        qgis.utils.iface.removeToolBarIcon(self.action_debugger)
        del self.action_debugger

        # unhook from exception handling
        qgis.utils.showException = self.old_show_exception

    def run_debugger(self):
        if self.debugger_widget is None:
            self.debugger_widget = DebuggerWidget()
        self.debugger_widget.show()
