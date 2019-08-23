import importlib
import sys
from unittest.mock import patch

import pytest

import typhon
import typhon.plugins
from typhon.widgets import TyphonDesignerMixin
from typhon.utils import TyphonBase


class TyphonDeviceWidget(TyphonBase, TyphonDesignerMixin):
    """Mock widget that tracks devices"""
    def __init__(self, **kwargs):
        self._md = list()
        super().__init__(**kwargs)

    def _receive_data(self, data=None, *args, **kwargs):
        super()._receive_data(data=data, *args, **kwargs)
        data = data or {}
        if data.get('metadata'):
            self._md.append(data['metadata'])


def test_connection(qtbot, client):
    widget = TyphonDeviceWidget()
    qtbot.addWidget(widget)
    widget.channel = 'happi://test_device'
    qtbot.waitUntil(lambda : widget._connected, 2000)
    assert widget.devices[0].name == 'test_device'
    assert widget._md[0]['name'] == 'test_device'


def test_repeated_connection(qtbot, client):
    widget = TyphonDeviceWidget()
    qtbot.addWidget(widget)
    widget.channel = 'happi://test_device'
    widget2 = TyphonDeviceWidget()
    qtbot.addWidget(widget2)
    widget2.channel = 'happi://test_device'
    assert len(widget.devices) == 1
    assert len(widget2.devices) == 1


def test_connection_for_child(qtbot, client):
    widget = TyphonDeviceWidget()
    qtbot.addWidget(widget)
    widget.channel = 'happi://test_motor.setpoint'
    qtbot.waitUntil(lambda : widget._connected, 2000)
    assert widget.devices[0].name == 'test_motor_setpoint'
    assert widget._md[0]['name'] == 'test_motor_setpoint'


def test_bad_address(qtbot, client):
    widget = TyphonDeviceWidget()
    qtbot.addWidget(widget)
    widget.channel = 'happi://not_a_device'
    assert widget._connected == False


def test_happi_is_optional():
    with patch.dict(sys.modules, {'happi': None}):
        importlib.reload(typhon.plugins)
        importlib.reload(typhon)
        assert sys.modules['happi'] is None
