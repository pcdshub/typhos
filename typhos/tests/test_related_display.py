import logging

import pytest
import pytestqt.qtbot
from ophyd import Component as Cpt
from ophyd import Device, Signal

from typhos.related_display import TyphosRelatedSuiteButton
from typhos.suite import TyphosSuite

from .conftest import show_widget

logger = logging.getLogger(__name__)


@pytest.fixture(scope='function')
def suite_button(qtbot: pytestqt.qtbot.QtBot, happi_cfg) -> TyphosRelatedSuiteButton:
    button = TyphosRelatedSuiteButton()
    button.happi_cfg = happi_cfg
    qtbot.addWidget(button)
    return button


class Dummy(Device):
    sig1 = Cpt(Signal, value=1)
    sig2 = Cpt(Signal, value='two')


def test_create_suite_happi(qtbot: pytestqt.qtbot.QtBot, suite_button: TyphosRelatedSuiteButton):
    logger.debug('Make sure we can load a suite using happi.')
    happi_names = ['test_motor', 'test_device']
    suite_button.happi_names = happi_names
    suite = suite_button.create_suite()
    qtbot.addWidget(suite)
    # Does the suite have the appropriate subdisplays?
    for name in happi_names:
        assert suite.get_subdisplay(name.replace('_', ' ')).device_name == name


def test_create_suite_add_devices(qtbot: pytestqt.qtbot.QtBot, suite_button: TyphosRelatedSuiteButton):
    logger.debug('Make sure we can load a suite using add_devices.')
    dev1 = Dummy(name='dummy1')
    dev2 = Dummy(name='dummy2')
    suite_button.add_device(dev1)
    suite_button.add_device(dev2)
    suite = suite_button.create_suite()
    qtbot.addWidget(suite)
    # Does the suite have the appropriate subdisplays?
    for device in (dev1, dev2):
        assert suite.get_subdisplay(device).device is device


def test_preload(qtbot: pytestqt.qtbot.QtBot, suite_button: TyphosRelatedSuiteButton):
    logger.debug('Make sure preload preloads.')
    dev1 = Dummy(name='dummy1')
    suite_button.add_device(dev1)
    # A _suite should be created after preload is set
    assert suite_button._suite is None
    suite_button.preload = True
    assert isinstance(suite_button._suite, TyphosSuite)
    qtbot.add_widget(suite_button._suite)


@show_widget
def test_show_suite(qtbot: pytestqt.qtbot.QtBot, suite_button: TyphosRelatedSuiteButton):
    logger.debug('Make sure no exception is raised when we show a suite.')
    dev1 = Dummy(name='dummy1')
    suite_button.add_device(dev1)
    suite = suite_button.create_suite()
    qtbot.addWidget(suite)
    suite_button.show_suite()


def test_suite_errors(suite_button: TyphosRelatedSuiteButton):
    logger.debug('Make sure we raise exceptions for bad inputs.')

    # No devices configured
    with pytest.raises(ValueError):
        suite_button.create_suite()

    # A device is misspelled
    suite_button.happi_names = ['test_motor', 'asdfasefasdc', 'test_device']
    with pytest.raises(ValueError):
        suite_button.get_happi_devices()
