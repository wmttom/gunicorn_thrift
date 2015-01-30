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
import sys
import logging
import socket

from logging.config import fileConfig

from gunicorn import util
from gunicorn.glogging import Logger, CONFIG_DEFAULTS

THRIFT_STATUS_CODE = {
    "TIMEOUT": 504,
    "SERVER_ERROR": 500,
    "FUNC_NOT_FOUND": 404,
    "OK": 200,
}

STREAM_OUTPUT_TYPE = {
    "error": sys.stderr,
    "access": sys.stdout,
}


class ThriftLogger(Logger):

    """ThriftLogger class,log access info."""

    def __init__(self, cfg):
        Logger.__init__(self, cfg)
        self.is_statsd = False
        statsd_server = os.environ.get("statsd")
        if statsd_server:
            try:
                host, port = statsd_server.split(":")
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.sock.connect((host, int(port)))
            except Exception:
                self.sock = None
            else:
                self.is_statsd = True

    def setup(self, cfg):
        loglevel = self.LOG_LEVELS.get(cfg.loglevel.lower(), logging.INFO)
        self.error_log.setLevel(loglevel)
        self.access_log.setLevel(logging.INFO)

        # set gunicorn.error handler
        self._set_handler(
            self.error_log, cfg.errorlog,
            logging.Formatter(self.error_fmt, self.datefmt), "error")

        # set gunicorn.access handler
        if cfg.accesslog is not None:
            self._set_handler(
                self.access_log, cfg.accesslog,
                logging.Formatter(self.access_fmt), "access")

        # set syslog handler
        if cfg.syslog:
            self._set_syslog_handler(
                self.error_log, cfg, self.syslog_fmt, "error"
            )
            self._set_syslog_handler(
                self.access_log, cfg, self.syslog_fmt, "access"
            )

        if cfg.logconfig:
            if os.path.exists(cfg.logconfig):
                fileConfig(
                    cfg.logconfig, defaults=CONFIG_DEFAULTS,
                    disable_existing_loggers=False)
            else:
                raise RuntimeError(
                    "Error: log config '%s' not found" % cfg.logconfig
                )

    def _set_handler(self, log, output, fmt, log_type):
        # remove previous gunicorn log handler
        h = self._get_gunicorn_handler(log)
        if h:
            log.handlers.remove(h)

        if output is not None:
            if output == "-":
                h = logging.StreamHandler(
                    STREAM_OUTPUT_TYPE.get(log_type, "error")
                )
            else:
                util.check_is_writeable(output)
                h = logging.FileHandler(output)

            h.setFormatter(fmt)
            h._gunicorn = True
            log.addHandler(h)

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
            if self.is_statsd:
                project_name = self.cfg.proc_name.split(":")[0]
                statsd_key_base = "thrift.{0}.{1}".format(project_name, func_name)
                self.increment("{0}.{1}".format(statsd_key_base, atoms["s"]), 1)
                self.histogram(statsd_key_base, atoms["T"])
        except:
            self.error(traceback.format_exc())

    def increment(self, name, value, sampling_rate=1.0):
        try:
            if self.sock:
                self.sock.send(
                    "{0}:{1}|c|@{2}".format(name, value, sampling_rate))
        except Exception:
            pass

    def histogram(self, name, value):
        try:
            if self.sock:
                self.sock.send("{0}:{1}|ms".format(name, value))
        except Exception:
            pass
