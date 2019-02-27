import logging
import os
import threading

from pyqtgraph.flowchart import (Flowchart, Node, NodeGraphicsItem,
                                 FlowchartWidget)
from pyqtgraph.flowchart.library import NodeLibrary
import pyqtgraph.widgets as qtg_widgets

from qtpy import QtWidgets, QtGui, QtCore

from ophyd import SimDetector, Component as Cpt, CommonPlugins_V32, CamBase


logger = logging.getLogger(__name__)


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
        return {'Out': 0}

    def processBypassed(self, args):
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


class PortTreeWidget(qtg_widgets.TreeWidget.TreeWidget):
    @QtCore.Slot()
    def reorder(self):
        ...


class PortGraphControlWidget(QtWidgets.QWidget):
    '''
    The widget that contains the list of all the nodes in a flowchart and their
    controls, as well as buttons for loading/saving flowcharts.

    '''
    # ((WIP reimplementation of FlowChartCtrlWidget))

    def __init__(self, chart):
        self.items = {}
        # self.loadDir = loadDir  ## where to look initially for chart files
        self.currentFileName = None
        super().__init__()
        self.chart = chart

        self.layout = QtWidgets.QGridLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setVerticalSpacing(0)

        self.reload_button = qtg_widgets.FeedbackButton.FeedbackButton(self)
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


class PortGraphMonitor(QtCore.QObject):
    edge_added = QtCore.Signal(str, str)
    edge_removed = QtCore.Signal(str, str)
    port_added = QtCore.Signal(str)
    port_removed = QtCore.Signal(str)
    update = QtCore.Signal(list, list, list, list)

    def __init__(self, detector, parent=None):
        super().__init__(parent=parent)
        self.digraph = None
        self.port_dict = {}
        self.edges = set()
        self.positions = {}
        self.detector = detector
        self._subscriptions = {}
        self.lock = threading.Lock()

    @property
    def cameras(self):
        'All camera port names'
        return [port
                for port, plugin in self.port_dict.items()
                if isinstance(plugin, CamBase)]

    def _port_changed_callback(self, value=None, obj=None, **kwargs):
        logger.debug('Source port of %s changed to %s', obj.name, value)
        self.update_ports()

    def update_ports(self):
        'Read the port digraph/dictionary from the detector and emit updates'
        self.detector.wait_for_connection()
        digraph, port_dict = self.detector.get_asyn_digraph()

        with self.lock:
            for port, plugin in sorted(port_dict.items()):
                if (port not in self._subscriptions and
                        hasattr(plugin, 'nd_array_port')):
                    logger.debug('Subscribing to port %s (%s) NDArrayPort',
                                 port, plugin.name)
                    self._subscriptions[port] = plugin.nd_array_port.subscribe(
                        self._port_changed_callback, run=False)
                # plugin_type, ad_core_version, driver_version

            edges = list(sorted(digraph.edges))
            ports_removed = list(sorted(set(self.port_dict) - set(port_dict)))
            ports_added = list(sorted(set(port_dict) - set(self.port_dict)))
            edges_removed = list(sorted(set(self.edges) - set(edges)))
            edges_added = list(sorted((set(edges) - set(self.edges))))

            self.digraph = digraph
            self.edges = edges
            self.port_dict.clear()
            self.port_dict.update(**port_dict)

            for port in ports_removed:
                sub = self._subscriptions.pop(port, None)
                if sub is not None:
                    plugin = port_dict[port].nd_array_port.unsubscribe(sub)

        for port in ports_removed:
            self.port_removed.emit(port)

        for port in ports_added:
            self.port_added.emit(port)

        for src, dest in edges_removed:
            self.edge_removed.emit(src, dest)

        for src, dest in edges_added:
            self.edge_added.emit(src, dest)

        if ports_removed or ports_added or edges_removed or edges_added:
            self.update.emit(ports_removed, ports_added, edges_removed,
                             edges_added)


class PortGraphFlowchart(Flowchart):
    def __init__(self, detector, library):
        super().__init__(terminals={},
                         library=library)
        self._widget = None

        # Unused input/output widgets:
        for node in (self.inputNode, self.outputNode):
            self.removeNode(node)

        self.monitor = PortGraphMonitor(detector, parent=self)

        self.monitor.update.connect(self._ports_updated)
        self._nodes = {}
        self._edges = set()
        self._auto_position = True

    def _ports_updated(self, ports_removed, ports_added, edges_removed,
                       edges_added):
        self.port_dict = self.monitor.port_dict

        for src, dest in edges_removed:
            try:
                src_node = self._nodes[src]['node']
                dest_node = self._nodes[dest]['node']
            except KeyError:
                logger.debug('Edge removed that did not connect a known port, '
                             'likely in error: %s -> %s', src, dest)
                continue

            src_node['Out'].disconnectFrom(dest_node['In'])
            self._edges.remove((src, dest))

        for port in ports_removed:
            node = self._nodes.pop(port)
            node.disconnectAll()
            self.removeNode(node)

        for port in ports_added:
            plugin = self.port_dict[port]
            self._nodes[port] = dict(node=self.add_port(port, plugin),
                                     plugin=plugin)

        for src, dest in edges_added:
            try:
                src_node = self._nodes[src]['node']
                dest_node = self._nodes[dest]['node']
            except KeyError:
                # Scenarios:
                #  1. Invalid port name used
                #  2. Associated plugin missing from the Detector class
                logger.debug('Edge added to unknown port: %s -> %s', src, dest)
                continue

            try:
                if src_node != dest_node:
                    self.connectTerminals(src_node['Out'], dest_node['In'])
            except Exception:
                logger.exception('Failed to connect terminals %s -> %s', src,
                                 dest)

            self._edges.add((src, dest))

        if self._auto_position:
            positions = position_nodes(self._edges, self.port_dict)
            for port, (px, py) in positions.items():
                node = self._nodes[port]['node']
                node.graphicsItem().setPos(px, py)

            self.widget().chartWidget.view.scale(1, 1)

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

    def add_port(self, name, plugin, pos=None):
        has_input = not isinstance(plugin, CamBase)
        node = PortNode(name, has_input=has_input)
        self.addNode(node, name, pos=pos)
        return node


def position_nodes(edges, port_dict, *, x_spacing=PortNodeItem.WIDTH * 1.5,
                   y_spacing=PortNodeItem.HEIGHT * 1.5, x=0, y=0):
    '''
    Generate an (x, y) position dictionary for all nodes in the port dictionary

    Parameters
    ----------
    edges : list of (src, dest)
        Digraph edges that connect source -> destination ports
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
        dests = [dest for src, dest in edges
                 if src == port
                 and src != dest]
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
    if positions:
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

    fc.monitor.update_ports()

    w = fc.widget()
    # layout.addWidget(fc.widget(), 0, 0, 2, 1)
    # win.show()
    w.show()


if __name__ == '__main__':
    import sys
    logging.basicConfig()
    logger.setLevel('DEBUG')
    app = QtGui.QApplication([])

    win = QtGui.QMainWindow()
    cw = QtGui.QWidget()
    win.setCentralWidget(cw)
    layout = QtGui.QGridLayout()
    cw.setLayout(layout)

    test()
    if sys.flags.interactive != 1:
        QtGui.QApplication.instance().exec_()
