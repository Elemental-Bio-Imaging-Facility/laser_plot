from pewpew.lib.laser.config import LaserConfig
from pewpew.lib.laser.data import LaserData

from typing import Callable, Tuple
import numpy as np


class VirtualData(LaserData):
    def __init__(
        self,
        data1: LaserData,
        name: str,
        op: Callable = None,
        data2: LaserData = None,
        condition1: Tuple[Callable, float] = None,
        condition2: Tuple[Callable, float] = None,
        fill_value: float = np.nan,
    ):
        self.data = np.empty((1, 1), dtype=float)
        self.name = name

        self.data1 = data1
        self.data2 = data2
        self.op = op
        self.condition1 = condition1
        self.condition2 = condition2
        self.fill_value = fill_value

        if self.op is not None and self.data2 is not None:
            self.gradient = self.op(self.data1.gradient, self.data2.gradient)
            self.intercept = self.op(self.data1.intercept, self.data2.intercept)
        else:
            self.gradient = self.data1.gradient
            self.intercept = self.data1.intercept
        self.unit = self.data1.unit

    def get(
        self,
        config: LaserConfig,
        calibrate: bool = False,
        extent: Tuple[float, float, float, float] = None,
    ) -> np.ndarray:
        d1 = self.data1.get(config, calibrate=calibrate, extent=extent)
        if self.condition1 is not None:
            mask = self.condition1[0](d1, self.condition1[1])
            d1 = np.full_like(d1, self.fill_value)[mask] = d1

        if self.op is not None and self.data2 is not None:
            d2 = self.data2.get(config, calibrate=calibrate, extent=extent)
            if self.condition2 is not None:
                mask = self.condition2[0](d2, self.condition2[1])
                d2 = np.full_like(d2, self.fill_value)[mask] = d2

            return self.op(d1, d2)

        return d1
