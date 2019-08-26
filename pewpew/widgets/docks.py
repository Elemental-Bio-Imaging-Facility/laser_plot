import copy
import numpy as np
import os.path

from PySide2 import QtCore, QtGui, QtWidgets

from laserlib import io
from laserlib import Laser
from laserlib.krisskross import KrissKross

from pewpew.lib.mpltools import image_extent_to_data
from pewpew.lib.viewoptions import ViewOptions
from pewpew.widgets import dialogs, exportdialogs
from pewpew.widgets.canvases import InteractiveLaserCanvas
from pewpew.widgets.prompts import OverwriteFilePrompt


class ImageDockTitleBar(QtWidgets.QWidget):

    nameChanged = QtCore.Signal("QString")

    def __init__(self, title: str, parent: QtWidgets.QWidget = None):
        super().__init__(parent)

        self.title = QtWidgets.QLabel(title)
        self.dlg: QtWidgets.QDialog = None

        # Button Bar
        self.button_move = QtWidgets.QPushButton(
            QtGui.QIcon.fromTheme("transform-move"), ""
        )
        self.button_select_rect = QtWidgets.QPushButton(
            QtGui.QIcon.fromTheme("draw-rectangle"), ""
        )
        self.button_select_lasso = QtWidgets.QPushButton(
            QtGui.QIcon.fromTheme("edit-select-lasso"), ""
        )
        self.button_zoom = QtWidgets.QPushButton(QtGui.QIcon.fromTheme("zoom-in"), "")
        self.button_zoom.setToolTip("Zoom into slected area.")
        self.button_zoom_original = QtWidgets.QPushButton(
            QtGui.QIcon.fromTheme("zoom-original"), ""
        )
        self.button_zoom_original.setToolTip("Reset to original zoom.")
        self.button_close = QtWidgets.QPushButton(
            QtGui.QIcon.fromTheme("edit-delete"), ""
        )
        self.button_close.setToolTip("Close the image.")

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.VLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)

        layout_buttons = QtWidgets.QHBoxLayout()
        layout_buttons.addWidget(self.button_move, 0, QtCore.Qt.AlignLeft)
        layout_buttons.addWidget(self.button_select_rect, 0, QtCore.Qt.AlignLeft)
        layout_buttons.addWidget(self.button_select_lasso, 0, QtCore.Qt.AlignLeft)
        layout_buttons.addWidget(line)
        layout_buttons.addWidget(self.button_zoom, 0, QtCore.Qt.AlignRight)
        layout_buttons.addWidget(self.button_zoom_original, 0, QtCore.Qt.AlignRight)
        layout_buttons.addWidget(self.button_close, 0, QtCore.Qt.AlignRight)

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.title, 1)
        layout.addLayout(layout_buttons, 0)

        self.setLayout(layout)

    def setTitle(self, title: str) -> None:
        if "&" not in title:
            self.title.setText(title)

    def mouseDoubleClickEvent(self, event: QtCore.QEvent) -> None:
        if self.title.underMouse():
            name, ok = QtWidgets.QInputDialog.getText(
                self, "Rename", "Name:", QtWidgets.QLineEdit.Normal, self.title.text()
            )
            if ok:
                self.nameChanged.emit(name)


class LaserImageDock(QtWidgets.QDockWidget):
    def __init__(
        self, laser: Laser, viewoptions: ViewOptions, parent: QtWidgets.QWidget = None
    ):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setFeatures(
            QtWidgets.QDockWidget.DockWidgetClosable
            | QtWidgets.QDockWidget.DockWidgetMovable
        )

        self.laser = laser
        self.canvas = InteractiveLaserCanvas(viewoptions=viewoptions, parent=self)
        self.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)
        # self.canvas.setFocus()

        self.combo_isotopes = QtWidgets.QComboBox()
        self.combo_isotopes.currentIndexChanged.connect(self.onComboIsotope)
        self.combo_isotopes.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.populateComboIsotopes()

        self.layout_bottom = QtWidgets.QHBoxLayout()
        self.layout_bottom.addWidget(self.combo_isotopes, 0, QtCore.Qt.AlignRight)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.canvas)
        layout.addLayout(self.layout_bottom)

        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        self.setWidget(widget)

        # Title bar
        self.title_bar = ImageDockTitleBar("", self)
        self.title_bar.nameChanged.connect(self.titleNameChanged)
        self.windowTitleChanged.connect(self.title_bar.setTitle)
        self.setTitleBarWidget(self.title_bar)
        self.setWindowTitle(self.laser.name)

        self.title_bar.button_move.clicked.connect(self.canvas.endSelection)
        self.title_bar.button_select_rect.clicked.connect(
            self.canvas.startRectangleSelection
        )
        self.title_bar.button_select_lasso.clicked.connect(
            self.canvas.startLassoSelection
        )
        self.title_bar.button_zoom.clicked.connect(self.canvas.startZoom)
        self.title_bar.button_zoom_original.clicked.connect(self.canvas.unzoom)
        self.title_bar.button_close.clicked.connect(self.onMenuClose)

        # Context menu actions
        self.action_copy_image = QtWidgets.QAction(
            QtGui.QIcon.fromTheme("insert-image"), "Copy Image", self
        )
        self.action_copy_image.setStatusTip("Copy image to clipboard.")
        self.action_copy_image.triggered.connect(self.canvas.copyToClipboard)

        self.action_save = QtWidgets.QAction(
            QtGui.QIcon.fromTheme("document-save"), "Save", self
        )
        self.action_save.setStatusTip("Save data to archive.")
        self.action_save.triggered.connect(self.onMenuSave)

        self.action_export = QtWidgets.QAction(
            QtGui.QIcon.fromTheme("document-save-as"), "Export", self
        )
        self.action_export.setStatusTip("Save data to different formats.")
        self.action_export.triggered.connect(self.onMenuExport)

        self.action_calibration = QtWidgets.QAction(
            QtGui.QIcon.fromTheme("go-top"), "Calibration", self
        )
        self.action_calibration.setStatusTip("Edit image calibration.")
        self.action_calibration.triggered.connect(self.onMenuCalibration)

        self.action_config = QtWidgets.QAction(
            QtGui.QIcon.fromTheme("document-edit"), "Config", self
        )
        self.action_config.setStatusTip("Edit image config.")
        self.action_config.triggered.connect(self.onMenuConfig)

        self.action_stats = QtWidgets.QAction(
            QtGui.QIcon.fromTheme(""), "Statistics", self
        )
        self.action_stats.setStatusTip("Data histogram and statistics.")
        self.action_stats.triggered.connect(self.onMenuStats)

        self.action_close = QtWidgets.QAction(
            QtGui.QIcon.fromTheme("edit-delete"), "Close", self
        )
        self.action_close.setStatusTip("Close the images.")
        self.action_close.triggered.connect(self.onMenuClose)

    def draw(self) -> None:
        self.canvas.drawLaser(self.laser, self.combo_isotopes.currentText())
        self.canvas.draw()

    def buildContextMenu(self) -> QtWidgets.QMenu:
        context_menu = QtWidgets.QMenu(self)
        context_menu.addAction(self.action_copy_image)
        context_menu.addSeparator()
        context_menu.addAction(self.action_save)
        context_menu.addAction(self.action_export)
        context_menu.addSeparator()
        context_menu.addAction(self.action_calibration)
        context_menu.addAction(self.action_config)
        context_menu.addAction(self.action_stats)
        context_menu.addSeparator()
        context_menu.addAction(self.action_close)
        return context_menu

    def populateComboIsotopes(self) -> None:
        isotopes = sorted(self.laser.isotopes)
        self.combo_isotopes.blockSignals(True)
        self.combo_isotopes.clear()
        self.combo_isotopes.addItems(isotopes)
        self.combo_isotopes.blockSignals(False)

    def contextMenuEvent(self, event: QtCore.QEvent) -> None:
        context_menu = self.buildContextMenu()
        context_menu.popup(event.globalPos())

    def onMenuSave(self) -> None:
        if self.laser.filepath.lower().endswith(".npz") and os.path.exists(
            self.laser.filepath
        ):
            path = self.laser.filepath
        else:
            path, _filter = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Save File",
                os.path.join(os.path.dirname(self.laser.filepath), self.laser.name),
                "Numpy archive(*.npz);;All files(*)",
            )
        if path:
            io.npz.save(path, [self.laser])
            self.laser.filepath = path

    def onMenuExportFileSelected(self, path: str) -> None:
        if path == "":
            return
        ext = os.path.splitext(path)[1].lower()
        if ext == ".npz":
            if OverwriteFilePrompt.promptOverwriteSingleFile(path, self):
                io.npz.save(path, [self.laser])
        elif ext == ".csv":
            dlg = exportdialogs.CsvExportDialog(
                self.laser, self.combo_isotopes.currentText(), parent=self
            )
            if dlg.exec_():
                dlg.export(path, self.viewoptions.calibrate, self.canvas.view_limits)

        elif ext == ".png":
            dlg = exportdialogs.PngExportDialog(
                self.laser, self.combo_isotopes.currentText(), parent=self
            )
            if dlg.exec_():
                dlg.export(path, self.viewoptions, self.canvas.options)
        elif ext == ".vti":
            dlg = exportdialogs.VtiExportDialog(
                self.laser, self.combo_isotopes.currentText(), parent=self
            )
            if dlg.exec_():
                dlg.export(path, self.viewoptions.calibrate)
        else:
            QtWidgets.QMessageBox.warning(
                self, "Invalid Format", f"Unable to export {ext} format."
            )

    def onMenuExport(self) -> None:
        self.dlg = QtWidgets.QFileDialog(
            self,
            "Export",
            os.path.join(os.path.dirname(self.laser.filepath), self.laser.name),
            "CSV files(*.csv);;Numpy archives(*.npz);;"
            "PNG images(*.png);;VTK Images(*.vti);;All files(*)",
        )
        self.dlg.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        self.dlg.setOption(QtWidgets.QFileDialog.DontConfirmOverwrite, True)
        self.dlg.fileSelected.connect(self.onMenuExportFileSelected)
        self.dlg.open()

    #         if ext == ".csv":
    #             self.dlg: exporters.ExportDialog = exporters.CSVExportDialog(
    #                 path,
    #                 name=self.combo_isotopes.currentText(),
    #                 names=len(self.laser.isotopes),
    #                 layers=1,
    #                 parent=self,
    #             )
    #             if self.dlg.open():
    #                 paths = self.dlg.generate_paths(self.laser)
    #                 kwargs = {
    #                     "calibrate": self.canvas.viewoptions["calibrate"],
    #                     "flat": True,
    #                 }
    #                 if self.dlg.options.trimmedChecked():
    #                     kwargs["extent"] = self.canvas.view_limits
    #                 for path, isotope, _ in paths:
    #                     io.csv.save(path, self.laser.get(isotope, **kwargs))
    #         elif ext == ".npz":
    #             io.npz.save(path, [self.laser])
    #         elif ext == ".png":
    #             self.dlg = exporters.PNGExportDialog(
    #                 path,
    #                 name=self.combo_isotopes.currentText(),
    #                 names=len(self.laser.isotopes),
    #                 layers=1,
    #                 viewlimits=self.canvas.view_limits,
    #                 parent=self,
    #             )
    #             if self.dlg.open():
    #                 paths = self.dlg.generate_paths(self.laser)
    #                 old_size = self.canvas.figure.get_size_inches()
    #                 size = self.dlg.options.imagesize()
    #                 dpi = self.canvas.figure.get_dpi()
    #                 self.canvas.figure.set_size_inches(size[0] / dpi, size[1] / dpi)

    #                 for path, isotope, _ in paths:
    #                     self.canvas.drawLaser(self.laser, isotope)
    #                     self.canvas.figure.savefig(path, transparent=True, frameon=False)

    #                 self.canvas.figure.set_size_inches(*old_size)
    #                 self.canvas.drawLaser(self.laser, self.combo_isotopes.currentText())
    #                 self.canvas.draw()
    #         elif ext == ".vti":
    #             spacing = (
    #                 self.laser.config.get_pixel_width(),
    #                 self.laser.config.get_pixel_height(),
    #                 self.laser.config.spotsize / 2.0,
    #             )
    #             io.vtk.save(
    #                 path,
    #                 self.laser.get_structured(
    #                     calibrate=self.canvas.viewoptions["calibrate"]
    #                 ),
    #                 spacing=spacing,
    #             )
    #         else:
    #             QtWidgets.QMessageBox.warning(
    #                 self, "Invalid Format", f"Unable to export {ext} format."
    #             )
    #             return self.onMenuExport()

    def onMenuCalibration(self) -> None:
        def applyDialog(dialog: dialogs.ApplyDialog) -> None:
            if dialog.check_all.isChecked():
                docks = self.parent().findChildren(LaserImageDock)
            else:
                docks = [self]
            for dock in docks:
                for isotope in self.dlg.calibrations.keys():
                    if isotope in dock.laser.isotopes:
                        dock.laser.data[isotope].calibration = copy.copy(
                            self.dlg.calibrations[isotope]
                        )
                dock.draw()

        calibrations = {
            isotope: self.laser.data[isotope].calibration
            for isotope in self.laser.data.keys()
        }
        self.dlg = dialogs.CalibrationDialog(
            calibrations, self.combo_isotopes.currentText(), parent=self
        )
        self.dlg.applyPressed.connect(applyDialog)
        self.dlg.open()

    def onMenuConfig(self) -> None:
        def applyDialog(dialog: dialogs.ApplyDialog) -> None:
            if dialog.check_all.isChecked():
                docks = self.parent().findChildren(LaserImageDock)
            else:
                docks = [self]
            for dock in docks:
                if type(dock.laser) == Laser:
                    dock.laser.config = copy.copy(dialog.config)
                    dock.draw()

        self.dlg = dialogs.ConfigDialog(self.laser.config, parent=self)
        self.dlg.applyPressed.connect(applyDialog)
        self.dlg.open()

    def onMenuStats(self) -> None:
        data = self.canvas.image.get_array()
        mask = self.canvas.getSelection()
        if mask is not None and not np.all(mask == 0):
            # Trim out nan rows and columns to get size
            data = np.where(mask, data, np.nan)
            data = data[:, ~np.isnan(data).all(axis=0)]
            data = data[~np.isnan(data).all(axis=1)]
        else:  # Trim to view limits
            x0, x1, y0, y1 = self.canvas.view_limits
            (x0, y0), (x1, y1) = (
                image_extent_to_data(self.canvas.image)
                .transform(((x0, y1), (x1, y0)))
                .astype(int)
            )
            data = data[y0:y1, x0:x1]  # type: ignore

        self.dlg = dialogs.StatsDialog(
            data,
            self.canvas.viewoptions.colors.get_range_as_float(
                self.combo_isotopes.currentText(), data
            ),
            parent=self,
        )
        self.dlg.show()

    def onMenuClose(self) -> None:
        self.close()

    def onComboIsotope(self, text: str) -> None:
        self.draw()

    def titleNameChanged(self, name: str) -> None:
        self.setWindowTitle(name)
        if self.laser is not None:
            self.laser.name = name


class KrissKrossImageDock(LaserImageDock):
    def __init__(
        self,
        laser: KrissKross,
        viewoptions: ViewOptions,
        parent: QtWidgets.QWidget = None,
    ):
        super().__init__(laser, viewoptions, parent)

        self.combo_layer = QtWidgets.QComboBox()
        self.combo_layer.currentIndexChanged.connect(self.onComboLayer)
        self.combo_layer.addItem("*")
        self.combo_layer.addItems([str(i) for i in range(0, self.laser.layers)])
        self.layout_bottom.insertWidget(0, self.combo_layer, 1, QtCore.Qt.AlignRight)

    def draw(self) -> None:
        try:
            layer = int(self.combo_layer.currentText())
        except ValueError:
            layer = None

        self.canvas.drawLaser(
            self.laser, self.combo_isotopes.currentText(), layer=layer
        )
        self.canvas.draw()

    def onComboLayer(self, text: str) -> None:
        self.draw()

    def onMenuConfig(self) -> None:
        def applyDialog(dialog: dialogs.ApplyDialog) -> None:
            if dialog.check_all.isChecked():
                docks = self.parent().findChildren(KrissKrossImageDock)
            else:
                docks = [self]
            for dock in docks:
                if type(dock.laser) == KrissKross:
                    if not dock.laser.check_config_valid(dialog.config):
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Invalid config!",
                            "Config is not valid for current image(s).",
                        )
                        return
                    dock.laser.config = copy.copy(dialog.config)
                    dock.draw()

        self.dlg = dialogs.ConfigDialog(self.laser.config, parent=self)
        self.dlg.applyPressed.connect(applyDialog)
        self.dlg.open()
