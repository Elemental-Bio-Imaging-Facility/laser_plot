from pytestqt.qtbot import QtBot

from PySide2 import QtCore, QtGui, QtWidgets

from pewpew.widgets.views import ViewSpace, View, ViewTabBar, ViewTitleBar


def test_view_space_active(qtbot: QtBot):
    viewspace = ViewSpace()
    qtbot.addWidget(viewspace)
    viewspace.show()
    # Default active
    assert viewspace.activeView() == viewspace.views[0]
    # Focus new widget
    viewspace.splitActiveHorizontal()
    assert viewspace.activeView() == viewspace.views[1]
    # Test focus changes active
    viewspace.views[0].setFocus()
    qtbot.waitUntil(lambda: viewspace.views[0].hasFocus())
    assert viewspace.activeView() == viewspace.views[0]
    # Test focus on tab changes active
    qtbot.mouseClick(viewspace.views[1].tabs, QtCore.Qt.LeftButton)
    assert viewspace.activeView() == viewspace.views[1]


def test_view_space_add_remove(qtbot: QtBot):
    viewspace = ViewSpace()
    qtbot.addWidget(viewspace)
    viewspace.show()

    assert len(viewspace.views) == 1

    with qtbot.waitSignal(viewspace.numViewsChanged):
        viewspace.splitActiveHorizontal()
    assert len(viewspace.views) == 2

    viewspace.setActiveView(viewspace.views[1])
    with qtbot.waitSignal(viewspace.numViewsChanged):
        viewspace.splitActiveVertical()
    assert len(viewspace.views) == 3

    with qtbot.waitSignal(viewspace.numViewsChanged):
        viewspace.splitView(viewspace.views[2], QtCore.Qt.Horizontal)
    assert len(viewspace.views) == 4

    # Should be 1 view on left, 1 on top right, 2 bottom right
    assert viewspace.count() == 2
    assert isinstance(viewspace.widget(0), View)
    assert isinstance(viewspace.widget(1), QtWidgets.QSplitter)

    assert viewspace.widget(1).count() == 2
    assert isinstance(viewspace.widget(1).widget(0), View)
    assert isinstance(viewspace.widget(1).widget(1), QtWidgets.QSplitter)

    assert viewspace.widget(1).widget(1).count() == 2
    assert isinstance(viewspace.widget(1).widget(1).widget(0), View)
    assert isinstance(viewspace.widget(1).widget(1).widget(1), View)

    with qtbot.waitSignal(viewspace.numViewsChanged):
        viewspace.closeView(viewspace.views[0])
    assert len(viewspace.views) == 3

    # Should be 1 view on top, 1 on bottom left, 1 bottom right
    # Original splitter changes orientation, inherits children of right splitter
    assert viewspace.count() == 2
    assert viewspace.orientation() == QtCore.Qt.Vertical
    assert isinstance(viewspace.widget(0), View)
    assert isinstance(viewspace.widget(1), QtWidgets.QSplitter)

    assert viewspace.widget(1).count() == 2
    assert isinstance(viewspace.widget(1).widget(0), View)
    assert isinstance(viewspace.widget(1).widget(1), View)

    with qtbot.waitSignal(viewspace.numViewsChanged):
        viewspace.closeActiveView()
    assert len(viewspace.views) == 2
    with qtbot.waitSignal(viewspace.numViewsChanged):
        viewspace.closeActiveView()
    assert len(viewspace.views) == 1
    with qtbot.assertNotEmitted(viewspace.numViewsChanged, wait=100):
        viewspace.closeActiveView()
    assert len(viewspace.views) == 1


def test_view_tabs(qtbot: QtBot):
    viewspace = ViewSpace()
    qtbot.addWidget(viewspace)
    viewspace.show()
    view = viewspace.activeView()
    # Creating tabs
    with qtbot.waitSignal(view.numTabsChanged):
        view.addTab("1", QtWidgets.QLabel("1"))
    with qtbot.waitSignal(viewspace.numTabsChanged):
        view.addTab("3", QtWidgets.QLabel("3"))
    with qtbot.waitSignal(view.numTabsChanged):
        view.insertTab(1, "2", QtWidgets.QLabel("2"))
    assert [view.tabs.tabText(i) for i in range(3)] == ["1", "2", "3"]
    assert [view.stack.widget(i).text() for i in range(3)] == ["1", "2", "3"]
    # Moving tabs
    with qtbot.assertNotEmitted(view.numTabsChanged, wait=100):
        view.tabs.moveTab(2, 0)
    assert [view.tabs.tabText(i) for i in range(3)] == ["3", "1", "2"]
    assert [view.stack.widget(i).text() for i in range(3)] == ["3", "1", "2"]
    # Removing tabs
    with qtbot.waitSignal(viewspace.numTabsChanged):
        view.removeTab(1)
    assert [view.tabs.tabText(i) for i in range(2)] == ["3", "2"]
    assert [view.stack.widget(i).text() for i in range(2)] == ["3", "2"]

    view.removeTab(0)
    assert len(view.widgets()) == 1
    view.removeTab(0)
    assert len(view.widgets()) == 0


def test_view_tab_bar(qtbot: QtBot):
    viewspace = ViewSpace()
    qtbot.addWidget(viewspace)
    viewspace.show()
    view = viewspace.activeView()
    tabs = view.tabs
    view.addTab("1", QtWidgets.QLabel("1"))
    view.addTab("2", QtWidgets.QLabel("2"))
    # Test double click rename
    mouse_event = QtGui.QMouseEvent(
        QtCore.QEvent.MouseButtonDblClick,
        tabs.tabRect(0).center(),
        QtCore.QPoint(0, 0),
        QtCore.Qt.LeftButton,
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoModifier,
    )
    dlg = tabs.mouseDoubleClickEvent(mouse_event)
    assert dlg.textValue() == "1"
    dlg.textValueSelected.emit("3")
    dlg.close()
    assert tabs.tabText(0) == "3"
    # Test drag and drop
