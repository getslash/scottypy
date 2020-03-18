from setuptools import setup, find_packages
import functools
import os

_in_same_dir = functools.partial(os.path.join, os.path.dirname(__file__))
with open(_in_same_dir("scottypy", "__version__.py")) as version_file:
    exec(version_file.read())  # pylint: disable=W0122

install_requires = [
    "capacity",
    "click",
    "emport",
    "python-dateutil",
    "requests",
    "pact"
]

setup(name="scottypy",
      classifiers=[
          "Programming Language :: Python :: 3.5",
          "Programming Language :: Python :: 3.6",
          "Programming Language :: Python :: 3.7",
          "Programming Language :: Python :: 3.8",
      ],
      description="A library for beaming up files to Scotty",
      license="BSD",
      author="Roey Darwish Dror",
      author_email="roey.ghost@gmail.com",
      url="https://github.com/getslash/scottypy",
      version=__version__,  # pylint: disable=E0602
      packages=find_packages(exclude=["unittests"]),
      install_requires=install_requires,
      entry_points=dict(
          console_scripts=[
              "scotty  = scottypy.app:main",
          ]
      ),
)
