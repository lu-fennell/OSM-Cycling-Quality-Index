from os.path import exists
import time
import typing

from cqi.util import unwrap
from qgis.core import NULL, QgsFeatureIterator, edit  # type: ignore[attr-defined]
from qgis.core import (
    QgsVectorFileWriter,
    QgsProject,
    QgsVectorLayer,
    QgsCoordinateReferenceSystem,
    QgsField,
)
from PyQt5.QtCore import QVariant
import qgis.processing as processing
from cqi.featuredb import FeatureDb, FeatureSet, TagType



class QgsFeatureIterable:
    def __init__(self, iter: QgsFeatureIterator):
        self.iter = unwrap(iter.__iter__())

    def __iter__(self):
        return self.iter

# TODO: document
def iter_features(layer: QgsVectorLayer) -> QgsFeatureIterable:
    return QgsFeatureIterable(layer.getFeatures())

class QgsFeatureDb(FeatureDb):
    def __init__(self, project: QgsProject):
        self.project: QgsProject = project
        self._added_layers: set[str] = set()

    # TODO: why are we not using attribute_list?
    def import_geojson(self, file: str, attributes_list: typing.Optional[list[str]] = None) -> "QgsFeatureSet":
        if not exists(file):
            msg = f'{time.strftime("%H:%M:%S", time.localtime())} [!] Error: No valid input file at {file}"'
            raise FileNotFoundError(msg)
        else:
            layer_id = self._add_layer(
                QgsVectorLayer(file + "|geometrytype=LineString", "way input", "ogr")
            )

            return QgsFeatureSet(self, layer_id)

    def import_layer(self, layer:QgsVectorLayer) -> "QgsFeatureSet":
        layer_id = self._add_layer(layer)
        return QgsFeatureSet(self, layer_id)
        

    def close(self):
        self.project.removeMapLayers(self._added_layers)

    def _add_layer(self, layer: QgsVectorLayer) -> str:
        self.project.addMapLayer(layer, addToLegend=False)
        self._added_layers.add(layer.id())
        return layer.id()

    def _remove_layer(self, layer_id: str):
        self.project.removeMapLayer(layer_id)
        self._added_layers.remove(layer_id)

    def _replace_layer(self, old_layer_id: str, new_layer: QgsVectorLayer) -> str:
        new_id = self._add_layer(new_layer)
        self._remove_layer(old_layer_id)
        return new_id


class QgsFeatureSet(FeatureSet):
    def __init__(self, db: QgsFeatureDb, layer_id: str):
        self.db = db
        self._layer_id = layer_id

    # TODO: really the right approach?
    def write(self, out_dir: str, trace_item_name: str):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GeoJSON"
        options.fileEncoding = "utf8"
        transform_context = self.db.project.transformContext()
        layer = self.to_layer()

        fname = f"{out_dir}/{trace_item_name}"
        error = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, fname, transform_context, options
        )

        if error[0] != QgsVectorFileWriter.NoError: # type: ignore
            raise Exception(f"{_error_string(error[0])}: {error[1]}")
        return f"{fname}.geojson"

    def reproject(self, metric):
        self._process(
            "native:reprojectlayer",
            {
                "INPUT": self._layer_id,
                "TARGET_CRS": QgsCoordinateReferenceSystem(metric),
            },
        )

    def add_tag_specs(self, tag_specs: dict[str, TagType]):
        layer = self.to_layer()
        fields = [QgsField(attr, _qvariant_type(ty)) for attr, ty in tag_specs.items() if layer.fields().indexOf(attr) == -1]
        with edit(layer):
            unwrap(layer.dataProvider()).addAttributes(fields)
            layer.updateFields()

    def retaintags(self, tags: set[str]):
        self._process(
            "native:retainfields", {"INPUT": self._layer_id, "FIELDS": list(tags)}
        )

    def _process(self, alg_name, opts):
        opts = opts.copy()
        opts["INPUT"] = self._layer_id
        new_layer = _process_to_mem_layer(alg_name, opts)
        self._set(new_layer)

    def _set(self, layer: QgsVectorLayer):
        self._layer_id = self.db._replace_layer(self._layer_id, layer)

    #########################
    # implementation specific
    #########################
    def to_layer(self) -> QgsVectorLayer:
        return typing.cast(QgsVectorLayer, self.db.project.mapLayer(self._layer_id))

    def copy_to_layer(self) -> QgsVectorLayer:
        return self._copy_to_mem_layer()

    def copy(self) -> 'QgsFeatureSet':
        new_layer = self.copy_to_layer()
        return QgsFeatureSet(self.db, self.db._add_layer(new_layer))

    

    # TODO: needed?
    def _copy_to_mem_layer(self) -> QgsVectorLayer:
        return _process_to_mem_layer(
            "qgis:extractbyexpression",
            {"INPUT": self._layer_id, "EXPRESSION": "TRUE"},
        )


def _error_string(e: int) -> str:
    error_map = {
        QgsVectorFileWriter.NoError: "NoError", # type: ignore
        QgsVectorFileWriter.ErrAttributeCreationFailed: "ErrAttributeCreationFailed", # type: ignore
        QgsVectorFileWriter.ErrAttributeTypeUnsupported: "ErrAttributeTypeUnsupported", # type: ignore
        QgsVectorFileWriter.ErrCreateDataSource: "ErrCreateDataSource", # type: ignore
        QgsVectorFileWriter.ErrCreateLayer: "ErrCreateLayer", # type: ignore
        QgsVectorFileWriter.ErrDriverNotFound: "ErrDriverNotFound", # type: ignore
        QgsVectorFileWriter.ErrFeatureWriteFailed: "ErrFeatureWriteFailed", # type: ignore
        QgsVectorFileWriter.ErrInvalidLayer: "ErrInvalidLayer", # type: ignore
        QgsVectorFileWriter.ErrProjection: "ErrProjection", # type: ignore
        QgsVectorFileWriter.ErrSavingMetadata: "ErrSavingMetadata", # type: ignore
    }
    return error_map[e] or f"Unknow error code: {e}"


def _process_to_mem_layer(name: str, opts: dict) -> QgsVectorLayer:
    opts = opts.copy()
    opts["OUTPUT"] = "memory:"
    return unwrap(processing.run(name, opts))["OUTPUT"]

def _qvariant_type(ty: TagType) -> QVariant.Type:
    # TODO: somehow in QGIS modules are loaded twice.. and we cannot match on ty because there are two TagType classes :(
    match str(ty):
        case 'TagType.INT':
            return QVariant.Int
        case 'TagType.DOUBLE':
            return QVariant.Double
        case 'TagType.STRING':
            return QVariant.String
        case _:
            raise ValueError(f'Unexpected: TagType not recognised: {ty}')
