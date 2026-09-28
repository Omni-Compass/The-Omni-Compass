#!/usr/bin/env bash
# One arm of the native-vs-Omni benchmark on the six-worker kind cluster (deploy/kind/cluster-full.yaml).
# Both arms are wired identically: same cluster, add-ons, workload, HPA (target 50), load schedule, capture and
# power model. The only difference:
#   ARM=native  Omni-Compass is not started at all. Kubernetes (HPA, scheduler) runs alone on all workers.
#   ARM=omni    Omni-Compass runs in nodepool mode with every live muscle: HPA target, node pool (prefer-not idle mark, first-to-go order),
#               power cap (CPU limit of php-apache, enforced by the kernel), heat (harness law on live power), security
#               (ConfigMap hold), rollout guard, and the latency afferent: 95th-percentile response time over SLO_MS
#               (declared before the run, default 500 ms) enters the engine as queue pressure. The power cap never goes
#               below pod usage x 1.3. Parked workers stay powered and Ready at their idle floor (STANDBY_W =
#               park_frac x idle, never off).
#   ARM=watch   Omni-Compass runs exactly as in ARM=omni (same process, same reads, same senses, same decisions) with
#               --dry-run: every write is logged, none is executed. Any difference from native in this arm is the cost of
#               Omni-Compass being there (its CPU on the shared runner, its API reads) plus run-to-run noise, never a
#               decision. The run fails if one write reached the cluster.
# The controller runs at the lowest CPU priority (nice 19) in every Omni arm: on a real cluster it runs on its own node,
# here all seven kind nodes share one 4-core runner with the service being measured.
# Both arms: a real response-time probe times HTTP requests to php-apache every 5 s (latency.csv).
# Load schedule: the load-generator replica count steps through LOAD_STEPS, each step DURATION/steps seconds,
# identical in both arms. Results in $OUT_DIR: capture.csv (every 15 s), nodes timeline, Omni audit (omni arm).
# Evidence discipline (adopted from the ChatGPT-built harness, extended to every muscle): pinned, SHA-256-checked
# metrics-server; preflight record of tool versions; clean-cluster check; Omni-Compass runs as a least-privilege service
# account (deploy/kind/rbac-omni.yaml) with `kubectl auth can-i` receipts for what it can and cannot do; the run fails if
# Omni made no write or if the kill switch leaves any record behind; SHA256SUMS.txt fingerprints every output file.
set -euo pipefail
ARM="${ARM:?set ARM=native, ARM=watch (Omni watches, writes nothing), ARM=omni (B: Omni on top) or ARM=strict (C: Omni decides replicas and nodes)}"
STRICT=""; [ "$ARM" = "strict" ] && STRICT="--strict-replicas"
DRY=""; [ "$ARM" = "watch" ] && DRY="--dry-run"
OUT_DIR="${OUT_DIR:-bench_$ARM}"; DURATION="${DURATION:-1200}"; WARMUP="${WARMUP:-120}"
LOAD_STEPS="${LOAD_STEPS:-1 2 3 1 2 1}"
export DRAIN_TIMEOUT="${DRAIN_TIMEOUT:-45s}"   # a drain blocked by the disruption budget gives up and the node stays in service
IDLE_W="${IDLE_W:-100}"; DYN_W="${DYN_W:-150}"
# no machine is ever powered off: an idle worker (marked prefer-not, its work gone) stays Ready and powered, gauged down
# to its idle floor, and is back in service the instant its mark is removed (muscle tone). It draws park_frac x idle power, the
# simulator's declared hardware property (fleet/harness.py park_frac = 0.25); the same accounting in every arm
PARK_FRAC="${PARK_FRAC:-0.25}"
STANDBY_W="${STANDBY_W:-$(python -c "print($IDLE_W * $PARK_FRAC)")}"; export IDLE_W DYN_W STANDBY_W
mkdir -p "$OUT_DIR"
WORKERS=$(kubectl get nodes -l '!node-role.kubernetes.io/control-plane' --no-headers | wc -l)
SITE_LIMIT_W=$(( WORKERS * (IDLE_W + DYN_W) ))

METRICS_SERVER_VERSION="${METRICS_SERVER_VERSION:-v0.9.0}"
METRICS_SERVER_SHA256="${METRICS_SERVER_SHA256:-1cec29a5267809306a2c6ec74a3e449abbb705b4a8beed0c8a1963910f72c79b}"
server_minor=$(kubectl version -o json | jq -r '.serverVersion.minor' | tr -cd '0-9')
[ -n "$server_minor" ] && [ "$server_minor" -ge 34 ] || { echo "metrics-server $METRICS_SERVER_VERSION needs Kubernetes 1.34+ (minor=$server_minor)"; exit 1; }
{
  echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; echo "arm=$ARM"; echo "git_commit=$(git rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "docker=$(docker --version 2>/dev/null || echo n/a)"; echo "kind=$(kind version 2>/dev/null || echo n/a)"
  echo "kubectl=$(kubectl version --client=true -o json | jq -r '.clientVersion.gitVersion')"
  kubectl version -o json | jq -r '"server=" + .serverVersion.gitVersion'; echo "python=$(python --version 2>&1)"
  echo "metrics_server=$METRICS_SERVER_VERSION sha256=$METRICS_SERVER_SHA256"; echo "workers=$WORKERS"
} | tee "$OUT_DIR/preflight.txt"
curl -fsSL "https://github.com/kubernetes-sigs/metrics-server/releases/download/${METRICS_SERVER_VERSION}/components.yaml" -o "$OUT_DIR/metrics-server-components.yaml"
actual_sha=$(sha256sum "$OUT_DIR/metrics-server-components.yaml" | cut -d' ' -f1)
[ "$actual_sha" = "$METRICS_SERVER_SHA256" ] || { echo "metrics-server manifest SHA-256 mismatch: $actual_sha"; exit 1; }
kubectl apply -f "$OUT_DIR/metrics-server-components.yaml"
kubectl -n kube-system patch deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
pin='{"spec":{"template":{"spec":{"nodeSelector":{"node-role.kubernetes.io/control-plane":""},"tolerations":[{"key":"node-role.kubernetes.io/control-plane","operator":"Exists","effect":"NoSchedule"}]}}}}'
kubectl -n kube-system patch deployment metrics-server -p "$pin"
kubectl -n kube-system patch deployment coredns -p "$pin"
kubectl -n kube-system rollout status deployment/metrics-server --timeout=300s
kubectl -n kube-system rollout status deployment/coredns --timeout=300s
kubectl apply -f deploy/kind/demo.yaml
kubectl apply -f deploy/kind/bench-serving.yaml
kubectl rollout status deployment/php-apache --timeout=300s
EDGE_IP=$(kubectl get nodes -l node-role.kubernetes.io/control-plane -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
PROBE_URL="http://${EDGE_IP}:30080/"
for i in $(seq 1 30); do curl -fsS -m 5 "$PROBE_URL" >/dev/null && break; sleep 2; done
curl -fsS -m 5 "$PROBE_URL" >/dev/null || { echo "serving path $PROBE_URL not reachable"; exit 1; }
echo "probe_url=$PROBE_URL (Service via kube-proxy on the control plane)" | tee -a "$OUT_DIR/preflight.txt"
kubectl create configmap omni-security --from-literal=hold=false --dry-run=client -o yaml | kubectl apply -f -
# LOADGEN=closed (default, every set before 22): waits for each answer. LOADGEN=open: a fixed rate, the same work in every arm
LOADGEN="${LOADGEN:-closed}"
if [ "$LOADGEN" = "open" ]; then kubectl apply -f deploy/kind/loadgen-open.yaml; else kubectl apply -f deploy/kind/loadgen.yaml; fi
echo "loadgen=$LOADGEN" | tee -a "$OUT_DIR/preflight.txt"
kubectl rollout status deployment/load-generator --timeout=300s
for i in $(seq 1 30); do kubectl top nodes >/dev/null 2>&1 && break; sleep 10; done
hpa_count=$(kubectl get hpa -A -o json | jq '.items | length')
[ "$hpa_count" = "1" ] || { echo "expected exactly one HPA, found $hpa_count"; exit 1; }
foreign=$(kubectl get pods -A -o json | jq '[.items[] | select(.metadata.namespace | IN("kube-system","local-path-storage","default","omni-compass") | not)] | length')
[ "$foreign" = "0" ] || { echo "cluster contains non-harness pods"; exit 1; }
if [ "$ARM" != "native" ]; then
  kubectl apply -f deploy/kind/rbac-omni.yaml
  SA="system:serviceaccount:omni-compass:omni-compass"
  can() { kubectl auth can-i "$@" --as="$SA"; }
  {
    echo "== can (each muscle's push)"
    echo "patch hpa/php-apache (hpa): $(can patch hpa/php-apache -n default)"
    echo "patch nodes (node pool: idle mark): $(can patch nodes)"
    echo "create pods/eviction (node pool: drain): $(can create pods --subresource=eviction -n default)"
    echo "patch pods/resize (power cap, in place): $(can patch pods --subresource=resize -n default)"
    echo "patch pods (make before break: which pods leave first): $(can patch pods -n default)"
    echo "get pods/resize (power cap reads before it writes): $(can get pods --subresource=resize -n default)"
    echo "patch deployment/php-apache (rollout guard, cap record): $(can patch deployment/php-apache -n default)"
    echo "get configmap/omni-security (security afferent): $(can get configmap/omni-security -n default)"
    echo "== cannot"
    echo "delete nodes: $(can delete nodes)"
    echo "create pods: $(can create pods -n default)"
    echo "delete pods: $(can delete pods -n default)"
    echo "delete deployments: $(can delete deployments -n default)"
    echo "patch deployment/load-generator: $(can patch deployment/load-generator -n default)"
    echo "patch deployments in kube-system: $(can patch deployments -n kube-system)"
    echo "patch hpa in kube-system: $(can patch hpa -n kube-system)"
    echo "get secrets (any namespace): $(can get secrets -A)"
    echo "create namespaces: $(can create namespaces)"
    echo "patch configmap/omni-security: $(can patch configmap/omni-security -n default)"
  } | tee "$OUT_DIR/rbac_omni.txt"
  ! sed -n '/== can/,/== cannot/p' "$OUT_DIR/rbac_omni.txt" | grep -q ": no$" || { echo "Omni identity is missing a permission it needs"; exit 1; }
  ! sed -n '/== cannot/,$p' "$OUT_DIR/rbac_omni.txt" | grep -q ": yes$" || { echo "Omni identity has a permission it must not have"; exit 1; }
  export KUBECTL="$(pwd)/scripts/kubectl_omni.sh"
fi
echo "== warm-up ${WARMUP}s (both arms)"; sleep "$WARMUP"

read -r -a steps <<< "$LOAD_STEPS"
step_s=$(( DURATION / ${#steps[@]} ))
( for r in "${steps[@]}"; do
    echo "$(date -u +%H:%M:%S) load-generator replicas -> $r"
    kubectl scale deployment/load-generator --replicas="$r" >/dev/null
    sleep "$step_s"
  done ) > "$OUT_DIR/load_schedule.log" 2>&1 &
load_pid=$!

# The probe reaches the app through the Service (NodePort on the control plane, deploy/kind/bench-serving.yaml), so a
# drain that moves a pod is seen exactly as a client sees it: kube-proxy sends the request to another ready endpoint.
INTERVAL=5 DURATION="$DURATION" python scripts/latency_probe.py "$PROBE_URL" "$OUT_DIR/latency.csv" &
probe_pid=$!
# every start of a serving pod, timed exactly: the API server's own record of each pod from creation to Ready, streamed
# for the whole measured window (pilot/bench_report.py pod_starts), in every arm alike
date -u +%s > "$OUT_DIR/window_start.txt"
kubectl get pods -n default -l run=php-apache -w --output-watch-events -o json > "$OUT_DIR/pod_watch.json" 2>"$OUT_DIR/pod_watch.err" &
watch_pid=$!
omni_pid=""
if [ "$ARM" != "native" ]; then
  echo "== ARM $ARM: Omni-Compass driving HPA target + node pool + power sensing${DRY:+ (dry run: watches only, writes nothing)}"
  nice -n 19 python -m omni_controller.controller $DRY --kubectl "$KUBECTL" --mode nodepool --active-nodes-only --interval 60 --floor-interval 5 --reflex-window-s 15 \
    --iterations $(( DURATION / 60 )) --min-nodes 1 --max-nodes "$WORKERS" --max-node-step 1 \
    --node-scale-cmd "bash scripts/kind_nodepool.sh {n}" --node-restore-cmd "bash scripts/kind_nodepool.sh $WORKERS" \
    --power-cmd "bash scripts/kind_power.sh" --site-limit-w "$SITE_LIMIT_W" \
    --cap-deployments default/php-apache --thermal-model --security-configmap default/omni-security \
    --rollout-guard default/php-apache --latency-file "$OUT_DIR/latency.csv" --slo-ms "${SLO_MS:-500}" \
    --audit "$OUT_DIR/audit.jsonl" --kill-file "$OUT_DIR/kill" $STRICT ${CLOSURE:+--closure "$CLOSURE"} > "$OUT_DIR/controller.log" 2>&1 &
  omni_pid=$!
else
  echo "== ARM native: Omni-Compass not running; Kubernetes alone"
fi

ACTIVE_ONLY=1 INTERVAL=15 DURATION="$DURATION" POWER_CMD="bash scripts/kind_power.sh" OUT="$OUT_DIR/capture.csv" \
  bash fleet/capture/kube_capture.sh
wait "$load_pid" || true
wait "$probe_pid" || true
date -u +%s > "$OUT_DIR/window_end.txt"
kill "$watch_pid" 2>/dev/null || true; wait "$watch_pid" 2>/dev/null || true
kubectl get pods -n default -l run=php-apache -o json > "$OUT_DIR/pods_end.json"
[ -n "$omni_pid" ] && { wait "$omni_pid" || true; }
kubectl get nodes -o wide > "$OUT_DIR/nodes_end.txt"
kubectl get hpa php-apache -o json > "$OUT_DIR/hpa_end.json"

if [ "$ARM" = "watch" ]; then
  echo "== watch arm: nothing may have reached the cluster"
  executed=$(grep '"write"' "$OUT_DIR/audit.jsonl" | grep -c '"dry_run": false' || true)
  logged=$(grep -c '"write"' "$OUT_DIR/audit.jsonl" || true)
  echo "writes Omni would have made: $logged; writes executed: $executed" | tee "$OUT_DIR/omni_writes.txt"
  cpu_limit=$(kubectl get pods -l run=php-apache -o jsonpath='{range .items[*]}{.spec.containers[0].resources.limits.cpu}{"\n"}{end}' | sort -u | tr '\n' ' ' | sed 's/ $//')
  target=$(kubectl get hpa php-apache -o jsonpath='{.spec.metrics[0].resource.target.averageUtilization}')
  range_now=$(kubectl get hpa php-apache -o jsonpath='{.spec.minReplicas},{.spec.maxReplicas}')
  back=$(kubectl get nodes -l '!node-role.kubernetes.io/control-plane' -o json | jq '[.items[] | select(.spec.unschedulable != true and (any(.spec.taints[]?; .key == "omnicompass.io/idle") | not))] | length')
  echo "cluster after the run: target $target, range $range_now, CPU limits $cpu_limit, workers $back of $WORKERS" | tee "$OUT_DIR/kill_switch.txt"
  test "$executed" = "0" && test "$target" = "50" && test "$range_now" = "1,10" && test "$cpu_limit" = "500m" && test "$back" = "$WORKERS"
elif [ "$ARM" != "native" ]; then
  echo "== kill switch"
  touch "$OUT_DIR/kill"
  omni_writes=$(grep -c '"write"' "$OUT_DIR/audit.jsonl" || true)
  echo "omni writes during the run: $omni_writes" | tee "$OUT_DIR/omni_writes.txt"
  [ "$omni_writes" -gt 0 ] || { echo "Omni made no write, so the kill switch would prove nothing"; exit 1; }
  python -m omni_controller.controller --kubectl "$KUBECTL" --mode nodepool --active-nodes-only --iterations 1 \
    --cap-deployments default/php-apache --rollout-guard default/php-apache \
    --node-restore-cmd "bash scripts/kind_nodepool.sh $WORKERS" --audit "$OUT_DIR/audit_kill.jsonl" --kill-file "$OUT_DIR/kill"
  cpu_limit=$(kubectl get pods -l run=php-apache -o jsonpath='{range .items[*]}{.spec.containers[0].resources.limits.cpu}{"\n"}{end}' | sort -u | tr '\n' ' ' | sed 's/ $//')
  echo "pod CPU limits after kill: $cpu_limit" | tee -a "$OUT_DIR/kill_switch.txt"
  restored=$(kubectl get hpa php-apache -o jsonpath='{.spec.metrics[0].resource.target.averageUtilization}')
  range_now=$(kubectl get hpa php-apache -o jsonpath='{.spec.minReplicas},{.spec.maxReplicas}')
  echo "HPA replica range after kill: $range_now" | tee -a "$OUT_DIR/kill_switch.txt"
  test "$range_now" = "1,10"
  back=$(kubectl get nodes -l '!node-role.kubernetes.io/control-plane' -o json | jq '[.items[] | select(.spec.unschedulable != true and (any(.spec.taints[]?; .key == "omnicompass.io/idle") | not))] | length')
  { echo "restored target: $restored"; echo "workers in service: $back of $WORKERS"; } | tee "$OUT_DIR/kill_switch.txt"
  leftover=$(kubectl get hpa php-apache -o json | jq -r '.metadata.annotations // {} | keys[] | select(startswith("omnicompass.io/"))'; kubectl get deployment php-apache -o json | jq -r '.metadata.annotations // {} | keys[] | select(startswith("omnicompass.io/"))')
  echo "Omni records left after kill: ${leftover:-none}" | tee -a "$OUT_DIR/kill_switch.txt"
  test "$restored" = "50" && test "$back" = "$WORKERS" && test "$cpu_limit" = "500m" && test -z "$leftover"
fi
echo "rows captured: $(( $(wc -l < "$OUT_DIR/capture.csv") - 1 ))"
( cd "$OUT_DIR" && sha256sum $(ls -1 | grep -v '^SHA256SUMS.txt$') > SHA256SUMS.txt )
if [ "$ARM" != "native" ]; then
  # Evidence discipline: the run counts only if the engine decided for the whole run.
  decisions=$(grep -c '"decision"' "$OUT_DIR/audit.jsonl" || true); expected=$(( DURATION / 60 ))
  errors=$(grep -c '"error"' "$OUT_DIR/audit.jsonl" || true)
  echo "== controller: decisions $decisions of $expected, failed decisions or checks $errors"
  echo "-- controller's own cost (CPU of the process and every command it ran): $(grep '"overhead"' "$OUT_DIR/audit.jsonl" | tail -n 1)"
  echo "-- my writes by muscle (count, first words of why)"
  jq -r 'select(.write) | .why // "?" | split(":")[0] + ": " + (split(":")[1] // "" | ltrimstr(" ") | split(" ")[0:3] | join(" "))' "$OUT_DIR/audit.jsonl" | sort | uniq -c | sort -rn | head -n 20 || true
  echo "-- conveyed CPU limits (last 8)"; grep '"convey:' "$OUT_DIR/audit.jsonl" | jq -r '.why' | tail -n 8 || true
  echo "-- pod reflex (last 8)"; grep '"pod reflex:' "$OUT_DIR/audit.jsonl" | jq -r '.why' | tail -n 8 || true
  echo "-- controller.log (last 40 lines)"; tail -n 40 "$OUT_DIR/controller.log" || true
  echo "-- audit errors (last 10)"; grep '"error"\|"failsafe"' "$OUT_DIR/audit.jsonl" | tail -n 10 || true
  echo "-- decision trail (nodes seen -> recommended | p95 ms | SLO clean | calm | node-view calm | node gate)"
  python - "$OUT_DIR/audit.jsonl" <<'PY' || true
import json, sys
sys.path.insert(0, ".")
from omnicompass.compass import say
auth = None
for line in open(sys.argv[1]):
    r = json.loads(line)
    if "compass" in r:
        print("  compass:", say(r["compass"]))
    elif "authority" in r:
        auth = r["authority"]
    elif isinstance(r.get("decision"), dict):
        d = r["decision"]; a = auth or {}
        print(f"  {d['nodes_observed']} -> {d['nodes_recommended']} | p95 {d.get('latency_p95_ms')} | clean {d.get('slo_clean')} | "
              f"calm {a.get('calm')} | node calm {a.get('node_view', {}).get('calm')} | gate {a.get('node_gate', {}).get('reason')} | "
              f"queue {d.get('queue_ratio')} | U {d['U']:.3f} | blind {[k for k, v in a.get('senses', {}).get('blind', {}).items() if v]} | "
              f"latency age {a.get('senses', {}).get('latency_age_s')} s | proprioception {a.get('proprioception')}")
PY
  [ $(( decisions * 10 )) -ge $(( expected * 8 )) ] || { echo "INVALID RUN: the controller stopped early"; exit 1; }
  ! grep -q '"failsafe"' "$OUT_DIR/audit.jsonl" || { echo "INVALID RUN: the fail-safe handed control back to native"; exit 1; }
fi
