# Install the package
$PYTHON setup.py install --single-version-externally-managed --record=record.txt

# Create auxillary
mkdir -p $PREFIX/etc/conda/activate.d
mkdir -p $PREFIX/etc/conda/deactivate.d
mkdir -p $PREFIX/etc/typhon

# Create auxiliary vars
DESIGNER_PLUGIN_PATH=$PREFIX/etc/typhon
DESIGNER_PLUGIN=$DESIGNER_PLUGIN_PATH/typhon_designer_plugin.py
ACTIVATE=$PREFIX/etc/conda/activate.d/typhon.sh
DEACTIVATE=$PREFIX/etc/conda/deactivate.d/typhon.sh

echo "from typhon.designer import *" >> $DESIGNER_PLUGIN
echo "export PYQTDESIGNERPATH="$DESIGNER_PLUGIN_PATH":$PYQTDESIGNERPATH" >> $ACTIVATE
echo "export PYDM_DESIGNER_ONLINE=True" >> $ACTIVATE
echo "unset PYQTDESIGNERPATH" >> $DEACTIVATE

unset DESIGNER_PLUGIN_PATH
unset DESIGNER_PLUGIN
unset ACTIVATE
unset DEACTIVATE
