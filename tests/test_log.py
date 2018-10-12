import logging

from ophyd import Device

from typhon.tools import TyphonLogDisplay


def test_log_display(qtbot):
    dev = Device(name='test')
    log_tool = TyphonLogDisplay.from_device(dev)
    qtbot.addWidget(log_tool)
    dev.log.error(dev.name)
    assert dev.name in log_tool.logdisplay.text.toPlainText()
    dev2 = Device(name='blah')
    log_tool.add_device(dev2)
    dev2.log.info(dev2.name)
    assert dev2.name in log_tool.logdisplay.text.toPlainText()
