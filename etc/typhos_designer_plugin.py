print("Importing Typhos QtDesigner plugins...")
import pydm  # noqa
from typhos.designer import *  # noqa

print("Loaded Typhos QtDesigner plugins. Available PyDM data plugins:",
      ', '.join(pydm.data_plugins.plugin_modules))
