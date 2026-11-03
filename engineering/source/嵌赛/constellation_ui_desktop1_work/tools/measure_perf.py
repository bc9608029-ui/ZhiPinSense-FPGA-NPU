#!/usr/bin/env python3
# measure_perf.py -- sample the running constellation_viewer's CPU% and RSS over
# time (honest desktop measurement; NOT board performance).
#
#   python3 measure_perf.py --seconds 60 --interval 2 -- <gui args...>
import argparse
import subprocess
import sys
import time


def read_rss_kb(pid):
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except OSError:
        return 0
    return 0


def read_cpu_jiffies(pid):
    try:
        with open(f"/proc/{pid}/stat") as f:
            parts = f.read().split()
        # fields 14,15 (1-based) are utime, stime
        return int(parts[13]) + int(parts[14])
    except (OSError, IndexError, ValueError):
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--settle", type=float, default=2.0)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    cmd = args.cmd
    if cmd and cmd[0] == "--":  # argparse.REMAINDER keeps the "--" separator
        cmd = cmd[1:]
    if not cmd:
        print("no command given after --", file=sys.stderr)
        return 2

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    pid = proc.pid
    try:
        time.sleep(args.settle)
        hz = 100  # Linux USER_HZ on this kernel; used only for CPU% scaling
        cpu_prev = read_cpu_jiffies(pid)
        samples = []
        t0 = time.time()
        while time.time() - t0 < args.seconds:
            time.sleep(args.interval)
            if proc.poll() is not None:
                print(f"GUI_EXITED rc={proc.returncode} at t={time.time()-t0:.1f}s")
                break
            cpu_now = read_cpu_jiffies(pid)
            rss = read_rss_kb(pid)
            dcpu = cpu_now - cpu_prev
            cpu_prev = cpu_now
            cpu_pct = dcpu / (args.interval * hz) * 100.0
            samples.append((cpu_pct, rss))
            print(f"t={time.time()-t0:6.1f}s cpu={cpu_pct:6.2f}% rss={rss:8d} kB")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    if not samples:
        print("SUMMARY: no samples")
        return 1
    cpus = [s[0] for s in samples]
    rsss = [s[1] for s in samples]
    print("SUMMARY samples=%d cpu_avg=%.2f%% cpu_max=%.2f%% | "
          "rss_min=%d rss_avg=%d rss_max=%d kB growth=%+d kB" %
          (len(samples), sum(cpus)/len(cpus), max(cpus),
           min(rsss), sum(rsss)//len(rsss), max(rsss), max(rsss)-min(rsss)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
