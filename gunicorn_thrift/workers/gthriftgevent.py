# -*- coding: utf-8 -
"""Based on gunicorn.workers.ggevent module under MIT license:

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

import errno
import os
import sys
import traceback
import time
from functools import partial

_socket = __import__("socket")

# workaround on osx, disable kqueue
if sys.platform == "darwin":
    os.environ['EVENT_NOKQUEUE'] = "1"

try:
    import gevent
except ImportError:
    raise RuntimeError("You need gevent installed to use this worker.")
from gevent.pool import Pool
from gevent.server import StreamServer
from gevent.socket import socket
from gevent.timeout import Timeout

import gunicorn
from gunicorn import util
from gunicorn.workers.async import AsyncWorker

from thrift.transport import TTransport
from thrift.transport.TTransport import TFileObjectTransport
from thrift.Thrift import TApplicationException, TMessageType, TType

from gunicorn_thrift.thrift.protocol import TBinaryProtocolFactoryExt

VERSION = "gevent/%s gunicorn/%s" % (gevent.__version__, gunicorn.__version__)


class ThriftFuncNotFound(Exception):
    pass


class ThriftGeventWorker(AsyncWorker):

    def patch(self):
        from gevent import monkey
        monkey.noisy = False

        # if the new version is used make sure to patch subprocess
        if gevent.version_info[0] == 0:
            monkey.patch_all()
        else:
            monkey.patch_all(subprocess=True)

        # patch sockets
        sockets = []
        for s in self.sockets:
            sockets.append(socket(s.FAMILY, _socket.SOCK_STREAM,
                                  _sock=s))
        self.sockets = sockets

    def notify(self):
        super(ThriftGeventWorker, self).notify()
        if self.ppid != os.getppid():
            self.log.info("Parent changed, shutting down: %s", self)
            sys.exit(0)

    def run(self):
        servers = []

        # init thrift transport&protocol objects
        self.tfactory = TTransport.TTransportFactoryBase()
        self.pfactory = TBinaryProtocolFactoryExt()

        for s in self.sockets:
            s.setblocking(1)
            pool = Pool(self.worker_connections)
            hfun = partial(self.handle, s)
            server = StreamServer(s, handle=hfun, spawn=pool)
            server.start()
            servers.append(server)

        try:
            while self.alive:
                self.notify()
                gevent.sleep(1.0)

        except KeyboardInterrupt:
            pass
        except:
            for server in servers:
                try:
                    server.stop()
                except:
                    pass
            raise

        try:
            # Stop accepting requests
            for server in servers:
                if hasattr(server, 'close'):  # gevent 1.0
                    server.close()
                if hasattr(server, 'kill'):  # gevent < 1.0
                    server.kill()

            # Handle current requests until graceful_timeout
            ts = time.time()
            while time.time() - ts <= self.cfg.graceful_timeout:
                accepting = 0
                for server in servers:
                    if server.pool.free_count() != server.pool.size:
                        accepting += 1

                # if no server is accepting a connection, we can exit
                if not accepting:
                    return

                self.notify()
                gevent.sleep(1.0)

            # Force kill all active the handlers
            self.log.warning("Worker graceful timeout (pid:%s)" % self.pid)
            [server.stop(timeout=1) for server in servers]
        except:
            pass

    def handle(self, listener, client, addr):
        try:
            listener_name = listener.getsockname()
            self.handle_request(listener_name, client, addr)
        except socket.error as e:
            if e.args[0] not in (errno.EPIPE, errno.ECONNRESET):
                self.log.exception("Socket error processing request.")
            else:
                if e.args[0] == errno.ECONNRESET:
                    self.log.debug("Ignoring connection reset")
                else:
                    self.log.debug("Ignoring EPIPE")
        except Exception as e:
            self.log.error(str(e) + traceback.format_exc())
        finally:
            util.close(client)

    def handle_request(self, *args):
        try:
            self._handle_request(*args)
        except gevent.GreenletExit:
            pass
        except SystemExit:
            pass

    def _handle_request(self, listener_name, sock, addr):
        client = TFileObjectTransport(sock.makefile())
        itrans = self.tfactory.getTransport(client)
        otrans = self.tfactory.getTransport(client)
        iprot = self.pfactory.getProtocol(itrans)
        oprot = self.pfactory.getProtocol(otrans)
        try:
            while True:
                (name, type, seqid) = iprot.readMessageBegin()
                request_start = time.time()
                try:
                    timeout_con = Timeout(self.cfg.timeout, Timeout)
                    timeout_con.start()
                    if name not in self.wsgi._processMap:
                        iprot.skip(TType.STRUCT)
                        iprot.readMessageEnd()
                        x = TApplicationException(
                            TApplicationException.UNKNOWN_METHOD, "Unknown function %s" % (name))
                        oprot.writeMessageBegin(
                            name, TMessageType.EXCEPTION, seqid)
                        x.write(oprot)
                        oprot.writeMessageEnd()
                        oprot.trans.flush()
                        raise ThriftFuncNotFound
                    else:
                        self.wsgi._processMap[name](self.wsgi, seqid, iprot, oprot)
                except ThriftFuncNotFound, ex:
                    self.log.error("Unknown function %s" % (name))
                    self.log.access(
                        addr, name, "FUNC_NOT_FOUND", time.time() - request_start)
                except Timeout, ex:
                    self.log.error("A greenlet process timeout.")
                    self.log.access(
                        addr, name, "TIMEOUT", time.time() - request_start)
                except Exception, ex:
                    self.log.error(str(ex) + traceback.format_exc())
                    self.log.access(
                        addr, name, "SERVER_ERROR", time.time() - request_start)
                else:
                    self.log.access(
                        addr, name, "OK", time.time() - request_start)
                finally:
                    timeout_con.cancel()
        except EOFError:
            pass
        except Exception, ex:
            pass
        finally:
            itrans.close()
            otrans.close()
        return True

    if gevent.version_info[0] == 0:

        def init_process(self):
            # monkey patch here
            self.patch()

            # reinit the hub
            import gevent.core
            gevent.core.reinit()

            # gevent 0.13 and older doesn't reinitialize dns for us after forking
            # here's the workaround
            gevent.core.dns_shutdown(fail_requests=1)
            gevent.core.dns_init()
            super(ThriftGeventWorker, self).init_process()

    else:

        def init_process(self):
            # monkey patch here
            self.patch()

            # reinit the hub
            from gevent import hub
            hub.reinit()

            # then initialize the process
            super(ThriftGeventWorker, self).init_process()
