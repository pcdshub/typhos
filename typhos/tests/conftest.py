import logging
import os.path
import pathlib
import time
from functools import wraps

import numpy as np
import ophyd.sim
import pytest
import qtpy
from happi import Client
from ophyd import Component as Cpt
from ophyd import Device
from ophyd import FormattedComponent as FC
from ophyd.sim import Signal, SynAxis, SynPeriodicSignal
from pydm import PyDMApplication
from pydm.widgets.logdisplay import GuiHandler
from qtpy import QtGui, QtWidgets

import typhos
from typhos.plugins.happi import register_client
from typhos.utils import SignalRO, TyphosBase

logger = logging.getLogger(__name__)

# Global testing variables
show_widgets = False
application = None

MODULE_PATH = pathlib.Path(__file__).parent


# Patch TyphosConsole on TyphosSuite. Creation of more than one QtConsole
# quicky in the test suite causes instabilities
typhos.TyphosSuite.default_tools['Console'] = TyphosBase


def pytest_addoption(parser):
    parser.addoption("--dark", action="store_true", default=False,
                     help="Use the dark stylesheet to display widgets")
    parser.addoption("--show-ui", action="store_true", default=False,
                     help="Show the widgets produced by each test")


# Create a fixture to configure whether widgets are shown or not
@pytest.fixture(scope='session', autouse=True)
def _show_widgets(pytestconfig):
    global show_widgets
    show_widgets = pytestconfig.getoption('--show-ui')
    if show_widgets:
        logger.info("Running tests while showing created widgets ...")


@pytest.fixture(scope='session', autouse=True)
def qapp(pytestconfig):
    global application
    if application:
        pass
    else:
        application = PyDMApplication(use_main_window=False)
        typhos.use_stylesheet(pytestconfig.getoption('--dark'))
    return application


@pytest.fixture(scope='session')
def test_images():
    return (os.path.join(os.path.dirname(__file__), 'utils/lenna.png'),
            os.path.join(os.path.dirname(__file__), 'utils/python.png'))


def save_image(widget, name, delay=0.5):
    '''
    Save `widget` to typhos/tests/artifacts/{name}.png after `delay` seconds.
    '''
    widget.show()

    app = QtWidgets.QApplication.instance()

    end_time = time.time() + delay
    while time.time() < end_time:
        app.processEvents()
        time.sleep(0.1)

    image = QtGui.QImage(widget.width(), widget.height(),
                         QtGui.QImage.Format_ARGB32_Premultiplied)

    image.fill(qtpy.QtCore.Qt.transparent)
    pixmap = QtGui.QPixmap(image)

    painter = QtGui.QPainter(pixmap)
    widget.render(image)
    painter.end()

    artifacts_path = MODULE_PATH / 'artifacts'
    artifacts_path.mkdir(exist_ok=True)

    path = str(artifacts_path / f'{name}.png')
    image.save(path)
    logger.debug('saved image to %s', path)


def show_widget(func):
    """
    Show a widget returned from arbitrary `func`
    """
    @wraps(func)
    def func_wrapper(*args, **kwargs):
        # Run function grab widget
        widget = func(*args, **kwargs)
        if widget is not None:
            save_image(widget, func.__name__)
        if show_widgets:
            # Display the widget
            widget.show()
            # Start the application
            application.exec_()
    return func_wrapper


@pytest.fixture(scope='session')
def motor():
    # Register all signals
    for sig in ophyd.sim.motor.component_names:
        typhos.register_signal(getattr(ophyd.sim.motor, sig))
    return ophyd.sim.motor


class RichSignal(Signal):

    def describe(self):
        return {self.name: {'enum_strs': ('a', 'b', 'c'),
                            'precision': 2,
                            'units': 'urad',
                            'dtype': 'number',
                            'shape': []}}


class DeadSignal(Signal):
    subscribable = False

    def subscribe(self, *args, **kwargs):
        if self.subscribable:
            pass
        else:
            raise TimeoutError("Timeout on subscribe")

    def get(self, *args, **kwargs):
        raise TimeoutError("Timeout on get")

    def describe(self, *args, **kwargs):
        raise TimeoutError("Timeout on describe")


class ConfiguredSynAxis(SynAxis):
    velocity = Cpt(Signal, value=100, kind='normal')
    acceleration = Cpt(Signal, value=10, kind='normal')
    resolution = Cpt(Signal, value=5, kind='normal')


class RandomSignal(SynPeriodicSignal):
    """
    Signal that randomly updates a random integer
    """

    def __init__(self, *args, **kwargs):
        super().__init__(func=lambda: np.random.uniform(0, 100),
                         period=10, period_jitter=4, **kwargs)


class MockDevice(Device):
    # Device signals
    readback = Cpt(RandomSignal, kind='normal')
    noise = Cpt(RandomSignal, kind='normal')
    transmorgifier = Cpt(SignalRO, value=4, kind='normal')
    setpoint = Cpt(Signal, value=0, kind='normal')

    velocity = Cpt(Signal, value=1, kind='config')
    flux = Cpt(RandomSignal, kind='config')
    modified_flux = Cpt(RandomSignal, kind='config')
    capacitance = Cpt(RandomSignal, kind='config')
    acceleration = Cpt(Signal, value=3, kind='config')
    limit = Cpt(Signal, value=4, kind='config')
    inductance = Cpt(RandomSignal, kind='normal')

    transformed_inductance = Cpt(SignalRO, value=3, kind='omitted')
    core_temperature = Cpt(RandomSignal, kind='omitted')
    resolution = Cpt(Signal, value=5, kind='omitted')
    duplicator = Cpt(Signal, value=6, kind='omitted')

    # Component Motors
    x = FC(ConfiguredSynAxis, name='X Axis')
    y = FC(ConfiguredSynAxis, name='Y Axis')
    z = FC(ConfiguredSynAxis, name='Z Axis')

    def insert(self, width: float = 2.0, height: float = 2.0,
               fast_mode: bool = False):
        """Fake insert function to display"""
        pass

    def remove(self, height: float,  fast_mode: bool = False):
        """Fake remove function to display"""
        pass

    @property
    def hints(self):
        return {'fields': [self.name+'_readback']}


@pytest.fixture(scope='function')
def device():
    dev = MockDevice('Tst:This', name='Simulated Device')
    yield dev
    clear_handlers(dev)


def clear_handlers(device):
    if isinstance(device.log, logging.Logger):
        _logger = device.log
    else:
        _logger = device.log.logger

    for handler in list(_logger.handlers):
        if isinstance(handler, GuiHandler):
            _logger.handlers.remove(handler)


@pytest.fixture(scope='session')
def client():
    client = Client(path=os.path.join(os.path.dirname(__file__),
                                      'happi.json'))
    register_client(client)
    return client


@pytest.fixture(scope='session')
def happi_cfg():
    path = str(MODULE_PATH / 'happi.cfg')
    os.environ['HAPPI_CFG'] = path
    return path
