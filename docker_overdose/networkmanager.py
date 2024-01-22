import docker
from .containermanager import docker_client, connect


class NetworkManager:
    def __init__(self, name):
        if not docker_client:
            connect()
        self.client = docker_client
        self.name = name

    @property
    def _network(self):
        try:
            return self.client.networks.get(self.name)
        except docker.errors.NotFound:
            return None

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
