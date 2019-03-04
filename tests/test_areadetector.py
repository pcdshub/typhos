import pytest
from qtpy import QtCore

from typhon.port_graph import PortGraphFlowchart


@pytest.fixture(scope='function')
def fake_detector():
    try:
        from ophyd import (SimDetector, CommonPlugins, select_version)
        from ophyd.sim import make_fake_device
    except ImportError as ex:
        pytest.skip(f'ophyd version not compatible ({ex})')

    CommonPlugins_V32 = select_version(CommonPlugins, (3, 2))

    class Detector(SimDetector, CommonPlugins_V32):
        ...

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


def test_monitor(monitor):
    assert not monitor._port_map
    monitor.update_port_map()
    print(list(sorted(monitor.port_map.keys())))
    assert monitor._port_map == monitor.port_map
    assert len(monitor._port_map) == len(monitor.port_information)
    assert len(monitor.get_edges()) == (len(monitor.port_map) - 1)



def test_graph_smoke(qtbot, fake_detector, port_graph):
    control_widget = port_graph.widget()
    qtbot.mouseClick(control_widget.reload_button, QtCore.Qt.LeftButton)
    qtbot.waitSignal(port_graph.flowchart_updated)
