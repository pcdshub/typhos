import os
from pyqtgraph.flowchart import (Flowchart, Node, NodeGraphicsItem,
                                 FlowchartWidget)
from pyqtgraph.flowchart.library import NodeLibrary
import pyqtgraph.widgets as pyqtgraph_widgets

from qtpy import QtWidgets, QtGui, QtCore

from ophyd import SimDetector, Component as Cpt, CommonPlugins_V32, CamBase


class PortNodeItem(NodeGraphicsItem):
    WIDTH = 100
    HEIGHT = 40

    def __init__(self, node):
        super().__init__(node)
        # Shrink the vertical size a bit:
        self.bounds = QtCore.QRectF(0, 0, self.WIDTH, self.HEIGHT)

        # Do not allow ports to be renamed:
        self.nameItem.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

    def mouseClickEvent(self, ev):
        if int(ev.button()) != int(QtCore.Qt.RightButton):
            super().mouseClickEvent(ev)
        else:
            ev.ignore()


class PortNode(Node):
    nodeName = 'PortNode'

    def __init__(self, name, *, has_input=True, has_output=True):
        terminals = {}
        if has_input:
            terminals['In'] = {'io': 'in'}
        if has_output:
            terminals['Out'] = {'io': 'out'}

        super().__init__(name, terminals=terminals, allowRemove=False)

    def process(self, **kwds):
        print('process!', self)
        return {'Out': 0}

    def processBypassed(self, args):
        print('bypassed', args, self)
        return super().processBypassed(args)

    def graphicsItem(self):
        if self._graphicsItem is None:
            self._graphicsItem = PortNodeItem(self)
        return self._graphicsItem


class Library(NodeLibrary):
    def __init__(self):
        super().__init__()
        self.addNodeType(PortNode, [('AreaDetector', )])

    def reload(self):
        ...


class PortTreeWidget(pyqtgraph_widgets.TreeWidget.TreeWidget):
    @QtCore.Slot()
    def reorder(self):
        ...


class PortGraphControlWidget(QtWidgets.QWidget):
    '''
    The widget that contains the list of all the nodes in a flowchart and their
    controls, as well as buttons for loading/saving flowcharts.

    ((WIP reimplementation of FlowChartCtrlWidget))
    '''

    def __init__(self, chart):
        self.items = {}
        # self.loadDir = loadDir  ## where to look initially for chart files
        self.currentFileName = None
        super().__init__()
        self.chart = chart

        self.layout = QtWidgets.QGridLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setVerticalSpacing(0)

        self.reload_button = pyqtgraph_widgets.FeedbackButton.FeedbackButton(self)
        self.reload_button.setText('Reload')
        self.reload_button.setCheckable(False)
        self.reload_button.setFlat(False)
        self.layout.addWidget(self.reload_button, 4, 0, 1, 2)

        self.show_chart_button = QtWidgets.QPushButton(self)
        self.show_chart_button.setText('Show chart')
        self.show_chart_button.setCheckable(True)
        self.layout.addWidget(self.show_chart_button, 4, 2, 1, 2)

        self.tree = PortTreeWidget(self)
        self.tree.headerItem().setText(0, 'Port')
        self.tree.header().setVisible(False)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, self.tree.header().Stretch)
        self.layout.addWidget(self.tree, 3, 0, 1, 4)

        self.tree.setColumnCount(2)
        self.tree.setColumnWidth(1, 20)
        self.tree.setVerticalScrollMode(self.tree.ScrollPerPixel)
        self.tree.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff)

        self.chartWidget = FlowchartWidget(chart, self)
        # self.chartWidget.viewBox().autoRange()
        self.chart_window = QtGui.QMainWindow()
        self.chart_window.setWindowTitle('Flowchart')
        self.chart_window.setCentralWidget(self.chartWidget)
        self.chart_window.resize(1000, 800)

        self.tree.itemChanged.connect(self.itemChanged)
        self.show_chart_button.toggled.connect(self.chartToggled)
        self.reload_button.clicked.connect(self.reloadClicked)

    def chartToggled(self, b):
        if b:
            self.chart_window.show()
        else:
            self.chart_window.hide()

    def reloadClicked(self):
        try:
            self.chartWidget.reloadLibrary()
            self.reload_button.success('Reloaded.')
        except Exception:
            self.reload_button.success('Error.')
            raise

    def itemChanged(self, *args):
        pass

    def scene(self):
        return self.chartWidget.scene()

    def viewBox(self):
        return self.chartWidget.viewBox()

    def nodeRenamed(self, node, oldName):
        self.items[node].setText(0, node.name())

    def addNode(self, node):
        ctrl = node.ctrlWidget()
        item = QtGui.QTreeWidgetItem([node.name(), '', ''])
        self.tree.addTopLevelItem(item)

        if ctrl is not None:
            item2 = QtGui.QTreeWidgetItem()
            item.addChild(item2)
            self.tree.setItemWidget(item2, 0, ctrl)

        self.items[node] = item

    def removeNode(self, node):
        if node in self.items:
            item = self.items[node]
            self.tree.removeTopLevelItem(item)

    def chartWidget(self):
        return self.chartWidget

    def outputChanged(self, data):
        pass

    def clear(self):
        self.chartWidget.clear()

    def select(self, node):
        item = self.items[node]
        self.tree.setCurrentItem(item)


class PortGraphFlowchart(Flowchart):
    def __init__(self, detector, library):
        super().__init__(terminals={},
                         library=library)

        # Unused input/output widgets:
        for node in (self.inputNode, self.outputNode):
            self.removeNode(node)

        self.port_dict = None
        self.digraph = None
        self.detector = detector
        self.nodes = {}
        self._widget = None

    def widget(self):
        """Return the control widget for this flowchart.

        This widget provides GUI access to the parameters for each node and a
        graphical representation of the flowchart.
        """
        if self._widget is None:
            self._widget = PortGraphControlWidget(self)
            self.scene = self._widget.scene()
            self.viewBox = self._widget.viewBox()
        return self._widget

    def add_port(self, name, plugin, pos):
        has_input = not isinstance(plugin, CamBase)
        node = PortNode(name, has_input=has_input)
        self.addNode(node, name, pos)
        return node

    @property
    def cameras(self):
        'All camera port names'
        return [port
                for port, plugin in self.port_dict.items()
                if isinstance(plugin, CamBase)]

    def read_ports(self):
        'Read the port digraph/dictionary from the detector'
        self.detector.wait_for_connection()
        self.digraph, self.port_dict = self.detector.get_asyn_digraph()

        self.nodes = {
            port: {'position': pos}
            for port, pos in
            position_nodes(self.digraph, self.port_dict).items()
        }

        for port, plugin in sorted(self.port_dict.items()):
            node_info = self.nodes[port]
            node_info['node'] = self.add_port(port, plugin,
                                              node_info['position'])

        for src, dest in self.digraph.edges:
            self.connectTerminals(self.nodes[src]['node']['Out'],
                                  self.nodes[dest]['node']['In'])

        # for port in self.cameras:
        #     cam = self.nodes[port]['node']
        #     cam.setInput(Out='test')


def position_nodes(digraph, port_dict, *, x_spacing=PortNodeItem.WIDTH * 1.5,
                   y_spacing=PortNodeItem.HEIGHT * 1.5, x=0, y=0):
    '''
    Generate an (x, y) position dictionary for all nodes in the port dictionary

    Parameters
    ----------
    digraph : networkx.Digraph
    port_dict : dict
        Dictionary of port name to ophyd plugin
    x_spacing : float, optional
        Horizontal spacing between items
    y_spacing : float, optional
        Horizontal spacing between items
    x : float, optional
        Starting x position
    y : float, optional
        Starting y position
    '''
    def position_port(port, x, y):
        positions[port] = (x, y)
        dests = [dest for src, dest in digraph.edges
                 if src == port]
        y -= y_spacing * (len(dests) // 2)
        for idx, dest in enumerate(sorted(dests)):
            position_port(dest, x + x_spacing, y + idx * y_spacing)

    cameras = [port for port, cam in port_dict.items()
               if isinstance(cam, CamBase)]

    start_x = x
    positions = {}

    # Start with all of the cameras and the plugins connected
    for camera in sorted(cameras):
        position_port(camera, x, y)
        x = start_x
        y = y_spacing + max(y for x, y in positions.values())

    # Add any ports that are otherwise unconnected
    x = start_x
    y = y_spacing + max(y for x, y in positions.values())

    for port in port_dict:
        if port not in positions:
            position_port(port, x, y)

    return positions


def test():
    class Detector(SimDetector):
        plugins = Cpt(CommonPlugins_V32, '')

    det = Detector(prefix='13SIM1:', name='det')

    fc = PortGraphFlowchart(detector=det, library=Library())

    fc.read_ports()

    w = fc.widget()
    # layout.addWidget(fc.widget(), 0, 0, 2, 1)
    # win.show()
    w.show()


if __name__ == '__main__':
    import sys
    app = QtGui.QApplication([])

    win = QtGui.QMainWindow()
    cw = QtGui.QWidget()
    win.setCentralWidget(cw)
    layout = QtGui.QGridLayout()
    cw.setLayout(layout)

    test()
    if sys.flags.interactive != 1:
        QtGui.QApplication.instance().exec_()
