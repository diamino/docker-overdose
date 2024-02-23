"""Test scenario: VLAN interfaces

"""
import time
from docker_overdose import (
    OverdoseManager,
    ProcessManager,
    ContainerManager,
)


def main():  # pragma: no cover
    host = ProcessManager("host", pid=1)

    host.create_vlan("enp0s2", 12)

    containers = OverdoseManager(host)

    vlantest = ContainerManager(
        "vlantest",
        image="network-test",
        run_options={"command": "sleep 9999", "network_mode": "bridge"},
        net_options={
            "add_if": "enp0s2.12",
            "intf_set_ip": {"intf": "enp0s2.12", "ipaddress": "10.12.0.2/24"},
            "intf_up": "enp0s2.12",
        },
        autostart=True,
    )
    containers.add(vlantest)

    containers.start_containers()

    print("Running post start config on containers...")
    containers.post_start_config()

    print("\nPress Control-C to stop the Network Manager...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # Destroy all running containers
        containers.stop_containers()
        print("Ready...")


if __name__ == "__main__":
    main()
