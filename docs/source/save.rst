##################
Saving and Loading
##################
:class:`.TyphonSuite` objects can be stored for later use. The devices that
were loaded into the suite via :meth:`.TyphonSuite.add_device` will be added
once again assuming that they are stored in a ``happi`` database. When you call
:meth:`.TyphonSuite.save` a Python file with the template shown below is saved
to disk.

.. code:: python

    import sys
    import typhon.cli

    devices = {devices}

    def create_suite(cfg=None):
        return typhon.cli.create_suite(devices, cfg=cfg)

    if __name__ == '__main__':
        typhon.cli.typhon_cli(devices + sys.argv[1:])


There are two major ways to use this created file:

1. Execute the Python file from the command line. This will route the call
   through the standard :func:`.cli.typhon_cli` meaning all options
   described there are also available.

.. code:: bash

   $ python saved_suite.py


2. The ``create_suite`` method generated in the saved file can be used to
   re-create the :class:`.TyphonSuite` in an already running Python process.
   Typhon provides the :func:`.load_suite` function to import the provided
   Python file and execute the stored ``create_suite`` method.  This is useful
   if you want to use the file to embed a saved :class:`.TyphonSuite` inside
   another PyQt window for instance, or load multiple suites at once.


.. code:: python

   from qtpy.QtWidgets import QApplication
   from typhon import load_suite

   app = QApplication([])
   saved_suite = load_suite('saved_suite.py')

   saved_suite.show()
   app.exec_()

 
.. note::

   The saved file only stores a reference to the devices loaded into the
   ``TyphonSuite`` by name. It is assumed that these devices will be available
   under the same name via the configured ``happi`` database when
   ``load_suite`` is called. If the device has a different name in the database
   or you have configured a different ``happi`` database to be used your
   devices will not be loaded properly.

  
