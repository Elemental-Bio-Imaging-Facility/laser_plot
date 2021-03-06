import numpy as np

from PySide2 import QtCore, QtWidgets

from pewlib.process import filters

from pewpew.graphics.lasergraphicsview import LaserGraphicsView
from pewpew.widgets.ext import ValidColorLineEdit
from pewpew.widgets.laser import LaserWidget
from pewpew.widgets.tools import ToolWidget

from pewpew.validators import ConditionalLimitValidator

from typing import Callable, List, Tuple


# Filters
def rolling_mean(x: np.ndarray, size: int, threshold: float) -> np.ndarray:
    size = int(size)
    return filters.rolling_mean(x, (size, size), threshold)


def rolling_median(x: np.ndarray, size: int, threshold: float) -> np.ndarray:
    size = int(size)
    return filters.rolling_median(x, (size, size), threshold)


# def simple_highpass(x: np.ndarray, limit: float, replace: float) -> np.ndarray:
#     return np.where(x < limit, replace, x)


# def simple_lowpass(x: np.ndarray, limit: float, replace: float) -> np.ndarray:
#     return np.where(x > limit, replace, x)


class FilteringTool(ToolWidget):
    methods: dict = {
        "Rolling Mean": {
            "filter": rolling_mean,
            "params": [
                ("size", 5, (2.5, 99), lambda x: (x + 1) % 2 == 0),
                ("σ", 3.0, (0.0, np.inf), None),
            ],
            "desc": ["Window size for local mean.", "Filter if > σ stddevs from mean."],
        },
        "Rolling Median": {
            "filter": rolling_median,
            "params": [
                ("size", 5, (2.5, 99), lambda x: (x + 1) % 2 == 0),
                ("M", 3.0, (0.0, np.inf), None),
            ],
            "desc": [
                "Window size for local median.",
                "Filter if > M medians from median.",
            ],
        },
        # "Simple High-pass": {
        #     "filter": simple_highpass,
        #     "params": [
        #         ("min", 1e3, (-np.inf, np.inf), None),
        #         ("replace", 0.0, (-np.inf, np.inf), None),
        #     ],
        #     "desc": ["Filter if below this value.", "Value to replace with."],
        # },
        # "Simple Low-pass": {
        #     "filter": simple_lowpass,
        #     "params": [
        #         ("max", 1e3, (-np.inf, np.inf), None),
        #         ("replace", 0.0, (-np.inf, np.inf), None),
        #     ],
        #     "desc": ["Filter if above this value.", "Value to replace with."],
        # },
    }

    def __init__(self, widget: LaserWidget):
        super().__init__(widget, graphics_label="Preview")

        self.graphics = LaserGraphicsView(self.viewspace.options, parent=self)
        # self.graphics.cursorClear.connect(self.widget.clearCursorStatus)
        # self.graphics.cursorMoved.connect(self.widget.updateCursorStatus)

        self.combo_isotope = QtWidgets.QComboBox()
        self.combo_isotope.activated.connect(self.completeChanged)
        self.combo_isotope.activated.connect(self.refresh)

        self.combo_filter = QtWidgets.QComboBox()
        self.combo_filter.addItems(FilteringTool.methods.keys())
        self.combo_filter.setCurrentText("Rolling Median")
        self.combo_filter.activated.connect(self.filterChanged)
        self.combo_filter.activated.connect(self.completeChanged)
        self.combo_filter.activated.connect(self.refresh)

        nparams = np.amax([len(f["params"]) for f in FilteringTool.methods.values()])
        self.label_fparams = [QtWidgets.QLabel() for i in range(nparams)]
        self.lineedit_fparams = [ValidColorLineEdit() for i in range(nparams)]
        for le in self.lineedit_fparams:
            le.textEdited.connect(self.completeChanged)
            le.editingFinished.connect(self.refresh)
            le.setValidator(ConditionalLimitValidator(0.0, 0.0, 4, condition=None))

        layout_graphics = QtWidgets.QVBoxLayout()
        layout_graphics.addWidget(self.graphics)
        layout_graphics.addWidget(self.combo_isotope, 0, QtCore.Qt.AlignRight)
        self.box_graphics.setLayout(layout_graphics)

        layout_controls = QtWidgets.QFormLayout()
        layout_controls.addWidget(self.combo_filter)
        for i in range(len(self.label_fparams)):
            layout_controls.addRow(self.label_fparams[i], self.lineedit_fparams[i])

        self.box_controls.setLayout(layout_controls)

        self.initialise()

    def apply(self) -> None:
        self.modified = True
        name = self.combo_isotope.currentText()
        self.widget.laser.data[name] = self.graphics.data

        self.initialise()

    @property
    def fparams(self) -> List[float]:
        return [float(le.text()) for le in self.lineedit_fparams if le.isEnabled()]

    def filterChanged(self) -> None:
        filter_ = FilteringTool.methods[self.combo_filter.currentText()]
        # Clear all the current params
        for le in self.label_fparams:
            le.setVisible(False)
        for le in self.lineedit_fparams:
            le.setVisible(False)

        params: List[Tuple[str, float, Tuple, Callable[[float], bool]]] = filter_[
            "params"
        ]

        for i, (symbol, default, range, condition) in enumerate(params):
            self.label_fparams[i].setText(f"{symbol}:")
            self.label_fparams[i].setVisible(True)
            self.lineedit_fparams[i].validator().setRange(range[0], range[1], 4)
            self.lineedit_fparams[i].validator().setCondition(condition)
            self.lineedit_fparams[i].setVisible(True)
            self.lineedit_fparams[i].setToolTip(filter_["desc"][i])
            # keep input that's still valid
            if not self.lineedit_fparams[i].hasAcceptableInput():
                self.lineedit_fparams[i].setText(str(default))
                self.lineedit_fparams[i].revalidate()

    def initialise(self) -> None:
        isotopes = self.widget.laser.isotopes
        self.combo_isotope.clear()
        self.combo_isotope.addItems(isotopes)

        self.filterChanged()
        self.refresh()

    def isComplete(self) -> bool:
        if not all(
            le.hasAcceptableInput() for le in self.lineedit_fparams if le.isEnabled()
        ):
            return False
        return True

    def previewData(self, data: np.ndarray) -> np.ndarray:
        filter_ = FilteringTool.methods[self.combo_filter.currentText()]["filter"]
        return filter_(data, *self.fparams)

    def refresh(self) -> None:
        if not self.isComplete():  # Not ready for update to preview
            return

        isotope = self.combo_isotope.currentText()

        data = self.previewData(
            self.widget.laser.get(isotope, flat=True, calibrated=False)
        )
        if data is None:
            return
        x0, x1, y0, y1 = self.widget.laser.config.data_extent(data.shape)
        rect = QtCore.QRectF(x0, y0, x1 - x0, y1 - y0)

        self.graphics.drawImage(data, rect, isotope)
        self.graphics.label.setText(isotope)

        self.graphics.setOverlayItemVisibility()
        self.graphics.updateForeground()
        self.graphics.invalidateScene()
