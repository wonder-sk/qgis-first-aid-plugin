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
from qgis.PyQt.QtWidgets import (
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QStyle,
    QTreeView,
    QApplication,
    QMenu,
    QAction
)

from qgis.PyQt.QtCore import (
    Qt,
    QAbstractItemModel,
    QModelIndex,
    pyqtSignal
)
from qgis.PyQt.QtGui import (
    QPen
)


Role_Name = Qt.ItemDataRole.UserRole+1
Role_Type = Qt.ItemDataRole.UserRole+2
Role_Value = Qt.ItemDataRole.UserRole+3
Role_Parent = Qt.ItemDataRole.UserRole+4

# database of handlers for custom classes to allow better introspection
# key = class, value = method with two arguments: 1. value, 2. parent item
# see handlers_qgis.py for how the handlers are implemented
custom_class_handlers = {}


class VariablesTreeItem:

    def __init__(self, name, value, parent=None):
        self.name = name
        self.value = value
        self.has_children = False
        self.populated_children = False

        self.parent = parent
        self.children = []
        if parent:
            parent.children.append(self)

    def val(self):
        return repr(self.value)

    def text(self):
        return "{} = {{{}}} {}".format(self.name, self.type_name(), self.val())

    def type_name(self):
        return type(self.value).__name__

    def populate_children(self):
        assert False  # not used in base class


class DictTreeItem(VariablesTreeItem):
    def __init__(self, name, value, parent=None):
        VariablesTreeItem.__init__(self, name, value, parent)

        self.has_children = len(value) > 0

        if parent is not None:
            ScalarTreeItem('__len__', len(value), self)

    def populate_children(self):
        self.populated_children = True
        all_strs = True
        for k, v in list(self.value.items()):
            if not isinstance(k, str):
                all_strs = False
            make_item(str(k), v, self)

        # sort items alphabetically
        if all_strs:
            self.children = sorted(self.children, key=lambda x: x.name)


class ListTreeItem(VariablesTreeItem):
    def __init__(self, name, value, parent=None):
        VariablesTreeItem.__init__(self, name, value, parent)

        self.has_children = len(value) > 0

        ScalarTreeItem('__len__', len(value), self)

    def populate_children(self):
        self.populated_children = True
        for i, v in enumerate(self.value):
            make_item(str(i), v, self)


class ObjectTreeItem(VariablesTreeItem):
    def __init__(self, name, value, parent=None):
        VariablesTreeItem.__init__(self, name, value, parent)

        self.custom_handler = None
        if hasattr(self.value, '__class__') and self.value.__class__ in custom_class_handlers:
            self.custom_handler = custom_class_handlers[self.value.__class__]

        self.has_children = len(value.__dict__) > 0 or self.custom_handler is not None

    def populate_children(self):
        self.populated_children = True
        for i, v in list(self.value.__dict__.items()):
            make_item(str(i), v, self)

        if self.custom_handler is not None:
            self.custom_handler(self.value, self)


class ScalarTreeItem(VariablesTreeItem):
    def __init__(self, name, value, parent):
        VariablesTreeItem.__init__(self, name, value, parent)


class StringTreeItem(VariablesTreeItem):
    def _is_internal(self):
        return len(self.value.split('\n')) > 0 and self.name == '__str__'

    def __init__(self, name, value, parent):
        VariablesTreeItem.__init__(self, name, value, parent)
        self.has_children = not self._is_internal()

    def val(self):
        if self._is_internal():
            return str(self.value)
        else:
            return VariablesTreeItem.val(self)

    def populate_children(self):
        self.populated_children = True
        make_item('__str__', self.value, self)


def make_item(name, value, parent=None):
    """ Generate VariablesTreeItem instance for the given variable """
    # print "MAKING", name, value
    if isinstance(value, dict):
        return DictTreeItem(name, value, parent)
    elif isinstance(value, list):
        return ListTreeItem(name, value, parent)
    elif hasattr(value, "__dict__"):
        return ObjectTreeItem(name, value, parent)
    elif isinstance(value, str):
        return StringTreeItem(name, value, parent)
    else:
        return ScalarTreeItem(name, value, parent)


class VariablesDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        # original command that would draw the whole thing with default style
        # style.drawControl(QStyle.CE_ItemViewItem, opt, painter)

        style = QApplication.instance().style()
        painter.save()
        painter.setClipRect(opt.rect)

        # background
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, opt, painter, None)

        text_margin = style.pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin, None, None) + 1
        text_rect = opt.rect.adjusted(text_margin, 0, -text_margin, 0)  # remove width padding

        # variable name
        painter.save()
        painter.setPen(QPen(Qt.GlobalColor.red))
        used_rect = painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft, index.data(Role_Name))
        painter.restore()

        # equals sign
        text_rect = text_rect.adjusted(used_rect.width(), 0, 0, 0)
        used_rect = painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft, " = ")

        # variable type
        text_rect = text_rect.adjusted(used_rect.width(), 0, 0, 0)
        painter.save()
        painter.setPen(QPen(Qt.GlobalColor.gray))
        used_rect = painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft, "{%s} " % index.data(Role_Type))
        painter.restore()

        # variable
        text_rect = text_rect.adjusted(used_rect.width(), 0, 0, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft, index.data(Role_Value))

        painter.restore()


class VariablesItemModel(QAbstractItemModel):
    def __init__(self, root_item, parent=None):
        QAbstractItemModel.__init__(self, parent)
        self.root_item = root_item

    def columnCount(self, parent):
        return 1

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        parent_item = self.root_item if not parent.isValid() else parent.internalPointer()
        if not parent_item.populated_children:  # lazy loading
            parent_item.populate_children()
        return len(parent_item.children)

    def hasChildren(self, index):
        if not index.isValid():
            return True
        return index.internalPointer().has_children

    def data(self, index, role):
        if not index.isValid():
            return

        item = index.internalPointer()
        if role == Qt.ItemDataRole.DisplayRole:
            return item.text()
        elif role == Role_Name:
            return item.name
        elif role == Role_Type:
            return item.type_name()
        elif role == Role_Parent:
            return item.parent
        elif role == Role_Value:
            return item.val()

        # return

    def flags(self, index):
        if not index.isValid():
            return 0
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_item = self.root_item if not parent.isValid() else parent.internalPointer()
        child_item = parent_item.children[row]
        return self.createIndex(row, column, child_item)

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        parent_item = index.internalPointer().parent
        if parent_item.parent is None:
            return QModelIndex()

        parent_index_in_grandparent = parent_item.parent.children.index(parent_item)
        return self.createIndex(parent_index_in_grandparent, 0, parent_item)

    def headerData(self, section, orientation, role):
        if section == 0 and orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return "Variables"


class VariablesView(QTreeView):
    object_picked = pyqtSignal(str)

    def __init__(self, parent=None):
        QTreeView.__init__(self, parent)
        self.setItemDelegate(VariablesDelegate(self))
        self.doubleClicked.connect(self.on_item_double_click)
        self.setExpandsOnDoubleClick(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._open_menu)

    def setVariables(self, variables):
        model = VariablesItemModel(DictTreeItem('', variables), self)
        self.setModel(model)

    def on_item_double_click(self, index):
        name = index.data(Role_Name)
        parent = index.data(Role_Parent)
        if parent.name:
            name = self.format_item_name_for_container_access(name, parent)
            self.object_picked.emit("{}{}".format(self.get_variable_parent_name(parent)[1:], name))
        else:
            self.object_picked.emit(name)

    def _open_menu(self, position):

        menu = QMenu()
        var_val_action = QAction("Copy Variable Value", menu)
        var_name_action = QAction("Copy Variable Name", menu)
        var_tree_action = QAction("Copy Variable Tree", menu)

        var_name_action.triggered.connect(self.copy_variable_name)
        var_val_action.triggered.connect(self.copy_variable_value)
        var_tree_action.triggered.connect(self.copy_variable_tree)

        menu.addAction(var_name_action)
        menu.addAction(var_val_action)
        menu.addAction(var_tree_action)

        menu.exec(self.viewport().mapToGlobal(position))

    def copy_variable_name(self):
        indexes = self.selectedIndexes()
        name = indexes[0].data(Role_Name)
        cb = QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText(name, mode=cb.Clipboard)

    def copy_variable_value(self):
        indexes = self.selectedIndexes()
        val = indexes[0].data(Role_Value)
        cb = QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText(val, mode=cb.Clipboard)

    def copy_variable_tree(self):
        indexes = self.selectedIndexes()
        val = indexes[0].data(Role_Name)
        parent = indexes[0].data(Role_Parent)
        if parent:
            val = ("{}.{}".format(self.get_variable_parent_name(parent)[1:], val))
        cb = QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText(val, mode=cb.Clipboard)

    def get_variable_parent_name(self, parent):
        if parent.parent is not None:
            parent_name = self.get_variable_parent_name(parent.parent)
            this_name = self.format_item_name_for_container_access(parent.name, parent.parent)
            return "{}{}".format(parent_name, this_name)

        else:
            return parent.name

    def format_item_name_for_container_access(self, name, parent):
        if isinstance(parent.value, list) or isinstance(parent.value, tuple):
            name = "[{}]".format(name)
        elif isinstance(parent.value, dict) and parent.parent is not None:
            name = "['{}']".format(name)
        else:
            name = ".{}".format(name)

        return name


if __name__ == '__main__':
    class TestClass:
        A1 = 123

        def __init__(self):
            self.x = 456


    def handle_TestClass(value, parent):
        make_item("handler test", 1234567890, parent)


    def long_string():
        return r"""
            SELECT
                *
            FROM
                mytable
            WHERE
                id = 1
            ORDER BY
                name"""


    custom_class_handlers[TestClass] = handle_TestClass

    import sys

    a = QApplication(sys.argv)

    tv = VariablesView()
    tv.setVariables({'a': 1, 'ax': [5, 6, 7], 'b': {'c': 3, 'd': 4}, 'tv': tv, 'e': TestClass(), 'ls': long_string()})
    tv.show()

    a.exec()
