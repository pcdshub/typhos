"""
Utility functions for typhos
"""
import contextlib
import collections
import importlib.util
############
# Standard #
############
import io
import logging
import os.path
import pathlib
import random
import re
import traceback

############
# External #
############
from ophyd import Kind, Device
from ophyd.signal import EpicsSignalBase, EpicsSignalRO
try:
    from ophyd.sim import SignalRO
except ImportError:
    import ophyd.sim
    from ophyd.utils import ReadOnlyError

    class SignalRO(ophyd.sim.Signal):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._metadata.update(
                connected=True,
                write_access=False,
            )

        def put(self, value, *, timestamp=None, force=False):
            raise ReadOnlyError("The signal {} is readonly.".format(self.name))

        def set(self, value, *, timestamp=None, force=False):
            raise ReadOnlyError("The signal {} is readonly.".format(self.name))
from qtpy.QtCore import QSize
from qtpy.QtGui import QColor, QPainter, QMovie
from qtpy.QtWidgets import (QApplication, QStyle, QStyleOption, QStyleFactory,
                            QWidget, QMessageBox, QLabel)

#############
#  Package  #
#############

logger = logging.getLogger(__name__)
ui_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'ui')
GrabKindItem = collections.namedtuple('GrabKindItem',
                                      ('attr', 'component', 'signal'))


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
    """
    Grab all signals of a specific Kind from a Device instance

    Parameters
    ----------
    device : ophyd.Device
        The device instance to introspect
    kind : Kind or str
        The kind to search for

    Returns
    -------
    signals : dict
        Keyed on attribute name, the signals dict contains GrabKindItem named
        tuples, which have attributes {attr, component, signal}.
    """
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
    signals = collections.OrderedDict()
    for attr in kind_attr:
        if '.' in attr:
            hierarchy = attr.split('.')
            attr_name = hierarchy.pop()
            dev = device
            for dev_name in hierarchy:
                dev = getattr(dev, dev_name)
        else:
            dev = device
            attr_name = attr

        signal = getattr(dev, attr_name)
        klass = dev.__class__

        if signal.kind >= kind and not isinstance(signal, Device):
            cpt = getattr(klass, attr_name)
            signals[attr] = GrabKindItem(attr=attr_name, component=cpt,
                                         signal=signal)
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
    Use the Typhos stylesheet

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
            raise EnvironmentError("Unable to find Typhos stylesheet in {}"
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


class TyphosLoading(QLabel):
    loading_gif = None
    """Simple widget that displays a loading GIF"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._icon_size = QSize(32, 32)
        if TyphosLoading.loading_gif is None:
            loading_path = os.path.join(ui_dir, 'loading.gif')
            TyphosLoading.loading_gif = QMovie(loading_path)
        self._animation = TyphosLoading.loading_gif
        self._animation.setScaledSize(self._icon_size)
        self.setMovie(self._animation)
        self._animation.start()

    @property
    def iconSize(self):
        return self._icon_size

    @iconSize.setter
    def iconSize(self, size):
        self._icon_size = size
        self._animation.setScaledSize(self._icon_size)


class TyphosBase(QWidget):
    """Base widget for all Typhos widgets that interface with devices"""
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

            tool = TyphosBase(parent=parent)
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
    Create a file capable of relaunching the TyphosSuite

    Parameters
    ----------
    suite: TyphosSuite

    file_or_buffer : str or file-like
        Either a path to the file or a handle that supports ``write``
    """
    # Accept file-like objects or a handle
    if isinstance(file_or_buffer, str):
        handle = open(file_or_buffer, 'w+')
    else:
        handle = file_or_buffer
    logger.debug("Saving TyphosSuite contents to %r", handle)
    devices = [device.name for device in suite.devices]
    handle.write(saved_template.format(devices=devices))


def load_suite(path, cfg=None):
    """"
    Load a file saved via Typhos

    Parameters
    ----------
    path: str
        Path to file describing the ``TyphosSuite``. This needs to be of the
        format created by the :meth:`.save_suite` function.

    cfg: str, optional
        Location of happi configuration file to use to load devices. If not
        entered the ``$HAPPI_CFG`` environment variable will be used.
    Returns
    -------
    suite: TyphosSuite
    """
    logger.info("Importing TyphosSuite from file %r ...", path)
    module_name = pathlib.Path(path).name.replace('.py', '')
    spec = importlib.util.spec_from_file_location(module_name,
                                                  path)
    suite_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(suite_module)
    if hasattr(suite_module, 'create_suite'):
        logger.debug("Executing create_suite method from %r", suite_module)
        return suite_module.create_suite(cfg=cfg)
    else:
        raise AttributeError("Imported module has no 'create_suite' method!")


saved_template = """\
import sys
import typhos.cli

devices = {devices}

def create_suite(cfg=None):
    return typhos.cli.create_suite(devices, cfg=cfg)

if __name__ == '__main__':
    typhos.cli.typhos_cli(devices + sys.argv[1:])
"""


@contextlib.contextmanager
def no_device_lazy_load():
    '''
    Context manager which disables the ophyd.device.Device
    `lazy_wait_for_connection` behavior and later restore its value.
    '''
    old_val = Device.lazy_wait_for_connection
    try:
        Device.lazy_wait_for_connection = False
        yield
    finally:
        Device.lazy_wait_for_connection = old_val


def _get_template_filenames_for_class(class_, view_type, *, extension='.ui',
                                      include_mro=True):
    '''
    Yields all possible template filenames that can be used for the class, in
    order of priority, including those in the class MRO.
    '''
    for cls in class_.mro():
        module = cls.__module__
        name = cls.__name__
        yield f'{module}.{name}.{view_type}{extension}'
        yield f'{name}.{view_type}{extension}'
        yield f'{name}{extension}'

        if not include_mro:
            break


def remove_duplicate_items(list_):
    'Return a de-duplicated list/tuple of items in `list_`, retaining order'
    cls = type(list_)
    return cls(sorted(set(list_), key=list_.index))


def find_templates_for_class(cls, view_type, paths, *, extension='.ui',
                             include_mro=True):
    '''
    Given a class `cls` and a view type (such as 'detailed'), search `paths`
    for potential templates to show.

    Parameters
    ----------
    cls : class
        Search for templates with this class name
    view_type : {'detailed', 'engineering', 'embedded'}
        The view type
    paths : iterable
        Iterable of paths to be expanded, de-duplicated, and searched
    extension : str, optional
        The template filename extension (default is ``'.ui'``)
    include_mro : bool, optional
        Include superclasses - those in the MRO - of ``cls`` as well

    Yields
    ------
    path : pathlib.Path
        A matching path, ordered from most-to-least specific.
    '''
    paths = remove_duplicate_items(
        [pathlib.Path(p).expanduser().resolve() for p in paths]
    )

    for candidate_filename in _get_template_filenames_for_class(
            cls, view_type, extension=extension, include_mro=include_mro):
        for path in paths:
            for match in path.glob(candidate_filename):
                if match.is_file():
                    yield match
