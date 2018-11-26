import os.path
from typhon import TyphonDisplay
from typhon.utils import clean_attr
from .conftest import show_widget


@show_widget
def test_device_display(device, motor, qtbot):
    panel = TyphonDisplay.from_device(motor)
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


def test_device_display_templates(motor, qtbot):
    panel = TyphonDisplay()
    qtbot.addWidget(panel)
    # Add a generic motor
    panel.add_device(motor)
    assert panel.devices[0] == motor
    assert panel.current_template == panel.default_templates['detailed_screen']
    # Changing template type changes template
    panel.template_type = panel.embedded_screen
    assert panel.current_template == panel.default_templates['embedded_screen']
    # Force a specific template
    eng_ui = panel.default_templates['engineering_screen']
    panel.use_template = eng_ui
    assert panel.use_template == eng_ui
    assert panel.current_template == eng_ui
    # Check that if we pass in a template as macros we use the forced template
    panel.load_template(macros={'embedded_screen': 'tst.ui'})
    assert panel.current_template == eng_ui
    panel.use_default_templates = True
    panel.use_template = ''
    panel.load_template(macros={'embedded_screen': 'tst.ui'})
    assert panel.current_template == panel.default_templates['embedded_screen']


def test_display_with_channel(client, qtbot):
    panel = TyphonDisplay()
    qtbot.addWidget(panel)
    panel.channel = 'happi://test_motor'
    assert panel.channel == 'happi://test_motor'
    assert len(panel.devices) == 1
