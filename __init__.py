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

from PyQt4.QtGui import *
from PyQt4.QtCore import *

import qgis.utils

from debugwidget import DebugWidget

import handlers_qgis   # for introspection of QGIS types

dw = None

def showException(etype, value, tb, msg, *args, **kwargs):
    global dw
    dw = DebugWidget((etype,value,tb))
    dw.show()


def classFactory(iface):
    return FirstAidPlugin(iface)


class FirstAidPlugin:
    def __init__(self, iface):
        self.old_show_exception = None

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

        # If ReportPlugin was activated, load and start it again to cooperate
        if report_plugin_active:
            qgis.utils.loadPlugin(report_plugin)
            qgis.utils.startPlugin(report_plugin)

    def unload(self):

        # unhook from exception handling
        qgis.utils.showException = self.old_show_exception
