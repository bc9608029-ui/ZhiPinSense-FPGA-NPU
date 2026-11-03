import pathlib,hashlib
root=pathlib.Path(__file__).parent
p=pathlib.Path('E:/嵌赛/rml24_scan_final_prep1_20261027/board_runtime/rml24_dualmode_receiver.py');s=p.read_text(encoding='utf-8')
old='''                    locked_lo_hz = hit.lo_hz
                    display_center_hz = int(round(hit.signal_hz))
                    raw_for_recovery = remove_coarse_cfo(hit.raw_iq, hit.detection.coarse_cfo_hz)'''
new='''                    # Candidate: centre the physical LO before frozen recovery.
                    # Public-reference CFO is a discovery estimate, not an IQ
                    # preprocessing step that removes the frozen two-DC basis.
                    initial_lo = hit.lo_hz
                    requested_center = int(round(hit.signal_hz))
                    if abs(hit.detection.coarse_cfo_hz) > 1000.0:
                        lo.tune(requested_center)
                        lo.flush()
                        centered_raw = np.asarray(radio.receive(65536))
                        centered_detection = detect_public_training(centered_raw, protocol.train)
                        if centered_detection.score < config.min_public_score or abs(centered_detection.coarse_cfo_hz) > 1000.0:
                            raise RuntimeError("public-centre verification failed")
                        hit = ScanHit(lo_hz=lo.current_hz,
                            signal_hz=float(lo.current_hz + centered_detection.coarse_cfo_hz),
                            detection=centered_detection, raw_iq=centered_raw)
                        row["public_centering"] = {
                            "initial_grid_lo_hz": initial_lo,
                            "requested_lo_hz": requested_center,
                            "actual_lo_hz": lo.current_hz,
                            "residual_cfo_hz": centered_detection.coarse_cfo_hz,
                            "public_score": centered_detection.score}
                    locked_lo_hz = hit.lo_hz
                    display_center_hz = int(round(hit.signal_hz))
                    raw_for_recovery = hit.raw_iq'''
assert s.count(old)==1;s=s.replace(old,new)
(root/'rml24_dualmode_receiver_centered_candidate.py').write_text(s,encoding='utf-8')
p=p.with_name('run_dualmode_receiver.sh');s=p.read_text(encoding='utf-8');assert s.count('rml24_dualmode_receiver.py')==1;s=s.replace('rml24_dualmode_receiver.py','rml24_dualmode_receiver_centered_candidate.py')
(root/'run_centered_candidate.sh').write_text(s,encoding='utf-8')
print('CANDIDATE_READY public LO centering only; FIXED branch and frozen recovery/model unchanged')