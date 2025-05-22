from abc import ABC,abstractmethod
from enum import Enum

class TagType(Enum):
    INT = 0
    DOUBLE = 1
    STRING = 2

    @staticmethod
    def parse(s: str) -> 'TagType':
        match s:
            case "Int":
                return TagType.INT
            case "Double":
                return TagType.DOUBLE
            case "String":
                return TagType.STRING
            case _:
                raise ValueError(f'Unknown TagType: "{s}"')


class FeatureSet(ABC):

    # TODO: TraceInfo as a type/parameter
    @abstractmethod
    def write(self, out_dir: str, trace_item_name: str):
        raise NotImplementedError

    ###########################
    # GIS ops
    ###########################
    @abstractmethod
    def reproject(self, metric: str):
        raise NotImplementedError

    @abstractmethod
    def retaintags(self, tags: set[str]):
        raise NotImplementedError

    @abstractmethod
    def add_tag_specs(self, tag_specs: dict[str, TagType]):
        raise NotImplementedError


# TODO: good type var name?
class FeatureDb(ABC):

    @abstractmethod
    def close(self):
        raise NotImplementedError

    @abstractmethod
    def import_geojson(self, file: str, attributes_list: list[str]) -> FeatureSet:
        raise NotImplementedError



