import random

import numpy as np
import pydm.utilities
import pytest
from ophyd.signal import Signal
from ophyd.sim import (FakeEpicsSignal, FakeEpicsSignalRO, SynSignal,
                       SynSignalRO)
from pydm.widgets import PyDMEnumComboBox
from qtpy.QtWidgets import QWidget

from typhos import cache, utils
from typhos.panel import SignalPanel, TyphosSignalPanel
from typhos.widgets import (ImageDialogButton, WaveformDialogButton,
                            create_signal_widget)

from .conftest import DeadSignal, RichSignal, show_widget


@pytest.fixture(scope='function')
def type_cache():
    type_cache = cache.get_global_widget_type_cache()
    type_cache.clear()
    type_cache.describe_cache.clear()
    return type_cache


@pytest.fixture(scope='function')
def panel(qtbot, type_cache, monkeypatch):
    panel = SignalPanel()
    yield panel


@pytest.fixture(scope='function')
def typhos_signal_panel(qtbot, monkeypatch, type_cache):
    typhos_panel = TyphosSignalPanel()
    qtbot.addWidget(typhos_panel)
    yield typhos_panel


@pytest.fixture(scope='function')
def panel_widget(qtbot, panel):
    widget = QWidget()
    qtbot.addWidget(widget)
    widget.setLayout(panel)
    return widget


def wait_panel(qtbot, panel, signal_names):
    def condition(loaded_signals):
        return set(loaded_signals) == signal_names

    blocker = qtbot.wait_signal(panel.loading_complete,
                                check_params_cb=condition)
    blocker.wait()

    print()
    print('Panel loaded all required signals.', signal_names)
    print('Panel layout:')
    print(utils.dump_grid_layout(panel))
    print()


@show_widget
def test_panel_creation(qtbot, panel, panel_widget):
    standard = FakeEpicsSignal('Tst:Pv', name='standard')
    read_and_write = FakeEpicsSignal('Tst:Read', write_pv='Tst:Write',
                                     name='read_and_write')
    read_only = FakeEpicsSignalRO('Tst:Pv:RO', name='read_only')
    simulated = SynSignal(func=random.random, name='simul')
    simulated_ro = SynSignalRO(func=random.random, name='simul_ro')

    standard.sim_put(1)
    read_and_write.sim_put(2)
    read_only.sim_put(3)
    simulated.put(4)

    signals = {
        # Signal is its own write
        'Standard': standard,
        # Signal has separate write/read
        'Read and Write': read_and_write,
        'Read Only': read_only,
        'Simulated': simulated,
        'SimulatedRO': simulated_ro,
        'Array': Signal(name='array', value=np.ones((5, 10)))
    }

    for name, signal in signals.items():
        panel.add_signal(signal, name=name)

    wait_panel(
        qtbot, panel,
        signal_names=set(sig.name for sig in signals.values())
    )

    def widget_at(row, col):
        return panel.itemAtPosition(row, col).widget()

    # Check read-only channels do not have write widgets
    assert widget_at(2, 1) is widget_at(2, 2)
    assert widget_at(4, 1) is widget_at(4, 2)

    # Array widget has only a button, even when writable
    assert widget_at(5, 1) is widget_at(5, 2)

    # Check write widgets are present
    assert widget_at(0, 1) is not widget_at(0, 2)
    assert widget_at(1, 1) is not widget_at(1, 2)
    assert widget_at(3, 1) is not widget_at(3, 2)
    return panel_widget


def test_panel_add_enum(qtbot, panel, panel_widget):
    # Create an enum signal
    syn_sig = RichSignal(name='Syn:Enum', value=1)
    row = panel.add_signal(syn_sig, "Sim Enum PV")
    # Check our signal was added a QCombobox

    wait_panel(qtbot, panel, signal_names={syn_sig.name})

    def widget_at(row, col):
        print('** widget_at ** panel is', panel, panel.signals)
        return panel.itemAtPosition(row, col).widget()

    assert isinstance(widget_at(row, 2), PyDMEnumComboBox)
    return panel_widget


def test_add_dead_signal(qtbot, panel, panel_widget):
    dead_sig = DeadSignal(name='ded', value=0)
    panel.add_signal(dead_sig, 'Dead Signal')
    assert dead_sig.name in panel.signals


@pytest.mark.xfail(
    reason='PVs do not exist so widgets are not created post refactor')
def test_add_pv(qtbot, panel, panel_widget):
    row = panel.add_pv('Tst:A', 'Read Only')
    assert 'Read Only' in panel.signals

    def widget_at(row, col):
        return panel.itemAtPosition(row, col).widget()

    # Check read-only spans setpoint/readback cols
    assert widget_at(row, 1) is widget_at(row, 2)

    row = panel.add_pv('Tst:A', "Write", write_pv='Tst:B')
    # Since it is not connected, it should show just the loading widget
    assert widget_at(row, 1) is widget_at(row, 2)


@show_widget
def test_typhos_panel(qapp, client, qtbot, typhos_signal_panel):
    panel = typhos_signal_panel

    # Setting Kind without device doesn't explode
    panel.showConfig = False
    panel.showConfig = True
    # Add a device channel
    panel.channel = 'happi://test_device'
    assert panel.channel == 'happi://test_device'
    # Reset channel and no smoke comes out
    panel.channel = 'happi://test_motor'
    pydm.utilities.establish_widget_connections(panel)

    def have_device():
        assert len(panel.devices) == 1

    qtbot.wait_until(have_device)

    device = panel.devices[0]
    num_hints = len(device.hints['fields'])
    num_read = len(device.read_attrs)

    def get_visible_signals():
        return panel.layout().visible_signals

    # Check we got all our signals
    assert len(get_visible_signals()) == len(device.component_names)

    panel.showOmitted = False
    panel.showConfig = False
    panel.showNormal = False
    panel.showHints = True
    assert len(get_visible_signals()) == num_hints

    panel.showNormal = True
    panel.showHints = False
    assert len(get_visible_signals()) == num_read - num_hints

    panel.showHints = True
    assert len(get_visible_signals()) == num_read
    return panel


@show_widget
def test_typhos_panel_sort_by_name(qapp, client, qtbot, typhos_signal_panel):
    panel = typhos_signal_panel
    panel.sortBy = panel.SignalOrder.byName
    panel.channel = 'happi://test_motor'
    pydm.utilities.establish_widget_connections(panel)

    def have_device():
        assert len(panel.devices) == 1

    qtbot.wait_until(have_device)
    device = panel.devices[0]
    sorted_names = [
        getattr(device, attr).name
        for attr in sorted(device.component_names)
    ]
    assert list(panel.layout().signals.keys()) == sorted_names
    return typhos_signal_panel


@show_widget
def test_typhos_panel_sort_by_kind(qapp, client, qtbot, typhos_signal_panel):
    # TODO: do not currently support dynamic sort order changing; so these
    # tests have been split
    panel = typhos_signal_panel

    panel.sortBy = panel.SignalOrder.byKind
    panel.channel = 'happi://test_motor'
    pydm.utilities.establish_widget_connections(panel)

    def have_device():
        assert len(panel.devices) == 1

    qtbot.wait_until(have_device)
    key_order = list(panel.layout().signals.keys())
    assert key_order[0] == 'test_motor'
    assert key_order[-1] == 'test_motor_unused'
    return panel


@show_widget
def test_signal_widget_waveform(qtbot):
    signal = Signal(name='test_wave', value=np.zeros((4, )))
    widget = create_signal_widget(signal)
    qtbot.addWidget(widget)
    assert isinstance(widget, WaveformDialogButton)
    return widget


@show_widget
def test_signal_widget_image(qtbot):
    signal = Signal(name='test_img', value=np.zeros((400, 540)))
    widget = create_signal_widget(signal)
    qtbot.addWidget(widget)
    assert isinstance(widget, ImageDialogButton)
    return widget
