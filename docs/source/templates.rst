================
Custom Templates
================
Typhos ships with a handful of built-in templates. You can see these when you
browse the ``typhos/ui/core`` and ``typhos/ui/devices`` directories.

.. note::

   This repo originally had a large number of LCLS-specific device templates.
   These have been moved to pcdsdevices.ui.


You can define your own templates outside of typhos to customize the behavior
of the module when launching screens. These can be done generically, to
replace the default templates, or per-class, to replace the templates in
specific cases.


Template Creation
=================
Templates are ``.ui`` files created in qt designer. These are largely just
normal pydm displays, with extra macro substitutions. See the
:ref:`pydm tutorial <pydm:designer>`
for more guidance on using the designer.


Template Substitutions
----------------------
All the information found in ``happi`` will be loaded as a pydm macro into the
template. It does this by checking for attributes on the ``device.md``
namespace object.

If no ``device.md`` object is found, we will still include ``device.name``
as the ``name`` macro and ``device.prefix`` as the ``prefix`` macro.

The upshot of this is that you can include ``${name}``, ``${prefix}``, and
other keys from the happi database in your template and they will be
filled in from the device database on load.


Template Filenames
------------------
To replace a default template, create a template with exactly the same name.

To create a template for a class, name it based on the class name
and the template type, e.g.:

- PositionerBase.embedded.ui
- PositionerBase.detailed.ui
- PositionerBase.engineering.ui

Note that we'll check an object class's mro() when deciding which template to
use- this is why all PositionerBase subclasses use the built-in
PositionerBase.detailed.ui template by default.

In this way you can create one template for a set of related classes.


Template Discovery
------------------
There are currently three places that typhos checks for templates.
In order of priority:

1. Check the paths defined by the ``PYDM_DISPLAYS_PATH`` environment variable.
2. Check any paths defined by the ``typhos.ui`` package entry point.
3. Check the built-in paths (core and devices)

With that in mind, there are two recommended workflows for running typhos with
custom templates:

1. Create a repository to store your screens, and set ``PYDM_DISPLAYS_PATH``
   to point to your repository clone's screens directory. This path works
   exactly like any other ``PATH`` variable in linux.
2. Create a module that defines the ``typhos.ui`` entry point. This entry
   point is expecting to find a ``str``, ``pathlib.Path``, or ``list`` of
   such objects at your entry point. One such example of how to do this can
   be found `here <https://github.com/pcdshub/pcdsdevices/blob/cab3fe158ebc0d032fe07f03ec52ca79cda90c6e/setup.py#L21>`_
