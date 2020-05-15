class MinecraftServer(object):
    def __init__(self, address, port):
        self._address = address
        self._port = port

    def start(self):
        print(self._address, self._port)
