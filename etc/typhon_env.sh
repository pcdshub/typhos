#!/usr/bin/env bash
TYPHON_DIR=$(python -c 'import typhon; import pathlib; print(pathlib.Path(typhon.__file__).parent.parent)')
export PYQTDESIGNERPATH="$TYPHON_DIR"/etc:$PYQTDESIGNERPATH
export PYDM_DESIGNER_ONLINE=True

