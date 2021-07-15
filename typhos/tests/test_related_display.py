import logging

import pytest
from ophyd import Component as Cpt
from ophyd import Device, Signal

from typhos.related_display import TyphosRelatedSuiteButton

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
    suite_button.devices = ['test_motor', 'test_device']
    suite = suite_button.create_suite()
    qtbot.addWidget(suite)
    # TODO check that this suite has test_motor and test_device represented


def test_create_suite_add_devices(qtbot, suite_button):
    logger.debug('Make sure we can load a suite using add_devices.')
    dev1 = Dummy(name='dummy1')
    dev2 = Dummy(name='dummy2')
    suite_button.add_device(dev1)
    suite_button.add_device(dev2)
    suite = suite_button.create_suite()
    qtbot.addWidget(suite)
    # TODO check that this suite has dev1 and dev2 represented


def test_preload(suite_button):
    logger.debug('Make sure preload preloads.')
    dev1 = Dummy(name='dummy1')
    suite_button.add_device(dev1)
    suite_button.preload = True
    assert suite_button._suite is not None


# TODO add the show window decorator
def test_show_suite(qtbot, suite_button):
    logger.debug('Make sure no exception is raised when we show a suite.')
    dev1 = Dummy(name='dummy1')
    suite_button.add_device(dev1)
    suite = suite_button.create_suite()
    qtbot.addWidget(suite)
    suite_button.show_suite()
