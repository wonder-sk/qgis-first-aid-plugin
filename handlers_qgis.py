
from qgis.core import *

from variablesview import custom_class_handlers, make_item


def handle_QgsCoordinateReferenceSystem(value, parent):
    make_item('authId', value.authid(), parent)
    make_item('proj4', value.toProj4(), parent)

def handle_QgsFeature(value, parent):
    make_item('id', value.id(), parent)
    make_item('geometry', value.geometry(), parent)
    make_item('attributes', value.attributes(), parent)

def handle_QgsField(value, parent):
    make_item('name', value.name(), parent)
    make_item('type', value.type(), parent)
    make_item('typeName', value.typeName(), parent)
    make_item('length', value.length(), parent)
    make_item('precision', value.precision(), parent)
    make_item('comment', value.comment(), parent)

def handle_QgsGeometry(value, parent):
    # TODO: improve
    make_item('wkb_type', value.wkbType(), parent)
    make_item('wkt', value.exportToWkt(), parent)

def handle_QgsMapLayer(value, parent):
    # TODO: improve
    make_item('id', value.id(), parent)
    make_item('name', value.name(), parent)
    make_item('extent', value.extent(), parent)
    make_item('crs', value.crs(), parent)

def handle_QgsPoint(value, parent):
    make_item('x', value.x(), parent)
    make_item('y', value.y(), parent)

def handle_QgsRectangle(value, parent):
    make_item('xMin', value.xMinimum(), parent)
    make_item('yMin', value.xMaximum(), parent)
    make_item('xMax', value.yMinimum(), parent)
    make_item('yMax', value.yMaximum(), parent)

def handle_QgsVectorLayer(value, parent):
    # TODO: improve
    handle_QgsMapLayer(value, parent)
    make_item('featureCount', value.pendingFeatureCount(), parent)
    make_item('fields', value.pendingFields().toList(), parent)

def handle_QgsPointLocator_Match(value, parent):
    make_item('type', value.type(), parent)
    make_item('distance', value.distance(), parent)
    make_item('point', value.point(), parent)
    make_item('layer', value.layer(), parent)
    make_item('featureId', value.featureId(), parent)
    make_item('vertexIndex', value.vertexIndex(), parent)


custom_class_handlers[QgsCoordinateReferenceSystem] = handle_QgsCoordinateReferenceSystem
custom_class_handlers[QgsFeature] = handle_QgsFeature
custom_class_handlers[QgsField] = handle_QgsField
custom_class_handlers[QgsGeometry] = handle_QgsGeometry
custom_class_handlers[QgsMapLayer] = handle_QgsMapLayer
custom_class_handlers[QgsPoint] = handle_QgsPoint
custom_class_handlers[QgsPointLocator.Match] = handle_QgsPointLocator_Match
custom_class_handlers[QgsRectangle] = handle_QgsRectangle
custom_class_handlers[QgsVectorLayer] = handle_QgsVectorLayer
