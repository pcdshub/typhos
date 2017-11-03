############
# Standard #
############

############
# External #
############
from pydm.PyQt.QtCore   import QSize, Qt
from pydm.widgets.label import PyDMLabel

###########
# Package #
###########

class TyphonLabel(PyDMLabel):
    """
    TyphonLabel

    Reimplemtation of PyDMLabel to set some custom defaults
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlignment(Qt.AlignCenter)

    def sizeHint(self):
        #This is to match the PyDMLineEdit sizeHint
        return QSize(100, 30)


