#!/bin/sh
# Same-period anchors for the Nitro run, in the main cluster: gVisor and Kata, cold and warm-pool claims.
set -e
cd /work
export RESULTS=/work/x/results DEPLOYMENT=/work/x/dep_na.json
python xrun.py deploy --spec na_spec.json
python - <<P
import json; p="/work/x/dep_na.json"; d=json.load(open(p)); d["backends"]["na-wgv"]={"kind":"eks_warm","pool":"wp-x86-gvisor"}; d["backends"]["na-wkt"]={"kind":"eks_warm","pool":"wp-x86-kata"}; json.dump(d,open(p,"w"))
P
cd /work/bench
python run.py cold_start --backends na-gv,na-kt,na-wgv,na-wkt --n 20 --round na
cd /work
python xrun.py mix --items na_items.json --n 12 --gap 30 --exp x_na_agent --round na
python xrun.py mix --items na_items.json --n 12 --gap 0 --task heavy --exp x_na_heavy --round na
echo NA_DONE
