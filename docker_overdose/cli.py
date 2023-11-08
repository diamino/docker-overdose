"""CLI interface for docker_overdose project.

"""
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
