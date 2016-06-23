
from PyQt4.QtCore import *

from variablesview import custom_class_handlers, make_item


def handle_QModelIndex(value, parent):
    make_item('valid', value.isValid(), parent)
    if value.isValid():
        make_item('row', value.row(), parent)
        make_item('column', value.column(), parent)
        make_item('parent', value.parent(), parent)


custom_class_handlers[QModelIndex] = handle_QModelIndex
