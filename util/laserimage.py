from matplotlib.ticker import MaxNLocator
from matplotlib.offsetbox import AnchoredText
from matplotlib_scalebar.scalebar import ScaleBar
from mpl_toolkits.axes_grid1 import make_axes_locatable

import numpy as np


def plotLaserImage(
    fig,
    ax,
    data,
    interpolation=None,
    extent=None,
    aspect="auto",
    colorbar=None,
    colorbarpos="bottom",
    colorbarlabel=None,
    scalebar=True,
    label=None,
    fontsize=10,
    vmin="0%",
    vmax="100%",
    cmap="magma",
):

    if data.size == 0:
        data = np.array([[0]], dtype=np.float64)

    if type(vmin) == str:
        vmin = np.percentile(data, float(vmin.rstrip("%")))
    if type(vmax) == str:
        vmax = np.percentile(data, float(vmax.rstrip("%")))

    im = ax.imshow(
        data,
        cmap=cmap,
        interpolation=interpolation,
        vmin=vmin,
        vmax=vmax,
        extent=extent,
        aspect=aspect,
    )

    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)
    ax.set_facecolor("black")
    ax.axis("scaled")

    if scalebar:
        scalebar = ScaleBar(
            1.0,
            "um",
            location="upper right",
            frameon=False,
            color="white",
            font_properties={"size": fontsize},
        )
        ax.add_artist(scalebar)

    if label is not None and label is not "":
        text = AnchoredText(
            label,
            "upper left",
            pad=0.2,
            borderpad=0.1,
            frameon=False,
            prop={"color": "white", "size": fontsize},
        )
        ax.add_artist(text)

    if colorbar is not None:
        div = make_axes_locatable(ax)
        cax = div.append_axes(colorbarpos, size=0.1, pad=0.05)
        if colorbarpos in ["right", "left"]:
            orientation = "vertical"
        else:
            orientation = "horizontal"
        fig.colorbar(
            im,
            label=colorbarlabel,
            cax=cax,
            orientation=orientation,
            ticks=MaxNLocator(nbins=6),
        )

    return im
