import os
import subprocess
import time
import threading
import docker

DOCKER_SOCK_OPTIONS = ("/var/run/docker.sock", "/var/run/balena-engine.sock")
DOCKER_SOCK = None
for opt in DOCKER_SOCK_OPTIONS:
    if os.path.exists(opt):
        DOCKER_SOCK = opt
        break
if not DOCKER_SOCK:
    raise Exception("No docker socket available!")

NSENTER_BIN = "/usr/bin/nsenter"
# IPTABLES_BIN="/usr/sbin/iptables"
IPTABLES_BIN = "/usr/sbin/iptables-legacy"
BRCTL_BIN = "/sbin/brctl"
IP_BIN = "/sbin/ip"

docker_client = None


def connect(base_url=f"unix:/{DOCKER_SOCK}"):
    global docker_client
    docker_client = docker.DockerClient(base_url=base_url)


class ProcessManager:
    def __init__(self, name="", pid=1):
        self.name = name
        self.pid = pid

    def nsenter(
        self, cmd="", target=None, mount=None, net=None, capture_output=False
    ):
        if not target:
            target = self.pid
        args = [NSENTER_BIN, "--target", str(target)]
        if mount:
            args += ["--mount"]
            if mount is not True:
                args += [mount]
        if net:
            args += ["--net"]
            if net is not True:
                args += [net]
        if isinstance(cmd, str):
            cmd = cmd.split()
        args += cmd
        # print(f"Will now execute [{' '.join(args)}]")
        return subprocess.run(args, capture_output=capture_output)

    def exec_in_netns(self, cmd, capture_output=False):
        return self.nsenter(net=True, cmd=cmd, capture_output=capture_output)

    def exec_in_mntns(self, cmd, capture_output=False):
        return self.nsenter(mount=True, cmd=cmd, capture_output=capture_output)

    def exec_in_ns(self, cmd, capture_output=False):
        return self.nsenter(
            cmd=cmd, mount=True, net=True, capture_output=capture_output
        )

    def intf_to_netns(self, intf, netns, force_wlan=False, force_eth=False):
        print(
            f"[{self.name}] Moving interface {intf} to namespace {netns}...",
            end="",
        )
        self.exec_in_ns("mkdir -p /var/run/netns")
        self.exec_in_ns(
            f"ln -s /proc/{netns}/ns/net /var/run/netns/{netns}",
            capture_output=True,
        )
        if (intf.startswith("phy") and not force_eth) or force_wlan:
            cmd = ["iw", "phy", intf, "set", "netns", str(netns)]
            res = self.exec_in_ns(cmd, capture_output=True)
        else:
            cmd = ["ip", "link", "set", intf, "netns", str(netns)]
            res = self.exec_in_netns(cmd, capture_output=True)
        rc = res.returncode
        if not rc:
            print("OK")
        else:
            print("NOK!")
        return rc

    def delete_default_route(self):
        print(f"[{self.name}] Delete default route...", end="")
        self.exec_in_netns("ip route del default")
        print("OK")

    def add_route(self, subnet, via):
        if isinstance(via, ContainerManager):
            via = via.ipaddress
        elif isinstance(via, tuple) and isinstance(via[0], ContainerManager):
            via = via[0].ipaddress_in_network(network=via[1])
        print(f"[{self.name}] Add new route to {subnet} via {via}...", end="")
        self.exec_in_netns(["ip", "route", "add", subnet, "via", via])
        print("OK")

    def change_default_route(self, ipaddress):
        self.delete_default_route()
        self.add_route("default", ipaddress)

    def change_nameserver(self, nameservers=["8.8.8.8"]):
        print(f"[{self.name}] Change nameserver...", end="")
        if isinstance(nameservers, str):
            nameservers = [nameservers]
        elif isinstance(nameservers, ContainerManager):
            nameservers = [nameservers.ipaddress]
        cmd = f"printf 'nameserver %s\n' {' '.join(nameservers)} > /etc/resolv.conf"  # noqa: E501
        self.exec_in_mntns(["sh", "-c", cmd])
        print("OK")

    def config_bridge(self, name, ifs=[], ipaddress=None):
        print(f"[{self.name}] Add bridge {name}...", end="")
        self.exec_in_netns([BRCTL_BIN, "addbr", name])
        for intf in ifs:
            self.exec_in_netns([BRCTL_BIN, "addif", name, intf])
        if ipaddress:
            self.exec_in_netns([IP_BIN, "addr", "add", ipaddress, "dev", name])
        self.exec_in_netns([IP_BIN, "link", "set", name, "up"])
        print("OK")

    def run_iptables(self, cmd):
        self.exec_in_netns([IPTABLES_BIN] + cmd, capture_output=True)

    def set_masquerade(self, interface):
        print(f"[{self.name}] Set up masquerading on {interface}...", end="")
        self.run_iptables(
            [
                "-t",
                "nat",
                "-I",
                "POSTROUTING",
                "-o",
                interface,
                "-j",
                "MASQUERADE",
            ]
        )
        print("OK")

    def create_vlan(self, interface, vlanid):
        print(
            f"[{self.name}] Creating VLAN {vlanid} on interface {interface}...",  # noqa : E501
            end="",
        )
        self.exec_in_ns(
            [
                IP_BIN,
                "link",
                "add",
                "link",
                interface,
                "name",
                f"{interface}.{vlanid}",
                "type",
                "vlan",
                "id",
                str(vlanid),
            ]
        )
        print("OK")

    def intf_set_ip(self, intf, ipaddress):
        print(
            f"[{self.name}] Setting IP address {ipaddress} on interface '{intf}'...",  # noqa : E501
            end="",
        )
        self.exec_in_netns(
            [
                IP_BIN,
                "addr",
                "add",
                ipaddress,
                "dev",
                intf,
            ]
        )
        print("OK")

    def intf_up(self, intf):
        print(
            f"[{self.name}] Bringing interface '{intf}' up...",
            end="",
        )
        self.exec_in_netns(
            [
                IP_BIN,
                "link",
                "set",
                intf,
                "up",
            ]
        )
        print("OK")


class ContainerManager(ProcessManager):
    def __init__(
        self,
        name,
        image=None,
        run_options={},
        net_options={},
        post_options={},
        autostart=True,
        host=None,
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

    def run(self, noconfig=False):
        # TODO: Check if the container is already running
        self.clear_cache()
        kwargs = self.run_options.copy()
        kwargs["name"] = self.name
        if "detach" not in kwargs:
            kwargs["detach"] = True
        if "auto_remove" not in kwargs:
            kwargs["auto_remove"] = True
        if ("network" not in kwargs) and ("network_mode" not in kwargs):
            kwargs["network_mode"] = "none"
        print(f"[{self.name}] Start container...", end="")
        self._container = self.client.containers.run(self.image, **kwargs)
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
    def ipaddress(self):
        return self.ipaddress_in_network()

    def ipaddress_in_network(self, network=None):
        try:
            networks = self.inspect["NetworkSettings"]["Networks"]
            if not network:
                n = next(iter(networks.values()))
            else:
                n = networks[network]
            return n["IPAddress"]
        except ValueError:  # TODO: Use correct error type(s)
            return False

    def add_network(self, network):
        if isinstance(network, str):
            network = self.client.networks.get(network)
        network.connect(self.name)

    def clear_cache(self):
        self._container = None
        self._pid = None


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


class ContainersManager:
    def __init__(self, host=None, containers={}, version="latest"):
        if not host:
            self.host = ProcessManager("host", pid=1)
        else:
            self.host = host
        self.containers = containers
        self.version = version

    def add(self, container):
        if ":" not in container.image:
            container.image = f"{container.image}:{self.version}"
        self.containers[container.name] = container
        container.host = self.host

    def start_containers(
        self, containers=None, noconfig=False, post_config=None
    ):  # noqa : E501
        if containers:
            # Start all specified containers
            if isinstance(containers, str):
                names = [containers]
            else:
                names = containers
        else:
            # Only start containers with autostart
            names = []
            for c in self.containers:
                if self.containers[c].autostart:
                    names.append(c)

        for n in names:
            c = self.containers[n]
            c.run(noconfig=noconfig)
            if post_config:
                c.post_config()

    def post_start_config(self, containers=None):
        if containers:
            # Config all specified containers
            if isinstance(containers, str):
                names = [containers]
            else:
                names = containers
        else:
            # Config all containers
            names = self.containers.keys()
        for n in names:
            if self.containers[n].is_running:
                self.containers[n].post_config()

    def stop_containers(self, containers=None):
        if containers:
            # Stop all specified containers
            if isinstance(containers, str):
                names = [containers]
            else:
                names = containers
        else:
            # Stop all containers
            names = self.containers.keys()
        for n in names:
            self.containers[n].stop()
