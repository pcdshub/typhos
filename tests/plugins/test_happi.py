import importlib
import sys
import types
from unittest.mock import Mock, patch

from happi import Device
import pytest

import typhon
import typhon.plugins
from typhon.plugins.happi import HappiPlugin, HappiChannel



def test_connection(client):
    hp = HappiPlugin()
    # Register a channel and check we received object and metadata
    mock = Mock()
    hc = HappiChannel(address='happi://test_device', tx_slot=mock)
    hp.add_connection(hc)
    assert mock.called
    tx = mock.call_args[0][0]
    assert isinstance(tx['obj'], types.SimpleNamespace)
    assert isinstance(tx['md'], dict)
    # Add another object and check that the connection does refire
    mock2 = Mock()
    hc2 = HappiChannel(address='happi://test_device', tx_slot=mock2)
    hp.add_connection(hc2)
    assert mock2.called
    mock.assert_called_once()
    # Disconnect
    hp.remove_connection(hc)
    hp.remove_connection(hc2)
    assert hp.connections == {}


def test_connection_for_child(client):
    hp = HappiPlugin()
    mock = Mock()
    hc = HappiChannel(address='happi://test_motor.setpoint', tx_slot=mock)
    hp.add_connection(hc)
    tx = mock.call_args[0][0]
    assert tx['obj'].name == 'test_motor_setpoint'


def test_bad_address_smoke(client):
    hp = HappiPlugin()
    hc = HappiChannel(address='happi://not_a_device', tx_slot=lambda x: None)
    hp.add_connection(hc)


def test_happi_is_optional():
    with patch.dict(sys.modules, {'happi': None}):
        importlib.reload(typhon.plugins)
        importlib.reload(typhon)
        assert sys.modules['happi'] is None
