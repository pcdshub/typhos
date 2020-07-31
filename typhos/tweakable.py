"""
Tweakable value widget.

Variety support pending:
- everything
"""
import logging

import qtpy
from qtpy import QtCore

from . import utils, variety

logger = logging.getLogger(__name__)


@variety.uses_key_handlers
@variety.use_for_variety_write('scalar-tweakable')
class TyphosTweakable(utils.TyphosBase):
    #  TODO rearrange package: widgets.TyphosDesignerMixin):
    """
    Widget for a tweakable scalar.

    Parameters
    ----------
    parent : QWidget
        The parent widget.

    init_channel : str, optional
        The channel to be used by the widget.

    Notes
    -----
    """

    ui_template = utils.ui_dir / 'widgets' / 'tweakable.ui'
    _readback_attr = 'readback'
    _setpoint_attr = 'setpoint'

    def __init__(self, parent=None, init_channel=None, variety_metadata=None,
                 ophyd_signal=None):

        self._ophyd_signal = ophyd_signal
        super().__init__(parent=parent)

        self.ui = qtpy.uic.loadUi(str(self.ui_template), self)
        self.ui.readback.channel = init_channel
        self.ui.setpoint.channel = init_channel
        self.ui.tweak_positive.clicked.connect(self.positive_tweak)
        self.ui.tweak_negative.clicked.connect(self.negative_tweak)

        self.variety_metadata = variety_metadata

    variety_metadata = variety.create_variety_property()

    def _update_variety_metadata(self, *, display_format=None, **kwargs):
        display_format = variety.get_display_format(display_format)
        self.ui.readback.displayFormat = display_format
        self.ui.setpoint.displayFormat = display_format

        variety._warn_unhandled_kwargs(self, kwargs)

    def tweak(self, offset):
        """Tweak by the given ``offset``."""
        try:
            setpoint = float(self.readback.text()) + float(offset)
        except Exception:
            logger.exception('Tweak failed')
            return

        self.ui.setpoint.setText(str(setpoint))
        self.ui.setpoint.send_value()

    @QtCore.Slot()
    def positive_tweak(self):
        """Tweak positive by the amount listed in ``ui.tweak_value``"""
        try:
            self.tweak(float(self.tweak_value.text()))
        except Exception:
            logger.exception('Tweak failed')

    @QtCore.Slot()
    def negative_tweak(self):
        """Tweak negative by the amount listed in ``ui.tweak_value``"""
        try:
            self.tweak(-float(self.tweak_value.text()))
        except Exception:
            logger.exception('Tweak failed')
