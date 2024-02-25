"""Test scenario: Routed network using default bridge driver. As right node a
   webserver is started. The scenario is implemented as a Pytest test case.

"""

from docker_overdose import (
    ContainerManager,
    ProcessManager,
    OverdoseManager,
    NetworkManager,
)
import pytest

DO_NOTHING = "tail -f /dev/null"
# DO_NOTHING = "sh -c 'while true; do sleep 1; done'"


@pytest.fixture(scope="session")
def setup_network():
    host = ProcessManager("host", pid=1)

    containers = OverdoseManager(host)

    """
    [left]                [router]                [nginx]
       |                   |    |                    |
       ---<overdose-left>---    ---<overdose-right>---
    """

    network_left = NetworkManager("overdose-left")
    network_right = NetworkManager("overdose-right")

    router = ContainerManager(
        "router",
        image="network-test",
        run_options={
            "command": DO_NOTHING,
            "network": network_left,
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

    nginx = ContainerManager(
        "nginx",
        image="nginx",
        run_options={
            "network": network_right,
        },
        net_options={"change_default_route": (router, network_right)},
        autostart=True,
    )

    containers.add(router)
    containers.add(left)
    containers.add(nginx)

    containers.start_containers()

    print("Running post start config on containers...")
    containers.post_start_config()

    yield (left, nginx)

    print("Will now teardown containers...")
    containers.stop_containers()


def test_connectivity(setup_network):
    left, nginx = setup_network
    result = left.exec_in_ns(f"ping {nginx.ipaddress} -c 10")
    assert result.returncode == 0


def test_webserver(setup_network):
    left, nginx = setup_network
    result = left.exec_in_ns(f"curl http://{nginx.ipaddress}:80/")
    assert result.returncode == 0
