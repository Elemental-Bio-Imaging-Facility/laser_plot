import numpy as np
from matplotlib.axes import Axes
from matplotlib.backend_bases import KeyEvent, MouseEvent
from matplotlib.image import AxesImage
from matplotlib.lines import Line2D
from matplotlib.path import Path
from matplotlib.text import Text
from matplotlib.widgets import _SelectorWidget

from pewpew.lib.mpltools import image_extent_to_data

from typing import Callable


class _ImageSelectionWidget(_SelectorWidget):
    STATE_MODIFIER_KEYS = dict(move="", clear="escape", add="shift", subtract="control")

    def __init__(
        self,
        image: AxesImage,
        callback: Callable[[np.ndarray, set], None],
        useblit=True,
        button: int = None,
    ):
        self.image = image
        self.callback = callback

        super().__init__(
            image.axes,
            None,
            useblit=useblit,
            button=button,
            state_modifier_keys=self.STATE_MODIFIER_KEYS,
        )

    def _on_key_release(self, event: KeyEvent) -> None:
        if event.key == self.state_modifier_keys["clear"]:
            self.callback(np.zeros(self.image.get_array().shape, dtype=bool), set())

    def update_mask(self, vertices: np.ndarray) -> None:
        shape = self.image.get_array().shape
        x0, x1, y0, y1 = self.image.get_extent()
        mask = np.zeros(shape[:2], dtype=np.bool)

        # Transform verticies into image data coords
        transform = self.ax.transData + self.image.get_transform().inverted()
        vertices = transform.transform(vertices)

        # Transform verticies into array coords
        transform = image_extent_to_data(self.image)
        vertices = transform.transform(vertices)
        vx = np.array([np.min(vertices[:, 0]), 1 + np.max(vertices[:, 0])], dtype=int)
        vy = np.array([np.min(vertices[:, 1]), 1 + np.max(vertices[:, 1])], dtype=int)

        # Bound to array size
        vx[0] = max(0, vx[0])
        vx[1] = min(shape[1], vx[1])
        vy[0] = max(0, vy[0])
        vy[1] = min(shape[0], vy[1])

        # If somehow the data is malformed then return
        if vx[1] - vx[0] < 1 or vy[1] - vy[0] < 1:
            return

        # Generate point mesh
        x = np.linspace(vx[0] + 0.5, vx[1] + 0.5, vx[1] - vx[0], endpoint=False)
        y = np.linspace(vy[0] + 0.5, vy[1] + 0.5, vy[1] - vy[0], endpoint=False)
        X, Y = np.meshgrid(x, y)
        pix = np.vstack((X.flatten(), Y.flatten())).T

        path = Path(vertices)
        ind = path.contains_points(pix)

        # Send via callback
        mask[vy[0] : vy[1], vx[0] : vx[1]].flat[ind] = True
        self.callback(mask, self.state)


class LassoImageSelectionWidget(_ImageSelectionWidget):
    def __init__(
        self,
        image: AxesImage,
        callback: Callable[[np.ndarray, set], None],
        useblit: bool = True,
        button: int = 1,
        lineprops: dict = None,
    ):
        super().__init__(image, callback, useblit=useblit, button=button)

        if lineprops is None:
            lineprops = dict()
        if useblit:
            lineprops["animated"] = True

        self.line = Line2D([], [], **lineprops)
        self.line.set_visible(False)
        self.ax.add_line(self.line)
        self.artists.append(self.line)

        self.verts: np.ndarray = None

    def _onmove(self, event: MouseEvent) -> None:
        if self.verts is None:
            return
        self.verts.append(self._get_data(event))
        self.line.set_data(list(zip(*self.verts)))
        self.update()

    def _press(self, event: MouseEvent) -> None:
        self.verts = [self._get_data(event)]
        self.line.set_visible(True)

    def _release(self, event: MouseEvent) -> None:
        self.line.set_data([[], []])
        self.line.set_visible(False)
        self.update()

        if self.verts is not None:
            self.verts.append(self._get_data(event))
            self.update_mask(self.verts)
        self.verts = None


class RectangleImageSelectionWidget(_ImageSelectionWidget):
    def __init__(
        self,
        image: AxesImage,
        callback: Callable[[np.ndarray, set], None],
        useblit: bool = True,
        button: int = 1,
        lineprops: dict = None,
    ):
        super().__init__(image, callback, useblit=useblit, button=button)

        if lineprops is None:
            lineprops = dict()
        if useblit:
            lineprops["animated"] = True

        self.line = Line2D([], [], **lineprops)
        self.line.set_visible(False)
        self.ax.add_line(self.line)
        self.artists.append(self.line)

    def _onmove(self, event: MouseEvent) -> None:
        if self.eventpress is None:
            return
        x0, y0 = self._get_data(self.eventpress)
        x1, y1 = self._get_data(event)
        self.line.set_visible(True)
        self.line.set_data([[x0, x0, x1, x1, x0], [y0, y1, y1, y0, y0]])
        self.update()

    def _release(self, event: MouseEvent) -> None:
        self.line.set_data([[], []])
        self.line.set_visible(False)
        self.update()

        if self.eventpress is not None:
            x0, y0 = self._get_data(self.eventpress)
            x1, y1 = self._get_data(event)
            self.update_mask([[x0, y0], [x0, y1], [x1, y1], [x1, y0]])


class RulerWidget(_SelectorWidget):
    def __init__(
        self,
        ax: Axes,
        callback: Callable[[float], None],
        useblit: bool = True,
        button: int = 1,
        lineprops: dict = None,
        drawtext: bool = False,
        textprops: dict = None,
    ):
        super().__init__(
            ax, None, useblit=useblit, button=button, state_modifier_keys=dict(),
        )

        self.callback = callback
        self.distance = 0.0

        if lineprops is None:
            lineprops = dict()
        if useblit:
            lineprops["animated"] = True

        self.line = Line2D([], [], **lineprops)
        self.line.set_visible(False)
        self.ax.add_line(self.line)
        self.artists.append(self.line)

        props = dict(animated=useblit, color="white", fontproperties=None)
        if textprops is not None:
            props.update(textprops)

        self.text: Text = None
        if drawtext:
            self.text = Text(0, 0, "", **props)
            self.text.set_visible(False)
            self.ax.add_artist(self.text)
            self.artists.append(self.text)

    def _onmove(self, event: MouseEvent) -> None:
        if self.eventpress is None:
            return
        x0, y0 = self._get_data(self.eventpress)
        x1, y1 = self._get_data(event)
        self.line.set_data([[x0, x1], [y0, y1]])
        if self.text is not None:
            self.text.set_position([x1, y1])
            self.text.set_text(f"{np.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2):.2f}")
        self.update()

    def _press(self, event: MouseEvent) -> None:
        self.line.set_visible(True)
        if self.text is not None:
            self.text.set_visible(True)

    def _release(self, event: MouseEvent) -> None:
        self.line.set_data([[], []])
        self.line.set_visible(False)
        if self.text is not None:
            self.text.set_visible(False)
        self.update()

        if self.eventpress is not None:
            x0, y0 = self._get_data(self.eventpress)
            x1, y1 = self._get_data(event)
            self.distance = np.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
            self.callback(self.distance)
