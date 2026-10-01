# Security

Report suspected vulnerabilities privately to The Omni-Compass LLC rather than in public issues.
The governor issues control actions only through the shield (omnicompass/shield.py, cpp/src/shield.cpp); the
capture script (fleet/capture/kube_capture.sh) is read-only. No component in this repository writes to a live cluster.
