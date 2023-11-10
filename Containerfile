FROM python:3.11-slim
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y iproute2 && \
    rm -rf /var/lib/apt/lists/*
COPY . /app
WORKDIR /app
RUN pip install .
CMD ["docker_overdose"]
