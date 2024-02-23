"""Test scenario: Link using default bridge driver

"""

import time
from docker_overdose import (
    ContainerManager,
    ProcessManager,
    OverdoseManager,
    NetworkManager,
)


def main():  # pragma: no cover
    host = ProcessManager("host", pid=1)

    containers = OverdoseManager(host)

    test_network = NetworkManager("overdose-test")

    left = ContainerManager(
        "left",
        image="network-test",
        run_options={
            "command": "sh -c 'while true; do sleep 1; done'",
            "network": test_network,
        },
        autostart=True,
    )

    right = ContainerManager(
        "right",
        image="network-test",
        run_options={
            "command": "sh -c 'while true; do sleep 1; done'",
            "network": test_network,
        },
        autostart=True,
    )

    containers.add(left)
    containers.add(right)

    containers.start_containers()

    print("Running post start config on containers...")
    containers.post_start_config()

    print("\nPress Control-C to stop the Network Manager...")

    try:
        left.exec_in_ns(f"ping {right.ipaddress}")

        print("Will now go into infinite loop...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # Destroy all running containers
        containers.stop_containers()
        print("Ready...")


if __name__ == "__main__":
    main()
