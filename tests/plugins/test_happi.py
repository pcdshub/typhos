import os.path
import types
from unittest.mock import Mock

from happi import Client, Device
import pytest

from typhon.plugins.happi import HappiPlugin, HappiChannel, register_client


@pytest.fixture(scope='module')
def client():
    client = Client(path=os.path.join(os.path.dirname(__file__),
                                      'happi.json'))
    register_client(client)
    return client


def test_connection(client):
    hp = HappiPlugin()
    # Register a channel and check we received object and metadata
    mock = Mock()
    hc = HappiChannel(address='happi://test_device', tx_slot=mock)
    hp.add_connection(hc)
    assert mock.called
    tx = mock.call_args[0][0]
    assert isinstance(tx['obj'], types.SimpleNamespace)
    assert isinstance(tx['md'], Device)
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

def test_bad_address_smoke(client):
    hp = HappiPlugin()
    hc = HappiChannel(address='happi://not_a_device', tx_slot=lambda x: None)
    hp.add_connection(hc)
