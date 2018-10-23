import matplotlib
from matplotlib_scalebar.scalebar import ScaleBar
from mpl_toolkits.axes_grid1 import make_axes_locatable
from matplotlib.offsetbox import TextArea, AnchoredOffsetbox, VPacker

from util.formatter import isotopeFormat


class LaserFig(object):
    def __init__(self, fig=None, cmap='magma'):
        if fig is None:
            self.fig = matplotlib.figure.Figure(frameon=False,
                                                facecolor='black')
        else:
            self.fig = fig
        self.cmap = cmap

        self.ax = self.fig.add_subplot(111)
        div = make_axes_locatable(self.ax)
        self.cax = div.append_axes('right', size=0.1, pad=0.05)

        self.im = self.ax.imshow([[0]], cmap=cmap, interpolation='none')
        self.fig.colorbar(self.im, cax=self.cax)

        self.ax.clear()
        self.ax.set_axis_off()
        self.ax.get_xaxis().set_visible(False)
        self.ax.get_yaxis().set_visible(False)
        self.ax.set_facecolor('black')

        self.fig.tight_layout()

    def update(self, data, label=None, aspect='auto', extent=None):
        self.ax.clear()
        self.cax.clear()
        # Plot the image
        self.im = self.ax.imshow(data, cmap=self.cmap,
                                 interpolation='none',
                                 extent=extent, aspect=aspect)
        # Create / update colorbarc
        self.fig.colorbar(self.im, cax=self.cax)
        # Draw scalebar
        scalebar = ScaleBar(1.0, 'um', frameon=False, color='white')
        self.ax.add_artist(scalebar)
        # Draw isotope label
        if label is not None:
            self.ax.annotate(isotopeFormat(label),
                             xycoords='axes fraction', xy=(0.05, 1.0),
                             textcoords='offset pixels', xytext=(0, -24),
                             ha='center',
                             color='white')
        self.fig.tight_layout()

    def show(self):
        self.fig.show()
