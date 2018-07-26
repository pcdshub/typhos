############
# Standard #
############
import os.path
import logging
from functools import wraps

############
# External #
############
import pytest
import ophyd.sim
from ophyd import Signal
from pydm import PyDMApplication

###########
# Package #
###########
import typhon

logger = logging.getLogger(__name__)

# Global testing variables
show_widgets = False
application = None


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
            application.establish_widget_connections(widget)
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

    def describe(self):
        return {self.name : {'enum_strs': ('a', 'b', 'c'),
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
