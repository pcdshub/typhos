# Install the package
$PYTHON setup.py install --single-version-externally-managed --record=record.txt

# Create auxiliary dirs
mkdir -p $PREFIX/etc/conda/activate.d
mkdir -p $PREFIX/etc/conda/deactivate.d
mkdir -p $PREFIX/etc/typhos

# Create auxiliary vars
DESIGNER_PLUGIN_PATH=$PREFIX/etc/typhos
DESIGNER_PLUGIN=$DESIGNER_PLUGIN_PATH/typhos_designer_plugin.py
ACTIVATE=$PREFIX/etc/conda/activate.d/typhos
DEACTIVATE=$PREFIX/etc/conda/deactivate.d/typhos

echo "from typhos.designer import *" >> $DESIGNER_PLUGIN

echo "export PYQTDESIGNERPATH=\$CONDA_PREFIX/etc/typhos:\$PYQTDESIGNERPATH" >> $ACTIVATE.sh
echo "unset PYQTDESIGNERPATH" >> $DEACTIVATE.sh

echo '@echo OFF' >> $ACTIVATE.bat
echo 'IF "%PYQTDESIGNERPATH%" == "" (' >> $ACTIVATE.bat
echo 'set PYQTDESIGNERPATH=%CONDA_PREFIX%\etc\typhos' >> $ACTIVATE.bat
echo ')ELSE (' >> $ACTIVATE.bat
echo 'set PYQTDESIGNERPATH=%CONDA_PREFIX%\etc\typhos;%PYQTDESIGNERPATH%' >> $ACTIVATE.bat
echo ')' >> $ACTIVATE.bat

unset DESIGNER_PLUGIN_PATH
unset DESIGNER_PLUGIN
unset ACTIVATE
unset DEACTIVATE
