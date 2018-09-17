############
# Standard #
############
import logging

############
# External #
############
from qtpy.QtCore import QSize, Qt, Slot
from qtpy.QtWidgets import (QListWidgetItem, QPushButton, QVBoxLayout,
                            QWidget)
from pydm.widgets import PyDMLabel, PyDMEnumComboBox, PyDMLineEdit

###########
# Package #
###########

logger = logging.getLogger(__name__)


class TogglePanel(QWidget):
    """
    Generic Panel Widget

    Displays a widget below QPushButton that hides and shows the contents. It
    is up to subclasses to re-point the attribute :attr:`.contents` to the
    widget whose visibility you would like to toggle.

    By default, it is assumed that the Panel is initialized with the
    :attr:`.contents` widget as visible, however the contents will be hidden
    and the button synced to the proper position if :meth:`.show_contents` is
    called after instance creation

    Parameters
    ----------
    title : str
        Title of Panel. This will be the text on the QPushButton

    parent : QWidget

    Attributes
    ----------
    contents : QWidget
        Widget whose visibility is controlled via the QPushButton
    """
    def __init__(self, title, parent=None):
        super().__init__(parent=parent)
        # Create Widget Infrastructure
        self.title = title
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(2, 2, 2, 2)
        self.layout().setSpacing(5)
        # Create button control
        # Assuming widget is visible, set the button as checked
        self.contents = None
        self.hide_button = QPushButton(self.title)
        self.hide_button.setCheckable(True)
        self.hide_button.setChecked(True)
        self.layout().addWidget(self.hide_button)
        self.hide_button.clicked.connect(self.show_contents)

    @Slot(bool)
    def show_contents(self, show):
        """
        Show the contents of the Widget

        Hides the :attr:`.contents` QWidget and sets the :attr:`.hide_button`
        to the proper status to indicate whether the widget is hidden or not

        Parameters
        ----------
        show : bool
        """
        # Configure our button in case this slot was called elsewhere
        self.hide_button.setChecked(show)
        # Show or hide the widget if the contents exist
        if self.contents:
            if show:
                self.show()
                self.contents.show()
            else:
                self.contents.hide()


class TyphonComboBox(PyDMEnumComboBox):
    """
    Reimplementation of PyDMEnumComboBox to set some custom defaults
    """
    def sizeHint(self):
        return QSize(100, 30)


class TyphonLineEdit(PyDMLineEdit):
    """
    Reimplementation of PyDMLineEdit to set some custom defaults
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.showUnits = True

    def sizeHint(self):
        return QSize(100, 30)


class TyphonLabel(PyDMLabel):
    """
    Reimplemtation of PyDMLabel to set some custom defaults
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlignment(Qt.AlignCenter)
        self.showUnits = True

    def sizeHint(self):
        return QSize(100, 30)


class TyphonSidebarItem(QListWidgetItem):
    """
    QListWidgetItem to display in DeviceDisplay sidebar
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setTextAlignment(Qt.AlignCenter)
