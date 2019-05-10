from PyQt5 import QtCore, QtGui, QtWidgets
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from laserlib.laser import Laser
from laserlib.krisskross import KrissKross
from matplotlib.backend_bases import MouseEvent, LocationEvent

from pewpew.lib.calc import rolling_mean_filter, rolling_median_filter

from matplotlib.widgets import RectangleSelector, LassoSelector
from matplotlib.ticker import MaxNLocator
from matplotlib.offsetbox import AnchoredText
from matplotlib_scalebar.scalebar import ScaleBar
from mpl_toolkits.axes_grid1 import make_axes_locatable

from typing import Dict, List
from matplotlib.image import AxesImage
from matplotlib.widgets import _SelectorWidget


class Canvas(FigureCanvasQTAgg):
    def __init__(
        self,
        viewconfig: dict,
        connect_mouse_events: bool = True,
        parent: QtWidgets.QWidget = None,
    ) -> None:
        fig = Figure(frameon=False, tight_layout=True, figsize=(5, 5), dpi=100)
        super().__init__(fig)
        self.options = {
            "colorbar": True,
            "scalebar": True,
            "label": True,
            "colorbarpos": "bottom",
        }
        self.viewconfig = viewconfig

        self.redraw_figure()
        self.image: AxesImage = None

        self.extent = (0.0, 0.0, 0.0, 0.0)
        self.view = (0.0, 0.0, 0.0, 0.0)

        self.selector: _SelectorWidget = None

        self.setParent(parent)
        self.setStyleSheet("background-color:transparent;")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )

        self.events: Dict[str, List[int]] = {}
        if connect_mouse_events:
            self.connect_events("status")

    def close(self) -> None:
        self.clearStatusBar()
        super().close()

    def redraw_figure(self) -> None:
        self.figure.clear()
        self.ax = self.figure.add_subplot(111)
        self.ax.axis("scaled")
        self.ax.set_facecolor("black")
        self.ax.get_xaxis().set_visible(False)
        self.ax.get_yaxis().set_visible(False)
        div = make_axes_locatable(self.ax)
        self.cax = div.append_axes(self.options["colorbarpos"], size=0.1, pad=0.05)

    def draw_colorbar(self, label: str) -> None:
        self.cax.clear()
        if self.options["colorbarpos"] in ["right", "left"]:
            orientation = "vertical"
        else:
            orientation = "horizontal"
        self.figure.colorbar(
            self.image,
            label=label,
            cax=self.cax,
            orientation=orientation,
            ticks=MaxNLocator(nbins=6),
        )

    def draw_data(self, data: np.ndarray, aspect: float) -> None:
        self.ax.clear()

        # Filter if required
        if self.viewconfig["filtering"]["type"] != "None":
            filter_type, window, threshold = (
                self.viewconfig["filtering"][x] for x in ["type", "window", "threshold"]
            )
            if filter_type == "Rolling mean":
                # rolling_mean_filter(data, window, threshold)
                data = rolling_mean_filter(data, window, threshold)
            elif filter_type == "Rolling median":
                data = rolling_median_filter(data, window, threshold)

        # Calculate the range
        if isinstance(self.viewconfig["cmap"]["range"][0], str):
            vmin = np.percentile(
                data, float(self.viewconfig["cmap"]["range"][0].rstrip("%"))
            )
        else:
            vmin = float(self.viewconfig["cmap"]["range"][0])
        if isinstance(self.viewconfig["cmap"]["range"][1], str):
            vmax = np.percentile(
                data, float(self.viewconfig["cmap"]["range"][1].rstrip("%"))
            )
        else:
            vmax = float(self.viewconfig["cmap"]["range"][1])

        # Plot the image
        self.image = self.ax.imshow(
            data,
            cmap=self.viewconfig["cmap"]["type"],
            interpolation=self.viewconfig["interpolation"].lower(),
            alpha=self.viewconfig["alpha"],
            vmin=vmin,
            vmax=vmax,
            extent=self.extent,
            aspect=aspect,
            origin="upper",
        )

    def draw_laser(self, laser: Laser, name: str) -> None:
        # Get the trimmed and calibrated data
        kwargs = {"calibrate": self.viewconfig["calibrate"]}
        if isinstance(laser, KrissKross):
            kwargs["flat"] = True
        data = laser.get(name, **kwargs)
        unit = (
            str(laser.data[name].calibration.unit)
            if self.viewconfig["calibrate"]
            else ""
        )

        # If the laser extent has changed (i.e. config edited) then reset the view
        x = data.shape[1] * laser.config.pixel_width()
        y = data.shape[0] * laser.config.pixel_height()
        extent = (0.0, x, 0.0, y)
        if self.extent != extent:
            self.extent = extent
            self.view = (0.0, 0.0, 0.0, 0.0)

        # If data is empty create a dummy data
        if data is None or data.size == 0:
            data = np.array([[0]], dtype=np.float64)

        self.draw_data(data, laser.config.aspect())
        if self.options["colorbar"]:
            self.cax.set_visible(True)
            self.draw_colorbar(unit)
        else:
            self.cax.set_visible(False)

        if self.options["label"]:
            text = AnchoredText(
                name,
                "upper left",
                pad=0.2,
                borderpad=0.1,
                frameon=False,
                prop={"color": "white", "size": self.viewconfig["font"]["size"]},
            )
            self.ax.add_artist(text)

        if self.options["scalebar"]:
            scalebar = ScaleBar(
                1.0,
                "um",
                location="upper right",
                frameon=False,
                color="white",
                font_properties={"size": self.viewconfig["font"]["size"]},
            )
            self.ax.add_artist(scalebar)

        if self.view == (0.0, 0.0, 0.0, 0.0):
            self.view = self.extent
            self.draw()
        else:
            self.setView(*self.view)

    def setView(self, x1: float, x2: float, y1: float, y2: float) -> None:
        self.ax.set_xlim(x1, x2)
        self.ax.set_ylim(y1, y2)
        self.view = (x1, x2, y1, y2)
        self.draw()

    def start_lasso(self) -> None:
        lineprops = {
            "color": self.palette().color(QtGui.QPalette.Highlight).name(),
            "alpha": 0.66,
        }
        self.selector = LassoSelector(
            self.ax, self.lasso, button=1, useblit=True, lineprops=lineprops
        )

    def lasso(self, vertices: List[np.ndarray]) -> None:
        self.selector = None
        print(vertices)

    def start_zoom(self) -> None:
        rectprops = {
            "edgecolor": self.palette().color(QtGui.QPalette.Shadow).name(),
            "facecolor": self.palette().color(QtGui.QPalette.Highlight).name(),
            "alpha": 0.33,
        }
        self.selector = RectangleSelector(
            self.ax,
            self.zoom,
            button=1,
            useblit=True,
            minspanx=5,
            minspany=5,
            rectprops=rectprops,
        )
        self.disconnect_events("drag")

    def zoom(self, press: MouseEvent, release: MouseEvent) -> None:
        self.setView(press.xdata, release.xdata, press.ydata, release.ydata)
        self.selector = None
        self.connect_events("drag")

    def unzoom(self) -> None:
        self.setView(*self.extent)
        self.disconnect_events("drag")

    def connect_events(self, key: str) -> None:
        if key == "status":
            self.events["status"] = [
                self.mpl_connect("motion_notify_event", self.update_status_bar),
                self.mpl_connect("axes_leave_event", self.clear_status_bar),
            ]
        elif key == "drag":
            self.events["drag"] = [
                self.mpl_connect("button_press_event", self.start_drag),
                self.mpl_connect("motion_notify_event", self.drag),
            ]

    def disconnect_events(self, key: str) -> None:
        if key in self.events.keys():
            for cid in self.events[key]:
                self.mpl_disconnect(cid)

    def start_drag(self, event: MouseEvent) -> None:
        if event.inaxes == self.ax and event.button == 1:
            self.drag_origin = event.xdata, event.ydata

    def drag(self, event: MouseEvent) -> None:
        if event.inaxes == self.ax and event.button == 1:
            x1, x2 = self.ax.get_xlim()
            y1, y2 = self.ax.get_ylim()

            # Move in opposite direction to drag
            x1 += self.drag_origin[0] - event.xdata
            x2 += self.drag_origin[0] - event.xdata
            y1 += self.drag_origin[1] - event.ydata
            y2 += self.drag_origin[1] - event.ydata
            # Bound to image exents
            xmin, xmax, ymin, ymax = self.image.get_extent()
            view = self.view
            if x1 > xmin and x2 < xmax:
                view = (x1, x2, view[2], view[3])
            if y1 > ymin and y2 < ymax:
                view = (view[0], view[1], y1, y2)
            if view != self.view:
                self.setView(*view)

    def update_status_bar(self, e: MouseEvent) -> None:
        if e.inaxes == self.ax and self.image._A is not None:
            x, y = e.xdata, e.ydata
            v = self.image.get_cursor_data(e)
            if self.window() is not None and self.window().statusBar() is not None:
                self.window().statusBar().showMessage(f"{x:.2f},{y:.2f} [{v:.2f}]")

    def clear_status_bar(self, e: LocationEvent = None) -> None:
        if self.window() is not None:
            self.window().statusBar().clearMessage()

    def sizeHint(self) -> QtCore.QSize:
        w, h = self.get_width_height()
        return QtCore.QSize(w, h)

    def minimumSizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(250, 250)
