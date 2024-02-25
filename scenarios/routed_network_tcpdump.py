"""Test scenario: Routed network using default bridge driver. A packet capture
   is written to the hosts tmp folder.

"""

from datetime import datetime
from docker_overdose import (
    ContainerManager,
    ProcessManager,
    OverdoseManager,
    NetworkManager,
)

NOW = datetime.now().strftime("%Y%m%d%H%M")

DO_NOTHING = "tail -f /dev/null"
# DO_NOTHING = "sh -c 'while true; do sleep 1; done'"
CMD_TCPDUMP = f"tcpdump -s 0 -i eth0 -w /output/tcpdump-{NOW}.pcap"


def main():  # pragma: no cover
    host = ProcessManager("host", pid=1)

    containers = OverdoseManager(host=host, name="routed")

    """
    [left]                [router]                [right]
       |                   |    |                    |
       ---<overdose-left>---    ---<overdose-right>---
    """

    network_left = NetworkManager("overdose-left")
    network_right = NetworkManager("overdose-right")

    router = ContainerManager(
        "router",
        image="network-test",
        run_options={
            "command": CMD_TCPDUMP,
            "network": network_left,
            "volumes": {"/tmp": {"bind": "/output", "mode": "rw"}},
        },
        net_options={"add_network": network_right},
        autostart=True,
    )

    left = ContainerManager(
        "left",
        image="network-test",
        run_options={
            "command": DO_NOTHING,
            "network": network_left,
        },
        net_options={"change_default_route": (router, network_left)},
        autostart=True,
    )

    right = ContainerManager(
        "right",
        image="network-test",
        run_options={
            "command": DO_NOTHING,
            "network": network_right,
        },
        net_options={"change_default_route": (router, network_right)},
        autostart=True,
    )

    containers.add(router)
    containers.add(left)
    containers.add(right)

    containers.start_containers()

    print("Running post start config on containers...")
    containers.post_start_config()

    print("\nPress Control-C to stop the Network Manager...")

    try:
        # result = left.exec_in_ns(f"ping {right.ipaddress} -c 10")
        result = left.exec_in_ns(f"ping {right.ipaddress}")
        print(f"Returncode = {result.returncode}")
        print("Will now teardown containers...")
        containers.stop_containers()

        # print("Will now go into infinite loop...")
        # while True:
        #     time.sleep(1)
    except KeyboardInterrupt:
        # Destroy all running containers
        containers.stop_containers()
        print("Ready...")


if __name__ == "__main__":
    main()
