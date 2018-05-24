############
# Standard #
############

############
# External #
############
from ophyd.tests.conftest import using_fake_epics_pv
from pydm.PyQt.QtGui import QWidget

###########
# Package #
###########
from typhon.widgets import RotatingImage, TogglePanel, ComponentButton
from .conftest import show_widget


def test_toggle_panel_hide():
    # Create basic panel
    panel = TogglePanel("Test Panel")
    panel.contents = QWidget()
    panel.layout().addWidget(panel.contents)
    # Toggle the button
    panel.show_contents(False)
    assert panel.contents.isHidden()


@using_fake_epics_pv
@show_widget
def test_component_button_add_pv():
    button = ComponentButton("Test Device")
    button.add_pv("Tst:Pv", "Test PV")
    assert button.ui.button_frame.layout().count() == 4
    return button


@using_fake_epics_pv
def test_component_button_checked():
    button = ComponentButton("Test Device")
    style = button.styleSheet()
    # Check the button and watch the stylesheet change and the button register
    # as checked
    button.setChecked(True)
    assert 'cyan' in button.styleSheet()
    assert button.isChecked()
    # Uncheck the button and make sure we are no longer checked and the
    # stylesheet has returned to normal
    button.setChecked(False)
    assert not button.isChecked()
    assert button.styleSheet() == style


@show_widget
def test_rotating_image(test_images):
    (lenna, python) = test_images
    # Create widget
    img = RotatingImage()
    img.add_image(lenna, 'lenna')
    img.add_image(python, 'python')
    # Set image to Python
    img.show_image('lenna')
    # Check that we are viewing the "lenna" image
    assert img.currentWidget().filename == lenna
    return img
