import os
import docker

DOCKER_SOCK_OPTIONS = ("/var/run/docker.sock", "/var/run/balena-engine.sock")
DOCKER_SOCK = None
for opt in DOCKER_SOCK_OPTIONS:
    if os.path.exists(opt):
        DOCKER_SOCK = opt
        break
if not DOCKER_SOCK:
    raise Exception("No docker socket available!")

docker_client = None


def connect(base_url=f"unix:/{DOCKER_SOCK}"):
    global docker_client
    docker_client = docker.DockerClient(base_url=base_url)


def get_docker_client():
    global docker_client
    if not docker_client:
        connect()
    return docker_client
