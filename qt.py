import sys

import matplotlib
matplotlib.use('Qt5Agg')

from PyQt5.QtWidgets import QApplication
from gui.qt.mainwindow import MainWindow


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    app.exec()
