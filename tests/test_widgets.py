############
# Standard #
############

############
# External #
############
from ophyd.tests.conftest import using_fake_epics_pv

###########
# Package #
###########
from typhon.display import ComponentButton
from .conftest import show_widget


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
