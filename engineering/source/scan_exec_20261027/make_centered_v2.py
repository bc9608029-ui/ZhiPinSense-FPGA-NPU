import pathlib
r=pathlib.Path(__file__).parent;s=(r/'rml24_dualmode_receiver_centered_candidate.py').read_text()
old='locked_ok = locked_detection.score >= config.min_public_score'
new='locked_ok = (locked_detection.score >= config.min_public_score and abs(locked_detection.coarse_cfo_hz) <= 1000.0)'
assert s.count(old)==1;s=s.replace(old,new)
start=s.index('                if hit is not None:\n',s.index('row["scan_steps"] = scan_steps'))
end=s.index('                else:\n                    row["error"] = "NO_PUBLIC_FRAME_IN_SCAN_RANGE"',start)
body=s[start+len('                if hit is not None:\n'):end]
s=s[:start]+'                if hit is not None:\n                    try:\n'+''.join('    '+line if line.strip() else line for line in body.splitlines(True))+'''                    except Exception as exc:
                        locked_lo_hz = None
                        raw_for_recovery = None
                        row["error"] = "PUBLIC_CENTERING_FAILED:" + type(exc).__name__ + ":" + str(exc)
'''+s[end:]
(r/'rml24_dualmode_receiver_centered_v2.py').write_bytes(s.encode('utf-8'))
s=(r/'run_centered_candidate.sh').read_text().replace('rml24_dualmode_receiver_centered_candidate.py','rml24_dualmode_receiver_centered_v2.py');(r/'run_centered_v2.sh').write_bytes(s.encode('utf-8'))
print('V2_READY: centred lock geometric bound; centering failure becomes invalid row rather than protocol abort; public-score threshold unchanged')