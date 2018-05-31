import versioneer
from setuptools import setup, find_packages

setup(name='typhon',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      author='SLAC National Accelerator Laboratory',
      packages=find_packages(),
      include_package_data=True,
      description='Interface generation for ophyd devices',
      )
