############
# Standard #
############
import sys

###############
# Third Party #
###############
import ophyd
from pydm.widgets.base import PyDMWritableWidget
from pydm.PyQt.QtGui import QWidget

##########
# Module #
##########
from typhon.plugins import SignalConnection, ClassConnection
from typhon.plugins.core import obj_from_string

class WritableWidget(QWidget, PyDMWritableWidget):
    """Simple Testing Widget"""
    pass


def test_obj_from_string():
    obj = obj_from_string('io.StringIO', 'random text')
    assert obj.read() == 'random text'


def test_class_connection():
    # Create a basic object
    address = 'ophyd.Device|Tst:Motor:1|name=Test Motor'
    cc = ClassConnection(address, address)
    assert cc.obj.prefix == 'Tst:Motor:1'
    assert cc.obj.name == 'Test Motor'
    # Create an arg-less example, must be imported example
    sys.modules.pop('io')
    address = 'io.StringIO|random text'
    cc_arg_less = ClassConnection(address, address)
    assert cc_arg_less.obj.read() == 'random text'
    # Check we do not create a new device where not requested
    cc_in = ClassConnection.from_object(cc.obj)
    assert id(cc_in.obj) == id(cc.obj)


def test_signal_connection(qapp):
    # Create a signal and attach our listener
    sig = ophyd.Signal(name='my_signal', value=1)
    widget = WritableWidget()
    listener = widget.channels()[0]
    sig_conn = SignalConnection.from_object(sig)
    sig_conn.add_listener(listener)
    # Check that our widget receives the initial value
    qapp.processEvents()
    assert widget.value == 1
    # Check that we can push values back to the signal which in turn causes the
    # internal value at the widget to update
    widget.send_value_signal.emit(2)
    qapp.processEvents()
    qapp.processEvents()  # Must be called twice. Multiple rounds of signals
    assert sig.get() == 2
    assert widget.value == 2
    sig_conn.remove_listener(listener)
    # Check that our signal is disconnected completely and maintains the same
    # value as the signal updates in the background
    sig.put(3)
    qapp.processEvents()
    assert widget.value == 2
    widget.send_value_signal.emit(1)
    qapp.processEvents()
    assert sig.get() == 3


def test_plugin_loading(qapp):
    print(qapp.plugins)
    assert qapp.plugins['sig'] == SignalConnection
    assert qapp.plugins['obj'] == SignalConnection
