import json, io, sys

path = r'C:\Users\shado\.claude\projects\F--\8c08ff05-786d-49e0-8c03-0af80e36a34b.jsonl'
out_path = r'F:\嵌赛\amssb_taskbook.txt'

target = None
with open(path, 'r', encoding='utf-8', errors='replace') as f:
    for idx, line in enumerate(f, 1):
        if idx != 136844:
            continue
        obj = json.loads(line)
        def walk(o):
            global target
            if isinstance(o, str):
                if 'M29-AMSSB-WC-SC-RAW24-DISTINGUISHABILITY-AUDIT' in o and 'pasted_content' in o:
                    target = o
            elif isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(obj)

if target is None:
    sys.stderr.write('NOT FOUND\n')
    sys.exit(1)

with io.open(out_path, 'w', encoding='utf-8') as f:
    f.write(target)
print('LEN', len(target))
