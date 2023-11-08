"""CLI interface for docker_overdose project.

"""
import time
from .containermanager import (
    ContainersManager,
    ProcessManager,
    ContainerManager,
)


def main():  # pragma: no cover
    host = ProcessManager("host", pid=1)

    containers = ContainersManager(host)

    nginx = ContainerManager(
        "nginx",
        image="nginx",
        run_options={"ports": {"80/tcp": 8080}},
        autostart=True,
    )
    containers.add(nginx)

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
