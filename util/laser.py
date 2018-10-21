from util.importers import importAgilentBatch


class Laser(object):
    DEFAULT_PARAMS = {
        "scantime": 1.0,  # s
        "speed": 1.0,     # um/s
        "spotsize": 1.0,  # um
        "gradient": 1.0,
        "intercept": 1.0
    }

    def __init__(self):
        self.data = []

        self.scantime = 1.0
        self.speed = 1.0
        self.spotsize = 1.0

        self.gradient = 1.0
        self.intercept = 0.0

    def getElements(self):
        return self.data.dtype.names

    def importData(self, path, importer='Agilent'):
        if importer is 'Agilent':
            self.data = importAgilentBatch(path)
        else:
            print(f'Laser.import: unknown importer \'{importer}\'!')

    def calibrate(self, gradient, intercept):
        self.gradient = gradient
        self.intercept = intercept

    def getData(self, element=None):
        if element is not None:
            data = self.data[element]
        else:
            data = self.data

        return (data - self.intercept) / self.gradient

    def getScale(self):
        x = self.data.shape
