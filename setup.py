import versioneer
from setuptools import setup, find_packages

setup(name='nabs',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      license='BSD',
      author='SLAC National Accelerator Laboratory',
      packages=find_packages(),
      description='Not a Beamline Scientist')
