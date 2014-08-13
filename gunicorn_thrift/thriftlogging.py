# -*- coding: utf-8 -
"""Based on gunicorn.glogging module under MIT license:
2009-2013 (c) Benoît Chesneau <benoitc@e-engura.org>
2009-2013 (c) Paul J. Davis <paul.joseph.davis@gmail.com>

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.
"""

import traceback
import os

from gunicorn.glogging import Logger

THRIFT_STATUS_CODE = {
    "TIMEOUT": 504,
    "SERVER_ERROR": 500,
    "FUNC_NOT_FOUND": 404,
    "OK": 200,
}


class ThriftLogger(Logger):

    """ThriftLogger class,log access info."""

    def atoms(self, address, func_name, status, finish):
        atoms = {
            'h': address[0],
            't': self.now(),
            'n': func_name,
            's': THRIFT_STATUS_CODE[status],
            'T': finish * 1000,
            'p': "<%s>" % os.getpid()
        }
        return atoms

    def access(self, address, func_name, status, finish):
        # logger_config_from_dict is used for on_staring-hook load logging-config from dict.
        if not self.cfg.accesslog and not self.cfg.logconfig and not getattr(self, "logger_config_from_dict", None):
            return
        atoms = self.atoms(address, func_name, status, finish)
        access_log_format = "%(h)s %(t)s %(n)s %(s)s %(T)s %(p)s"
        try:
            self.access_log.info(access_log_format % atoms)
        except:
            self.error(traceback.format_exc())

