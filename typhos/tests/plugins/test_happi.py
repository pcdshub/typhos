import importlib
import sys
from unittest.mock import Mock, patch

import happi
import ophyd
import pydm
import pytest
from pytestqt.qtbot import QtBot

import typhos
import typhos.plugins
from typhos.plugins.happi import HappiPlugin
from typhos.widgets import HappiChannel


@pytest.fixture(scope="function")
def happi_plugin() -> HappiPlugin:
    # This uses the global HappiPlugin - other tests may leak and cause this to
    # fail:
    hp = pydm.data_plugins.plugin_for_address("happi://")
    if hp is None:
        raise RuntimeError("Unable to get happi plugin")

    assert isinstance(hp, HappiPlugin)
    # So nuke its state (this is the test suite after all):
    hp.connections.clear()
    hp.channels.clear()
    return hp


def test_connection(
    qtbot: QtBot,
    happi_plugin: HappiPlugin,
    client: happi.Client,
):
    # Starting conditions
    assert happi_plugin.connections == {}

    # Register a channel and check we received object and metadata
    mock = Mock()
    hc = HappiChannel(address='happi://test_device', tx_slot=mock)
    hc.connect()

    assert set(happi_plugin.channels) == {hc}

    def mock_called():
        assert mock.called

    qtbot.wait_until(mock_called)

    tx = mock.call_args[0][0]
    assert isinstance(tx['obj'], ophyd.sim.SynAxis)
    assert isinstance(tx['md'], dict)
    # Add another object and check that the connection does refire
    mock2 = Mock()
    hc2 = HappiChannel(address='happi://test_device', tx_slot=mock2)
    hc2.connect()

    assert set(happi_plugin.channels) == {hc, hc2}

    def mock2_called():
        assert mock2.called

    qtbot.wait_until(mock2_called)
    mock.assert_called_once()
    # Disconnect

    hc.disconnect()
    hc2.disconnect()
    assert happi_plugin.connections == {}


def test_connection_for_child(
    qtbot: QtBot,
    client: happi.Client,
    happi_plugin: HappiPlugin,
):
    mock = Mock()
    hc = HappiChannel(address='happi://test_motor.setpoint', tx_slot=mock)
    hc.connect()

    def mock_called():
        assert mock.called

    qtbot.wait_until(mock_called)
    tx = mock.call_args[0][0]
    assert tx['obj'].name == 'test_motor_setpoint'


def test_bad_address_smoke(client: happi.Client):
    hc = HappiChannel(address='happi://not_a_device', tx_slot=lambda x: None)
    hc.connect()


def test_happi_is_optional():
    with patch.dict(sys.modules, {'happi': None}):
        importlib.reload(typhos.plugins)
        importlib.reload(typhos)
        assert sys.modules['happi'] is None
