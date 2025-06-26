from dataclasses import dataclass
from typing import Optional


@dataclass
class SidepathDictEntry:
    checks: int
    id: dict[str, int]
    highway: dict[str, int]
    name: dict[str, int]
    maxspeed: dict[str, int]

    @staticmethod
    def from_dict(d: dict) -> 'SidepathDictEntry':
       return SidepathDictEntry(
         checks = d.get('checks', 0),
         id = d.get('id', {}),
         highway= d.get('highway', {}),
         name=d.get('name', {}),
         maxspeed=d.get('maxspeed', {}),
        )

    def is_sidepath(self) -> bool:
        return (
            _is_sidepath(self.checks, self.id) or
            _is_sidepath(self.checks, self.highway) or
            _is_sidepath(self.checks, self.name)
        )
 
def _is_sidepath(checks: int, histogram: dict[str, int]) -> bool:
    def checks_threshold(count: int) -> bool:
        if checks <= 2:
            return checks == count
        else:
            return checks * 0.66 <= count
    return next((k for k, v in histogram.items() if checks_threshold(v)), None) is not None

        

@dataclass
class SidpathTags:
    is_sidpath: bool
    highway: Optional[str]
    is_sidepath_of: Optional[str]

def proc_is_sidepath(sidepath_tags: SidpathTags, sidepath_entry: SidepathDictEntry) -> bool:
    return False

