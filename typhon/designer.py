import logging

from pydm.widgets.qtplugin_base import qtplugin_factory

from .signal import TyphonSignalPanel
from .display import TyphonDisplay
from .func import TyphonMethodButton
from .positioner import TyphonPositionerWidget

logger = logging.getLogger(__name__)

logging.info("Loading Typhon QtDesigner plugins ...")
TyphonSignalPanelPlugin = qtplugin_factory(TyphonSignalPanel)
TyphonDisplayPlugin = qtplugin_factory(TyphonDisplay)
TyphonMethodButtonPlugin = qtplugin_factory(TyphonMethodButton)
TyphonPositionerWidgetPlugin = qtplugin_factory(TyphonPositionerWidget)
