from uuid import uuid4

from happi.item import HappiItem
from happi.loader import from_container
from ophyd import Device, Component as Cpt
from ophyd.utils.epics_pvs import AlarmSeverity
import pytest

from typhos.alarm import (TyphosAlarmCircle, TyphosAlarmRectangle,
                          TyphosAlarmTriangle, TyphosAlarmEllipse,
                          TyphosAlarmPolygon, AlarmLevel)
from typhos.plugins.core import register_signal
from typhos.plugins.happi import register_client, HappiClientState

from .conftest import show_widget, RichSignal


@pytest.fixture(
    scope='function',
    params=(
        TyphosAlarmCircle,
        TyphosAlarmRectangle,
        TyphosAlarmTriangle,
        TyphosAlarmEllipse,
        TyphosAlarmPolygon,
        ),
    )
def alarm(qtbot, request):
    alarm_widget = request.param()
    alarm_widget.kindLevel = alarm_widget.KindLevel.HINTED
    qtbot.addWidget(alarm_widget)
    return alarm_widget


class SimpleDevice(Device):
    hint_sig = Cpt(RichSignal, kind='hinted')
    norm_sig = Cpt(RichSignal, kind='normal')
    conf_sig = Cpt(RichSignal, kind='config')
    omit_sig = Cpt(RichSignal, kind='omitted')


@pytest.fixture(scope='function')
def device():
    return SimpleDevice(name='simple_' + str(uuid4()))


@pytest.fixture(scope='function')
def alarm_add_device(alarm, device, qtbot):
    with qtbot.wait_signal(alarm.alarm_changed, timeout=1000):
        alarm.add_device(device)
    return alarm


@show_widget
def test_alarm_basic(alarm):
    assert alarm.alarm_summary == AlarmLevel.DISCONNECTED


def test_alarm_add_device_basic(alarm_add_device):
    assert alarm_add_device.alarm_summary == AlarmLevel.NO_ALARM


alarm_cases = [
    ({'connected': False}, AlarmLevel.DISCONNECTED),
    ({'severity': AlarmSeverity.MINOR}, AlarmLevel.MINOR),
    ({'severity': AlarmSeverity.MAJOR}, AlarmLevel.MAJOR),
    ({'severity': AlarmSeverity.INVALID}, AlarmLevel.INVALID),
    ]


@pytest.mark.parametrize("metadata,response", alarm_cases)
def test_one_alarm_add_device(
        alarm_add_device, device, qtbot, metadata, response
        ):
    alarm = alarm_add_device

    with qtbot.wait_signal(alarm.alarm_changed, timeout=1000):
        device.hint_sig.update_metadata(metadata)

    assert alarm.alarm_summary == response


@pytest.mark.parametrize("metadata,response", alarm_cases)
def test_one_alarm_sig_ch(alarm, qtbot, metadata, response):
    name = 'one_sig_ch_' + str(uuid4())
    sig = RichSignal(name=name)
    register_signal(sig)

    with qtbot.wait_signal(alarm.alarm_changed, timeout=1000):
        alarm.channel = 'sig://' + name

    with qtbot.wait_signal(alarm.alarm_changed, timeout=1000):
        sig.update_metadata(metadata)

    assert alarm.alarm_summary == response


@pytest.fixture(scope='function')
def fake_client():
    old_client = HappiClientState.client
    client = FakeClient()
    register_client(client)
    yield client
    register_client(old_client)


class FakeClient:
    def find_device(self, *args, name, **kwargs):
        return HappiItem(
            name=name,
            device_class='typhos.tests.test_alarm.SimpleDevice',
            kwargs={'name': '{{name}}'},
            )


@pytest.mark.parametrize("metadata,response", alarm_cases)
def test_one_alarm_happi_ch(alarm, qtbot, metadata, response, fake_client):
    name = 'happi_test_device_' + str(uuid4()).replace('-', '_')
    item = fake_client.find_device(name=name)
    device = from_container(item)

    alarm.channel = 'happi://' + name

    with qtbot.wait_signal(alarm.alarm_changed, timeout=1000):
        device.hint_sig.update_metadata(metadata)

    assert alarm.alarm_summary == response


def test_kinds_many_alarms_add_device(alarm_add_device, device, qtbot):
    alarm = alarm_add_device

    device.hint_sig.update_metadata({'severity': AlarmSeverity.NO_ALARM})
    device.norm_sig.update_metadata({'severity': AlarmSeverity.MINOR})
    device.conf_sig.update_metadata({'severity': AlarmSeverity.MAJOR})
    device.omit_sig.update_metadata({'severity': AlarmSeverity.INVALID})

    assert alarm.alarm_summary == AlarmLevel.NO_ALARM

    # Step up the KindLevel and watch the alarm change
    with qtbot.wait_signal(alarm.alarm_changed, timeout=1000):
        alarm_add_device.kindLevel = alarm.KindLevel.NORMAL

    assert alarm.alarm_summary == AlarmLevel.MINOR

    with qtbot.wait_signal(alarm.alarm_changed, timeout=1000):
        alarm_add_device.kindLevel = alarm.KindLevel.CONFIG

    assert alarm.alarm_summary == AlarmLevel.MAJOR

    with qtbot.wait_signal(alarm.alarm_changed, timeout=1000):
        alarm_add_device.kindLevel = alarm.KindLevel.OMITTED

    assert alarm.alarm_summary == AlarmLevel.INVALID

    # Disconnect the no_alarm signal to look for a response
    with qtbot.wait_signal(alarm.alarm_changed, timeout=1000):
        device.hint_sig.update_metadata({'connected': False})

    assert alarm.alarm_summary == AlarmLevel.DISCONNECTED
