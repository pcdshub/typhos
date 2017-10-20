import versioneer
from setuptools import setup, find_packages

setup(name='typhon',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      author='SLAC National Accelerator Laboratory',
      packages=find_packages(),
      description='Interface generation for ophyd devices',
      )
