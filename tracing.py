import os
import json

from qgis.core import QgsProject, QgsVectorFileWriter, QgsVectorLayer
from PyQt5.QtCore import QVariant


class Trace:
    def __init__(self, tracing_out_dir: str, session_name: str, pretty: bool = False):
        self.session_name = session_name
        self.tracing_dir = tracing_out_dir

        self.out_dir = f"{tracing_out_dir}/{session_name}"
        self.pretty = pretty
        self.count = 1

        os.makedirs(self.out_dir, exist_ok=True)
        for fname in os.listdir(self.out_dir):
            os.remove(f"{self.out_dir}/{fname}")

    def add_layer(self, layer: QgsVectorLayer, tag: str | None = None):
        fname = write_layer(self.out_dir, self._next_name(tag), layer)
        if self.pretty:
            _make_pretty(fname)

    def add_dict(self, d: dict, tag: str | None = None):
        write_dict(self.out_dir, self._next_name(tag), d, self.pretty)

    def _next_name(self, tag: str | None = None) -> str:
        count_part = f'{self.count:0>2d}'
        if tag:
            name = f"{count_part}_{tag}"
        else:
            name = count_part
        self.count = self.count + 1
        return name


def write_dict(
    out_dir: str, trace_item_name: str, d: dict, pretty: bool = False
) -> str:
    fname = f"{out_dir}/{trace_item_name}.json"
    indent = 2 if pretty else None
    d = _fix_value(d)
    with open(fname, "w") as f:
        json.dump(d, f, indent=indent)
    return fname


def _fix_value(v):
    if isinstance(v, dict):
        return _fix_dict(v)
    elif isinstance(v, list):
        return _fix_list(v)
    else:
        return _fix_null(v)


def _fix_dict(d: dict) -> dict:
    return {(_fix_null(k)): _fix_value(v) for (k, v) in d.items()}


def _fix_list(d: list) -> list:
    return [_fix_value(v) for v in d]


def _fix_null(k):
    if isinstance(k, QVariant) and k.isNull():
        return None
    else:
        return k


def write_layer(out_dir: str, trace_item_name: str, layer: QgsVectorLayer) -> str:
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GeoJSON"
    options.fileEncoding = "utf8"
    transform_context = QgsProject.instance().transformContext()

    fname = f"{out_dir}/{trace_item_name}"
    error = QgsVectorFileWriter.writeAsVectorFormatV3(
        layer, fname, transform_context, options
    )

    if error[0] != QgsVectorFileWriter.NoError:
        raise Exception(f"{_error_string(error[0])}: {error[1]}")
    return f"{fname}.geojson"


def _make_pretty(fname: str):
    with open(fname, "r") as f:
        content = json.load(f)
    with open(fname, "w") as f:
        json.dump(content, f, indent=2)


# Stubs don't seem to allow to complete QgsVectorFileWriter.NoError
def _error_string(e: int) -> str:
    error_map = {
        QgsVectorFileWriter.NoError: "NoError",
        QgsVectorFileWriter.ErrAttributeCreationFailed: "ErrAttributeCreationFailed",
        QgsVectorFileWriter.ErrAttributeTypeUnsupported: "ErrAttributeTypeUnsupported",
        QgsVectorFileWriter.ErrCreateDataSource: "ErrCreateDataSource",
        QgsVectorFileWriter.ErrCreateLayer: "ErrCreateLayer",
        QgsVectorFileWriter.ErrDriverNotFound: "ErrDriverNotFound",
        QgsVectorFileWriter.ErrFeatureWriteFailed: "ErrFeatureWriteFailed",
        QgsVectorFileWriter.ErrInvalidLayer: "ErrInvalidLayer",
        QgsVectorFileWriter.ErrProjection: "ErrProjection",
        QgsVectorFileWriter.ErrSavingMetadata: "ErrSavingMetadata",
    }
    return error_map[e] or f"Unknow error code: {e}"
