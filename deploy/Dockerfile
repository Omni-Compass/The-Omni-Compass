# Omni-Compass controller image. kubectl comes from the official Kubernetes image (no package manager, no curl).
FROM registry.k8s.io/kubectl:v1.32.2 AS kubectl
FROM python:3.12-slim
COPY --from=kubectl /bin/kubectl /usr/local/bin/kubectl
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY omnicompass omnicompass
COPY omni_controller omni_controller
COPY hardware hardware
# the frozen, benchmarked closure-law setting (--closure /app/law/closure.json)
COPY tuning/GLOBAL_LEAGUE_PREREGISTRATION.json law/closure.json
USER 10001
ENTRYPOINT ["python", "-m", "omni_controller.controller"]
