'''
Very confusing widget overview:

PortNode(Node)
|- ._graphicsItem = PortNodeItem(NodeGraphicsItem)

PortGraphMonitor(QObject):
|- .detector = ophyd.Detector
|- + signals for updates

PortGraphFlowchart(Flowchart)        <-- The chart, created first
|- .monitor = PortGraphMonitor
|- ._widget = PortGraphControlWidget

FlowchartWidget(DockArea)            <-- Dock with info about selection
PortGraphFlowchartWidget(FlowchartWidget)
|- .chart = PortGraphFlowchart
|- .ctrl = PortGraphControlWidget
|- .hoverItem = ...
|- .view = FlowchartGraphicsView
|- .hoverText = QTextEdit
|- .selInfo = QWidget
|- ._scene => .view.scene()
|- ._viewBox => .view.viewBox()

PortGraphControlWidget(QWidget)     <-- Widget with tree
|   Reimplementation of FlowChartCtrlWidget
|- .tree = PortTreeWidget
|- .reload_button = FeedbackButton
|- .chartWidget = PortGraphFlowchartWidget
'''
import collections
import logging
import threading
import types

from pyqtgraph.flowchart import (Flowchart, Node, NodeGraphicsItem,
                                 FlowchartWidget, Terminal,
                                 TerminalGraphicsItem, ConnectionItem)
from pyqtgraph.flowchart.library import NodeLibrary
import pyqtgraph.widgets as qtg_widgets

from qtpy import QtWidgets, QtCore

from ophyd import (SimDetector, CommonPlugins, CamBase, select_version)


logger = logging.getLogger(__name__)


class PortTerminal(Terminal):
    def __init__(self, node, name, io, optional=False, multi=False, pos=None,
                 renamable=False, removable=False, multiable=False,
                 bypass=None):
        super().__init__(node, name, io, optional=optional, multi=multi,
                         pos=pos, renamable=renamable, removable=removable,
                         multiable=multiable, bypass=bypass)

        def mouse_drag_event(tgi, ev):
            if ev.button() != QtCore.Qt.LeftButton:
                ev.ignore()
                return

            ev.accept()
            if ev.isStart():
                if tgi.newConnection is None:
                    tgi.newConnection = ConnectionItem(tgi)
                    tgi.getViewBox().addItem(tgi.newConnection)
                tgi.newConnection.setTarget(tgi.mapToView(ev.pos()))
            elif ev.isFinish():
                if tgi.newConnection is not None:
                    items = tgi.scene().items(ev.scenePos())
                    targets = [item for item in items
                               if isinstance(item, TerminalGraphicsItem)]
                    if not targets:
                        tgi.newConnection.close()
                        tgi.newConnection = None
                        return

                    target = targets[0]
                    tgi.newConnection.setTarget(target)
                    a_term = tgi.term
                    b_term = target.term
                    a_node, a_name, a_term = (a_term.node(),
                                              a_term.node().name(),
                                              a_term.name())
                    b_node, b_name, b_term = (b_term.node(),
                                              b_term.node().name(),
                                              b_term.name())
                    if a_term == 'In' and b_term == 'Out':
                        b_node.connection_drawn.emit(b_name, a_name)
                    elif a_term == 'Out' and b_term == 'In':
                        a_node.connection_drawn.emit(a_name, b_name)
                    else:
                        logger.error('Cannot connect %s.%s to %s.%s',
                                     a_name, a_term, b_name, b_term)
                    # tgi.scene().removeItem(tgi.newConnection)
                    tgi.newConnection.close()
                    tgi.newConnection = None
            else:
                if tgi.newConnection is not None:
                    tgi.newConnection.setTarget(tgi.mapToView(ev.pos()))

        # Monkey-patch because we're animals:
        self._graphicsItem.mouseDragEvent = types.MethodType(
            mouse_drag_event, self._graphicsItem)

        # Alternatives: either re-implement __init__, or nuke the graphicsItem
        # and re-create it...


class PortNodeItem(NodeGraphicsItem):
    'The scene graphics item associated with one AreaDetector PortNode'
    WIDTH = 100
    HEIGHT = 40

    def __init__(self, node):
        super().__init__(node)
        # Shrink the vertical size a bit:
        self.bounds = QtCore.QRectF(0, 0, self.WIDTH, self.HEIGHT)

        # Do not allow ports to be renamed:
        self.nameItem.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)

    def mouseClickEvent(self, ev):
        if int(ev.button()) != int(QtCore.Qt.RightButton):
            super().mouseClickEvent(ev)
        else:
            ev.ignore()


class PortNode(Node):
    'A graph node representing one AreaDetector port'
    nodeName = 'PortNode'
    connection_drawn = QtCore.Signal(str, str)

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

    def addTerminal(self, name, **opts):
        """Add a new terminal to this Node with the given name.

        Notes
        -----
        Extra keyword arguments are passed to Terminal.__init__.
        Causes sigTerminalAdded to be emitted.
        """
        name = self.nextTerminalName(name)
        term = PortTerminal(self, name, **opts)
        self.terminals[name] = term
        if term.isInput():
            self._inputs[name] = term
        elif term.isOutput():
            self._outputs[name] = term
        self.graphicsItem().updateTerminals()
        self.sigTerminalAdded.emit(self, term)
        return term

    def graphicsItem(self):
        if self._graphicsItem is None:
            self._graphicsItem = PortNodeItem(self)
        return self._graphicsItem


class Library(NodeLibrary):
    'Container for AreaDetector port graphs which contain only PortNodes'
    def __init__(self):
        super().__init__()
        self.addNodeType(PortNode, [('AreaDetector', )])

    def reload(self):
        ...


class PortTreeWidget(QtWidgets.QTreeWidget):
    'Tree representation of AreaDetector port graph'
    def __init__(self, chart, parent=None):
        super().__init__(parent=parent)
        self.chart = chart
        self.port_to_item = {}
        self.chart.flowchart_updated.connect(self._chart_updated)
        self.setDragEnabled(True)
        self.setDragDropMode(self.InternalMove)

    def dropEvent(self, ev):
        super().dropEvent(ev)
        dragged_to = self.itemAt(ev.pos())
        source_port = dragged_to.text(0)
        dest_port = self.currentItem().text(0)
        self.chart.monitor.set_new_source(source_port, dest_port)

    def _chart_updated(self):
        root = self.invisibleRootItem()
        for item in self.port_to_item.values():
            parent = (root if item.parent() is None
                      else item.parent())
            parent.takeChild(parent.indexOfChild(item))

        monitor = self.chart.monitor
        edges = monitor.edges
        cams = monitor.cameras
        for cam in cams:
            item = self.port_to_item[cam]
            self.addTopLevelItem(item)

        for src, dest in sorted(edges):
            src_item = self.port_to_item[src]
            dest_item = self.port_to_item[dest]

            old_parent = dest_item.parent()
            if old_parent is not None:
                old_parent.removeChild(dest_item)
            src_item.addChild(dest_item)

        for item in self.port_to_item.values():
            item.setExpanded(True)


class PortGraphFlowchartWidget(FlowchartWidget):
    def __init__(self, chart, ctrl):
        super().__init__(chart, ctrl)
        self.hoverDock.setVisible(False)

    def selectionChanged(self):
        items = self._scene.selectedItems()
        if len(items) == 0 or not hasattr(items[0], 'node'):
            self.selectedTree.setData(None, hideRoot=True)
            return

        node = items[0].node
        self.ctrl.select(node)

        inputs = [conn.node().name()
                  for input in node.inputs().values()
                  for conn in input.connections()]

        monitor = self.chart.monitor
        port_info = monitor.port_information.get(node.name(), {})

        connectivity = {}
        connectivity['Input'] = inputs[0] if inputs else 'N/A'

        outputs = [conn.node().name()
                   for output in node.outputs().values()
                   for conn in output.connections()]

        # But multiple outputs
        connectivity.update(**{f'Output{idx}': output for idx, output
                               in enumerate(outputs, 1)})

        self.selNameLabel.setText(node.name())
        self.selDescLabel.setText(
            f"<b>{node.nodeName}</b>: {node.__class__.__doc__}"
        )

        # if node.exception is not None:
        #     data['exception'] = node.exception

        data = {'Version': port_info,
                'Connectivity': connectivity
                }
        self.selectedTree.setData(data, hideRoot=True)

    def hoverOver(self, items):
        ...
        # Hiding the hover information for now - any ideas for usage?


class PortGraphControlWidget(QtWidgets.QWidget):
    '''
    The widget that contains the list of all the nodes in a flowchart and their
    controls, as well as buttons for loading/saving flowcharts.
    '''

    def __init__(self, chart):
        self.port_to_item = {}
        self.currentFileName = None
        super().__init__()
        self.chart = chart

        layout = QtWidgets.QGridLayout(self)
        self.layout = layout
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setVerticalSpacing(0)

        reload_button = qtg_widgets.FeedbackButton.FeedbackButton(self)
        self.reload_button = reload_button
        reload_button.setText('Reload')
        reload_button.setCheckable(False)
        reload_button.setFlat(False)
        layout.addWidget(reload_button, 1, 0, 1, 4)

        tree = PortTreeWidget(chart, self)
        self.tree = tree
        tree.headerItem().setText(0, 'Port')
        tree.header().setVisible(False)
        tree.header().setStretchLastSection(False)
        tree.header().setSectionResizeMode(0, tree.header().Stretch)
        layout.addWidget(tree, 0, 0, 1, 4)

        tree.setColumnCount(2)
        tree.setColumnWidth(1, 20)
        tree.setVerticalScrollMode(tree.ScrollPerPixel)
        tree.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.chartWidget = PortGraphFlowchartWidget(chart, self)
        layout.addWidget(self.chartWidget, 0, 4, 4, 1)
        # self.chartWidget.viewBox().autoRange()

        tree.itemChanged.connect(self.itemChanged)
        reload_button.clicked.connect(self.reloadClicked)

    def reloadClicked(self):
        try:
            self.chart.monitor.update_ports()
        except Exception:
            self.reload_button.failure('Error.')
            logger.exception('Failed to reload')
        else:
            self.reload_button.success('Reloaded.')

    def itemChanged(self, *args):
        pass

    def scene(self):
        return self.chartWidget.scene()

    def viewBox(self):
        return self.chartWidget.viewBox()

    def nodeRenamed(self, node, oldName):
        self.port_to_item[node.name()].setText(0, node.name())

    def addNode(self, node):
        ctrl = node.ctrlWidget()
        item = QtWidgets.QTreeWidgetItem([node.name()])
        self.tree.addTopLevelItem(item)

        if ctrl is not None:
            item2 = QtWidgets.QTreeWidgetItem()
            item.addChild(item2)
            self.tree.setItemWidget(item2, 0, ctrl)

        self.tree.port_to_item[node.name()] = item

    def removeNode(self, node):
        try:
            item = self.tree.port_to_item.pop(node.name())
        except KeyError:
            ...
        else:
            parent = (item.parent()
                      if item.parent() is not None
                      else self.tree.invisibleRootItem())
            parent.takeChild(parent.indexOfChild(item))

    def chartWidget(self):
        return self.chartWidget

    def outputChanged(self, data):
        pass

    def clear(self):
        self.chartWidget.clear()

    def select(self, node):
        item = self.tree.port_to_item[node.name()]
        self.tree.setCurrentItem(item)


class PortGraphMonitor(QtCore.QObject):
    '''Monitors the connectivity of all AreaDetector ports in a detector

    Parameters
    ----------
    detector : ophyd.Detector
        The detector to monitor
    parent : QtCore.QObject, optional
        The parent widget

    Attributes
    ----------
    edge_added : Signal
        An edge was added between (src, dest)
    edge_removed : Signal
        An edge was removed between (src, dest)
    port_added : Signal
        A port was added with name (port_name, )
    update : Signal
        A full batch update including all edges added and removed, ports added
        and removed, with the signature (ports_removed, ports_added,
        edges_removed, edges_added), all of which are lists of strings.
    '''
    edge_added = QtCore.Signal(str, str)
    edge_removed = QtCore.Signal(str, str)
    port_added = QtCore.Signal(str)
    port_removed = QtCore.Signal(str)
    update = QtCore.Signal(list, list, list, list)
    port_information_attrs = ['plugin_type', 'ad_core_version',
                              'driver_version']

    def __init__(self, detector, parent=None):
        super().__init__(parent=parent)
        self.known_ports = []
        self.edges = set()
        self.positions = {}
        self.detector = detector
        self.lock = threading.Lock()
        self._port_map = {}
        self._subscriptions = {}

    def update_port_map(self):
        'Update the port map'
        self.detector.wait_for_connection()
        self._port_map = self.detector.get_asyn_port_dictionary()
        self._port_information = {port: self.get_port_information(port)
                                  for port in self._port_map
                                  }

    @property
    def port_map(self):
        'Port map of {port_name: ophyd_plugin}'
        if not self._port_map:
            self.update_port_map()
        return dict(self._port_map)

    @property
    def port_information(self):
        'Map of {port_name: dict(information_key=...)}'
        if not self._port_map:
            self.update_port_map()
        return dict(self._port_information)

    def get_port_information(self, port):
        'Get information on a specific port/plugin'
        info = {}
        plugin = self.port_map[port]
        for attr in self.port_information_attrs:
            try:
                info[attr] = getattr(plugin, attr).get()
            except AttributeError:
                ...
        return info

    def get_edges(self):
        '''Get an updated list of the directed graph edges

        Returns
        -------
        edges : list
            List of (src, dest)
        '''
        edges = set()
        for out_port, cpt in self.port_map.items():
            try:
                in_port = cpt.nd_array_port.get()
            except AttributeError:
                ...
            else:
                edges.add((in_port, out_port))

        return edges

    def set_new_source(self, source_port, dest_port):
        '''Set a new source port for a plugin

        Parameters
        ----------
        source_port : str
            The source port (e.g., CAM1)
        dest_port : str
            The destination port (e.g., ROI1)
        '''
        logger.info('Attempting to connect %s -> %s', source_port, dest_port)
        try:
            source_plugin = self.port_map[source_port]
            dest_plugin = self.port_map[dest_port]
        except KeyError as ex:
            raise ValueError(
                f'Invalid source/destination port: {ex}') from None

        if source_plugin == dest_plugin or source_port == dest_port:
            raise ValueError('Cannot connect a port to itself')

        try:
            signal = dest_plugin.nd_array_port
        except AttributeError:
            raise ValueError(f'Destination plugin {dest_plugin} does not '
                             f'have an input')
        else:
            signal.put(source_port, wait=False)

    @property
    def cameras(self):
        'All camera port names'
        return [port
                for port, plugin in self.port_map.items()
                if isinstance(plugin, CamBase)]

    def _port_changed_callback(self, value=None, obj=None, **kwargs):
        logger.debug('Source port of %s changed to %s', obj.name, value)
        self.update_ports()

    def update_ports(self):
        'Read the port digraph/dictionary from the detector and emit updates'
        port_map = self.port_map
        edges = self.get_edges()

        with self.lock:
            for port, plugin in sorted(port_map.items()):
                if (port not in self._subscriptions and
                        hasattr(plugin, 'nd_array_port')):
                    logger.debug('Subscribing to port %s (%s) NDArrayPort',
                                 port, plugin.name)
                    self._subscriptions[port] = plugin.nd_array_port.subscribe(
                        self._port_changed_callback, run=False)

            ports_removed = list(sorted(set(self.known_ports) - set(port_map)))
            ports_added = list(sorted(set(port_map) - set(self.known_ports)))
            edges_removed = list(sorted(set(self.edges) - set(edges)))
            edges_added = list(sorted((set(edges) - set(self.edges))))

            self.edges = edges
            self.known_ports = list(port_map)

            for port in ports_removed:
                sub = self._subscriptions.pop(port, None)
                if sub is not None:
                    plugin = port_map[port].nd_array_port.unsubscribe(sub)

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
    '''
    A flow chart representing one AreaDetector's port connectivity

    Parameters
    ----------
    detector : ophyd.Detector
        The detector to monitor
    parent : QtCore.QObject, optional
        The parent widget
    '''

    flowchart_updated = QtCore.Signal()

    def __init__(self, detector, *, library=None):
        if library is None:
            library = Library()

        super().__init__(terminals={}, library=library)
        # Through some strange __init__ mechanism, the associated
        # PortGraphControlWidget actually gets created by this point.

        # Unused input/output widgets:
        for node in (self.inputNode, self.outputNode):
            self.removeNode(node)

        self.monitor = PortGraphMonitor(detector, parent=self)
        self.monitor.update.connect(self._ports_updated)

        self._port_nodes = {}
        self._edges = set()
        self._auto_position = True

    def _ports_updated(self, ports_removed, ports_added, edges_removed,
                       edges_added):
        self.port_map = self.monitor.port_map

        for src, dest in edges_removed:
            try:
                src_node = self._port_nodes[src]['node']
                dest_node = self._port_nodes[dest]['node']
            except KeyError:
                logger.debug('Edge removed that did not connect a known port, '
                             'likely in error: %s -> %s', src, dest)
                continue

            src_node['Out'].disconnectFrom(dest_node['In'])
            self._edges.remove((src, dest))

        for port in ports_removed:
            node = self._port_nodes.pop(port)
            node.disconnectAll()
            self.removeNode(node)

        for port in ports_added:
            plugin = self.port_map[port]
            self._port_nodes[port] = dict(node=self.add_port(port, plugin),
                                          plugin=plugin)

        for src, dest in edges_added:
            try:
                src_node = self._port_nodes[src]['node']
                dest_node = self._port_nodes[dest]['node']
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

        control_widget = self.widget()

        if self._auto_position:
            positions = position_nodes(self._edges, self.port_map)
            for port, (px, py) in positions.items():
                node = self._port_nodes[port]['node']
                node.graphicsItem().setPos(px, py)

            control_widget.chartWidget.view.scale(1, 1)

        self.flowchart_updated.emit()

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
        node.connection_drawn.connect(self.monitor.set_new_source)
        self.addNode(node, name, pos=pos)
        return node


def position_nodes(edges, port_map, *, x_spacing=PortNodeItem.WIDTH * 1.5,
                   y_spacing=PortNodeItem.HEIGHT * 1.5, x=0, y=0):
    '''
    Generate an (x, y) position dictionary for all nodes in the port dictionary

    Parameters
    ----------
    edges : list of (src, dest)
        Directed graph edges that connect source -> destination ports
    port_map : dict
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
        if y < y_minimum[x]:
            y = y_minimum[x]

        y_minimum[x] = y + y_spacing

        positions[port] = (x, y)
        dests = [dest for src, dest in edges
                 if src == port
                 and src != dest]
        y -= y_spacing * (len(dests) // 2)
        for idx, dest in enumerate(sorted(dests)):
            position_port(dest, x + x_spacing, y + idx * y_spacing)

    cameras = [port for port, cam in port_map.items()
               if isinstance(cam, CamBase)]

    y_minimum = collections.defaultdict(lambda: -len(port_map) * y_spacing)

    start_x = x
    positions = {}

    def get_next_y():
        if positions:
            return y_spacing + max(y for x, y in positions.values())
        else:
            return 0

    # Start with all of the cameras and the plugins connected
    for camera in sorted(cameras):
        position_port(camera, start_x, get_next_y())

    # Add any ports that are otherwise unconnected
    for port in port_map:
        if port not in positions:
            position_port(port, start_x, get_next_y())

    return positions
