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
from pydm.PyQt.QtGui import QStackedWidget, QPushButton
from pydm.PyQt.QtCore import QObject, pyqtSignal, pyqtSlot


logger = logging.getLogger(__name__)


class QRunEngine(QObject, RunEngine):

    state_changed = pyqtSignal('QString', 'QString')
    update_rate = 0.02
    command_registry = {'Halt': RunEngine.halt,
                        'Abort': RunEngine.abort,
                        'Resume': RunEngine.resume,
                        'Pause': RunEngine.request_pause,
                        'Stop': RunEngine.stop}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Attach the state_hook to emit signals
        self.state_hook = self.on_state_change
        # Create a kicker, not worried about doing this multiple times as this
        # is checked by `install_qt_kicker` itself
        install_qt_kicker(update_rate=self.update_rate)
        # Allow a plan to be stored on the RunEngine
        self.plan_creator = None

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
        self.state_changed.emit(state, old_state)

    @pyqtSlot()
    def start(self):
        """Start the RunEngine"""
        if not self.plan_creator:
            logger.error("Commanded RunEngine to start but there "
                         "is no source for a plan")
            return
        # Execute our loaded function
        try:
            self.__call__(self.plan_creator())
        # Pausing raises an exception
        except RunEngineInterrupted as exc:
            logger.debug("RunEngine paused")

    @pyqtSlot()
    def pause(self):
        """Pause the RunEngine"""
        self.request_pause()

    @pyqtSlot('QString')
    def command(self, command):
        """
        Accepts commands and instructs the RunEngine accordingly

        Parameters
        ----------
        command : str
            Name of the command in the :attr:`.command_registry:`
        """
        logger.info("Requested command %s for RunEngine", command)
        # Load the function from registry
        try:
            func = self.command_registry[command]
        # Catch commands that we have no idea how to obey 
        except KeyError as exc:
            logger.exception('Unrecognized command for RunEngine -> %s',
                             exc)
        # Execute the command
        else:
            try:
                func(self)
            except RunEngineInterrupted as exc:
                logger.debug("RunEngine paused")


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


    def connect(self, engine):
        """Connect an existing QRunEngine"""
        engine.state_changed.connect(self.on_state_change)
        self.on_state_change(engine.state, None)

class EngineControl(QStackedWidget):
    """
    RunEngine through a QComboBox

    Listens to the state of the RunEngine and shows the available commands for
    the current state.

    Attributes
    ----------
    state_widgets: dict

    pause_commands: list
        Available RunEngine commands while the Engine is Paused
    """
    pause_commands = ['Abort', 'Halt',  'Resume', 'Stop']

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # Create our widgets
        self.state_widgets = {'idle': QPushButton('Start'),
                              'running': QPushButton('Pause'),
                              'paused': QComboBox()}
        # Add the options to QComboBox
        self.state_widgets['paused'].insertItems(0, self.pause_commands)
        # Add all the widgets to the stack
        for widget in self.state_widgets.values():
            self.addWidget(widget)

    @pyqtSlot('QString', 'QString')
    def on_state_change(self, state, old_state):
        """Update the control widget based on the state"""
        self.setCurrentWidget(self.state_widgets[state])

    def connect(self, engine):
        """Connect a QRunEngine object"""
        # Connect all the control signals to the engine slots
        self.state_widgets['idle'].clicked.connect(engine.start)
        self.state_widgets['running'].clicked.connect(engine.request_pause)
        self.state_widgets['paused'].activated['QString']\
                                    .connect(engine.command)
        # Update our control widgets based on this engine
        engine.state_changed.connect(self.on_state_change)
        # Set the current widget correctly
        self.on_state_change(engine.state, None)


class EngineWidget(QGroupBox):
    """
    RunEngine Control Widget

    Parameters
    ----------
    engine : RunEngine, optional
        The underlying RunEngine object. A basic version wil be instatiated if
        one is not provided

    plan_creator : callable, optional
        A callable  that takes no parameters and returns a generator. If the
        plan is meant to be called repeatedly the function should make sure
        that a refreshed generator is returned each time
    """
    def __init__(self, engine=None, plan_creator=None, parent=None):
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
        self.engine = engine or QRunEngine()
        if plan_creator:
            self.engine.plan_creator = plan_creator

    @property
    def engine(self):
        """
        Underlying QRunEngine object
        """
        return self._engine

    @engine.setter
    def engine(self, engine):
        logger.debug("Storing a new RunEngine object")
        # Do not allow engine to be swapped while RunEngine is active
        if self._engine and self._engine.state != 'idle':
            raise RuntimeError("Can not change the RunEngine while the "
                               "RunEngine is running!")
        # Connect signals
        self._engine = engine
        self.label.connect(self._engine)
        self.control.connect(self._engine)
