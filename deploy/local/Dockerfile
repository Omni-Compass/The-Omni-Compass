# Runner image: kind + kubectl + jq + Python + the Omni-Compass harness.
# It drives your local Docker Desktop (through the mounted docker.sock) to create the Kubernetes cluster.
FROM docker:27-cli AS dockercli

FROM python:3.12-slim
ARG TARGETARCH
ARG KIND_VERSION=v0.27.0
ARG KUBECTL_VERSION=v1.32.2

RUN apt-get update \
 && apt-get install -y --no-install-recommends bash curl jq ca-certificates procps \
 && rm -rf /var/lib/apt/lists/*

COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker

RUN ARCH="${TARGETARCH:-amd64}" \
 && curl -fsSLo /usr/local/bin/kind "https://github.com/kubernetes-sigs/kind/releases/download/${KIND_VERSION}/kind-linux-${ARCH}" \
 && curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl" \
 && chmod +x /usr/local/bin/kind /usr/local/bin/kubectl

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app/
COPY deploy/local/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /app/scripts/*.sh /app/fleet/capture/*.sh

ENTRYPOINT ["/entrypoint.sh"]
