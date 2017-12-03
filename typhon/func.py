"""
Display an arbitrary Python function inside our PyQt UI

The class :class:`.FunctionDisplay` uses the function annotation language
described in PEP 3107 to automatically create a widget based on the arguments
and keywords contained within.

To keep track of parameter information subclassed versions of QWidgets are
instantiated. Each one is expected to keep track of the parameter it controls
with the attribute ``parameter``, and each one should return the present value
with the correct type with the method `get_param_value``. There may be cases
where these widgets find that the user has entered inappropriate values, in
this case they should return np.nan to halt the function from being called.
"""
############
# Standard #
############
import logging
import inspect
from functools import partial

############
# External #
############
import numpy as np
from pydm.PyQt.QtCore import pyqtSlot, Qt, QSize
from pydm.PyQt.QtGui import QSizePolicy, QFont, QGroupBox, QHBoxLayout, QLabel
from pydm.PyQt.QtGui import QSpacerItem, QWidget, QPushButton
from pydm.PyQt.QtGui import QLineEdit, QVBoxLayout, QCheckBox

###########
# Package #
###########
from .utils import clean_attr
from .panel import Panel

logger = logging.getLogger(__name__)


class ParamWidget(QWidget):
    """
    Generic Parameter Widget

    This creates the QLabel for the parameter and defines the interface
    required for subclasses of the ParamWidget
    """
    def __init__(self, parameter,  default=inspect._empty, parent=None):
        super().__init__(parent=parent)
        # Store parameter information
        self.parameter = parameter
        self.default = default
        self.setLayout(QHBoxLayout())
        # Create our label
        self.param_label = QLabel(parent=self)
        self.param_label.setText(clean_attr(parameter))
        self.layout().addWidget(self.param_label)
        # Indicate required parameters in bold font
        if default == inspect._empty:
            logger.debug("Inferring that %s has no default", parameter)
            bold = QFont()
            bold.setBold(True)
            self.param_label.setFont(bold)

    def get_param_value(self):
        """Must be redefined by subclasses"""
        raise NotImplementedError


class ParamCheckBox(ParamWidget):
    """
    QCheckBox for operator control of boolean values

    Parameters
    ----------
    parameter : str
        Name of parameter this widget controls

    default : bool, optional
        Default state of the box

    parent : QWidget, optional
    """
    def __init__(self, parameter, default=inspect._empty, parent=None):
        super().__init__(parameter, default=default, parent=parent)
        self.param_control = QCheckBox(parent=self)
        self.layout().addWidget(self.param_control)
        # Configure default QCheckBox position
        if default != inspect._empty:
            self.param_control.setChecked(default)

    def get_param_value(self):
        """
        Return the checked state of the QCheckBox
        """
        return self.param_control.isChecked()


class ParamLineEdit(ParamWidget):
    """
    QLineEdit for typed user entry control

    Parameter
    ---------
    parameter : str
        Name of parameter this widget controls

    _type : type
        Type to convert the text to before sending it to the function. All
        values are initially `QString`s and then they are converted to the
        specified type. If this raises a ``ValueError`` due to an improperly
        entered value a ``np.nan`` is returned.

    default : bool, optional
        Default text for the QLineEdit. This if automatically populated into
        the QLineEdit field and it is also set as the ``placeHolderText``

    parent : QWidget, optional
    """
    def __init__(self, parameter, _type, default='', parent=None):
        super().__init__(parameter, default=default, parent=parent)
        # Store type information
        self._type = _type
        # Create our LineEdit
        # Set our default text
        self.param_edit = QLineEdit(parent=self)
        self.param_edit.setAlignment(Qt.AlignCenter)
        self.layout().addWidget(self.param_edit)
        # Configure default text of LineEdit
        # If there is no default, still give some placeholder text
        # to indicate the type of the command needed
        if default != inspect._empty:
            self.param_edit.setText(str(self.default))
            self.param_edit.setPlaceholderText(str(self.default))
        elif self._type in (int, float):
            self.param_edit.setPlaceholderText(str(self._type(0.0)))

    def get_param_value(self):
        """
        Return the current value of the QLineEdit converted to :attr:`._type`
        """
        # Cast the current text into our type
        try:
            val = self._type(self.param_edit.text())
        # If not possible, capture the exception and report `np.nan`
        except ValueError as exc:
            logger.exception("Could not convert text to %r",
                             self._type.__name__)
            val = np.nan
        return val


class FunctionDisplay(QGroupBox):
    """
    Display controls for an annotated function in a QGroupBox

    In order to display function arguments in the user interface, the class
    must be aware of what the type is of each of the parameters. Instead of
    requiring a user to enter this information manually, the class takes
    advantage of the function annotation language described in PEP 3107. This
    allows us to quickly create the appropriate widget for the given parameter
    based on the type.

    If a function parameter is not given an annotation, we will attempt to
    infer it from the default value if available. If this is not possible, and
    the type is not specified in the ``annotations`` dictionary an exception
    will be raised.

    The created user interface consists of a button to execute the function,
    the required parameters are always displayed beneath the button, and
    a :class:`.Panel` object that toggles the view of the optional parameters
    below.

    Attributes
    ----------
    accepted_types : list
        List of types FunctionDisplay can create widgets for

    Parameters
    ----------
    func : callable

    name : str, optional
        Name to label the box with, by default this will be the function
        meeting

    annotations : dict, optional
        If the function your are creating a display for is not annotated, you
        may manually supply types for parameters by passing in a dictionary of
        name to type mapping

    hide_params : list, optional
        List of parameters to exclude from the display. These should have
        appropriate defaults. By default, ``self``, ``args`` and ``kwargs`` are
        all excluded

    parent : QWidget, optional
    """
    accepted_types = [bool, str, int, float]

    def __init__(self, func, name=None, annotations=None,
                 hide_params=None, parent=None):
        # Function information
        self.func = func
        self.signature = inspect.signature(func)
        self.name = name or self.func.__name__
        # Initialize parent
        super().__init__('{} Parameters'.format(clean_attr(self.name)),
                         parent=parent)
        # Ignore certain parameters, args and kwargs by default
        self.hide_params = ['self', 'args', 'kwargs']
        if hide_params:
            self.hide_params.extend(hide_params)
        # Create basic layout
        self._layout = QVBoxLayout()
        self._layout.setSpacing(2)
        self.setLayout(self._layout)
        # Create an empty list to fill later with parameter widgets
        self.param_controls = list()
        # Add our button to execute the function
        self.execute_button = QPushButton()
        self.execute_button.setText(clean_attr(self.name))
        self.execute_button.clicked.connect(self.execute)
        self._layout.addWidget(self.execute_button)
        # Add a panel for the optional parameters
        self.optional = Panel("Optional Parameters")
        self.optional.contents = QWidget()
        self.optional.contents.setLayout(QVBoxLayout())
        self.optional.contents.layout().setSpacing(2)
        self.optional.layout().addWidget(self.optional.contents)
        self.optional.show_contents(False)
        self._layout.addWidget(self.optional)
        self._layout.addItem(QSpacerItem(10, 5, vPolicy=QSizePolicy.Expanding))
        # Create parameters from function signature
        annotations = annotations or dict()
        for param in [param for param in self.signature.parameters.values()
                      if param.name not in self.hide_params]:
            logger.debug("Adding parameter %s ", param.name)
            # See if we received a manual annotation for this parameter
            if param.name in annotations:
                _type = annotations[param.name]
                logger.debug("Found manually specified type %r",
                             _type.__name__)
            # Try and get the type from the function annotation
            elif param.annotation != inspect._empty:
                _type = param.annotation
                logger.debug("Found annotated type %r ",
                             _type.__name__)
            # Try and get the type from the default value
            elif param.default != inspect._empty:
                _type = type(param.default)
                logger.debug("Gathered type %r from parameter default ",
                             _type.__name__)
            # If we don't have a default value or an annotation,
            # we can not make a widget for this parameter. Since
            # this is a required variable (no default), the function
            # will not work without it. Raise an Exception
            else:
                raise TypeError("Parameter {} has an unspecified "
                                "type".format(param.name))
            # Add our parameter
            self.add_parameter(param.name, _type, default=param.default)
        # Hide optional parameter widget if there are no such parameters
        if not self.optional_params:
            self.optional.hide()

    @property
    def required_params(self):
        """
        Required parameters
        """
        parameters = self.signature.parameters
        return [param.parameter for param in self.param_controls
                if parameters[param.parameter].default == inspect._empty]

    @property
    def optional_params(self):
        """
        Optional parameters
        """
        parameters = self.signature.parameters
        return [param.parameter for param in self.param_controls
                if parameters[param.parameter].default != inspect._empty]

    @pyqtSlot()
    def execute(self):
        """
        Execute :attr:`.func`

        This takes the parameters configured by the :attr:`.param_controls`
        widgets and passes them into the given callable. All generated
        exceptions are captured and logged
        """
        logger.info("Executing %s ...", self.name)
        # If our function does not take any argument
        # just pass it on. Otherwise, collect information
        # from the appropriate widgets
        if not self.signature.parameters:
            func = self.func
        else:
            kwargs = dict()
            # Gather information from parameter widgets
            for button in self.param_controls:
                logger.debug("Gathering parameters for %s ...",
                             button.parameter)
                val = button.get_param_value()
                logger.debug("Received %s", val)
                # Watch for NaN values returned from widgets
                # This indicates that there was improper information given
                if np.isnan(val):
                    logger.error("Invalid information supplied for %s "
                                 "parameter", button.parameter)
                    return
                kwargs[button.parameter] = val
            # Button up function call with partial to try below
            func = partial(self.func, **kwargs)
        try:
            # Execute our function
            func()
        except Exception as exc:
            logger.exception("Exception while executing function")
        else:
            logger.info("Operation Complete")

    def add_parameter(self, name, _type, default=inspect._empty):
        """
        Add a parameter to the function display

        Parameters
        ----------
        name : str
            Parameter name

        _type : type
            Type of variable that we are expecting the user to input

        default : optional
            Default value for the parameter
        """
        # Create our parameter control widget
        # QCheckBox field
        if _type == bool:
            cntrl = ParamCheckBox(name, default=default)
        else:
            # Check if this is a valid type
            if _type not in self.accepted_types:
                raise TypeError("Parameter {} has type {} which can not "
                                "be represented in a widget"
                                "".format(name, _type.__name__))
            # Create our QLineEdit
            cntrl = ParamLineEdit(name, default=default, _type=_type)
        # Add our button to the widget
        # If it is required add it above the panel so that it is always
        # visisble. Otherwise, add it to the hideable panel
        self.param_controls.append(cntrl)
        if default == inspect._empty:
            self.layout().insertWidget(len(self.required_params), cntrl)
        else:
            # If this is the first optional parameter,
            # show the whole optional panel
            if self.optional.isHidden():
                self.optional.show()
            # Add the control widget to our contents
            self.optional.contents.layout().addWidget(cntrl)

    def sizeHint(self):
        """Suggested size"""
        return QSize(175, 100)


class FunctionPanel(Panel):
    """
    Function Panel

    Similar to :class:`.SignalPanel` but instead displays a set of function
    widgets arranged in a row. Each provided method has a
    :class:`.FunctionDisplay` generated for it an added to the layout

    Parameters
    ----------
    methods : list of callables, optional
        List of callables to add to the FunctionPanel

    parent : QWidget
    """
    def __init__(self, methods=None, parent=None):
        # Initialize parent
        super().__init__("Functions", parent=parent)
        self.contents = QWidget()
        self.layout().addWidget(self.contents)
        # Create Layout
        self.contents.setLayout(QHBoxLayout())
        # Add two spacers to center our functions without
        # expanding them
        self.contents.layout().addItem(QSpacerItem(10, 20))
        self.contents.layout().addItem(QSpacerItem(10, 20))
        # Add methods
        methods = methods or list()
        self.methods = dict()
        for method in methods:
            self.add_method(method)

    def add_method(self, func, *args, **kwargs):
        """
        Add a :class:`.FunctionDisplay`

        Parameters
        ----------
        func : callable
            Annotated callable function

        args, kwargs:
            All additional parameters are passed directly to the
            :class:`.FunctionDisplay` constructor
        """
        # Create method display
        func_name = kwargs.get('name', func.__name__)
        logger.debug("Adding method %s ...", func_name)
        widget = FunctionDisplay(func, *args, **kwargs)
        # Store for posterity
        self.methods[func_name] = widget
        # Add to panel. Make sure that if this is
        # the first added method that the panel is visible
        self.show_contents(True)
        self.contents.layout().insertWidget(len(self.methods),
                                            widget)
