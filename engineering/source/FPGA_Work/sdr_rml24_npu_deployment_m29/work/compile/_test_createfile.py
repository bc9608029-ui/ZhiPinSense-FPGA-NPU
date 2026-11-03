import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

CreateFileA = kernel32.CreateFileA
CreateFileA.restype = wintypes.HANDLE
CreateFileA.argtypes = [ctypes.c_char_p, wintypes.DWORD, wintypes.DWORD,
                        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]

CreateFileW = kernel32.CreateFileW
CreateFileW.restype = wintypes.HANDLE
CreateFileW.argtypes = [ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD,
                        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]

CloseHandle = kernel32.CloseHandle

GENERIC_READ = 0x80000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value


def errname(code):
    names = {
        2: 'ERROR_FILE_NOT_FOUND', 3: 'ERROR_PATH_NOT_FOUND',
        5: 'ERROR_ACCESS_DENIED', 32: 'ERROR_SHARING_VIOLATION',
        33: 'ERROR_LOCK_VIOLATION', 4: 'ERROR_TOO_MANY_OPEN_FILES',
        87: 'ERROR_INVALID_PARAMETER', 123: 'ERROR_INVALID_NAME',
        206: 'ERROR_FILENAME_EXCED_RANGE', 1114: 'ERROR_DLL_INIT_FAILED',
        1920: 'ERROR_CANT_ACCESS_FILE',
    }
    return names.get(code, str(code))


def test_createfile(what, fn, path):
    for share in (1, 3, 0):  # READ, READ|WRITE, NONE
        ctypes.set_last_error(0)
        h = fn(path, GENERIC_READ, share, None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
        if h == INVALID_HANDLE_VALUE:
            e = ctypes.get_last_error()
            print('  %-10s share=%-2d -> FAIL GetLastError=%d (%s)' % (what, share, e, errname(e)))
        else:
            print('  %-10s share=%-2d -> SUCCESS handle=0x%x' % (what, share, h))
            CloseHandle(h)


print('=== ANSI CreateFileA (fopen 内部等价) ===')
for p in (b'D:\\icraft\\bin\\poly_params.json', b'C:\\Icraft\\CLI v3.39.0\\bin\\poly_params.json'):
    print(' path:', p)
    test_createfile('CreateFileA', CreateFileA, p)

print('=== WIDE CreateFileW (Python open 内部等价) ===')
for p in ('D:\\icraft\\bin\\poly_params.json', 'C:\\Icraft\\CLI v3.39.0\\bin\\poly_params.json'):
    print(' path:', p)
    test_createfile('CreateFileW', CreateFileW, p)

print('DONE')
