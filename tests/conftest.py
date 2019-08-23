############
# Standard #
############
import os.path
import pathlib
import logging
from functools import wraps

############
# External #
############
from happi import Client
import numpy as np
import ophyd.sim
from ophyd import Device, Component as C, FormattedComponent as FC
from ophyd.sim import SynAxis, Signal, SynPeriodicSignal, SignalRO
import pytest
from pydm import PyDMApplication

###########
# Package #
###########
import typhon
from typhon.plugins.happi import register_client
from typhon.utils import TyphonBase

logger = logging.getLogger(__name__)

# Global testing variables
show_widgets = False
application = None

# Patch TyphonConsole on TyphonSuite. Creation of more than one QtConsole
# quicky in the test suite causes instabilities
typhon.TyphonSuite.default_tools['Console'] = TyphonBase


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
        typhon.use_stylesheet(pytestconfig.getoption('--dark'))
    return application


@pytest.fixture(scope='session')
def test_images():
    return (os.path.join(os.path.dirname(__file__), 'utils/lenna.png'),
            os.path.join(os.path.dirname(__file__), 'utils/python.png'))


def show_widget(func):
    """
    Show a widget returned from arbitrary `func`
    """
    @wraps(func)
    def func_wrapper(*args, **kwargs):
        # Run function grab widget
        widget = func(*args, **kwargs)
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
        typhon.register_signal(getattr(ophyd.sim.motor, sig))
    return ophyd.sim.motor


class RichSignal(Signal):

    def __init__(self, *args, metadata=None, **kwargs):
        metadata = metadata or dict()
        metadata.update({'enum_strs': ('a', 'b', 'c'),
                         'severity': 0,
                         'precision': 2,
                         'lower_ctrl_limit': -100,
                         'upper_ctrl_limit': 100,
                         'units': 'urad'})
        super().__init__(*args, metadata=metadata, **kwargs)

    def describe(self):
        """Add metadata to description"""
        desc = super().describe()
        desc[self.name].update(self._metadata)
        return desc

class DeadSignal(Signal):
    subscribable = False

    def wait_for_connection(self, *args, **kwargs):
        raise TimeoutError("Timeout on wait_for_connection")

    def get(self, *args, **kwargs):
        raise TimeoutError("Timeout on get")

    def describe(self, *args, **kwargs):
        raise TimeoutError("Timeout on describe")


class ConfiguredSynAxis(SynAxis):
    velocity = C(Signal, value=100)
    acceleration = C(Signal, value=10)
    resolution = C(Signal, value=5)
    _default_configuration_attrs = ['velocity', 'acceleration']


class RandomSignal(SynPeriodicSignal):
    """
    Signal that randomly updates a random integer
    """
    def __init__(self,*args, **kwargs):
        super().__init__(func=lambda: np.random.uniform(0, 100),
                         period=10, period_jitter=4, **kwargs)


class MockDevice(Device):
    # Device signals
    readback = C(RandomSignal)
    noise = C(RandomSignal)
    transmorgifier = C(SignalRO, value=4)
    setpoint = C(Signal, value=0)
    velocity = C(Signal, value=1)
    flux = C(RandomSignal)
    modified_flux = C(RandomSignal)
    capacitance = C(RandomSignal)
    acceleration = C(Signal, value=3)
    limit = C(Signal, value=4)
    inductance = C(RandomSignal)
    transformed_inductance = C(SignalRO, value=3)
    core_temperature = C(RandomSignal)
    resolution = C(Signal, value=5)
    duplicator = C(Signal, value=6)

    # Component Motors
    x = FC(ConfiguredSynAxis, name='X Axis')
    y = FC(ConfiguredSynAxis, name='Y Axis')
    z = FC(ConfiguredSynAxis, name='Z Axis')

    # Default Signal Sorting
    _default_read_attrs = ['readback', 'setpoint', 'transmorgifier',
                           'noise', 'inductance']
    _default_configuration_attrs = ['flux', 'modified_flux', 'capacitance',
                                    'velocity', 'acceleration']

    def insert(self, width: float=2.0, height: float=2.0,
               fast_mode: bool=False):
        """Fake insert function to display"""
        pass

    def remove(self, height: float,  fast_mode: bool=False):
        """Fake remove function to display"""
        pass

    @property
    def hints(self):
        return {'fields': [self.name+'_readback']}


@pytest.fixture(scope='function')
def device():
    return MockDevice('Tst:This', name='Simulated Device')


@pytest.fixture(scope='session')
def client():
    client = Client(path=os.path.join(os.path.dirname(__file__),
                                      'happi.json'))
    register_client(client)
    return client


@pytest.fixture(scope='session')
def happi_cfg():
    path = pathlib.Path(__file__)
    return str(path.parent / 'happi.cfg')
