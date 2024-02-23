import subprocess
from typing import Optional, Iterable

NSENTER_BIN = "/usr/bin/nsenter"
IPTABLES_BIN = "/usr/sbin/iptables"
# IPTABLES_BIN = "/usr/sbin/iptables-legacy"
BRCTL_BIN = "/sbin/brctl"
IP_BIN = "/sbin/ip"


class ProcessManager:
    def __init__(self, name: str = "", pid: int = 1):
        self.name = name
        self.pid = pid

    def nsenter(
        self,
        cmd: str | list[str] = "",
        target: Optional[int] = None,
        mount: Optional[str | bool] = None,
        net: Optional[str | bool] = None,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess:
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

    def exec_in_netns(
        self, cmd: str | list[str], capture_output: bool = False
    ) -> subprocess.CompletedProcess:
        return self.nsenter(net=True, cmd=cmd, capture_output=capture_output)

    def exec_in_mntns(
        self, cmd: str | list[str], capture_output: bool = False
    ) -> subprocess.CompletedProcess:
        return self.nsenter(mount=True, cmd=cmd, capture_output=capture_output)

    def exec_in_ns(
        self, cmd: str | list[str], capture_output: bool = False
    ) -> subprocess.CompletedProcess:
        return self.nsenter(
            cmd=cmd, mount=True, net=True, capture_output=capture_output
        )

    def intf_to_netns(
        self,
        intf: str,
        netns: int,
        force_wlan: bool = False,
        force_eth: bool = False,
    ) -> int:
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

    def delete_default_route(self) -> None:
        print(f"[{self.name}] Delete default route...", end="")
        self.exec_in_netns("ip route del default")
        print("OK")

    def add_route(
        self,
        subnet: str,
        via: str,
    ) -> None:
        print(f"[{self.name}] Add new route to {subnet} via {via}...", end="")
        self.exec_in_netns(["ip", "route", "add", subnet, "via", via])
        print("OK")

    def change_default_route(self, ipaddress: str) -> None:
        self.delete_default_route()
        self.add_route("default", ipaddress)

    def change_nameserver(
        self,
        nameservers: str | Iterable[str] = ["8.8.8.8"],
    ) -> None:
        print(f"[{self.name}] Change nameserver...", end="")
        if isinstance(nameservers, str):
            _nameservers = [nameservers]
        else:
            _nameservers = nameservers
        cmd = f"printf 'nameserver %s\n' {' '.join(_nameservers)} > /etc/resolv.conf"  # noqa: E501
        self.exec_in_mntns(["sh", "-c", cmd])
        print("OK")

    def config_bridge(
        self, name: str, ifs: list[str] = [], ipaddress: Optional[str] = None
    ) -> None:
        print(f"[{self.name}] Add bridge {name}...", end="")
        self.exec_in_netns([BRCTL_BIN, "addbr", name])
        for intf in ifs:
            self.exec_in_netns([BRCTL_BIN, "addif", name, intf])
        if ipaddress:
            self.exec_in_netns([IP_BIN, "addr", "add", ipaddress, "dev", name])
        self.exec_in_netns([IP_BIN, "link", "set", name, "up"])
        print("OK")

    def run_iptables(self, cmd: list[str]) -> None:
        # self.exec_in_netns([IPTABLES_BIN] + cmd, capture_output=True)
        self.exec_in_ns([IPTABLES_BIN] + cmd, capture_output=True)

    def set_masquerade(self, interface: str) -> None:
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

    def create_vlan(self, interface: str, vlanid: int | str) -> None:
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

    def intf_set_ip(self, intf: str, ipaddress: str) -> None:
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

    def intf_up(self, intf: str) -> None:
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
