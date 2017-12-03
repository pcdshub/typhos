=====================
Including Python Code
=====================


Adding Methods
==============
Each :class:`.TyphonDisplay` has an :attr:`.method_panel`. You can add methods
manually or pass them in via the constructor. In order to make the appropriate
widgets,  the function signature is examined. For example lets make a mock
function:

.. code:: python

   def foo(a: int, b: int, c: bool=False, d: float=3.14, e: bool=False):
       pass

When you add the method to the panel the Python ``inspect`` module looks for
type annotations for each parameter. It also determines which parameters are
optional and which are not. Boolean variables are given QCheckboxes, while
others are given QLineEdits for entry. Optional keywords are also hidden from
the user unless they choose to expand the tab. Using
:meth:`.FunctionPanel.add_method` would look like this:

.. code:: python

   panel.add_method(foo, hide_params=['e'])


|function| |expanded|


.. |function| image:: _static/function.png
   :width: 40 %

.. |expanded| image:: _static/expanded.jpg
   :width: 40 %


If you don't want to annotate your function as above, Typhon will attempt to
guess the type of optional variables via their default value. You can also pass
in an `annotations` dictionary that fulfills the indicates the type of each
variable.
