import tarfile, os, sys, json, hashlib

ARCHIVE = r"F:/嵌赛/board_capture/rml24_rx_diagnostics_full_1773379631.tar.gz"
DEST = r"F:/嵌赛/fix10class24_rxresidual_audit1_work/board_capture_extracted"

def is_safe_member(m):
    name = m.name
    # absolute / drive-letter / backslash forms
    if name.startswith("/") or name.startswith("\\"):
        return False
    if len(name) >= 2 and name[1] == ":":
        return False
    parts = name.replace("\\", "/").split("/")
    if any(p == ".." for p in parts):
        return False
    if m.issym() or m.islnk():
        return False
    return True

def dest_path(m, dest):
    return os.path.normpath(os.path.join(dest, m.name.replace("\\", "/")))

tf = tarfile.open(ARCHIVE, "r:gz")
members = tf.getmembers()
bad = [m.name for m in members if not is_safe_member(m)]
if bad:
    print("UNSAFE MEMBERS:", bad)
    sys.exit(1)

# verify no member escapes dest
dest_abs = os.path.abspath(DEST)
for m in members:
    if m.isdir():
        continue
    p = dest_path(m, DEST)
    if not os.path.abspath(p).startswith(dest_abs + os.sep):
        print("ESCAPE:", m.name, p)
        sys.exit(1)

tf.extractall(DEST, members=[m for m in members if not m.isdir()])
# dirs
for m in members:
    if m.isdir():
        p = dest_path(m, DEST)
        os.makedirs(p, exist_ok=True)
print("EXTRACTED", len(members), "members to", DEST)
