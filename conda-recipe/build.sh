# Install the package
$PYTHON setup.py install --single-version-externally-managed --record=record.txt

# Create auxillary
mkdir -p $PREFIX/etc/conda/activate.d
mkdir -p $PREFIX/etc/conda/deactivate.d
mkdir -p $PREFIX/etc/typhos

# Create auxiliary vars
DESIGNER_PLUGIN_PATH=$PREFIX/etc/typhos
DESIGNER_PLUGIN=$DESIGNER_PLUGIN_PATH/typhos_designer_plugin.py
ACTIVATE=$PREFIX/etc/conda/activate.d/typhos.sh
DEACTIVATE=$PREFIX/etc/conda/deactivate.d/typhos.sh

echo "from typhos.designer import *" >> $DESIGNER_PLUGIN
echo "export PYQTDESIGNERPATH="$DESIGNER_PLUGIN_PATH":\$PYQTDESIGNERPATH" >> $ACTIVATE
echo "export PYDM_DESIGNER_ONLINE=True" >> $ACTIVATE
echo "unset PYQTDESIGNERPATH" >> $DEACTIVATE

unset DESIGNER_PLUGIN_PATH
unset DESIGNER_PLUGIN
unset ACTIVATE
unset DEACTIVATE
