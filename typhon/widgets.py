############
# Standard #
############

############
# External #
############
from pydm.PyQt.QtCore import QSize, Qt
from pydm.widgets import PyDMLabel, PyDMEnumComboBox

###########
# Package #
###########


class TyphonComboBox(PyDMEnumComboBox):
    """
    Reimplementation of PyDMEnumComboBox to set some custom defaults
    """
    def sizeHint(self):
        # This is to match teh PyDMLineEdit sizeHint
        return QSize(100, 30)


class TyphonLabel(PyDMLabel):
    """
    Reimplemtation of PyDMLabel to set some custom defaults
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlignment(Qt.AlignCenter)

    def sizeHint(self):
        # This is to match the PyDMLineEdit sizeHint
        return QSize(100, 30)
