import os

from PySide2 import QtCore, QtGui, QtWidgets

from pew import io
from pew.config import Config
from pew.srr import SRRLaser, SRRConfig

from pewpew.validators import DecimalValidator, DecimalValidatorNoZero
from pewpew.widgets.ext import MultipleDirDialog
from pewpew.widgets.wizards.import_ import ImportFormatPage

from typing import List


class LaserImportList(QtWidgets.QListWidget):
    def __init__(
        self, allowed_exts: List[str] = None, parent: QtWidgets.QWidget = None
    ):
        super().__init__(parent)
        self.allowed_exts = allowed_exts
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setTextElideMode(QtCore.Qt.ElideLeft)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                if url.isLocalFile():
                    path = url.toLocalFile()
                    name, ext = os.path.splitext(path)
                    if self.allowed_exts is None or ext in self.allowed_exts:
                        self.addItem(path)
        else:
            super().dropEvent(event)

    @QtCore.Property("QStringList")
    def paths(self) -> List[str]:
        return [self.item(i).text() for i in range(0, self.count())]


class SRRFilesPage(QtWidgets.QWizardPage):
    def __init__(
        self, min_files: int = 1, max_files: int = -1, parent: QtWidgets.QWidget = None
    ):
        super().__init__(parent)

        self.min_files = min_files
        self.max_files = max_files

        self.setTitle("Files and Directories")
        # List and box

        self.list = LaserImportList()
        self.list.model().rowsInserted.connect(self.completeChanged)
        self.list.model().rowsRemoved.connect(self.completeChanged)

        dir_box = QtWidgets.QGroupBox("Layer Order", self)
        box_layout = QtWidgets.QVBoxLayout()
        box_layout.addWidget(self.list)
        dir_box.setLayout(box_layout)

        # Buttons
        button_file = QtWidgets.QPushButton("Open")
        button_file.clicked.connect(self.buttonAdd)
        button_dir = QtWidgets.QPushButton("Open All...")
        button_dir.clicked.connect(self.buttonAddAll)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(button_file)
        button_layout.addWidget(button_dir)
        box_layout.addLayout(button_layout)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addWidget(dir_box)
        self.setLayout(main_layout)

        self.registerField("paths", self.list, "paths")

    def initializePage(self) -> None:
        if self.field("numpy"):
            ext = ".npz"
        elif self.field("agilent"):
            ext = ".b"
        elif self.field("thermo"):
            ext = ".csv"
        self.list.allowed_exts = [ext]

    def buttonAdd(self) -> None:
        if self.field("numpy"):
            paths, _filter = QtWidgets.QFileDialog.getOpenFileNames(
                self, "Select Files", "", "Numpy Archives(*.npz);;All Files(*)"
            )
        elif self.field("agilent"):
            paths = MultipleDirDialog.getExistingDirectories(self, "Select Batches", "")
        elif self.field("thermo"):
            paths, _filter = QtWidgets.QFileDialog.getOpenFileNames(
                self, "Select Files", "", "CSV Documents(*.csv);;All Files(*)"
            )

        for path in paths:
            self.list.addItem(path)

    def buttonAddAll(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory", "")
        if len(path) == 0:
            return
        files = os.listdir(path)
        files.sort()

        ext = ".npz"
        if self.field("agilent"):
            ext = ".b"
        elif self.field("thermo"):
            ext = ".csv"

        for f in files:
            if f.lower().endswith(ext):
                self.list.addItem(os.path.join(path, f))

    def keyPressEvent(self, event: QtCore.QEvent) -> None:
        if (
            event.key() == QtCore.Qt.Key_Delete
            or event.key() == QtCore.Qt.Key_Backspace
        ):
            for item in self.list.selectedItems():
                self.list.takeItem(self.list.row(item))
        super().keyPressEvent(event)

    def isComplete(self) -> bool:
        return self.list.count() >= self.min_files and (
            self.max_files < 0 or self.list.count() <= self.max_files
        )


class SRRImportWizard(QtWidgets.QWizard):
    laserImported = QtCore.Signal(SRRLaser)

    def __init__(self, config: Config, parent: QtWidgets.QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("SRR Import Wizard")

        self.config = SRRConfig(config.spotsize, config.speed, config.scantime)

        self.laser = None

        overview = QtWidgets.QLabel(
            "This wizard will import SRR-LA-ICP-MS data. To begin, select "
            "the type of data to import. You may then reorder imported layers "
            "and edit the laser configuration."
        )
        format_page = ImportFormatPage(overview, parent=self)
        format_page.radio_text.setEnabled(False)
        self.addPage(format_page)
        self.addPage(SRRFilesPage(min_files=2))
        self.addPage(SRRConfigPage(self.config))

        self.resize(540, 480)

    def accept(self) -> None:
        self.config.spotsize = float(self.field("spotsize"))
        self.config.speed = float(self.field("speed"))
        self.config.scantime = float(self.field("scantime"))
        self.config.warmup = float(self.field("warmup"))

        subpixel_width = self.field("subpixel_width")
        self.config.set_equal_subpixel_offsets(subpixel_width)

        paths = self.field("paths")
        layers = []

        if self.field("numpy"):
            for path in paths:
                lds = io.npz.load(path)
                if len(lds) > 1:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Import Error",
                        f'Archive "{os.path.basename(path)}" '
                        "contains more than one image.",
                    )
                    return
                layers.append(lds[0].get())
        elif self.field("agilent"):
            for path in paths:
                layers.append(io.agilent.load(path))
        elif self.field("thermo"):
            for path in paths:
                layers.append(io.thermo.load(path))

        self.laserImported.emit(
            SRRLaser(
                layers,
                config=self.config,
                name=os.path.splitext(os.path.basename(paths[0]))[0],
                path=paths[0],
            )
        )
        super().accept()


class SRRConfigPage(QtWidgets.QWizardPage):
    def __init__(self, config: SRRConfig, parent: QtWidgets.QWidget = None):
        super().__init__(parent)

        self.lineedit_spotsize = QtWidgets.QLineEdit()
        self.lineedit_spotsize.setText(str(config.spotsize))
        self.lineedit_spotsize.setValidator(DecimalValidatorNoZero(0, 1e3, 4))
        self.lineedit_spotsize.textEdited.connect(self.completeChanged)

        self.lineedit_speed = QtWidgets.QLineEdit()
        self.lineedit_speed.setText(str(config.speed))
        self.lineedit_speed.setValidator(DecimalValidatorNoZero(0, 1e3, 4))
        self.lineedit_speed.textEdited.connect(self.completeChanged)

        self.lineedit_scantime = QtWidgets.QLineEdit()
        self.lineedit_scantime.setText(str(config.scantime))
        self.lineedit_scantime.setValidator(DecimalValidatorNoZero(0, 1e3, 4))
        self.lineedit_scantime.textEdited.connect(self.completeChanged)

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

        # Form layout for line edits
        config_layout = QtWidgets.QFormLayout()
        config_layout.addRow("Spotsize (μm):", self.lineedit_spotsize)
        config_layout.addRow("Speed (μm):", self.lineedit_speed)
        config_layout.addRow("Scantime (s):", self.lineedit_scantime)

        config_gbox = QtWidgets.QGroupBox("Laser Configuration", self)
        config_gbox.setLayout(config_layout)

        params_layout = QtWidgets.QFormLayout()
        params_layout.addRow("Warmup (s):", self.lineedit_warmup)
        params_layout.addRow("Subpixel width:", self.spinbox_offsets)

        params_gbox = QtWidgets.QGroupBox("SRRLaser Parameters", self)
        params_gbox.setLayout(params_layout)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(config_gbox)
        layout.addWidget(params_gbox)
        self.setLayout(layout)

        self.registerField("spotsize", self.lineedit_spotsize)
        self.registerField("speed", self.lineedit_speed)
        self.registerField("scantime", self.lineedit_scantime)
        self.registerField("warmup", self.lineedit_warmup)
        self.registerField("subpixel_width", self.spinbox_offsets)

    def isComplete(self) -> bool:
        return all(
            [
                self.lineedit_spotsize.hasAcceptableInput(),
                self.lineedit_speed.hasAcceptableInput(),
                self.lineedit_scantime.hasAcceptableInput(),
                self.lineedit_warmup.hasAcceptableInput(),
            ]
        )