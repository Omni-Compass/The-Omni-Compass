#!/usr/bin/env bash
# Live proof of the added levers on a real Kubernetes API server (kind): rightsize, coldstart, batch pace, containment
# and the cooling connector. Omni-Compass runs as its least-privilege service account (rbac-omni.yaml + rbac-levers.yaml,
# with `kubectl auth can-i` receipts). For each lever the script drives the triggering condition, checks with kubectl that
# the real object changed, then fires the kill switch from a fresh process and checks every object is back and no
# omnicompass.io record is left. The cooling connector writes to a stand-in building controller (a file): a CI runner has
# no chiller, so that lever proves the mechanism only. Results in $OUT_DIR/levers.txt.
set -euo pipefail
OUT_DIR="${OUT_DIR:-levers_out}"; mkdir -p "$OUT_DIR"
show() { echo "-- lever errors in the audit log"; grep '"error"' "$OUT_DIR/audit.jsonl" 2>/dev/null | tail -n 30 || true
         echo "-- controller.log (last 40 lines)"; tail -n 40 "$OUT_DIR/controller.log" 2>/dev/null || true; }
trap show EXIT
METRICS_SERVER_VERSION="${METRICS_SERVER_VERSION:-v0.9.0}"
METRICS_SERVER_SHA256="${METRICS_SERVER_SHA256:-1cec29a5267809306a2c6ec74a3e449abbb705b4a8beed0c8a1963910f72c79b}"
curl -fsSL "https://github.com/kubernetes-sigs/metrics-server/releases/download/${METRICS_SERVER_VERSION}/components.yaml" -o "$OUT_DIR/ms.yaml"
[ "$(sha256sum "$OUT_DIR/ms.yaml" | cut -d' ' -f1)" = "$METRICS_SERVER_SHA256" ] || { echo "metrics-server SHA mismatch"; exit 1; }
kubectl apply -f "$OUT_DIR/ms.yaml"
kubectl -n kube-system patch deployment metrics-server --type=json -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl -n kube-system rollout status deployment/metrics-server --timeout=300s
kubectl apply -f deploy/kind/demo.yaml
kubectl create configmap omni-security --from-literal=hold=false --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f deploy/kind/levers.yaml
kubectl rollout status deployment/php-apache --timeout=300s
kubectl rollout status deployment/idle-worker --timeout=300s
kubectl -n agents rollout status deployment/agent --timeout=300s
kubectl wait --for=condition=Ready pod -l app=train-a --timeout=300s
for i in $(seq 1 30); do kubectl top pods -n agents --no-headers >/dev/null 2>&1 && kubectl top pods --no-headers >/dev/null 2>&1 && break; sleep 10; done
kubectl apply -f deploy/kind/rbac-omni.yaml -f deploy/kind/rbac-levers.yaml
SA="system:serviceaccount:omni-compass:omni-compass"; can() { kubectl auth can-i "$@" --as="$SA"; }
{
  echo "== can"
  echo "patch pods/resize default (rightsize): $(can patch pods --subresource=resize -n default)"
  echo "patch deployment/idle-worker (coldstart record): $(can patch deployment/idle-worker -n default)"
  echo "patch deployments/scale idle-worker (coldstart): $(can patch deployments/idle-worker --subresource=scale -n default)"
  echo "get configmap/omni-work (coldstart afferent): $(can get configmap/omni-work -n default)"
  echo "patch jobs default (batch pace): $(can patch jobs -n default)"
  echo "create resourcequotas agents (contain): $(can create resourcequotas -n agents)"
  echo "delete resourcequotas agents (contain): $(can delete resourcequotas -n agents)"
  echo "patch pods/resize agents (contain): $(can patch pods --subresource=resize -n agents)"
  echo "== cannot"
  echo "delete pods agents: $(can delete pods -n agents)"
  echo "create pods agents: $(can create pods -n agents)"
  echo "delete deployments agents: $(can delete deployments -n agents)"
  echo "patch deployment/load-generator: $(can patch deployment/load-generator -n default)"
  echo "create resourcequotas default: $(can create resourcequotas -n default)"
  echo "get secrets (any namespace): $(can get secrets -A)"
} | tee "$OUT_DIR/rbac_levers.txt"
! sed -n '/== can/,/== cannot/p' "$OUT_DIR/rbac_levers.txt" | grep -q ": no$" || { echo "missing a permission"; exit 1; }
! sed -n '/== cannot/,$p' "$OUT_DIR/rbac_levers.txt" | grep -q ": yes$" || { echo "has a forbidden permission"; exit 1; }
K="$(pwd)/scripts/kubectl_omni.sh"
BMS="$OUT_DIR/bms_setpoints.log"
run() {  # run the controller for N decisions with extra arguments
  local n=$1; shift
  python -m omni_controller.controller --kubectl "$K" --mode target --interval 5 --iterations "$n" \
    --rightsize-deployments default/php-apache --coldstart-deployments default/idle-worker --coldstart-signal default/omni-work \
    --coldstart-idle 2 --batch-pace --contain-namespaces agents --cooling-cmd "sh -c 'echo {c} >> $BMS'" \
    --audit "$OUT_DIR/audit.jsonl" --kill-file "$OUT_DIR/kill" "$@" >> "$OUT_DIR/controller.log" 2>&1
}
req() { kubectl get pods -l run=php-apache -o jsonpath='{range .items[*]}{.spec.containers[0].resources.requests.cpu}{" "}{end}'; }
lim() { kubectl get pods -n agents -l app=agent -o jsonpath='{range .items[*]}{.spec.containers[0].resources.limits.cpu}{" "}{end}'; }
rep() { kubectl get deployment idle-worker -o jsonpath='{.spec.replicas}'; }
susp() { kubectl get job train-a -o jsonpath='{.spec.suspend}'; }
quota() { kubectl get resourcequota omni-containment -n agents --no-headers 2>/dev/null | wc -l; }
R0="$(req)"; L0="$(lim)"
echo "== phase 1: no work waiting, power stress over the pace threshold, agents over budget"
run 3 --pace-high 0 --contain-cpu-m 200
R1="$(req)"; L1="$(lim)"; P1="$(rep)"; S1="$(susp)"; Q1="$(quota)"
echo "== phase 2: work waiting, calm, budget raised"
kubectl patch configmap omni-work --type=merge -p '{"data":{"queue":"5"}}'
run 2 --pace-high 5 --pace-low 5 --contain-cpu-m 100000
P2="$(rep)"; S2="$(susp)"; Q2="$(quota)"; L2="$(lim)"
echo "== phase 3: stress again, then the kill switch from a fresh process"
kubectl patch configmap omni-work --type=merge -p '{"data":{"queue":"0"}}'
run 3 --pace-high 0 --contain-cpu-m 200
P3="$(rep)"; S3="$(susp)"; Q3="$(quota)"
touch "$OUT_DIR/kill"; run 1 --contain-cpu-m 200
R4="$(req)"; L4="$(lim)"; P4="$(rep)"; S4="$(susp)"; Q4="$(quota)"
left=$( (kubectl get deployment php-apache idle-worker -o json | jq -r '.items[].metadata.annotations // {} | keys[]'; \
         kubectl get job train-a -o json | jq -r '.metadata.annotations // {} | keys[]') | grep '^omnicompass.io/' || true)
{
  echo "rightsize   php-apache CPU requests: before [$R0] after [$R1]; after kill [$R4]"
  echo "coldstart   idle-worker replicas: idle -> $P1; work waiting -> $P2; idle again -> $P3; after kill -> $P4"
  echo "batch_pace  train-a suspended: stress -> $S1; calm -> $S2; stress -> $S3; after kill -> $S4"
  echo "contain     agent quota present: over budget -> $Q1; under budget -> $Q2; over -> $Q3; after kill -> $Q4"
  echo "            agent CPU limits: before [$L0] contained [$L1] lifted [$L2] after kill [$L4]"
  echo "cooling     setpoints written to the stand-in controller: $(tr '\n' ' ' < "$BMS" 2>/dev/null)"
  echo "records left after kill: ${left:-none}"
  echo "writes by lever: $(grep -o '"why": "[a-z_]*' "$OUT_DIR/audit.jsonl" | cut -d'"' -f4 | sort | uniq -c | tr '\n' ';')"
} | tee "$OUT_DIR/levers.txt"
test "$R1" != "$R0" && test "$R4" = "$R0"
test "$P1" = "0" && test "$P2" = "2" && test "$P3" = "0" && test "$P4" = "2"
test "$S1" = "true" && test "$S2" = "false" && test "$S3" = "true" && test "$S4" = "false"
test "$Q1" = "1" && test "$Q2" = "0" && test "$Q3" = "1" && test "$Q4" = "0"
test "$L1" != "$L0" && test "$L2" = "$L0" && test "$L4" = "$L0"
test -z "$left"
test "$(tail -n1 "$BMS")" = "22.0"
echo "LIVE LEVERS: PASS"
