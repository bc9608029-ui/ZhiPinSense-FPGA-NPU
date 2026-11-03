#!/usr/bin/env python3
"""Board-only typed command plan. No transport assumption; operator pipes lines to verified Unix client."""
import json,argparse
p=argparse.ArgumentParser();p.add_argument('--emit',action='store_true');a=p.parse_args()
commands=['GET_TUNING','STOP','SET_FIXED_HZ 2400000000','SET_MODE FIXED','START','STOP']
for start,stop,step,n in [(2395000000,2405000000,1000000,11),(2396000000,2404000000,2000000,5),(2395000000,2405000000,500000,21),(2395000000,2405000000,1500000,8)]:
 commands += ['SET_SCAN_RANGE_HZ %d %d %d'%(start,stop,step),'GET_TUNING']
for mode in ['BAND_SCAN','CONTINUOUS_SCAN']:
 commands += ['SET_MODE '+mode,'START','GET_TUNING','STOP']
for args in ['2405000000 2395000000 1000000','2395000000 2395000000 1000000','2395000000 2405000000 0','2395000000 2405000000 -1','2395000000 2405000000 2304001','2395000000 2405000000 1']:
 commands+=['GET_TUNING','SET_SCAN_RANGE_HZ '+args,'GET_TUNING']
commands+=['STOP','SET_FIXED_HZ 2400000000','SET_SCAN_RANGE_HZ 2395000000 2405000000 1000000','SET_MODE FIXED','GET_TUNING']
if a.emit:print('\n'.join(commands))
else:print(json.dumps({'status':'PLAN_ONLY_NOT_EXECUTED','commands':commands,'requirement':'After each accepted command poll GET_TUNING until applied matches. Invalid commands must leave applied state unchanged. Save complete replies; accepted is not applied.'},indent=2))
