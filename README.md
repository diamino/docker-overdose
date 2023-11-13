# docker_overdose

[![codecov](https://codecov.io/gh/diamino/docker-overdose/branch/main/graph/badge.svg?token=docker-overdose_token_here)](https://codecov.io/gh/diamino/docker-overdose)
[![CI](https://github.com/diamino/docker-overdose/actions/workflows/main.yml/badge.svg)](https://github.com/diamino/docker-overdose/actions/workflows/main.yml)

Docker-compose alternative with (too much) added functionality.

## Install it from PyPI

```bash
pip install docker_overdose
```

## Usage

```py
from docker_overdose.containermanager import ContainerManager, ContainersManager

# Instantiate the orchestrator
containers = ContainersManager()
# Instantiate a container
container = ContainerManager('container-name',
                             image='debian:bookworm-slim',
                             run_options={"command": f"sh -c 'while true; do echo Hello World!; sleep 1; done'"},
                             net_options={"add_if": "enp0s2"},
                             autostart=True)
containers.add(container)
containers.start()
```

```bash
$ python -m docker_overdose
#or
$ docker_overdose
```

## Development

Read the [CONTRIBUTING.md](CONTRIBUTING.md) file.
