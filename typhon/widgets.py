############
# Standard #
############
import logging
import os.path

############
# External #
############
from pydm.PyQt import uic
from pydm.PyQt.QtCore import QSize, Qt
from pydm.PyQt.QtGui import QStackedWidget, QLabel, QAbstractButton
from pydm.widgets import PyDMDrawingImage, PyDMLabel, PyDMEnumComboBox

###########
# Package #
###########
from .utils import ui_dir, channel_name

logger = logging.getLogger(__name__)


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


class ComponentButton(QAbstractButton):
    """
    Button to display a Component

    Displays the name given along with a layout that you can add PVs.The
    ComponentButton is used by :func:`.TyphonDisplay.add_subdevice`.

    Parameters
    ----------
    name : str
        Name displayed on button

    parent : QWidget, optional
    """
    def __init__(self, name, parent=None):
        # Basic widget setup
        super().__init__(parent=parent)
        self.setCheckable(True)
        # Instantiate UI
        self.ui = uic.loadUi(os.path.join(ui_dir, 'button.ui'), self)
        self.ui.name_label.setText(name)
        self.toggled.connect(self.setChecked)
        # Store orignal stylesheet
        self.fixed_style = self.styleSheet()

    def add_pv(self, pv, name):
        """
        Add a PV to the ComponentButton

        Parameters
        ----------
        pv : str
            Name of PV to add to the button
        """
        # Create label
        label = QLabel(name)
        label.setAlignment(Qt.AlignCenter)
        # Create PyDMLabel and add everything to layout
        widget = TyphonLabel(init_channel=channel_name(pv))
        self.ui.button_frame.layout().addWidget(label)
        self.ui.button_frame.layout().addWidget(widget)

    def paintEvent(self, evt):
        """
        Reimplement paintEvent to hide `NotImplementedError`
        """
        pass

    def setChecked(self, checked):
        """
        Change the border of the ComponentButton when checked

        Calls `QAbstractButton.setChecked` underneath to manage button state.

        Parameters
        ----------
        checked : bool
            Whether to set the ComponentButton checked or unchecked.
        """
        # Change stylesheet
        if checked:
            self.setStyleSheet("QFrame {border-color : cyan}")
        else:
            self.setStyleSheet(self.fixed_style)
        # Register with QAbstractButton
        super().setChecked(checked)


class RotatingImage(QStackedWidget):
    """
    Rotating Image Handler

    Allows users to add images with clean user aliases, and then swap between
    them using :meth:`.show_image`

    Parameters
    ----------
    parent : QWidget, optional

    Attributes
    ----------
    images : dict
        Table of image names and their index in the stack
    """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.images = dict()

    def add_image(self, path, name):
        """
        Add an image to the widget

        Parameters
        ----------
        path : str
            Absolute or relative path to the widget

        name : str
            Name to refer to the image as
        """
        # Warn users if they enter a duplicate name
        if name in self.images:
            logger.warning("Overwriting image for %s", name)
        # Create the ImageWidget
        drawing = PyDMDrawingImage(filename=path)
        # Add the widget to the stack
        idx = self.addWidget(drawing)
        # Save the idx for reference
        self.images[name] = idx

    def show_image(self, name):
        """
        Show the named image

        Parameters
        ----------
        name : str
            Image name saved in the :attr:`.images` dictionary
        """
        self.setCurrentIndex(self.images[name])
