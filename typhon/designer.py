import logging

from pydm.widgets.qtplugin_base import qtplugin_factory

from .signal import TyphonPanel
from .display import TyphonDisplay
from .func import TyphonMethodButton
logger = logging.getLogger(__name__)

logging.info("Loading Typhon QtDesigner plugins ...")
TyphonPanelPlugin = qtplugin_factory(TyphonPanel)
TyphonDisplayPlugin = qtplugin_factory(TyphonDisplay)
TyphonMethodButtonPlugin = qtplugin_factory(TyphonMethodButton)
