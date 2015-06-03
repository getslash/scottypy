from setuptools import setup, find_packages
import functools
import os
import platform

_in_same_dir = functools.partial(os.path.join, os.path.dirname(__file__))
with open(_in_same_dir("scotty", "__version__.py")) as version_file:
    exec(version_file.read())  # pylint: disable=W0122

install_requires = [
    "emport",
    "requests",
    "python-dateutil",
]

setup(name="scotty",
      classifiers=[
          "Programming Language :: Python :: 2.6",
          "Programming Language :: Python :: 2.7",
          "Programming Language :: Python :: 3.3",
          "Programming Language :: Python :: 3.4",
      ],
      description="A library for beaming up files to Scotty",
      license="BSD",
      author="Roey Darwish Dror",
      author_email="roeyd@infinidat.com",
      url="http://git.infinidat.com/roeyd/scotty-python",
      version=__version__,  # pylint: disable=E0602
      packages=find_packages(exclude=["tests"]),
      install_requires=install_requires,
      entry_points=dict(
          console_scripts=[
              "beamup  = scotty.beamup:main",
          ]
      ),
)
