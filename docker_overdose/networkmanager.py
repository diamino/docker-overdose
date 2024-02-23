import docker
import atexit
from .dockerclient import get_docker_client
from .processmanager import ProcessManager


class NetworkManager:
    def __init__(self, name, host=None, internal=True, isolate=False):
        self.client = get_docker_client()
        if not host:
            self.host = ProcessManager("host", pid=1)
        else:
            self.host = host
        self.name = name
        self.by_overdose = False
        if self._network is None:
            self.create(internal)
            self.by_overdose = True
        if not isolate:
            self.remove_isolation()
        atexit.register(self.close)

    def close(self):
        if self._network:
            self.delete_isolation_circumvention()
            if self.by_overdose:
                self._network.remove()

    @property
    def _network(self):
        try:
            return self.client.networks.get(self.name)
        except docker.errors.NotFound:
            return None

    def create(self, internal):
        self.client.networks.create(name=self.name, internal=internal)

    def remove_isolation(self):
        print(f"Removing isolation for network [{self.name}]...")
        self.delete_isolation_circumvention()
        self.set_isolation_circumvention()

    def set_isolation_circumvention(self):
        self.host.run_iptables(
            ["-I", "DOCKER-USER", "-s", self.ipsubnet, "-j", "ACCEPT"]
        )
        self.host.run_iptables(
            ["-I", "DOCKER-USER", "-d", self.ipsubnet, "-j", "ACCEPT"]
        )

    def delete_isolation_circumvention(self):
        self.host.run_iptables(
            ["-D", "DOCKER-USER", "-s", self.ipsubnet, "-j", "ACCEPT"]
        )
        self.host.run_iptables(
            ["-D", "DOCKER-USER", "-d", self.ipsubnet, "-j", "ACCEPT"]
        )

    @property
    def inspect(self):
        if self._network:
            self._network.reload()
            return self._network.attrs
        else:
            return False

    @property
    def ipsubnet(self):
        return self.inspect["IPAM"]["Config"][0]["Subnet"]

    @property
    def gateway(self):
        return self.inspect["IPAM"]["Config"][0]["Gateway"]
