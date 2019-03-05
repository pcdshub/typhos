import pytest
from qtpy import QtCore

from typhon.port_graph import PortGraphFlowchart


@pytest.fixture(scope='function')
def fake_detector():
    try:
        from ophyd import (SimDetector, CommonPlugins, SimDetectorCam,
                           Component as Cpt, select_version)
        from ophyd.sim import make_fake_device
    except ImportError as ex:
        pytest.skip(f'ophyd version not compatible ({ex})')

    CommonPlugins_V32 = select_version(CommonPlugins, (3, 2))

    class Detector(SimDetector, CommonPlugins_V32):
        cam = Cpt(SimDetectorCam, 'cam1:')
        cam2 = Cpt(SimDetectorCam, 'cam2:')

    FakeDetector = make_fake_device(Detector)
    det = FakeDetector('13SIM1:', name='det')

    for dotted, subdev in sorted(det.walk_subdevices(include_lazy=True)):
        if hasattr(subdev, 'nd_array_port'):
            subdev.port_name.sim_put(subdev.dotted_name)
            subdev.nd_array_port.sim_put('cam')
        elif hasattr(subdev, 'port_name'):
            subdev.port_name.sim_put(subdev.dotted_name)

    return det


@pytest.fixture(scope='function')
def port_graph(qtbot, fake_detector):
    widget = PortGraphFlowchart(fake_detector)
    qtbot.addWidget(widget)
    return widget


@pytest.fixture(scope='function')
def monitor(port_graph):
    return port_graph.monitor


@pytest.fixture(scope='function')
def control_widget(port_graph):
    'PortGraphControlWidget'
    return port_graph.widget()


@pytest.fixture(scope='function')
def chart_widget(control_widget):
    'PortGraphFlowchartWidget'
    return control_widget.chartWidget


def test_monitor(monitor):
    assert not monitor._port_map
    monitor.update_port_map()
    print(list(sorted(monitor.port_map.keys())))
    assert monitor._port_map == monitor.port_map
    assert len(monitor._port_map) == len(monitor.port_information)
    assert monitor.cameras == ['cam', 'cam2']
    # Default configuration: all plugins connected to cam
    # Subtract 2 for: cam and cam2
    assert len(monitor.get_edges()) == (len(monitor.port_map) - 2)


def test_monitor_sources(monitor):
    # connected to itself
    with pytest.raises(ValueError):
        monitor.set_new_source('tiff1', 'tiff1')

    # invalid source/dest port
    with pytest.raises(ValueError):
        monitor.set_new_source('ab', 'cd')

    # no input on cams
    with pytest.raises(ValueError):
        monitor.set_new_source('tiff1', 'cam')

    # actually modify the graph: roi1 -> tiff1
    monitor.set_new_source('roi1', 'tiff1')
    assert ('roi1', 'tiff1') in monitor.get_edges()


def test_add_edge(qtbot, monitor, port_graph):
    reload_graph(qtbot, port_graph)
    monitor.set_new_source('roi1', 'tiff1')
    reload_graph(qtbot, port_graph)


def test_add_then_remove_edge(qtbot, monitor, port_graph):
    reload_graph(qtbot, port_graph)
    monitor.set_new_source('roi1', 'tiff1')
    reload_graph(qtbot, port_graph)
    monitor.set_new_source('cam', 'tiff1')
    reload_graph(qtbot, port_graph)


def reload_graph(qtbot, port_graph):
    control_widget = port_graph.widget()
    qtbot.mouseClick(control_widget.reload_button, QtCore.Qt.LeftButton)
    qtbot.waitSignal(port_graph.flowchart_updated)


def test_graph_basic(qtbot, fake_detector, port_graph):
    reload_graph(qtbot, port_graph)


def test_graph_bad_edge(qtbot, fake_detector, port_graph):
    fake_detector.tiff1.nd_array_port.sim_put('UNKNOWN')
    reload_graph(qtbot, port_graph)


def test_graph_cycle(qtbot, fake_detector, port_graph):
    fake_detector.tiff1.nd_array_port.sim_put('tiff1')
    reload_graph(qtbot, port_graph)


def get_node(port_graph, node_name):
    return port_graph._port_nodes[node_name]['node']


def test_graph_select_node(qtbot, fake_detector, port_graph, chart_widget):
    reload_graph(qtbot, port_graph)

    item = get_node(port_graph, 'cam').graphicsItem()
    qtbot.waitSignal(port_graph.flowchart_updated)

    item.setSelected(True)
    chart_widget.selectionChanged()
    item.setSelected(False)
    chart_widget.selectionChanged()


class FakeDragEvent:
    def __init__(self, pos, scene_pos, *, button=QtCore.Qt.LeftButton,
                 finish=False):
        self._button = button
        self._finish = finish
        self._pos = pos
        self._scene_pos = scene_pos
        self._accepted = False
        self._ignored = False

    def pos(self):
        return self._pos

    def scenePos(self):
        return self._scene_pos

    def button(self):
        return self._button

    def isStart(self):
        return not self._finish

    def isFinish(self):
        return self._finish

    def accept(self):
        self._accepted = True

    def ignore(self):
        self._ignored = True


def test_graph_connect_output_to_input(qtbot, fake_detector, port_graph,
                                       chart_widget):
    reload_graph(qtbot, port_graph)

    cam_node = get_node(port_graph, 'cam')
    cam_out = cam_node['Out']._graphicsItem
    tiff_node = get_node(port_graph, 'tiff1')
    tiff_in = tiff_node['In']._graphicsItem

    ev = FakeDragEvent(scene_pos=cam_out.scenePos(), pos=cam_out.pos())
    cam_out.mouseDragEvent(ev)

    ev = FakeDragEvent(scene_pos=tiff_in.scenePos(), pos=tiff_in.pos(),
                       finish=True,
                       )
    cam_out.mouseDragEvent(ev)

    # TODO: this does not find the tiff_in terminal, somehow (see coverage)
