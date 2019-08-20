import os.path

import pytest

from pydm import Display
from typhon import TyphonDeviceDisplay
from typhon.utils import clean_attr

from .conftest import show_widget


@pytest.fixture(scope='function')
def display(qtbot):
    display = TyphonDeviceDisplay()
    qtbot.addWidget(display)
    return display


@show_widget
def test_device_display(device, motor, qtbot):
    panel = TyphonDeviceDisplay.from_device(motor)
    panel_main = panel._main_widget
    qtbot.addWidget(panel)
    # We have all our signals
    shown_read_sigs = list(panel_main.read_panel.layout().signals.keys())
    assert all([clean_attr(sig) in shown_read_sigs
                for sig in motor.read_attrs])
    shown_cfg_sigs = list(panel_main.config_panel.layout().signals.keys())
    assert all([clean_attr(sig) in shown_cfg_sigs
                for sig in motor.configuration_attrs])
    # Check that we can add multiple devices
    device.name ='test'
    panel.add_device(device)
    panel_main = panel._main_widget
    assert panel_main.ui.name_label.text() == 'test'
    # We have all our signals
    shown_read_sigs = list(panel_main.read_panel.layout().signals.keys())
    assert all([clean_attr(sig) in shown_read_sigs
                for sig in device.read_attrs])
    shown_cfg_sigs = list(panel_main.config_panel.layout().signals.keys())
    assert all([clean_attr(sig) in shown_cfg_sigs
                for sig in device.configuration_attrs])
    return panel


def test_display_with_md(motor, display):
    display.load_template(macros={'detailed_screen': 'tst.ui'})
    assert display.templates['detailed_screen'] == 'tst.ui'


def test_display_type_change(display):
    # Changing template type changes template
    display.display_type = display.embedded_screen
    assert display.current_template == display.templates['embedded_screen']


def test_display_modified_templates(display, motor):
    display.add_device(motor)
    eng_ui = display.templates['engineering_screen']
    display.templates['embedded_screen'] = eng_ui
    display.display_type = display.embedded_screen
    assert display.current_template == eng_ui


def test_display_force_template(display):
    # Check that we use the forced template
    display.force_template = 'tst.ui'
    assert display.force_template == 'tst.ui'
    assert display.current_template == 'tst.ui'

def test_display_with_channel(client, qtbot):
    panel = TyphonDeviceDisplay()
    qtbot.addWidget(panel)
    panel.channel = 'happi://test_motor'
    assert panel.channel == 'happi://test_motor'
    assert len(panel.devices) == 1


def test_display_device_class_property(motor, display):
    assert display.device_class == ''
    display.add_device(motor)
    assert display.device_class == 'ophyd.sim.SynAxis'


def test_display_device_name_property(motor, display):
    assert display.device_name == ''
    display.add_device(motor)
    assert display.device_name == motor.name


def test_display_with_py_file(display):
    py_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'utils/display.py')
    display.force_template = py_file
    display.load_template()
    assert isinstance(display._main_widget, Display)
    assert getattr(display._main_widget, 'is_from_test_file', False)


@pytest.mark.parametrize('display_type',
                         tuple(TyphonDeviceDisplay.TemplateEnum))
def test_display_template_property_getters(display, display_type):
    attr = display_type.name.replace('screen', 'template')
    template = getattr(display, attr)
    assert template == display.templates[display_type.name]


@pytest.mark.parametrize('display_type',
                         tuple(TyphonDeviceDisplay.TemplateEnum))
def test_display_template_property_setters(display, display_type):
    attr = display_type.name.replace('screen', 'template')
    setattr(display, attr, 'tst.ui')
    assert display.templates[display_type.name] == 'tst.ui'


def test_display_template_change(display):
    display.display_type = display.embedded_screen
    new_template = display.templates['engineering_screen']
    display.embedded_template = new_template
    assert display.current_template == new_template
    assert display._main_widget.ui_filename() == new_template
