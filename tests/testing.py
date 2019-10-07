import numpy as np

from typing import List, Union


def rand_data(names: Union[str, List[str]]) -> np.ndarray:
    names = names if isinstance(names, list) else [names]
    dtype = [(name, float) for name in names]
    data = np.empty((10, 10), dtype=dtype)
    for name in names:
        data[name] = np.random.random((10, 10))
    return data
