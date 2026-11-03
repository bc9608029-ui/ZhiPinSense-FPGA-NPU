"""Deterministic first-capture scoring; never choose by prediction correctness."""
def score(events,records,offset):
    scored=[]
    for tx in events:
        start=tx['start_ns']+1500000000;end=tx['end_ns']-300000000
        eligible=[v for v in records if start<=v['capture_time_ns']+offset<=end]
        chosen=min(eligible,key=lambda v:v['capture_time_ns']) if eligible else None
        pred=chosen['pred'] if chosen and chosen['finite'] else -1
        scored.append(dict(index=tx['index'],file=tx['file'],label=tx['label'],pred=pred,
                           correct=pred==tx['label'],chosen_frame=chosen['frame_id'] if chosen else None,
                           eligible_count=len(eligible)))
    return scored
