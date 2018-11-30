import versioneer
from setuptools import setup, find_packages


with open('requirements.txt') as f:
    requirements = f.read().split()

requirements = [r for r in requirements if not r.startswith('git+')]
git_requirements = [r for r in requirements if r.startswith('git+')]
print("User must install \n" +
      "\n".join(f' {r}' for r in git_requirements) +
      "\n\nmanually")


setup(name='typhon',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      author='SLAC National Accelerator Laboratory',
      packages=find_packages(),
      include_package_data=True,
      install_requires=requirements,
      description='Interface generation for ophyd devices',
      )
