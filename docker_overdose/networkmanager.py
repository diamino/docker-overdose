import docker
import atexit
from .dockerclient import get_docker_client


class NetworkManager:
    def __init__(self, name, internal=True):
        self.client = get_docker_client()
        self.name = name
        self.by_overdose = False
        if self._network is None:
            self.create(internal)
            self.by_overdose = True
        atexit.register(self.close)

    def close(self):
        if self.by_overdose and self._network:
            self._network.remove()

    @property
    def _network(self):
        try:
            return self.client.networks.get(self.name)
        except docker.errors.NotFound:
            return None

    def create(self, internal):
        self.client.networks.create(name=self.name, internal=internal)

    @property
    def inspect(self):
        if self._network:
            return self._network.attrs
        else:
            return False

    @property
    def ipsubnet(self):
        return self.inspect["IPAM"]["Config"][0]["Subnet"]

    @property
    def gateway(self):
        return self.inspect["IPAM"]["Config"][0]["Gateway"]
