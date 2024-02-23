"""Test scenario: Virtual interfaces

"""
import time
from docker_overdose import ContainerManager, ProcessManager, OverdoseManager

LEFT_IP = "192.168.133.1"
RIGHT_IP = "192.168.133.2"


def main():  # pragma: no cover
    host = ProcessManager("host", pid=1)

    containers = OverdoseManager(host)

    left = ContainerManager(
        "left",
        image="network-test",
        run_options={"command": f"sh -c 'sleep 3; ping {RIGHT_IP}'"},
        autostart=True,
    )

    right = ContainerManager(
        "right",
        image="network-test",
        run_options={"command": f"sh -c 'sleep 3; ping {LEFT_IP}'"},
        autostart=True,
    )

    containers.add(left)
    containers.add(right)

    containers.start_containers()

    print("Running post start config on containers...")
    containers.post_start_config()

    print(f"{left.pid=}, {right.pid=}")

    host.exec_in_netns(
        f"ip link add veth-left netns {left.pid} type veth peer name veth-right netns {right.pid}"  # noqa : E501
    )

    left.intf_set_ip("veth-left", f"{LEFT_IP}/24")
    right.intf_set_ip("veth-right", f"{RIGHT_IP}/24")
    left.intf_up("veth-left")
    right.intf_up("veth-right")

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
