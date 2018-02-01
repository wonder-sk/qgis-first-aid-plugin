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

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *

import os
import traceback

from qgis.PyQt.QtWidgets import QTreeView


class FramesModel(QAbstractListModel):

    def __init__(self, tb, parent=None):
        QAbstractListModel.__init__(self, parent)
        if isinstance(tb, list):
            self.tb = None
            self.entries = tb
        else:
            self.tb = tb
            self.entries = traceback.extract_tb(tb)

    def rowCount(self, parent):
        return len(self.entries)

    def data(self, index, role):
        if not index.isValid():
            return

        if role == Qt.DisplayRole:
            entry = self.entries[index.row()]
            return "%s [%s:%d]" % (entry[2], os.path.basename(entry[0]), entry[1])
        elif role == Qt.ToolTipRole:
            entry = self.entries[index.row()]
            return "<b>Method:</b> %s\n<br>\n<b>Line:</b> %d\n<br><br>\n<b>Path:</b><br>\n%s" % (entry[2], entry[1], entry[0])

    def headerData(self, section, orientation, role):
        if section == 0 and orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return "Traceback (most recent call last)" #"Frames"


class FramesView(QTreeView):
    def __init__(self, parent=None):
        QTreeView.__init__(self, parent)
        self.setRootIsDecorated(False)

    def setTraceback(self, tb):
        self.setModel(FramesModel(tb, self))
