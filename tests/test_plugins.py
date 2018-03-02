############
# Standard #
############
import sys
###############
# Third Party #
###############


##########
# Module #
##########
from typhon.plugins import ClassConnection


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
