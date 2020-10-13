from setuptools import find_packages, setup

import versioneer

setup(name='nabs',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      license='BSD',
      author='SLAC National Accelerator Laboratory',
      packages=find_packages(),
      description='NABS: Not a beamline scientist. Beamline automatation '
                  'that should be handled by code, not by people.')
