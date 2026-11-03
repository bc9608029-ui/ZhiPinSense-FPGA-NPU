import os, sys

# Same DLL registration as test_import.py
candidates = [
    r"F:\FPGA_Work\pluto_tools\libiio\Windows-VS-2022-x64\Release",
    r"F:\FPGA_Work\pluto_tools\libiio\Windows-MinGW-W64",
]
for d in candidates:
    if os.path.isdir(d):
        os.add_dll_directory(d)
        os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]

import iio

print("=== step 1: scan for IIO contexts (how Windows sees the Pluto) ===")
try:
    ctxs = iio.scan_contexts()
except Exception as e:
    print("scan failed:", type(e).__name__, "-", e)
    ctxs = []

if not ctxs:
    print("NO IIO CONTEXT FOUND -> Pluto 没被识别。排查：")
    print("  1. Pluto 的 USB 是否插到这台电脑；")
    print("  2. 驱动是否装好（出厂固件会枚举成 RNDIS 网卡，电脑应多出一个网络适配器，")
    print("     默认可 ping 通 192.168.2.1；若走 libusb 后端则需 WinUSB 驱动）。")
    sys.exit(2)

for uri, desc in ctxs:
    print(f"  uri={uri!r}  desc={desc!r}")

print("\n=== step 2: connect + read RX/TX attributes ===")
sdr = None
for uri, desc in ctxs:
    try:
        import adi
        sdr = adi.Pluto(uri)
        # force a real connection by touching a property
        _ = sdr.sample_rate
        print(f"CONNECTED via {uri!r}")
        break
    except Exception as e:
        print(f"  uri={uri!r} connect failed: {type(e).__name__}: {e}")
        sdr = None

if sdr is None:
    print("\nAll contexts failed to connect.")
    sys.exit(3)

print("  sample_rate            :", sdr.sample_rate)
print("  rx_lo                  :", sdr.rx_lo)
print("  tx_lo                  :", sdr.tx_lo)
print("  rx_rf_bandwidth        :", sdr.rx_rf_bandwidth)
print("  tx_rf_bandwidth        :", sdr.tx_rf_bandwidth)
print("  rx_hardwaregain_chan0  :", sdr.rx_hardwaregain_chan0)
print("  tx_hardwaregain_chan0  :", sdr.tx_hardwaregain_chan0)
print("  gain_control_mode_chan0:", sdr.gain_control_mode_chan0)
print("  tx buffer size         :", sdr.tx_buffer_size)
print("  rx buffer size         :", sdr.rx_buffer_size)
print("\nPROBE OK — 电脑已能控制这块 Pluto 的收发属性。")
