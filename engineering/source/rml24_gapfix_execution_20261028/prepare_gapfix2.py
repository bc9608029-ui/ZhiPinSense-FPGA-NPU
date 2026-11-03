from pathlib import Path
r=Path(r'E:\rml24_gapfix_execution_20261028')
s=(r/'delivery/overlay/rml24_final/board_runtime/standalone_receiver.py').read_text(encoding='utf-8')
s=s.replace('last_state=0.0;locked=None;seq=0','last_state=0.0;locked=None;last_good_lo=None;scan_cursor=0;seq=0')
s=s.replace('nonlocal locked\n','nonlocal locked,last_good_lo,scan_cursor\n').replace('locked=None\n            lock_policy.reset()','locked=None;last_good_lo=None;scan_cursor=0\n            lock_policy.reset()')
a=s.index("                    if raw is None and locked is None:")
b=s.index('                arm={};tensor=None;frame=None',a)
s=s[:a]+'''                    if raw is None and locked is None:
                        # After losing a proven lock, revisit it between every
                        # search point. Never disappear into an 11-point sweep.
                        if last_good_lo is not None:
                            actual=lo.tune(last_good_lo);lo.flush()
                            ctl.update(actual_lo_hz=actual)
                            candidate=np.asarray(radio.receive(65536));capture_ns=time.time_ns()
                            d=detect_public_training(candidate,public.train)
                            ok=d.score>=.10 and abs(d.coarse_cfo_hz)<=1000
                            steps.append(dict(lo_hz=actual,public_score=d.score,
                                cfo_hz=d.coarse_cfo_hz,locked_check=True,
                                home_revisit=True,accepted=ok))
                            if ok:raw=candidate;center=int(round(actual+d.coarse_cfo_hz))
                        if raw is None:
                            config=ScanConfig(s['start_hz'],s['stop_hz'],s['step_hz'])
                            frequencies=config.lo_frequencies()
                            index=scan_cursor % len(frequencies)
                            scan_cursor=(index+1) % len(frequencies)
                            checkpoint()
                            actual=lo.tune(frequencies[index]);lo.flush()
                            ctl.update(actual_lo_hz=actual,scan_index=index+1,scan_points=len(frequencies))
                            state('ACQUIRING',True)
                            candidate=np.asarray(radio.receive(65536))
                            d=detect_public_training(candidate,public.train)
                            steps.append(dict(lo_hz=actual,public_score=d.score,cfo_hz=d.coarse_cfo_hz,
                                              locked_check=False,incremental_scan=True,accepted=d.score>=.10))
                            if d.score>=.10:
                                target=int(round(actual+d.coarse_cfo_hz))
                                if args.minimum_hz<=target<=args.maximum_hz:
                                    actual=lo.tune(target);lo.flush()
                                    ctl.update(actual_lo_hz=actual)
                                    candidate=np.asarray(radio.receive(65536));capture_ns=time.time_ns()
                                    d=detect_public_training(candidate,public.train)
                                    if d.score>=.10 and abs(d.coarse_cfo_hz)<=1000:
                                        raw=candidate;center=int(round(actual+d.coarse_cfo_hz))
''' +s[b:]
s=s.replace('                if frame is not None:\n                    lock_policy.hit()',"                if frame is not None:\n                    if s['mode']=='BAND_SCAN':\n                        locked=lo.current_hz;last_good_lo=lo.current_hz\n                    lock_policy.hit()")
compile(s,'standalone_receiver.py','exec')
(r/'standalone_receiver_gapfix2.py').write_text(s,encoding='utf-8')
