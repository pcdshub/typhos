"""
Module Docstring
"""
############
# Standard #
############
import logging

###############
# Third Party #
###############
from pydm.PyQt.QtGui import QColor
from pydm.PyQt.QtCore import Qt

##########
# Module #
##########
from typhon.plot import ChannelDisplay


def test_channeldisplay():
    disp = ChannelDisplay('Test Channel', QColor(Qt.white))
    assert disp.ui.name.text() == 'Test Channel'
    assert disp.ui.color.brush.color() == QColor(Qt.white)
