import importlib
import sys
from unittest.mock import Mock, patch

import ophyd
import typhos
import typhos.plugins
from typhos.plugins.happi import HappiPlugin
from typhos.widgets import HappiChannel


def test_connection(qtbot, client):
    hp = HappiPlugin()
    # Register a channel and check we received object and metadata
    mock = Mock()
    hc = HappiChannel(address='happi://test_device', tx_slot=mock)
    hp.add_connection(hc)

    def mock_called():
        assert mock.called

    qtbot.wait_until(mock_called)

    tx = mock.call_args[0][0]
    assert isinstance(tx['obj'], ophyd.sim.SynAxis)
    assert isinstance(tx['md'], dict)
    # Add another object and check that the connection does refire
    mock2 = Mock()
    hc2 = HappiChannel(address='happi://test_device', tx_slot=mock2)
    hp.add_connection(hc2)

    def mock2_called():
        assert mock2.called

    qtbot.wait_until(mock2_called)
    mock.assert_called_once()
    # Disconnect
    hp.remove_connection(hc)
    hp.remove_connection(hc2)
    assert hp.connections == {}


def test_connection_for_child(qtbot, client):
    hp = HappiPlugin()
    mock = Mock()
    hc = HappiChannel(address='happi://test_motor.setpoint', tx_slot=mock)
    hp.add_connection(hc)

    def mock_called():
        assert mock.called

    qtbot.wait_until(mock_called)
    tx = mock.call_args[0][0]
    assert tx['obj'].name == 'test_motor_setpoint'


def test_bad_address_smoke(client):
    hp = HappiPlugin()
    hc = HappiChannel(address='happi://not_a_device', tx_slot=lambda x: None)
    hp.add_connection(hc)


def test_happi_is_optional():
    with patch.dict(sys.modules, {'happi': None}):
        importlib.reload(typhos.plugins)
        importlib.reload(typhos)
        assert sys.modules['happi'] is None
