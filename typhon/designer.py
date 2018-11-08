import logging

from pydm.widgets.qtplugin_base import qtplugin_factory

from .signal import TyphonPanel


logger = logging.getLogger(__name__)

logging.info("Loading Typhon QtDesigner plugins ...")
TyphonPanelPlugin = qtplugin_factory(TyphonPanel)
