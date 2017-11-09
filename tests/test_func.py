############
# Standard #
############

############
# External #
############
import pytest

###########
# Package #
###########
from .conftest import show_widget
from typhon.func import FunctionPanel, FunctionDisplay

kwargs = dict()


@pytest.fixture(scope='module')
def func_display():
    # Create mock function
    def foo(first, second: float=3.14, hide: bool=True, third: bool=False):
        kwargs.update({"first": first, "second": second,
                       "hide": hide, "third": third})
    # Create display
    func_dis = FunctionDisplay(foo, annotations={'first': int},
                               hide_params=['hide'])
    return func_dis


@show_widget
def test_func_display_creation(func_display):
    # Check we made the proper number of control widgets
    assert len(func_display.param_controls) == 3
    # Check our hidden parameter is not available
    assert 'hide' not in [widget.parameter
                          for widget in func_display.param_controls]
    # Check that we sorted our parameters correctly
    assert 'first' in func_display.required_params
    assert all([key in func_display.optional_params
                for key in ['second', 'third']])
    return func_display


def test_func_execution(func_display):
    # Configure parameters
    func_display.param_controls[0].param_edit.setText('1')
    func_display.param_controls[1].param_edit.setText('3.14159')
    func_display.param_controls[2].param_control.setChecked(True)
    # Check function execution
    func_display.execute()
    assert kwargs['first'] == 1
    assert kwargs['second'] == 3.14159
    assert kwargs['hide']
    assert kwargs['third']


def test_func_exceptions(func_display):
    # Clear our cache
    kwargs.clear()
    # Configure parameters
    # Improper typing
    func_display.param_controls[0].param_edit.setText('Invalid')
    func_display.param_controls[1].param_edit.setText('3.14159')
    func_display.param_controls[2].param_control.setChecked(True)
    # Check function execution
    func_display.execute()
    # Check our function was not run
    assert kwargs == {}


@show_widget
def test_func_panel():
    # Mock functions
    def foo(a: int, b: bool=False, c: bool=True):
        pass

    def foobar(a: float, b: str, c: float=3.14, d: bool=False):
        pass
    # Create Panel
    fp = FunctionPanel([foo, foobar])
    # Check that all our methods made it in
    assert 'foo' in fp.methods
    assert 'foobar' in fp.methods
    return fp
