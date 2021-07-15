import logging

import pytest
from ophyd import Component as Cpt
from ophyd import Device, Signal

from typhos.related_display import TyphosRelatedSuiteButton
from typhos.suite import TyphosSuite

from .conftest import show_widget

logger = logging.getLogger(__name__)


@pytest.fixture(scope='function')
def suite_button(qtbot, happi_cfg):
    button = TyphosRelatedSuiteButton()
    button.happi_cfg = happi_cfg
    qtbot.addWidget(button)
    return button


class Dummy(Device):
    sig1 = Cpt(Signal, value=1)
    sig2 = Cpt(Signal, value='two')


def test_create_suite_happi(qtbot, suite_button):
    logger.debug('Make sure we can load a suite using happi.')
    device_names = ['test_motor', 'test_device']
    suite_button.devices = device_names
    suite = suite_button.create_suite()
    qtbot.addWidget(suite)
    # Does the suite have the appropriate subdisplays?
    for name in device_names:
        assert suite.get_subdisplay(name.replace('_', ' ')).device_name == name


def test_create_suite_add_devices(qtbot, suite_button):
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


def test_preload(suite_button):
    logger.debug('Make sure preload preloads.')
    dev1 = Dummy(name='dummy1')
    suite_button.add_device(dev1)
    # A _suite should be created after preload is set
    assert suite_button._suite is None
    suite_button.preload = True
    assert isinstance(suite_button._suite, TyphosSuite)


@show_widget
def test_show_suite(qtbot, suite_button):
    logger.debug('Make sure no exception is raised when we show a suite.')
    dev1 = Dummy(name='dummy1')
    suite_button.add_device(dev1)
    suite = suite_button.create_suite()
    qtbot.addWidget(suite)
    suite_button.show_suite()
