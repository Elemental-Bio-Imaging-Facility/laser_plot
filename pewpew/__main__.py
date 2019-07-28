import sys

from PySide2.QtCore import QTimer, Qt
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import QApplication
from pewpew.ui import MainWindow
from pewpew.resource import app_icon  # noqa: F401

if sys.platform in ['win32', 'darwin']:
    from pewpew.resource import breath_icons  # noqa: F401
    QIcon.setThemeName("breath")

if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)

    window = MainWindow()
    sys.excepthook = window.exceptHook  # type: ignore
    window.show()
    window.setWindowIcon(QIcon(":/app.ico"))

    # Keep event loop active with timer
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)

    app.exec_()
