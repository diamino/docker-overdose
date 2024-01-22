import os
import time
import threading
import docker
from typing import Optional, Union
from .processmanager import ProcessManager

DOCKER_SOCK_OPTIONS = ("/var/run/docker.sock", "/var/run/balena-engine.sock")
DOCKER_SOCK = None
for opt in DOCKER_SOCK_OPTIONS:
    if os.path.exists(opt):
        DOCKER_SOCK = opt
        break
if not DOCKER_SOCK:
    raise Exception("No docker socket available!")

docker_client = None


def connect(base_url=f"unix:/{DOCKER_SOCK}"):
    global docker_client
    docker_client = docker.DockerClient(base_url=base_url)


class ContainerManager(ProcessManager):
    def __init__(
        self,
        name: str,
        image: Optional[str] = None,
        run_options={},
        net_options={},
        post_options={},
        autostart: bool = True,
        host: Optional["ContainerManager"] = None,
    ):
        if not docker_client:
            connect()
        self.client = docker_client
        self.name = name
        self.image = image
        self.run_options = run_options
        self.net_options = net_options
        self.post_options = post_options
        self.autostart = autostart
        self.host = host
        self._container = None
        self._pid = None
        self.is_running

    def run(self, noconfig: bool = False):
        # TODO: Check if the container is already running
        self.clear_cache()
        run_kwargs = self.run_options.copy()
        run_kwargs["name"] = self.name
        if "detach" not in run_kwargs:
            run_kwargs["detach"] = True
        if "auto_remove" not in run_kwargs:
            run_kwargs["auto_remove"] = True
        if ("network" not in run_kwargs) and (
            "network_mode" not in run_kwargs
        ):
            run_kwargs["network_mode"] = "none"
        print(f"[{self.name}] Start container...", end="")
        self._container = self.client.containers.run(self.image, **run_kwargs)
        print("OK")
        if not noconfig and self.net_options:
            self.config(self.net_options)
        # TODO: Spawn logging thread
        self.logthread = threading.Thread(target=self.logger)
        self.logthread.start()

    def logger(self, timestamps=True):
        i = self._container.logs(
            stream=True, follow=True, timestamps=timestamps
        )
        try:
            while True:
                line = next(i).decode().strip("\n\r")
                print(f"[{self.name}] {line}")
        except StopIteration:
            print(
                f"[{self.name}] !!! Logging interrupted. Container stopped? !!!"  # noqa : E501
            )  # noqa: E501

    def config(self, options):
        self.wait_for_start()

        DEPENDENCY_TIMEOUT = 0

        # Wait for related containers
        dependencies = set()
        if "depends" in options:
            if isinstance(options["depends"], ContainerManager):
                dependencies.add(options["depends"])
            else:
                dependencies.update(options["depends"])
        # TODO: Search for other dependencies in the options
        for d in dependencies:
            print("\t", end="")
            if not d.wait_for_start(timeout=DEPENDENCY_TIMEOUT):
                print(
                    f"[{self.name}] Dependency [{d.name}] failed to start! (Timeout set to {DEPENDENCY_TIMEOUT}s) Stopping configuration..."  # noqa : E501
                )
                return False

        for o in options:
            ignorelist = ("depends",)
            if o in ignorelist:
                continue
            whitelist = (
                "add_if",
                "intf_set_ip",
                "intf_up",
                "delete_default_route",
                "change_default_route",
                "add_route",
                "change_nameserver",
                "set_masquerade",
                "config_bridge",
                "add_network",
            )
            if o not in whitelist:
                print(f"[{self.name}] Option '{o}' is not supported!")
                continue
            try:
                f = self.__getattribute__(o)
            except AttributeError:
                print(f"[{self.name}] Option '{o}' is not supported!")
                continue

            arglist = (
                options[o] if isinstance(options[o], list) else [options[o]]
            )  # noqa: E501
            for arg in arglist:
                if isinstance(arg, bool):
                    f()
                elif isinstance(arg, dict):
                    f(**arg)
                else:
                    f(arg)
        return True

    def post_config(self):
        if self.post_options:
            self.config(self.post_options)

    def add_if(self, interface):
        print(f"[{self.name}] Add interface {interface} to container...")
        self.host.intf_to_netns(interface, self.pid)

    def stop(self):
        if self.is_running:
            print(f"[{self.name}] Stopping container...", end="")
            self._container.stop()
            print("OK")
        else:
            print(f"[{self.name}] Container already stopped...")
        self.clear_cache()

    @property
    def container(self):
        if not self.is_running:
            return None
        else:
            return self._container

    @property
    def pid(self):
        if not self.is_running:
            return False
        if not self._pid:
            self._pid = self.inspect["State"]["Pid"]
        return self._pid

    @property
    def is_running(self):
        try:
            self._container = self.client.containers.list(
                filters={"name": self.name, "status": "running"}
            )[
                0
            ]  # noqa: E501
            return True
        except IndexError:
            return False

    def wait_for_start(self, timeout=60):
        print(f"[{self.name}] Waiting for container to start...", end="")
        starttime = time.time()
        while (not self.is_running) and (time.time() - starttime < timeout):
            time.sleep(1)
        if self.is_running:
            print("OK")
            return True
        else:
            print("NOK!")
            return False

    @property
    def inspect(self):
        if self._container:
            return self._container.attrs
        else:
            return False

    @property
    def ipaddress(self) -> str | bool:
        return self.ipaddress_in_network()

    def ipaddress_in_network(self, network=None) -> str | bool:
        try:
            networks = self.inspect["NetworkSettings"]["Networks"]
            if not network:
                n = next(iter(networks.values()))
            else:
                n = networks[network]
            return n["IPAddress"]
        except ValueError:  # TODO: Use correct error type(s)
            return False

    def add_route(
        self,
        subnet: str,
        via: Union["ContainerManager", tuple["ContainerManager", str], str],
    ):
        if isinstance(via, ContainerManager):
            _via = via.ipaddress
        elif isinstance(via, tuple) and isinstance(via[0], ContainerManager):
            _via = via[0].ipaddress_in_network(network=via[1])
        else:
            _via = via
        super().add_route(subnet, _via)

    def add_network(self, network):
        if isinstance(network, str):
            network = self.client.networks.get(network)
        network.connect(self.name)

    def change_nameserver(self, nameservers):
        if isinstance(nameservers, ContainerManager):
            _nameservers = [nameservers.ipaddress]
        else:
            _nameservers = nameservers
        super().change_nameserver(_nameservers)

    def clear_cache(self):
        self._container = None
        self._pid = None
