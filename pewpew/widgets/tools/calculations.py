import numpy as np

from PySide2 import QtCore, QtGui, QtWidgets

from pewpew.lib.pratt import Parser, ParserException
from pewpew.lib.viewoptions import ViewOptions

from pewpew.widgets.canvases import LaserCanvas
from pewpew.widgets.docks import LaserImageDock
from pewpew.widgets.tools import Tool

from typing import List, Union


class ValidColorLineEdit(QtWidgets.QLineEdit):
    def __init__(self, text: str, parent: QtWidgets.QWidget = None):
        super().__init__(text, parent)
        self.textChanged.connect(self.revalidate)
        self.color_good = self.palette().color(QtGui.QPalette.Base)
        self.color_bad = QtGui.QColor.fromRgb(255, 172, 172)

    def revalidate(self) -> bool:
        palette = self.palette()
        if self.hasAcceptableInput():
            color = self.color_good
        else:
            color = self.color_bad
        palette.setColor(QtGui.QPalette.Base, color)
        self.setPalette(palette)


class NameLineEdit(ValidColorLineEdit):
    def __init__(
        self, text: str, badnames: List[str], parent: QtWidgets.QWidget = None
    ):
        super().__init__(text, parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Minimum)
        self.badchars = " +-=*/\\^<>!()[]"
        self.badnames = badnames
        self._badnames = ["", "if", "then", "else"]

    def hasAcceptableInput(self) -> bool:
        if any(c in self.text() for c in self.badchars):
            return False
        if self.text() in self._badnames:
            return False
        if self.text() in self.badnames:
            return False
        return True


class FormulaLineEdit(ValidColorLineEdit):
    def __init__(self, text: str, variables: dict, parent: QtWidgets.QWidget = None):
        super().__init__(text, parent)
        self.setClearButtonEnabled(True)
        self.parser = Parser(variables)

        self.valid = True
        self.cgood = self.palette().color(QtGui.QPalette.Base)
        self.cbad = QtGui.QColor.fromRgb(255, 172, 172)

    def hasAcceptableInput(self) -> bool:
        return self.valid

    def value(self) -> Union[float, np.ndarray]:
        try:
            result = self.parser.reduceString(self.text())
            self.valid = True
            return result
        except ParserException:
            self.valid = False
            return None


class CalculationsTool(Tool):
    def __init__(
        self,
        dock: LaserImageDock,
        viewoptions: ViewOptions,
        parent: QtWidgets.QWidget = None,
    ):
        super().__init__(parent)
        self.dock = dock
        # Custom viewoptions
        self.viewoptions = ViewOptions()
        self.viewoptions.canvas.colorbar = False
        self.viewoptions.canvas.label = False
        self.viewoptions.canvas.scalebar = False
        self.viewoptions.image.cmap = viewoptions.image.cmap

        self.canvas = LaserCanvas(self.viewoptions)

        self.lineedit_name = NameLineEdit("", badnames=[])
        self.lineedit_name.textChanged.connect(self.completeChanged)

        self.combo_isotopes = QtWidgets.QComboBox()
        self.combo_isotopes.activated.connect(self.insertVariable)

        self.formula = FormulaLineEdit("", variables={})
        self.formula.textChanged.connect(self.updateCanvas)
        self.formula.textChanged.connect(self.completeChanged)

        layout_form = QtWidgets.QFormLayout()
        layout_form.addRow("Name:", self.lineedit_name)
        layout_form.addRow("Insert:", self.combo_isotopes)
        layout_form.addRow("Formula:", self.formula)

        self.layout_main.addWidget(self.canvas)
        self.layout_main.addLayout(layout_form)

        self.newDockAdded()

    def apply(self) -> None:
        self.dock.laser.add(
            self.lineedit_name.text(), np.array(self.canvas.image.get_array())
        )
        self.newDockAdded()

    def insertVariable(self, index: int) -> None:
        if index == 0:
            return
        self.formula.setText(
            self.formula.text() + " " + self.combo_isotopes.currentText()
        )
        self.combo_isotopes.setCurrentIndex(0)

    def isComplete(self) -> bool:
        if not self.formula.hasAcceptableInput():
            return False
        name = self.lineedit_name.text()
        if name == "" or " " in name or name in self.dock.laser.isotopes:
            return False
        return True

    def updateCanvas(self) -> None:
        result = self.formula.value()

        if result is None or isinstance(result, float):
            return
        # Remove all nan and inf values
        result = np.where(np.isfinite(result), result, 0.0)
        extent = self.dock.laser.config.data_extent(result)
        self.canvas.drawData(result, extent)
        self.canvas.draw()

    def newDockAdded(self) -> None:
        self.combo_isotopes.clear()
        self.combo_isotopes.addItem("Isotopes")
        self.combo_isotopes.addItems(self.dock.laser.isotopes)

        self.lineedit_name.badnames = self.dock.laser.isotopes

        self.formula.parser.variables = {
            k: v.data for k, v in self.dock.laser.data.items()
        }
        self.formula.valid = True
        self.formula.setText(self.dock.laser.isotopes[0])

        self.updateCanvas()

    @QtCore.Slot("QWidget*")
    def endMouseSelect(self, widget: QtWidgets.QWidget) -> None:
        if self.dock == widget:
            return
        self.dock = widget
        self.newDockAdded()
        super().endMouseSelect(widget)