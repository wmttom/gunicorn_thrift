# coding:utf8
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol

from ping import Ping


class PingClient(object):

    def __init__(self):
        self.transport = TSocket.TSocket('127.0.0.1', 7748)
        self.transport = TTransport.TBufferedTransport(self.transport)
        self.protocol = TBinaryProtocol.TBinaryProtocol(self.transport)
        self.client = Ping.Client(self.protocol)
        self.transport.open()

    def send_ping(self, msg):
        return self.client.send_ping(msg)

if __name__ == '__main__':
    client = PingClient()
    print client.send_ping("ping!")
    import time
    time.sleep(40)
    print client.send_ping("ping!")
