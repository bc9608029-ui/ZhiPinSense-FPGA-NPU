import ctypes
import ctypes.wintypes as wt

ucrt = ctypes.CDLL('ucrtbase.dll')
ucrt.fopen.restype = ctypes.c_void_p
ucrt.fopen.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
ucrt.fclose.argtypes = [ctypes.c_void_p]
ucrt._wfopen.restype = ctypes.c_void_p
ucrt._wfopen.argtypes = [ctypes.c_wchar_p, ctypes.c_char_p]


def test(label, path, fn):
    fp = fn(path, b'rb')
    status = 'OPEN OK  fp=0x%x' % fp if fp else 'FAIL  fp=NULL'
    print('%s -> %s' % (label, status))
    if fp:
        ucrt.fclose(fp)


SYM = b'C:/Icraft/CLI/bin/poly_params.json'
VER = b'C:/Icraft/CLI v3.39.0/bin/poly_params.json'
test('ANSI fopen symlink  ', SYM, ucrt.fopen)
test('ANSI fopen versioned', VER, ucrt.fopen)
test('wide _wfopen symlink  ', SYM.decode(), ucrt._wfopen)
test('wide _wfopen versioned', VER.decode(), ucrt._wfopen)

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.CreateFileW.restype = wt.HANDLE
k32.CreateFileW.argtypes = [ctypes.c_wchar_p, wt.DWORD, wt.DWORD, ctypes.c_void_p,
                            wt.DWORD, wt.DWORD, wt.HANDLE]
k32.CloseHandle.argtypes = [wt.HANDLE]
GENERIC_READ = 0x80000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
INVALID = wt.HANDLE(-1).value


def createfile(path, share, sharename):
    h = k32.CreateFileW(path, GENERIC_READ, share, None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
    if h == INVALID:
        print('CreateFileW %s -> FAIL err=%d' % (sharename, ctypes.get_last_error()))
    else:
        print('CreateFileW %s -> OK handle=0x%x' % (sharename, h))
        k32.CloseHandle(h)


createfile(SYM.decode(), 1 | 2, 'symlink share=RW')
createfile(SYM.decode(), 1, 'symlink share=R')
createfile(VER.decode(), 1 | 2, 'versioned share=RW')
