############
# Standard #
############
import logging
from functools import wraps
############
# External #
############
import pytest
from pydm import PyDMApplication
###########
# Package #
###########

logger = logging.getLogger(__name__)

#Global testing variables
show_widgets = False
application  = None


def pytest_addoption(parser):
    parser.addoption("--log", action="store", default="INFO",
                     help="Set the level of the log")
    parser.addoption("--logfile", action="store", default=None,
                     help="Write the log output to specified file path")
    parser.addoption("--show", action="store_true", default=False,
                     help="Show the widgets produced by each test")

#Create a fixture to automatically instantiate logging setup
@pytest.fixture(scope='session', autouse=True)
def _set_level(pytestconfig):
    #Read user input logging level
    log_level = getattr(logging, pytestconfig.getoption('--log'), None)

    #Report invalid logging level
    if not isinstance(log_level, int):
        raise ValueError("Invalid log level : {}".format(log_level))

    #Create basic configuration
    logging.basicConfig(level=log_level,
                        filename=pytestconfig.getoption('--logfile'),
                        format='%(asctime)s - %(levelname)s ' +
                               '- %(name)s - %(message)s')

#Create a fixture to configure whether widgets are shown or not
@pytest.fixture(scope='session', autouse=True)
def _show_widgets(pytestconfig):
    global show_widgets
    show_widgets = pytestconfig.getoption('--show')
    if show_widgets:
        logger.info("Running tests while showing created widgets ...")

@pytest.fixture(scope='module')
def qapp():
    global application
    if application:
        pass
    else:
        application = PyDMApplication()
    return application

def show_widget(func):
    """
    Show a widget returned from arbitrary `func`
    """
    @wraps(func)
    def func_wrapper(*args, **kwargs):
        #Run function grab widget
        widget = func(*args, **kwargs)
        if show_widgets:
            #Display the widget
            widget.show()
            #Start the application
            application.exec_()
    return func_wrapper
