from setuptools.command.install import install
from setuptools.command.develop import develop
from setuptools.command.egg_info import egg_info

from setuptools import setup, find_packages

import sys

def genResources():
    from PyQt5.pyrcc_main import main as pyrcc_main
    saved_argv = sys.argv
    # Use current environment to find pyrcc but use the public interface
    sys.argv = ['pyrcc5', '-o', 'remy/gui/resources.py', 'resources.qrc']
    pyrcc_main()
    sys.argv = saved_argv

# https://stackoverflow.com/questions/19569557/pip-not-picking-up-a-custom-install-cmdclass
class genResourcesInstall(install):
    def run(self):
        genResources()
        install.run(self)

class genResourcesDevelop(develop):
    def run(self):
        genResources()
        develop.run(self)

class genResourcesEggInfo(egg_info):
    def run(self):
        genResources()
        egg_info.run(self)

setup(
  name='Remy',
  version='0.5',
  url='https://github.com/bordaigorl/remy',
  description='Remy, a reMarkable tablet manager app',
  author='Emanuele D\'Osualdo',
  author_email='emanuele.dosualdo@gmail.com',
  classifiers=[
    'Development Status :: 3 - Alpha',
    'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
  ],
  packages=find_packages(),
  python_requires=">=3.8",
  install_requires=['pyqt5', 'requests', 'sip', 'arrow', 'paramiko', 'pypdf2'],
  extras_require={
    'default': ['pymupdf'],
    'simpl': ['simplification'],
    'mupdf': ['pymupdf'],
    'poppler': ['python-poppler-qt5']
  },
  entry_points={
    'console_scripts': ['remy = remy.gui.app:main']
  },
  license='GPLv3',
  cmdclass={
    'install': genResourcesInstall,
    'develop': genResourcesDevelop,
    'egg_info': genResourcesEggInfo,
  }
)
