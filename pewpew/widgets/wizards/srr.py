import numpy as np
import numpy.lib.recfunctions as rfn
from pathlib import Path

from PySide2 import QtCore, QtGui, QtWidgets

from pewlib import io
from pewlib.config import Config
from pewlib.srr import SRRLaser, SRRConfig

from pewpew.validators import DecimalValidator

from pewpew.widgets.wizards.import_ import ConfigPage, FormatPage
from pewpew.widgets.wizards.options import PathAndOptionsPage

from typing import List, Tuple


class SRRImportWizard(QtWidgets.QWizard):
    page_format = 0
    page_agilent = 1
    page_numpy = 2
    page_text = 3
    page_thermo = 4
    page_config = 5

    laserImported = QtCore.Signal(SRRLaser)

    def __init__(
        self,
        paths: List[Path] = [],
        config: Config = None,
        parent: QtWidgets.QWidget = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("SRR Import Wizard")

        _config = SRRConfig()
        if config is not None:
            _config.spotsize = config.spotsize
            _config.speed = config.speed
            _config.scantime = config.scantime

        overview = (
            "The wizard will guide you through importing LA-ICP-MS data "
            "and provides a higher level to control than the standard import. "
            "To begin select the format of the file being imported."
        )

        format_page = FormatPage(
            overview,
            page_id_dict={
                "agilent": self.page_agilent,
                "numpy": self.page_numpy,
                "text": self.page_text,
                "thermo": self.page_thermo,
            },
            parent=self,
        )

        self.setPage(self.page_format, format_page)
        self.setPage(
            self.page_agilent,
            SRRPathAndOptionsPage(
                paths, "agilent", nextid=self.page_config, parent=self
            ),
        )
        self.setPage(
            self.page_numpy,
            SRRPathAndOptionsPage(paths, "numpy", nextid=self.page_config, parent=self),
        )
        self.setPage(
            self.page_text,
            SRRPathAndOptionsPage(paths, "text", nextid=self.page_config, parent=self),
        )
        self.setPage(
            self.page_thermo,
            SRRPathAndOptionsPage(
                paths, "thermo", nextid=self.page_config, parent=self
            ),
        )

        self.setPage(self.page_config, SRRConfigPage(_config, parent=self))

    def accept(self) -> None:
        calibration = None
        if self.field("agilent"):
            path = Path(self.field("agilent.paths")[0])
        elif self.field("numpy"):
            path = Path(self.field("numpy.paths")[0])
            if self.field("numpy.useCalibration"):  # pragma: no cover
                # Hack
                calibration = io.npz.load(path).calibration
        elif self.field("text"):
            path = Path(self.field("text.paths")[0])
        elif self.field("thermo"):
            path = Path(self.field("thermo.paths")[0])
        else:  # pragma: no cover
            raise ValueError("Invalid filetype selection.")

        data = self.field("laserdata")
        config = SRRConfig(
            spotsize=float(self.field("spotsize")),
            scantime=float(self.field("scantime")),
            speed=float(self.field("speed")),
            warmup=float(self.field("warmup")),
        )
        config.set_equal_subpixel_offsets(self.field("subpixelWidth"))
        self.laserImported.emit(
            SRRLaser(
                data,
                calibration=calibration,
                config=config,
                name=path.stem,
                path=path,
            )
        )
        super().accept()


class SRRConfigPage(ConfigPage):
    dataChanged = QtCore.Signal()

    def __init__(self, config: SRRConfig, parent: QtWidgets.QWidget = None):
        super().__init__(config, parent)
        self._srrdata: List[np.ndarray] = []

        # Krisskross params
        self.lineedit_warmup = QtWidgets.QLineEdit()
        self.lineedit_warmup.setText(str(config.warmup))
        self.lineedit_warmup.setValidator(DecimalValidator(0, 1e2, 2))
        self.lineedit_warmup.textEdited.connect(self.completeChanged)

        self.spinbox_offsets = QtWidgets.QSpinBox()
        self.spinbox_offsets.setRange(2, 10)
        self.spinbox_offsets.setValue(config._subpixel_size)
        self.spinbox_offsets.setToolTip(
            "The number of subpixels per pixel in each dimension."
        )

        params_box = QtWidgets.QGroupBox("SRR Parameters", self)
        params_layout = QtWidgets.QFormLayout()
        params_layout.addRow("Warmup (s):", self.lineedit_warmup)
        params_layout.addRow("Subpixel width:", self.spinbox_offsets)
        params_box.setLayout(params_layout)

        self.layout().addWidget(params_box)

        self.registerField("warmup", self.lineedit_warmup)
        self.registerField("subpixelWidth", self.spinbox_offsets)

    def getData(self) -> np.ndarray:
        return self._srrdata

    def setData(self, data: np.ndarray) -> None:
        self._srrdata = data
        self.dataChanged.emit()

    def initializePage(self) -> None:
        if self.field("agilent"):
            paths = [Path(p) for p in self.field("agilent.paths")]
            data, params = self.readSRRAgilent(paths)
        elif self.field("numpy"):
            paths = [Path(p) for p in self.field("numpy.paths")]
            data, params = self.readSRRNumpy(paths)
        elif self.field("text"):
            paths = [Path(p) for p in self.field("text.paths")]
            data, params = self.readSRRText(paths)
        elif self.field("thermo"):
            paths = [Path(p) for p in self.field("thermo.paths")]
            data, params = self.readSRRThermo(paths)

        if "scantime" in params:
            self.setField("scantime", f"{params['scantime']:.6g}")
        if "speed" in params:
            self.setField("speed", f"{params['speed']:.6g}")
        if "spotsize" in params:
            self.setField("spotsize", f"{params['spotsize']:.6g}")

        self.setField("laserdata", data)
        self.setElidedNames(data[0].dtype.names)

    def configValid(self) -> bool:
        data = self.field("laserdata")
        if len(data) < 2:
            return False
        spotsize = float(self.field("spotsize"))
        speed = float(self.field("speed"))
        scantime = float(self.field("scantime"))
        warmup = float(self.field("warmup"))
        config = SRRConfig(
            spotsize=spotsize, speed=speed, scantime=scantime, warmup=warmup
        )
        return config.valid_for_data(data)

    def getNames(self) -> List[str]:
        data = self.field("laserdata")[0]
        return data.dtype.names if data is not None else []

    def isComplete(self) -> bool:
        if not super().isComplete():
            return False
        if not self.lineedit_warmup.hasAcceptableInput():
            return False
        return self.configValid()

    def readSRRAgilent(self, paths: List[Path]) -> Tuple[List[np.ndarray], dict]:
        data, param = self.readAgilent(paths[0])
        datas = [data]
        for path in paths[1:]:
            data, _ = self.readAgilent(path)
            datas.append(data)

        return datas, param

    def readSRRNumpy(self, paths: List[Path]) -> Tuple[List[np.ndarray], dict]:
        lasers = [io.npz.load(path) for path in paths]
        param = dict(
            scantime=lasers[0].config.scantime,
            speed=lasers[0].config.speed,
            spotsize=lasers[0].config.spotsize,
        )
        return [laser.data for laser in lasers], param

    def readSRRText(self, paths: List[Path]) -> Tuple[np.ndarray, dict]:
        data, param = self.readText(paths[0])
        datas = [data]
        for path in paths[1:]:
            data, _ = self.readText(path)
            datas.append(data)

        return datas, param

    def readSRRThermo(self, paths: List[Path]) -> Tuple[np.ndarray, dict]:
        data, param = self.readThermo(paths[0])
        datas = [data]
        for path in paths[1:]:
            data, _ = self.readThermo(path)
            datas.append(data)

        return datas, param

    def setElidedNames(self, names: List[str]) -> None:
        text = ", ".join(name for name in names)
        fm = QtGui.QFontMetrics(self.label_isotopes.font())
        text = fm.elidedText(text, QtCore.Qt.ElideRight, self.label_isotopes.width())
        self.label_isotopes.setText(text)

    def updateNames(self, rename: dict) -> None:
        datas = self.field("laserdata")
        for i in range(len(datas)):
            remove = [name for name in datas[i].dtype.names if name not in rename]
            datas[i] = rfn.drop_fields(datas[i], remove, usemask=False)
            datas[i] = rfn.rename_fields(datas[i], rename)

        self.setField("laserdata", datas)
        self.setElidedNames(datas[0].dtype.names)

    data_prop = QtCore.Property("QVariant", getData, setData, notify=dataChanged)


class SRRPathAndOptionsPage(PathAndOptionsPage):
    def __init__(
        self,
        paths: List[Path],
        format: str,
        nextid: int,
        parent: QtWidgets.QWidget = None,
    ):
        super().__init__(
            paths, format, multiplepaths=True, nextid=nextid, parent=parent
        )

    def isComplete(self) -> bool:
        if not super().isComplete():  # pragma: no cover
            return False
        return len(self.path.paths) >= 2
