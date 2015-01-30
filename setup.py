# -*- coding: utf-8 -
import os
from setuptools import setup, find_packages, Command
import sys

from gunicorn_thrift import __version__


setup(
    name = 'ggthrift',
    version = __version__,

    description = 'python thrift server plugin for gunicorn.',
    author = 'wmttom',
    author_email = 'wmttom@gmail.com',
    license = 'MIT',
    url = 'http://github.com/wmttom/gunicorn_thrift',

    zip_safe = False,
    packages = find_packages(exclude=['examples', 'tests']),
    include_package_data = True,

    install_requires = [
        "gunicorn>=19.1.1",
        "gevent==1.0.1",
        "thrift>=0.9.1",
    ],

    entry_points="""

    [console_scripts]
    gunicorn_thrift=gunicorn_thrift.app.thriftapp:run

    """
)
