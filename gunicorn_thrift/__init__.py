# -*- coding: utf-8 -

version_info = (19, 0, 1)
__version__ = ".".join([str(v) for v in version_info])
SERVER_SOFTWARE = "gunicorn_thrift/%s" % __version__
