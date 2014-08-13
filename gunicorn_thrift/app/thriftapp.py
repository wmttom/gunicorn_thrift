# -*- coding: utf-8 -
"""Based on gunicorn.app.wsgiapp module under MIT license:

2009-2013 (c) Benoît Chesneau <benoitc@e-engura.org>
2009-2013 (c) Paul J. Davis <paul.joseph.davis@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import os
import sys

from gunicorn.errors import AppImportError
from gunicorn.app.wsgiapp import WSGIApplication


class ThriftApplication(WSGIApplication):

    def _import_app(self, module):
        """fork from gunicorn.until.import_app.
        thrift app is not callable,delete callable test.
        """
        parts = module.split(":", 1)
        if len(parts) == 1:
            module, obj = module, "application"
        else:
            module, obj = parts[0], parts[1]
        try:
            __import__(module)
        except ImportError:
            if module.endswith(".py") and os.path.exists(module):
                raise ImportError("Failed to find application, did "
                                  "you mean '%s:%s'?" % (module.rsplit(".", 1)[0], obj))
            else:
                raise

        mod = sys.modules[module]
        try:
            app = eval(obj, mod.__dict__)
        except NameError:
            raise AppImportError("Failed to find application: %r" % module)

        if app is None:
            raise AppImportError("Failed to find application object: %r" % obj)
        return app

    def load_thriftapp(self):
        self.chdir()

        # load the app
        return self._import_app(self.app_uri)

    def load(self):
        return self.load_thriftapp()


def run():
    """\
    The ``gunicorn_thrift`` command line runner for launching Gunicorn with
    generic thrift applications.
    """
    from gunicorn_thrift.app.thriftapp import ThriftApplication
    ThriftApplication("%(prog)s [OPTIONS] [APP_MODULE]").run()


if __name__ == '__main__':
    run()
