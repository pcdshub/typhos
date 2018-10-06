from typhon.device import TyphonPanel
from typhon.utils import clean_attr
from .conftest import show_widget


@show_widget
def test_device_panel(device):
    device.name ='test'
    panel = TyphonPanel.from_device(device, methods=[device.insert,
                                                     device.remove])
    assert panel.title.lower() == 'test'
    # We have all our signals
    shown_read_sigs = list(panel.read_panel.signals.keys())
    assert all([clean_attr(sig) in shown_read_sigs
                for sig in device.read_attrs])
    shown_cfg_sigs = list(panel.config_panel.signals.keys())
    assert all([clean_attr(sig) in shown_cfg_sigs
                for sig in device.configuration_attrs])
    # The method panel is visible
    assert not panel.method_panel.isHidden()
    # Assert we have all our specified functions
    assert 'insert' in panel.method_panel.methods
    assert 'remove' in panel.method_panel.methods
    return panel


@show_widget
def test_device_with_images(test_images):
    (lenna, python) = test_images
    # Create a display with our image
    panel = TyphonPanel(name="Image Test", image=lenna)
    assert panel.image_widget.filename == lenna
    # Add our python image
    panel.add_image(python)
    assert panel.image_widget.filename == python
    return panel
