from typing import Optional, TypeVar


T = TypeVar('T')

def unwrap(v: Optional[T], v_description = 'value') -> T:
    if v is None:
        raise ValueError(f'{v_description} is None')
    else:
        return v


