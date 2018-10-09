import types
import happi
from happi.loader import from_container
from typhon.tools import TyphonConsole

from .conftest import show_widget


def test_base_console():
    tc = TyphonConsole()
    assert tc.kernel_manager.is_alive()


@show_widget
def test_add_device(qapp):
    # Create a device and attach metadata
    md = happi.Device(name='Test This', prefix='Tst:This:1', beamline='TST',
                      device_class='types.SimpleNamespace', args=list(),
                      kwargs={'here': 'very unique text'})
    device = from_container(md)
    # Add the device to the Console
    tc = TyphonConsole.from_device(device)
    # Check that we created the object in the shell
    tc.kernel_client.execute('print(test_this.here)', silent=False)
    while 'In [' not in tc._control.toPlainText():
        qapp.processEvents()
    assert md.kwargs['here'] in tc._control.toPlainText()
    # Smoke test not happi Device
    tc.add_device(types.SimpleNamespace(hi=3))
    return tc
