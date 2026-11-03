import ctypes
import sys

paths = [
    b'D:/icraft/bin/poly_params.json',
    b'D:\\icraft\\bin\\poly_params.json',
    b'C:/Icraft/CLI v3.39.0/bin/poly_params.json',
]


def try_fopen(libname, path_bytes):
    try:
        lib = ctypes.CDLL(libname)
        lib.fopen.restype = ctypes.c_void_p
        lib.fopen.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        fp = lib.fopen(path_bytes, b'rb')
        return ('OK fp=0x%x' % fp) if fp else 'NULL(FAIL)'
    except Exception as e:
        return 'EXC %r' % (e,)


def try_wfopen(libname, path_str):
    try:
        lib = ctypes.CDLL(libname)
        lib._wfopen.restype = ctypes.c_void_p
        lib._wfopen.argtypes = [ctypes.c_wchar_p, ctypes.c_char_p]
        fp = lib._wfopen(path_str, b'rb')
        return ('OK fp=0x%x' % fp) if fp else 'NULL(FAIL)'
    except Exception as e:
        return 'EXC %r' % (e,)


print('Python version:', sys.version)
for p in paths:
    print('--- path bytes %r ---' % p)
    print('  msvcrt.dll  fopen :', try_fopen('msvcrt.dll', p))
    print('  ucrtbase    fopen :', try_fopen('ucrtbase.dll', p))
    print('  ucrtbase   _wfopen:', try_wfopen('ucrtbase.dll', p.decode('ascii')))
print('DONE')
