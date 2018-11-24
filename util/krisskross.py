import numpy as np

from util.laser import LaserData


def krissKrossLayers(layers, aspect, warmup, horizontal_first=True):

        j = 0 if horizontal_first else 1
        aspect = int(aspect)
        trim = int(aspect / 2)
        # Calculate the line lengths
        length = (layers[1].shape[0] * aspect,
                  layers[0].shape[0] * aspect)

        # Reshape the layers and stack into matrix
        transformed = []
        for i, layer in enumerate(layers):
            # Trim data of warmup time and excess
            layer = layer[:, warmup:warmup+length[(i + j) % 2]]
            # Stretch array
            layer = np.repeat(layer, aspect, axis=0)
            # Flip vertical layers and trim
            if (i + j) % 2 == 1:
                layer = layer.T
                layer = layer[trim:, trim:]
            elif trim > 0:
                layer = layer[:-trim, :-trim]

            transformed.append(layer)

        data = np.dstack(transformed)

        # TODO find a way to do this, less copy() required
        # if self.params['rastered']:
        #     self.data[1::2, :, 0::2] = self.data[1::2, ::-1, 0::2]
        #     self.data[:, 1::2, 1::2] = self.data[::-1, 1::2, 1::2]

        return data


class KrissKrossData(LaserData):
    def __init__(self, data=None, isotope="", config=None, source=""):
        super().__init__(data=data, isotope=isotope,
                         config=config, source=source)

    def fromLayers(self, layers, warmup_time=12.0, horizontal_first=True):
        warmup = int(warmup_time / self.config['scantime'])
        self.data = krissKrossLayers(layers, self.aspect(),
                                     warmup, horizontal_first)

    def flatten(self):
        return np.mean(self.data, axis=2)

    def calibrated(self, flat=False):
        return np.mean(super().calibrated(), axis=2) if flat \
               else super().calibrated()