# coding:utf8
from ping import Ping


class PingServer(object):

    def send_ping(self, msg):
        return msg


handler = PingServer()
processor = Ping.Processor(handler)

if __name__ == '__main__':
    from thrift.transport import TSocket
    from thrift.transport import TTransport
    from thrift.protocol import TBinaryProtocol
    from thrift.server import TServer
    from thrift.server.TProcessPoolServer import TProcessPoolServer

    transport = TSocket.TServerSocket("0.0.0.0", 7748)
    tfactory = TTransport.TBufferedTransportFactory()
    pfactory = TBinaryProtocol.TBinaryProtocolFactory()

    server = TProcessPoolServer(processor, transport, tfactory, pfactory)

    server.serve()
