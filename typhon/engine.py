############
# Standard #
############
import logging


############
# External #
############
from bluesky import RunEngine
from bluesky.utils import RunEngineInterrupted, install_qt_kicker
from pydm.PyQt.QtGui import QVBoxLayout, QLabel, QComboBox, QGroupBox
from pydm.PyQt.QtCore import pyqtSignal, pyqtSlot


logger = logging.getLogger(__name__)


def no_plan_warning(*args, **kwargs):
    """
    Convienence function to raise a user warning
    """
    logger.critical("Attempting to use the RunEngine "
                    "without configuring a plan")


class EngineLabel(QLabel):
    """
    QLabel to display the RunEngine Status

    Attributes
    ----------
    color_map : dict
        Mapping of Engine states to color displays
    """
    color_map = {'running': 'green',
                 'paused': 'yellow',
                 'idle': 'red'}

    @pyqtSlot('QString', 'QString')
    def on_state_change(self, state, old_state):
        """Update the display Engine"""
        # Update the label
        self.setText(state.capitalize())
        # Update the background color
        color = self.color_map[state]
        self.setStyleSheet('QLabel {background-color: %s}' % color)


class EngineControl(QComboBox):
    """
    RunEngine through a QComboBox

    Listens to the state of the RunEngine and shows the available commands for
    the current state.

    Attributes
    ----------
    null_command : str
        Display value for the empty command

    available_commands: dict
        Mapping of state to available RunEngine commands
    """
    null_command = '-'
    available_commands = {'running': ['Halt', 'Pause'],
                          'idle': ['Start'],
                          'paused': ['Abort', 'Halt',  'Resume', 'Stop']}

    @pyqtSlot('QString', 'QString')
    def on_state_change(self, state, old_state):
        # Clear old commands
        self.clear()
        # Find the list of available commands
        self.addItems([self.null_command] + self.available_commands[state])


class EngineWidget(QGroupBox):
    """
    RunEngine Control Widget

    Parameters
    ----------
    engine : RunEngine, optional
        The underlying RunEngine object. A basic version wil be instatiated if
        one is not provided

    plan : callable, optional
        A callable  that takes no parameters and returns a generator. If the
        plan is meant to be called repeatedly the function should make sure
        that a refreshed generator is returned each time

    Attributes
    ----------
    engine_state_change : pyqtSignal('QString', 'QString')
        Signal emitted by changes in the RunEngine state. The first string is
        the current state, the second is the previous state

    update_rate: float
        Update rate the qt_kicker is installed at

    command_registry: dict
        Mapping of commands received by the pyqtSlot `command` and actual
        Python callables
    """
    engine_state_change = pyqtSignal('QString', 'QString')
    update_rate = 0.02
    command_registry = {'Halt': RunEngine.halt,
                        'Start': no_plan_warning,
                        'Abort': RunEngine.abort,
                        'Resume': RunEngine.resume,
                        'Pause': RunEngine.request_pause,
                        'Stop': RunEngine.stop}

    def __init__(self, engine=None, plan=None, parent=None):
        # Instantiate widget information and layout
        super().__init__('Engine Control', parent=parent)
        self.setStyleSheet('QLabel {qproperty-alignment: AlignCenter}')
        self.label = EngineLabel(parent=self)
        self.command_label = QLabel('Available Commands')
        self.status_label = QLabel('Engine Status')
        self.control = EngineControl()
        lay = QVBoxLayout()
        lay.addWidget(self.status_label)
        lay.addWidget(self.label)
        lay.addWidget(self.command_label)
        lay.addWidget(self.control)
        self.setLayout(lay)
        # Create a new RunEngine if we were not provided one
        self._engine = None
        self._plan = None
        self.engine = engine or RunEngine()

    @property
    def plan(self):
        """
        Stored plan callable
        """
        return self._plan

    @plan.setter
    def plan(self, plan):
        logger.debug("Storing a new plan for the RunEngine")
        # Do not allow plans to be set while RunEngine is active
        if self.engine and self.engine.state != 'idle':
            logger.exception("Can not change the configured plan while the "
                             "RunEngine is running!")
            return
        # Store our plan internally
        self._plan = plan
        # Register a new call command
        self.command_registry['Start'] = (lambda x:
                                          RunEngine.__call__(x, self.plan()))

    @property
    def engine(self):
        """
        Underlying RunEngine object
        """
        return self._engine

    @engine.setter
    def engine(self, engine):
        logger.debug("Storing a new RunEngine object")
        # Do not allow engine to be swapped while RunEngine is active
        if self._engine and self._engine.state != 'idle':
            raise RuntimeError("Can not change the RunEngine while the "
                               "RunEngine is running!")
        # Create a kicker, not worried about doing this multiple times as this
        # is checked by `install_qt_kicker` itself
        install_qt_kicker(update_rate=self.update_rate)
        engine.state_hook = self.on_state_change
        # Connect signals
        self._engine = engine
        self.engine_state_change.connect(self.label.on_state_change)
        self.engine_state_change.connect(self.control.on_state_change)
        self.control.currentIndexChanged['QString'].connect(self.command)
        # Run callbacks manually to initialize widgets. We can not emit the
        # signal specifically because we can not emit signals in __init__
        state = self._engine.state
        self.label.on_state_change(state, None)
        self.control.on_state_change(state, None)

    def on_state_change(self, state, old_state):
        """
        Report a state change of the RunEngine

        This is added directly to the `RunEngine.state_hook` and emits the
        `engine_state_change` signal.

        Parameters
        ----------
        state: str

        old_state: str

        """
        self.engine_state_change.emit(state, old_state)

    @pyqtSlot('QString')
    def command(self, command):
        """
        Accepts commands and instructs the RunEngine accordingly

        Parameters
        ----------
        command : str
            Name of the command in the :attr:`.command_registry:`
        """
        # Ignore null commands
        if not command or command == self.control.null_command:
            return
        logger.info("Requested command %s for RunEngine", command)
        # Load thefunction from registry
        try:
            func = self.command_registry[command]
        except KeyError as exc:
            logger.exception('Unrecognized command for RunEngine -> %s',
                             exc)
            return
        # Execute our loaded function
        try:
            func(self.engine)
        # Pausing raises an exception
        except RunEngineInterrupted as exc:
            logger.debug("RunEngine paused")
