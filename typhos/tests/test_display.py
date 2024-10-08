from __future__ import annotations

from pathlib import Path

import ophyd
import pytest
from pydm import Display

import typhos.display
from typhos import utils
from typhos.display import DisplayTypes, get_template_display_type

from . import conftest
from .conftest import show_widget


@pytest.fixture(scope='function')
def display(request, qtbot):
    display = typhos.display.TyphosDeviceDisplay()
    display.setObjectName(display.objectName() + request.node.nodeid)
    qtbot.addWidget(display)
    yield display


@pytest.fixture(scope='function', params=[False, True])
def show_switcher(request):
    return request.param


@show_widget
def test_device_title(device, motor, show_switcher, qtbot, request):
    title = typhos.display.TyphosDisplayTitle(show_switcher=show_switcher)
    qtbot.add_widget(title)

    title.setObjectName(title.objectName() + request.node.nodeid)


@show_widget
def test_device_display(device, motor, qtbot, request):
    def signals_from_panel(panel_name):
        panel_widget = getattr(panel.display_widget, panel_name)
        return set(panel_widget.layout().signals)

    def signals_from_device(device, kinds):
        def filter_by(sig):
            if sig.item.kind == ophyd.Kind.omitted:
                return False
            return sig.item.kind in kinds

        return {
            sig.name for sig in
            utils.get_all_signals_from_device(device, filter_by=filter_by)
        }

    def check_hint_panel(device):
        device_signals = signals_from_device(device, ophyd.Kind.hinted)
        if 'motor_setpoint' in device_signals:
            # Signal is renamed and not reflected here
            device_signals.remove('motor_setpoint')
            device_signals.add('motor')
        assert device_signals == signals_from_panel('hint_panel')

    def check_read_panel(device):
        device_signals = signals_from_device(device, ophyd.Kind.normal)
        assert device_signals == signals_from_panel('normal_panel')

    def check_config_panel(device):
        device_signals = signals_from_device(device, ophyd.Kind.config)
        assert device_signals == signals_from_panel('config_panel')

    print("Creating signal panel")
    panel = typhos.display.TyphosDeviceDisplay.from_device(motor)
    panel.setObjectName(panel.objectName() + request.node.nodeid)
    panel.force_template = utils.ui_dir / "core" / "detailed_screen.ui"
    qtbot.addWidget(panel)
    check_hint_panel(motor)
    check_read_panel(motor)
    check_config_panel(motor)

    device.name = 'test'
    print("Adding a new device")
    panel.add_device(device)
    check_read_panel(device)
    check_config_panel(device)
    print("Done, returning panel", panel)
    return panel


def test_display_without_md(motor, display):
    # Add a generic motor
    display.add_device(motor)
    assert display.devices[0] == motor
    assert display.current_template == display.templates['detailed_screen'][0]


def test_display_with_md(motor, display):
    screen = 'engineering_screen.ui'
    display.add_device(
        motor, macros={'detailed_screen': screen})
    display.load_best_template()
    assert display.current_template.name == screen
    assert display.templates['detailed_screen'][0].name == screen


def test_display_type_change(motor, display):
    # Changing template type changes template
    display.add_device(motor)
    display.display_type = display.embedded_screen
    assert display.current_template == display.templates['embedded_screen'][0]


def test_display_modified_templates(display, motor):
    display.add_device(motor)
    eng_ui = display.templates['engineering_screen']
    display.templates['embedded_screen'] = eng_ui
    display.display_type = display.embedded_screen
    assert display.current_template == eng_ui[0]


def test_display_force_template(display, motor):
    # Check that we use the forced template
    display.add_device(motor)
    to_force = display.templates['engineering_screen'][0]
    display.force_template = to_force
    # Top-level screens always get detailed tree if nothing else is available
    assert display.force_template.name == to_force.name
    assert display.current_template.name == to_force.name


def test_display_with_channel(client, qtbot):
    panel = typhos.display.TyphosDeviceDisplay()
    qtbot.addWidget(panel)
    panel.channel = 'happi://test_motor'
    assert panel.channel == 'happi://test_motor'

    def device_added():
        assert len(panel.devices) == 1

    qtbot.wait_until(device_added)


def test_display_device_class_property(motor, display, qtbot):
    qtbot.add_widget(display)
    assert display.device_class == ''
    display.add_device(motor)
    assert display.device_class == 'ophyd.sim.SynAxis'


def test_display_device_name_property(motor, display, qtbot):
    qtbot.add_widget(display)
    assert display.device_name == ''
    display.add_device(motor)
    assert display.device_name == motor.name


def test_display_with_py_file(display, motor, qtbot):
    qtbot.add_widget(display)
    py_file = str(conftest.MODULE_PATH / 'utils' / 'display.py')
    display.add_device(motor, macros={'detailed_screen': py_file})
    display.load_best_template()
    assert isinstance(display.display_widget, Display)
    assert getattr(display.display_widget, 'is_from_test_file', False)


def test_display_with_sig_template(display, device, qapp, qtbot):
    qtbot.add_widget(display)
    display.force_template = str(conftest.MODULE_PATH / 'utils' / 'sig.ui')
    display.add_device(device)
    qapp.processEvents()
    for num in range(10):
        device.setpoint.put(num)
        qapp.processEvents()
        assert display.display_widget.ui.setpoint.text() == str(num)


@pytest.mark.parametrize(
    "path, expected",
    [
        (Path("typhos/ui/core/detailed_screen.ui"), DisplayTypes.detailed_screen),
        (Path("typhos/ui/core/detailed_tree.ui"), DisplayTypes.detailed_screen),
        (Path("typhos/ui/core/embedded_screen.ui"), DisplayTypes.embedded_screen),
        (Path("typhos/ui/core/engineering_screen.ui"), DisplayTypes.engineering_screen),
        (Path("typhos/ui/devices/PositionerBase.detailed.ui"), DisplayTypes.detailed_screen),
        (Path("typhos/ui/devices/PositionerBase.embedded.ui"), DisplayTypes.embedded_screen),
        (Path("user/module/Potato.embedded.ui"), DisplayTypes.embedded_screen),
        (Path("user/module/Potato.detailed.ui"), DisplayTypes.detailed_screen),
        (Path("user/module/Potato.engineering.ui"), DisplayTypes.engineering_screen),
        (Path("user/module/enigma.ui"), ValueError),
        (Path("user/module/not_very_detailed.ui"), ValueError),
    ]
)
def test_get_template_display_type(path: Path, expected: DisplayTypes | Exception):
    if issubclass(expected, Exception):
        with pytest.raises(expected):
            get_template_display_type(path)
    else:
        assert get_template_display_type(path) == expected


def test_display_effective_display_type(display, device, qapp, qtbot):
    qtbot.add_widget(display)
    assert display.effective_display_type == display.display_type
    display.force_template = str(conftest.MODULE_PATH / 'utils' / 'sig.ui')
    assert display.effective_display_type == display.display_type
    display.force_template = str(conftest.MODULE_PATH.parent / 'ui' / 'core' / 'embedded_screen.ui')
    assert display.effective_display_type == DisplayTypes.embedded_screen
    display.force_template = str(conftest.MODULE_PATH.parent / 'ui' / 'core' / 'detailed_tree.ui')
    assert display.effective_display_type == DisplayTypes.detailed_screen
    display.force_template = str(conftest.MODULE_PATH.parent / 'ui' / 'core' / 'engineering_screen.ui')
    assert display.effective_display_type == DisplayTypes.engineering_screen
