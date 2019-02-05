"""
Utility functions for typhon
"""
############
# Standard #
############
import io
import importlib.util
import pathlib
import re
import logging
import os.path
import random
import traceback

############
# External #
############
from ophyd import Kind, Device
from ophyd.signal import EpicsSignalBase, EpicsSignalRO
from ophyd.sim import SignalRO
from qtpy.QtGui import QColor, QPainter
from qtpy.QtWidgets import (QApplication, QStyle, QStyleOption, QStyleFactory,
                            QWidget, QMessageBox)

#############
#  Package  #
#############

logger = logging.getLogger(__name__)
ui_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'ui')


def channel_from_signal(signal):
    """
    Create a PyDM address from arbitrary signal type
    """
    # Add an item
    if isinstance(signal, EpicsSignalBase):
        return channel_name(signal._read_pv.pvname)
    else:
        return channel_name(signal.name, protocol='sig')


def is_signal_ro(signal):
    """
    Return whether the signal is read-only

    In the future this may be easier to do through improvements to
    introspection in the ophyd library. Until that day we need to check classes
    """
    return isinstance(signal, (SignalRO, EpicsSignalRO))


def grab_kind(device, kind):
    """Grab all signals of a specific Kind from a Device"""
    # Accept actual Kind or string value
    if not isinstance(kind, Kind):
        kind = Kind[kind]
    # Find the right attribute store
    kind_attr = {Kind.hinted: device.read_attrs,
                 Kind.normal: device.read_attrs,
                 Kind.config: device.configuration_attrs,
                 Kind.omitted: [attr for attr in device.component_names
                                if attr not in device.read_attrs +
                                device.configuration_attrs]}[kind]
    # Return that kind filtered for devices
    signals = []
    for attr in kind_attr:
        cpt = getattr(device, attr)
        if cpt.kind >= kind and not isinstance(cpt, Device):
            signals.append((attr, cpt))
    return signals


def channel_name(pv, protocol='ca'):
    """
    Create a valid PyDM channel from a PV name
    """
    return protocol + '://' + pv


def clean_attr(attr):
    """
    Create a nicer, human readable alias from a Python attribute name
    """
    return attr.replace('.', ' ').replace('_', ' ')


def clean_name(device, strip_parent=True):
    """
    Create a human readable name for a device

    Parameters
    ----------
    device: ophyd.Device

    strip_parent: bool or Device
        Remove the parent name of the device from name. If strip_parent is
        True, the name of the direct parent of the device is stripped. If a
        device is provided the name of that device is used. This allows
        specification for removal at any point of the device schema
    """
    name = device.name
    if strip_parent and device.parent:
        if isinstance(strip_parent, Device):
            parent_name = strip_parent.name
        else:
            parent_name = device.parent.name
        name = name.replace(parent_name + '_', '')
    # Return the cleaned alias
    return clean_attr(name)


def use_stylesheet(dark=False, widget=None):
    """
    Use the Typhon stylesheet

    Parameters
    ----------
    dark: bool, optional
        Whether or not to use the QDarkStyleSheet theme. By default the light
        theme is chosen.
    """
    # Dark Style
    if dark:
        import qdarkstyle
        style = qdarkstyle.load_stylesheet_pyqt5()
    # Light Style
    else:
        # Load the path to the file
        style_path = os.path.join(ui_dir, 'style.qss')
        if not os.path.exists(style_path):
            raise EnvironmentError("Unable to find Typhon stylesheet in {}"
                                   "".format(style_path))
        # Load the stylesheet from the file
        with open(style_path, 'r') as handle:
            style = handle.read()
    if widget is None:
        widget = QApplication.instance()
    # We can set Fusion style if it is an application
    if isinstance(widget, QApplication):
        widget.setStyle(QStyleFactory.create('Fusion'))
    # Set Stylesheet
    widget.setStyleSheet(style)


def random_color():
    """Return a random hex color description"""
    return QColor(random.randint(0, 255),
                  random.randint(0, 255),
                  random.randint(0, 255))


class TyphonBase(QWidget):
    """Base widget for all Typhon widgets that interface with devices"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.devices = list()

    def add_device(self, device):
        """
        Add a new device to the widget

        Parameters
        ----------
        device : ophyd.Device
        """
        logger.debug("Adding device %s ...", device.name)
        self.devices.append(device)

    def paintEvent(self, event):
        # This is necessary because by default QWidget ignores stylesheets
        # https://wiki.qt.io/How_to_Change_the_Background_Color_of_QWidget
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter()
        painter.begin(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, painter, self)
        super().paintEvent(event)

    @classmethod
    def from_device(cls, device, parent=None, **kwargs):
        """
        Create a new instance of the widget for a Device

        Shortcut for:

        .. code::

            tool = TyphonBase(parent=parent)
            tool.add_device(device)

        Parameters
        ----------
        device: ophyd.Device

        parent: QWidget
        """
        instance = cls(parent=parent, **kwargs)
        instance.add_device(device)
        return instance


def make_identifier(name):
    """Make a Python string into a valid Python identifier"""
    # That was easy
    if name.isidentifier():
        return name
    # Lowercase
    name = name.lower()
    # Leading / following whitespace
    name = name.strip()
    # Intermediate whitespace should be underscores
    name = re.sub('[\\s\\t\\n]+', '_', name)
    # Remove invalid characters
    name = re.sub('[^0-9a-zA-Z_]', '', name)
    # Remove leading characters until we find a letter or an underscore
    name = re.sub('^[^a-zA-Z_]+', '', name)
    return name


def flatten_tree(param):
    """Flatten a tree of parameters"""
    tree = [param]
    for child in param.childs:
        tree.extend(flatten_tree(child))
    return tree


def clear_layout(layout):
    """Clear a QLayout"""
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()
        elif child.layout():
            clear_layout(child.layout())


def raise_to_operator(exc):
    """Utility function to show an Exception to a user"""
    logger.error("Reporting error %r to user ...", exc)
    err_msg = QMessageBox()
    err_msg.setText(f'{exc.__class__.__name__}: {exc}')
    err_msg.setWindowTitle(type(exc).__name__)
    err_msg.setIcon(QMessageBox.Critical)
    handle = io.StringIO()
    traceback.print_tb(exc.__traceback__, file=handle)
    handle.seek(0)
    err_msg.setDetailedText(handle.read())
    err_msg.exec_()
    return err_msg


def reload_widget_stylesheet(widget, cascade=False):
    """Reload the stylesheet of the provided widget"""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
    if cascade:
        for child in widget.children():
            if isinstance(child, QWidget):
                reload_widget_stylesheet(child, cascade=True)


def save_suite(suite, file_or_buffer):
    """
    Create a file capable of relaunching the TyphonSuite

    Parameters
    ----------
    suite: TyphonSuite

    file_or_buffer : str or file-like
        Either a path to the file or a handle that supports ``write``
    """
    # Accept file-like objects or a handle
    if isinstance(file_or_buffer, str):
        handle = open(file_or_buffer, 'w+')
    else:
        handle = file_or_buffer
    logger.debug("Saving TyphonSuite contents to %r", handle)
    devices = [device.name for device in suite.devices]
    handle.write(saved_template.format(devices=devices))


def load_suite(path):
    """"
    Load a file saved via Typhon

    Parameters
    ----------
    path: str
        Path to file describing the ``TyphonSuite``. This needs to be of the
        format created by the :meth:`.save_suite` function.

    Returns
    -------
    suite: TyphonSuite
    """
    logger.info("Importing TyphonSuite from file %r ...", path)
    module_name = pathlib.Path(path).name.replace('.py', '')
    spec = importlib.util.spec_from_file_location(module_name,
                                                  path)
    suite_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(suite_module)
    if hasattr(suite_module, 'create_suite'):
        logger.debug("Executing create_suite method from %r", suite_module)
        return suite_module.create_suite()
    else:
        raise AttributeError("Imported module has no 'create_suite' method!")


saved_template = """\
import sys
import typhon.cli

devices = {devices}

def create_suite(cfg=None):
    return typhon.cli.create_suite(devices, cfg=cfg)

if __name__ == '__main__':
    typhon.cli.typhon_cli(devices + sys.argv[1:])
"""
