import os, sys

# Register every libiio build dir so ctypes / LoadLibrary can resolve libiio.dll
# and its dependency DLLs (libusb-1.0, libxml2, libserialport, zstd, msvc runtime).
candidates = [
    r"F:\FPGA_Work\pluto_tools\libiio\Windows-VS-2022-x64\Release",
    r"F:\FPGA_Work\pluto_tools\libiio\Windows-MinGW-W64",
]
for d in candidates:
    if os.path.isdir(d):
        os.add_dll_directory(d)
        os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]

try:
    import iio
    print("iio import OK, version:", iio.version[0], iio.version[1])
except Exception as e:
    print("iio import FAIL:", type(e).__name__, "-", e)
    sys.exit(1)

try:
    import adi
    print("adi import OK, pyadi-iio", adi.__version__)
except Exception as e:
    print("adi import FAIL:", type(e).__name__, "-", e)
    sys.exit(1)

print("ALL IMPORTS OK")
