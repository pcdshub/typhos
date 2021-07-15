import logging

import pytest
from ophyd import Component as Cpt
from ophyd import Device, Signal

from typhos.related_display import TyphosRelatedSuiteButton

logger = logging.getLogger(__name__)


@pytest.fixture(scope='function')
def suite_button(happi_cfg):
    button = TyphosRelatedSuiteButton()
    button.happi_cfg = happi_cfg
    return button


class Dummy(Device):
    sig1 = Cpt(Signal, value=1)
    sig2 = Cpt(Signal, value='two')


def test_create_suite_happi(suite_button):
    logger.debug('Make sure we can load a suite using happi.')
    suite_button.devices = ['test_motor', 'test_device']
    suite_button.create_suite()
    # TODO check that this suite has test_motor and test_device represented


def test_create_suite_add_devices(suite_button):
    logger.debug('Make sure we can load a suite using add_devices.')
    dev1 = Dummy(name='dummy1')
    dev2 = Dummy(name='dummy2')
    suite_button.add_device(dev1)
    suite_button.add_device(dev2)
    # TODO check that this suite has dev1 and dev2 represented


def test_preload(suite_button):
    logger.debug('Make sure preload preloads.')
    dev1 = Dummy(name='dummy1')
    suite_button.add_device(dev1)
    suite_button.preload = True
    assert suite_button._suite is not None


# TODO add the show window decorator
def test_show_suite(suite_button):
    logger.debug('Make sure no exception is raised when we show a suite.')
    dev1 = Dummy(name='dummy1')
    suite_button.add_device(dev1)
    suite_button.show_suite()
