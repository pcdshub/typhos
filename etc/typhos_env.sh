#!/usr/bin/env bash
TYPHOS_DIR=$(python -c 'import typhos; import pathlib; print(pathlib.Path(typhos.__file__).parent.parent)')
export PYQTDESIGNERPATH="$TYPHOS_DIR"/etc:$PYQTDESIGNERPATH
export PYDM_DESIGNER_ONLINE=True

