import types

import pytest

import happi
from happi.loader import from_container
from typhos.tools import TyphosConsole


def test_base_console(qtbot):
    tc = TyphosConsole()
    qtbot.addWidget(tc)
    assert tc.kernel.kernel_manager.is_alive()
    tc.shutdown()
    assert not tc.kernel.kernel_manager.is_alive()
    tc.shutdown()


@pytest.mark.timeout(30)
@pytest.mark.xfail
def test_add_device(qapp, qtbot):
    # Create a device and attach metadata
    md = happi.Device(name='Test This', prefix='Tst:This:1', beamline='TST',
                      device_class='types.SimpleNamespace', args=list(),
                      kwargs={'here': 'very unique text'})
    device = from_container(md)
    # Add the device to the Console
    tc = TyphosConsole.from_device(device)
    qtbot.addWidget(tc)
    # Check that we created the object in the shell
    tc.kernel.kernel_client.execute('print(test_this.here)', silent=False)
    while md.kwargs['here'] not in tc.kernel._control.toPlainText():
        qapp.processEvents()
    # Smoke test not happi Device
    tc.add_device(types.SimpleNamespace(hi=3))
    tc.shutdown()
