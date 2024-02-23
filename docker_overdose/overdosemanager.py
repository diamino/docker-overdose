from .processmanager import ProcessManager


class OverdoseManager:
    def __init__(self, host=None, name=None, containers={}, version="latest"):
        if not host:
            self.host = ProcessManager("host", pid=1)
        else:
            self.host = host
        self.name = name
        self.containers = containers
        self.version = version

    def add(self, container):
        if ":" not in container.image:
            container.image = f"{container.image}:{self.version}"
        self.containers[container.name] = container
        container.host = self.host
        if self.name:
            container.name = f"{self.name}_{container.name}"

    def start_containers(
        self, containers=None, noconfig=False, post_config=False
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
