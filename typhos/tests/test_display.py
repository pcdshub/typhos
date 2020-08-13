import ophyd
import pytest
from pydm import Display

import typhos.display
from typhos import utils

from . import conftest
from .conftest import show_widget


@pytest.fixture(scope='function')
def display(qtbot):
    display = typhos.display.TyphosDeviceDisplay()
    qtbot.addWidget(display)
    return display


@pytest.fixture(scope='function', params=[False, True])
def show_switcher(request):
    return request.param


@show_widget
def test_device_title(device, motor, show_switcher, qtbot):
    typhos.display.TyphosDisplayTitle(show_switcher=show_switcher)


@show_widget
def test_device_display(device, motor, qtbot):
    def signals_from_panel(panel_name):
        panel_widget = getattr(panel.display_widget, panel_name)
        return set(panel_widget.layout().signals)

    def signals_from_device(device, kinds):
        def filter_by(sig):
            if sig.item.kind == ophyd.Kind.omitted:
                return False
            return sig.item.kind in kinds

        return set(
            sig.name for sig in
            utils.get_all_signals_from_device(device, filter_by=filter_by)
        )

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

    panel = typhos.display.TyphosDeviceDisplay.from_device(
        motor, composite_heuristics=False)
    qtbot.addWidget(panel)
    check_hint_panel(motor)
    check_read_panel(motor)
    check_config_panel(motor)

    device.name = 'test'
    panel.add_device(device)
    check_read_panel(device)
    check_config_panel(device)
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
    display.force_template = display.templates['engineering_screen'][0]
    assert display.force_template.name == 'engineering_screen.ui'
    assert display.current_template.name == 'engineering_screen.ui'


def test_display_with_channel(client, qtbot):
    panel = typhos.display.TyphosDeviceDisplay()
    qtbot.addWidget(panel)
    panel.channel = 'happi://test_motor'
    assert panel.channel == 'happi://test_motor'

    def device_added():
        assert len(panel.devices) == 1

    qtbot.wait_until(device_added)


def test_display_device_class_property(motor, display):
    assert display.device_class == ''
    display.add_device(motor)
    assert display.device_class == 'ophyd.sim.SynAxis'


def test_display_device_name_property(motor, display):
    assert display.device_name == ''
    display.add_device(motor)
    assert display.device_name == motor.name


def test_display_with_py_file(display, motor):
    py_file = str(conftest.MODULE_PATH / 'utils' / 'display.py')
    display.add_device(motor, macros={'detailed_screen': py_file})
    display.load_best_template()
    assert isinstance(display.display_widget, Display)
    assert getattr(display.display_widget, 'is_from_test_file', False)
