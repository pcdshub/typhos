"""
Utility functions for typhos
"""
import collections
import contextlib
import functools
import importlib.util
import inspect
import io
import logging
import operator
import os
import pathlib
import random
import re
import threading

import ophyd
import ophyd.sim
from ophyd import Device
from ophyd.signal import EpicsSignalBase, EpicsSignalRO
from pydm.exception import raise_to_operator  # noqa
from pydm.widgets.base import PyDMWritableWidget
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QSize
from qtpy.QtGui import QColor, QMovie, QPainter
from qtpy.QtWidgets import QWidget

from typhos import plugins

try:
    import happi
except ImportError:
    happi = None

logger = logging.getLogger(__name__)
MODULE_PATH = pathlib.Path(__file__).parent.resolve()
ui_dir = MODULE_PATH / 'ui'
ui_core_dir = ui_dir / 'core'
GrabKindItem = collections.namedtuple('GrabKindItem',
                                      ('attr', 'component', 'signal'))
DEBUG_MODE = bool(os.environ.get('TYPHOS_DEBUG', False))


if happi is None:
    logger.info("happi is not installed; some features may be unavailable")


def _get_display_paths():
    """Get all display paths based on PYDM_DISPLAYS_PATH + typhos built-ins."""
    paths = os.environ.get('PYDM_DISPLAYS_PATH', '')
    for path in paths.split(os.pathsep):
        path = pathlib.Path(path).expanduser().resolve()
        if path.exists() and path.is_dir():
            yield path
    yield ui_dir / 'core'
    yield ui_dir / 'devices'


DISPLAY_PATHS = list(_get_display_paths())


if hasattr(ophyd.signal, 'SignalRO'):
    SignalRO = ophyd.signal.SignalRO
else:
    # SignalRO was re-introduced to ophyd.signal in December 2019 (1f83a055).
    # If unavailable, fall back to our previous definition:
    class SignalRO(ophyd.sim.SynSignalRO):
        def __init__(self, value=0, *args, **kwargs):
            self._value = value
            super().__init__(*args, **kwargs)
            self._metadata.update(
                connected=True,
                write_access=False,
            )

        def get(self):
            return self._value


def channel_from_signal(signal, read=True):
    """
    Create a PyDM address from arbitrary signal type
    """
    # Add an item
    if isinstance(signal, EpicsSignalBase):
        if read:
            return channel_name(signal._read_pv.pvname)
        return channel_name(signal._write_pv.pvname)
    return channel_name(signal.name, protocol='sig')


def is_signal_ro(signal):
    """
    Return whether the signal is read-only, based on its class.

    In the future this may be easier to do through improvements to
    introspection in the ophyd library. Until that day we need to check classes
    """
    return isinstance(signal, (SignalRO, EpicsSignalRO, ophyd.sim.SynSignalRO))


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
        widget = QtWidgets.QApplication.instance()
    # We can set Fusion style if it is an application
    if isinstance(widget, QtWidgets.QApplication):
        widget.setStyle(QtWidgets.QStyleFactory.create('Fusion'))

    # Set Stylesheet
    widget.setStyleSheet(style)


def random_color():
    """Return a random hex color description"""
    return QColor(random.randint(0, 255),
                  random.randint(0, 255),
                  random.randint(0, 255))


class TyphosLoading(QtWidgets.QLabel):
    """
    A QLabel with an animation for loading status.

    Attributes
    ----------
    LOADING_TIMEOUT_MS : int
        The timeout value in milliseconds for when to stop the animation
        and replace it with a default timeout message.

    """
    LOADING_TIMEOUT_MS = 10000
    loading_gif = None

    def __init__(self, timeout_message, *, parent=None, **kwargs):
        self.timeout_message = timeout_message
        super().__init__(parent=parent, **kwargs)
        self._icon_size = QSize(32, 32)
        if TyphosLoading.loading_gif is None:
            loading_path = os.path.join(ui_dir, 'loading.gif')
            TyphosLoading.loading_gif = QMovie(loading_path)
        self._animation = TyphosLoading.loading_gif
        self._animation.setScaledSize(self._icon_size)
        self.setMovie(self._animation)
        self._animation.start()
        if self.LOADING_TIMEOUT_MS > 0:
            QtCore.QTimer.singleShot(self.LOADING_TIMEOUT_MS,
                                     self._handle_timeout)

        self.setContextMenuPolicy(QtCore.Qt.DefaultContextMenu)

    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu(parent=self)

        def copy_to_clipboard(*, text):
            clipboard = QtWidgets.QApplication.instance().clipboard()
            clipboard.setText(text)

        menu.addSection('Copy to clipboard')
        action = menu.addAction('&All')
        action.triggered.connect(functools.partial(copy_to_clipboard,
                                                   text=self.toolTip()))
        menu.addSeparator()

        for line in self.toolTip().splitlines():
            action = menu.addAction(line)
            action.triggered.connect(
                functools.partial(copy_to_clipboard, text=line)
            )

        menu.exec_(self.mapToGlobal(event.pos()))

    def _handle_timeout(self):
        self._animation.stop()
        self.setMovie(None)
        self.setText(self.timeout_message)

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
        opt = QtWidgets.QStyleOption()
        opt.initFrom(self)
        painter = QPainter()
        painter.begin(self)
        self.style().drawPrimitive(QtWidgets.QStyle.PE_Widget, opt, painter,
                                   self)
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


def pyqt_class_from_enum(enum):
    '''
    Create an inheritable base class from a Python Enum, which can also be used
    for Q_ENUMS.
    '''
    enum_dict = {item.name: item.value for item in list(enum)}
    return type(enum.__name__, (object, ), enum_dict)


def _get_template_filenames_for_class(class_, view_type, *, include_mro=True):
    '''
    Yields all possible template filenames that can be used for the class, in
    order of priority, including those in the class MRO.

    This does not include the file extension, to be appended by the caller.
    '''
    for cls in class_.mro():
        module = cls.__module__
        name = cls.__name__
        yield f'{module}.{name}.{view_type}'
        yield f'{name}.{view_type}'
        yield f'{name}'

        if not include_mro:
            break


def remove_duplicate_items(list_):
    'Return a de-duplicated list/tuple of items in `list_`, retaining order'
    cls = type(list_)
    return cls(sorted(set(list_), key=list_.index))


def is_standard_template(template):
    """
    Is the template a core one provided with typhos?

    Parameters
    ----------
    template : str or pathlib.Path
    """
    common_path = pathlib.Path(os.path.commonpath((template, ui_core_dir)))
    return common_path == ui_core_dir


def find_templates_for_class(cls, view_type, paths, *, extensions=None,
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
    extensions : str or list, optional
        The template filename extension (default is ``'.ui'`` or ``'.py'``)
    include_mro : bool, optional
        Include superclasses - those in the MRO - of ``cls`` as well

    Yields
    ------
    path : pathlib.Path
        A matching path, ordered from most-to-least specific.
    '''
    if not inspect.isclass(cls):
        cls = type(cls)

    if not extensions:
        extensions = ['.py', '.ui']
    elif isinstance(extensions, str):
        extensions = [extensions]

    from .cache import _CachedPath
    paths = remove_duplicate_items(
        [_CachedPath.from_path(p) for p in paths]
    )

    for candidate_filename in _get_template_filenames_for_class(
            cls, view_type, include_mro=include_mro):
        for extension in extensions:
            for path in paths:
                for match in path.glob(candidate_filename + extension):
                    if match.is_file():
                        yield match


def find_file_in_paths(filename, *, paths=None):
    '''
    Search for filename ``filename`` in the list of paths ``paths``

    Parameters
    ----------
    filename : str or pathlib.Path
        The filename
    paths : list or iterable, optional
        List of paths to search. Defaults to DISPLAY_PATHS.

    Yields
    ------
    All filenames that match in the given paths
    '''
    if paths is None:
        paths = DISPLAY_PATHS

    if isinstance(filename, pathlib.Path):
        if filename.is_absolute():
            if filename.exists():
                yield filename
            return

        filename = filename.name

    from .cache import _CachedPath
    paths = remove_duplicate_items(
        [_CachedPath.from_path(p) for p in paths]
    )

    for path in paths:
        for match in path.glob(filename):
            if match.is_file():
                yield match


def get_device_from_fake_class(cls):
    """
    Return the non-fake class, given a fake class

    That is::

        fake_cls = ophyd.sim.make_fake_device(cls)
        get_device_from_fake_class(fake_cls)  # -> cls

    Parameters
    ----------
    cls : type
        The fake class
    """
    bases = cls.__bases__
    if not bases or len(bases) != 1:
        raise ValueError('Not a fake class based on inheritance')

    actual_class, = bases

    if actual_class not in ophyd.sim.fake_device_cache:
        raise ValueError('Not a fake class (ophyd.sim does not know about it)')

    return actual_class


def is_fake_device_class(cls):
    """
    Is ``cls`` a fake device from :func:`ophyd.sim.make_fake_device`?
    """
    try:
        get_device_from_fake_class(cls)
    except ValueError:
        return False
    return True


def code_from_device_repr(device):
    """
    Return code to create a device from its ``repr`` information.

    Parameters
    ----------
    device : ophyd.Device
    """
    try:
        module = device.__module__
    except AttributeError:
        raise ValueError('Device class must be in a module') from None

    class_name = device.__class__.__name__
    if module == '__main__':
        raise ValueError('Device class must be in a module')

    cls = device.__class__
    is_fake = is_fake_device_class(cls)

    full_class_name = f'{module}.{class_name}'
    kwargs = '\n   '.join(f'{k}={v!r},' for k, v in device._repr_info())
    logger.debug('%r fully qualified Device class: %r', device.name,
                 full_class_name)
    if is_fake:
        actual_class = get_device_from_fake_class(cls)
        actual_name = f'{actual_class.__module__}.{actual_class.__name__}'
        logger.debug('%r fully qualified Device class is fake, based on: %r',
                     device.name, actual_class)
        return f'''\
import ophyd.sim
import pcdsutils

{actual_class.__name__} = pcdsutils.utils.import_helper({actual_name!r})
{class_name} = ophyd.sim.make_fake_device({actual_class.__name__})
{device.name} = {class_name}(
    {kwargs}
)
ophyd.sim.clear_fake_device({device.name})
'''

    return f'''\
import pcdsutils

{class_name} = pcdsutils.utils.import_helper({full_class_name!r})
{device.name} = {class_name}(
    {kwargs}
)
'''


def code_from_device(device):
    """
    Generate code required to load ``device`` in another process
    """
    is_fake = is_fake_device_class(device.__class__)
    if happi is None or not hasattr(device, 'md') or is_fake:
        return code_from_device_repr(device)

    happi_name = device.md.name
    return f'''\
import happi
from happi.loader import from_container
client = happi.Client.from_config()
md = client.find_device(name="{happi_name}")
{device.name} = from_container(md)
'''


@contextlib.contextmanager
def subscription_context(*objects, callback, event_type=None, run=True):
    '''
    [Context manager] Subscribe to a specific event from all objects

    Unsubscribes all signals before exiting

    Parameters
    ----------
    *objects : ophyd.OphydObj
        Ophyd objects (signals) to monitor
    callback : callable
        Callback to run, with same signature as that of
        :meth:`ophyd.OphydObj.subscribe`.
    event_type : str, optional
        The event type to subscribe to
    run : bool, optional
        Run the previously cached subscription immediately
    '''
    obj_to_cid = {}
    try:
        for obj in objects:
            try:
                obj_to_cid[obj] = obj.subscribe(callback,
                                                event_type=event_type, run=run)
            except Exception:
                logger.exception('Failed to subscribe to object %s', obj.name)
        yield dict(obj_to_cid)
    finally:
        for obj, cid in obj_to_cid.items():
            try:
                obj.unsubscribe(cid)
            except KeyError:
                # It's possible that when the object is being torn down, or
                # destroyed that this has already been done.
                ...


def get_all_signals_from_device(device, include_lazy=False, filter_by=None):
    '''
    Get all signals in a given device

    Parameters
    ----------
    device : ophyd.Device
        ophyd Device to monitor
    include_lazy : bool, optional
        Include lazy signals as well
    filter_by : callable, optional
        Filter signals, with signature ``callable(ophyd.Device.ComponentWalk)``
    '''
    if not filter_by:
        def filter_by(walk):
            return True

    def _get_signals():
        return [
            walk.item
            for walk in device.walk_signals(include_lazy=include_lazy)
            if filter_by(walk)
        ]

    if not include_lazy:
        return _get_signals()

    with no_device_lazy_load():
        return _get_signals()


@contextlib.contextmanager
def subscription_context_device(device, callback, event_type=None, run=True, *,
                                include_lazy=False, filter_by=None):
    '''
    [Context manager] Subscribe to ``event_type`` from signals in ``device``

    Unsubscribes all signals before exiting

    Parameters
    ----------
    device : ophyd.Device
        ophyd Device to monitor
    callback : callable
        Callback to run, with same signature as that of
        :meth:`ophyd.OphydObj.subscribe`
    event_type : str, optional
        The event type to subscribe to
    run : bool, optional
        Run the previously cached subscription immediately
    include_lazy : bool, optional
        Include lazy signals as well
    filter_by : callable, optional
        Filter signals, with signature ``callable(ophyd.Device.ComponentWalk)``
    '''
    signals = get_all_signals_from_device(device, include_lazy=include_lazy)
    with subscription_context(*signals, callback=callback,
                              event_type=event_type, run=run) as obj_to_cid:
        yield obj_to_cid


class _ConnectionStatus:
    def __init__(self, callback):
        self.connected = set()
        self.callback = callback
        self.lock = threading.Lock()
        # NOTE: this will be set externally
        self.obj_to_cid = {}
        self.objects = set()

    def clear(self):
        for obj in list(self.objects):
            self.remove_object(obj)

    def _run_callback_hack_on_object(self, obj):
        '''
        HACK: peek into ophyd objects to see if they're connected but have
        never run metadata callbacks

        This is part of an ongoing ophyd issue and may be removed in the
        future.
        '''
        if obj not in self.objects:
            return

        if obj.connected and obj._args_cache.get('meta') is None:
            md = dict(obj.metadata)
            if 'connected' not in md:
                md['connected'] = True
            self._connection_callback(obj=obj, **md)

    def add_object(self, obj):
        'Add an additional object to be monitored'
        with self.lock:
            if obj in self.objects:
                return

        self.objects.add(obj)
        try:
            self.obj_to_cid[obj] = obj.subscribe(
                self._connection_callback, event_type='meta', run=True)
        except Exception:
            logger.exception('Failed to subscribe to object: %s', obj.name)
            self.objects.remove(obj)
        else:
            self._run_callback_hack_on_object(obj)

    def remove_object(self, obj):
        'Remove an object from being monitored - no more callbacks'
        with self.lock:
            if obj in self.connected:
                self.connected.remove(obj)

            self.objects.remove(obj)
            cid = self.obj_to_cid.pop(obj)
            try:
                obj.unsubscribe(cid)
            except KeyError:
                # It's possible that when the object is being torn down, or
                # destroyed that this has already been done.
                ...

    def _connection_callback(self, *, obj, connected, **kwargs):
        with self.lock:
            if obj not in self.objects:
                # May have been removed
                return

            if connected and obj not in self.connected:
                self.connected.add(obj)
            elif not connected and obj in self.connected:
                self.connected.remove(obj)
            else:
                return

        logger.debug('Connection update: %r (obj=%s connected=%s kwargs=%r)',
                     self, obj.name, connected, kwargs)
        self.callback(obj=obj, connected=connected, **kwargs)

    def __repr__(self):
        return (
            f'<{self.__class__.__name__} connected={len(self.connected)} '
            f'objects={len(self.objects)}>'
        )


@contextlib.contextmanager
def connection_status_monitor(*signals, callback):
    '''
    [Context manager] Monitor connection status from a number of signals

    Filters out any other metadata updates, only calling once
    connected/disconnected

    Parameters
    ----------
    *signals : ophyd.OphydObj
        Signals to monitor
    callback : callable
        Callback to run, with same signature as that of
        :meth:`ophyd.OphydObj.subscribe`. ``obj`` and ``connected`` are
        guaranteed kwargs.
    '''

    status = _ConnectionStatus(callback)

    with subscription_context(*signals, callback=status._connection_callback,
                              event_type='meta', run=True
                              ) as status.obj_to_cid:
        for sig in signals:
            status._run_callback_hack_on_object(sig)

        yield status


class DeviceConnectionMonitorThread(QtCore.QThread):
    '''
    Monitor connection status in a background thread

    Parameters
    ----------
    device : ophyd.Device
        The device to grab signals from
    include_lazy : bool, optional
        Include lazy signals as well

    Attributes
    ----------
    connection_update : QtCore.Signal
        Connection update signal with signature::

            (signal, connected, metadata_dict)
    '''

    connection_update = QtCore.Signal(object, bool, dict)

    def __init__(self, device, include_lazy=False, **kwargs):
        super().__init__(**kwargs)
        self.device = device
        self.include_lazy = include_lazy
        self._update_event = threading.Event()

    def callback(self, obj, connected, **kwargs):
        self._update_event.set()
        self.connection_update.emit(obj, connected, kwargs)

    def run(self):
        signals = get_all_signals_from_device(
            self.device, include_lazy=self.include_lazy)

        with connection_status_monitor(*signals, callback=self.callback):
            while not self.isInterruptionRequested():
                self._update_event.clear()
                self._update_event.wait(timeout=0.5)


class ObjectConnectionMonitorThread(QtCore.QThread):
    '''
    Monitor connection status in a background thread

    Attributes
    ----------
    connection_update : QtCore.Signal
        Connection update signal with signature::

            (signal, connected, metadata_dict)
    '''

    connection_update = QtCore.Signal(object, bool, dict)

    def __init__(self, objects=None, **kwargs):
        super().__init__(**kwargs)
        self._init_objects = list(objects or [])
        self.status = None
        self.lock = threading.Lock()
        self._update_event = threading.Event()

    def clear(self):
        if self.status:
            self.status.clear()

    def add_object(self, obj):
        with self.lock:
            # If the thread hasn't started yet, add it to the list
            if self.status is None:
                self._init_objects.append(obj)
                return

        self.status.add_object(obj)

    def remove_object(self, obj):
        with self.lock:
            # If the thread hasn't started yet, remove it prior to monitoring
            if self.status is None:
                self._init_objects.remove(obj)
                return

        self.status.remove_object(obj)

    def callback(self, obj, connected, **kwargs):
        self._update_event.set()
        self.connection_update.emit(obj, connected, kwargs)

    def run(self):
        self.lock.acquire()
        try:
            with connection_status_monitor(
                    *self._init_objects,
                    callback=self.callback) as self.status:
                self._init_objects.clear()
                self.lock.release()
                while not self.isInterruptionRequested():
                    self._update_event.clear()
                    self._update_event.wait(timeout=0.5)
        finally:
            if self.lock.locked():
                self.lock.release()


class ThreadPoolWorker(QtCore.QRunnable):
    '''
    Worker thread helper

    Parameters
    ----------
    func : callable
        The function to call during :meth:`.run`
    *args
        Arguments for the function call
    **kwargs
        Keyword rarguments for the function call
    '''

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    @QtCore.Slot()
    def run(self):
        try:
            self.func(*self.args, **self.kwargs)
        except Exception:
            logger.exception('Failed to run %s(*%s, **%r) in thread pool',
                             self.func, self.args, self.kwargs)


def _get_top_level_components(device_cls):
    """Get all top-level components from a device class."""
    return list(device_cls._sig_attrs.items())


def find_parent_with_class(widget, cls=QWidget):
    """
    Finds the first parent of a widget that is an instance of ``klass``

    Parameters
    ----------
    widget : QWidget
        The widget from which to start the search
    cls : type, optional
        The class which the parent must be an instance of

    """
    parent = widget
    while parent is not None:
        if isinstance(parent, cls):
            return parent
        parent = parent.parent()
    return None


def dump_grid_layout(layout, rows=None, cols=None, *, cell_width=60):
    """
    Dump the layout of a :class:`QtWidgets.QGridLayout` to ``file``.

    Parameters
    ----------
    layout : QtWidgets.QGridLayout
        The layout
    rows : int
        Number of rows to iterate over
    cols : int
        Number of columns to iterate over

    Returns
    -------
    table : str
        The text for the summary table
    """
    rows = rows or layout.rowCount()
    cols = cols or layout.columnCount()

    separator = '-' * ((cell_width + 4) * cols)
    cell = ' {:<%ds}' % cell_width

    def get_text(item):
        if not item:
            return ''

        entry = item.widget() or item.layout()
        visible = entry is None or entry.isVisible()
        if isinstance(entry, QtWidgets.QLabel):
            entry = f'<QLabel {entry.text()!r}>'

        if not visible:
            entry = f'(invis) {entry}'
        return entry

    with io.StringIO() as file:
        print(separator, file=file)
        for row in range(rows):
            print('|', end='', file=file)
            for col in range(cols):
                item = get_text(layout.itemAtPosition(row, col))
                print(cell.format(str(item)), end=' |', file=file)

            print(file=file)

        print(separator, file=file)
        return file.getvalue()


@contextlib.contextmanager
def nullcontext():
    """Stand-in for py3.7's contextlib.nullcontext"""
    yield


def get_component(obj):
    """
    Get the component that made the given object.

    Parameters
    ----------
    obj : ophyd.OphydItem
        The ophyd item for which to get the component.

    Returns
    -------
    component : ophyd.Component
        The component, if available.
    """
    if obj.parent is None:
        return None

    return getattr(type(obj.parent), obj.attr_name, None)


def get_variety_metadata(cpt):
    """
    Get "variety" metadata from a component or signal.

    Parameters
    ----------
    cpt : ophyd.Component or ophyd.OphydItem
        The component / ophyd item to get the metadata for.

    Returns
    -------
    metadata : dict
        The metadata, if set. Otherwise an empty dictionary.  This metadata is
        guaranteed to be valid according to the known schemas.
    """
    if not isinstance(cpt, ophyd.Component):
        cpt = get_component(cpt)

    return getattr(cpt, '_variety_metadata', {})


def widget_to_image(widget, fill_color=QtCore.Qt.transparent):
    """
    Paint the given widget in a new QtGui.QImage.

    Returns
    -------
    QtGui.QImage
        The display, as an image.
    """
    image = QtGui.QImage(widget.width(), widget.height(),
                         QtGui.QImage.Format_ARGB32_Premultiplied)

    image.fill(fill_color)
    pixmap = QtGui.QPixmap(image)

    painter = QtGui.QPainter(pixmap)
    widget.render(image)
    painter.end()
    return image


_connect_slots_unpatched = None


def patch_connect_slots():
    """
    Patches QtCore.QMetaObject.connectSlotsByName to catch SystemErrors.
    """
    global _connect_slots_unpatched

    if _connect_slots_unpatched is not None:
        return

    # TODO there could be a version check here if we can isolate it

    _connect_slots_unpatched = QtCore.QMetaObject.connectSlotsByName

    def connect_slots_patch(top_level_widget):
        try:
            return _connect_slots_unpatched(top_level_widget)
        except SystemError as ex:
            logger.debug(
                "Eating system error.  This may possibly be solved by either "
                "downgrading Python or upgrading pyqt5 to >= 5.13.1. "
                "For further discussion, see "
                "https://github.com/pcdshub/typhos/issues/354",
                exc_info=ex
            )

    QtCore.QMetaObject.connectSlotsByName = connect_slots_patch


def link_signal_to_widget(signal, widget):
    """
    Registers the signal with PyDM, and sets the widget channel.

    Parameters
    ----------
    signal : ophyd.OphydObj
        The signal to use.

    widget : QtWidgets.QWidget
        The widget with which to connect the signal.
    """
    if signal is not None:
        plugins.register_signal(signal)
        if widget is not None:
            read = not isinstance(widget, PyDMWritableWidget)
            widget.channel = channel_from_signal(signal, read=read)


def linked_attribute(property_attr, widget_attr, hide_unavailable=False):
    """
    Decorator which connects a device signal with a widget.

    Retrieves the signal from the device, registers it with PyDM, and sets the
    widget channel.

    Parameters
    ----------
    property_attr : str
        This is one level of indirection, allowing for the component attribute
        to be configurable by way of designable properties.
        In short, this looks like:
        ``getattr(self.device, getattr(self, property_attr))``
        The component attribute name may include multiple levels (e.g.,
        ``'cpt1.cpt2.low_limit'``).

    widget_attr : str
        The attribute name of the widget, referenced from ``self``.
        The component attribute name may include multiple levels (e.g.,
        ``'ui.low_limit'``).

    hide_unavailable : bool
        Whether or not to hide widgets for which the device signal is not
        available
    """
    get_widget_attr = operator.attrgetter(widget_attr)

    def wrapper(func):
        @functools.wraps(func)
        def wrapped(self):
            widget = get_widget_attr(self)
            device_attr = getattr(self, property_attr)
            get_device_attr = operator.attrgetter(device_attr)

            try:
                signal = get_device_attr(self.device)
            except AttributeError:
                signal = None
            else:
                # Fall short of an `isinstance(signal, OphydObj) check here:
                try:
                    link_signal_to_widget(signal, widget)
                except Exception:
                    logger.exception(
                        'device.%s => self.%s (signal: %s widget: %s)',
                        device_attr, widget_attr, signal, widget)
                    signal = None
                else:
                    logger.debug('device.%s => self.%s (signal=%s widget=%s)',
                                 device_attr, widget_attr, signal, widget)

            if signal is None and hide_unavailable:
                widget.setVisible(False)

            return func(self, signal, widget)

        return wrapped
    return wrapper
