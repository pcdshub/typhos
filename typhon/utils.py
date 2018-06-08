"""
Utility functions for typhon
"""
############
# Standard #
############
import os.path
import random

############
# External #
############
from ophyd.signal import EpicsSignalBase
from pydm.PyQt.QtGui import QApplication, QColor

#############
#  Package  #
#############

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


def channel_name(pv, protocol='ca'):
    """
    Create a valid PyDM channel from a PV name
    """
    return protocol + '://' + pv


def clean_attr(attr):
    """
    Create a nicer, human readable alias from a Python attribute name
    """
    return ' '.join([word[0].upper() + word[1:] for word in attr.split('_')])


def clean_source(source):
    """
    Strip the PV prefix off the `source` returned from an Ophyd description
    """
    return source.lstrip('PV:')


def clean_name(device, strip_parent=True):
    """
    Create a human readable name for a device

    Parameters
    ----------
    device: ophyd.Device

    strip_parent: bool
        Remove the parent name of the device from name
    """
    name = device.name
    # Strip the parent name if present and desired
    if device.parent and strip_parent:
        name = name.replace(device.parent.name + '_', '')
    # Return the cleaned alias
    return clean_attr(name)


def use_stylesheet():
    """
    Use the Typhon stylesheet
    """
    # Load the path to the file
    style_path = os.path.join(ui_dir, 'style.qss')
    if not os.path.exists(style_path):
        raise EnvironmentError("Unable to find Typhon stylesheet in {}"
                               "".format(style_path))
    # Load the stylesheet from the file
    with open(style_path, 'r') as handle:
        app = QApplication.instance()
        app.setStyleSheet(handle.read())


def random_color():
    """Return a random hex color description"""
    return QColor(random.randint(0, 255),
                  random.randint(0, 255),
                  random.randint(0, 255))
