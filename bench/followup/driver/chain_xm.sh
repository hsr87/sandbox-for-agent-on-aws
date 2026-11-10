#!/bin/sh
# Comparison reruns. Stops at the first failed smoke run, before any long measurement starts.
cd /work
export RESULTS=/work/x/results DEPLOYMENT=/work/x/dep_m.json
python xrun.py deploy --spec xm_m1_spec.json --par 18
python xrun.py deploy --spec xm_cmp_spec.json --par 6
python xrun.py deploy --spec xm_vpc_spec.json --par 4
echo DEPLOY_ALL_DONE
until [ -f /work/x/usage_on ]; do sleep 5; done
python xrun.py warm --items xm_m1_items.json --n 8 --gap 960 --lead 1200 --round xm > /work/x/xm_warm.log 2>&1 &
python xrun.py mix --items xm_vpc_items.json --n 12 --gap 30 --exp x_vpc --round xm
python xrun.py mix --items xm_heavy_items.json --n 16 --gap 0 --task heavy --exp x_heavy --round xm
python xrun.py conc --items xm_conc_items.json --n 4 --gap 30 --sizes 5,20 --exp x_conc --round xm
wait
echo XM_DONE
