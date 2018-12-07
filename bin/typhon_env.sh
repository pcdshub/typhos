#!/usr/bin/env bash
TYPHON_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
export PYQTDESIGNERPATH="$TYPHON_DIR":$PYQTDESIGNERPATH
export PYDM_DESIGNER_ONLINE=True

