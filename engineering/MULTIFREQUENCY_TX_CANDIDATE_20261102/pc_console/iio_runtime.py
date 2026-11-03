"""Select a compatible libiio for child processes; never create an IIO context."""
import ctypes
import os
from pathlib import Path

REQUIRED = ('iio_create_context_from_uri', 'iio_context_destroy', 'iio_context_set_timeout',
            'iio_context_find_device', 'iio_device_find_channel', 'iio_channel_attr_read',
            'iio_channel_attr_write', 'iio_channel_enable', 'iio_channel_disable',
            'iio_channel_is_enabled', 'iio_device_create_buffer', 'iio_buffer_destroy',
            'iio_buffer_start', 'iio_buffer_end', 'iio_buffer_step', 'iio_buffer_push',
            'iio_buffer_refill', 'iio_create_scan_context', 'iio_scan_context_get_info_list',
            'iio_context_info_get_uri', 'iio_context_info_list_free', 'iio_scan_context_destroy')
_handles = []


def resolve(interpreter):
    home = Path(interpreter).resolve().parent
    candidates = []
    if os.environ.get('LIBIIO_LIBRARY'): candidates.append(Path(os.environ['LIBIIO_LIBRARY']))
    candidates += [home / 'Library/bin/libiio.dll', home / 'libiio.dll',
                   Path('D:/radioconda/Library/bin/libiio.dll'),
                   Path('D:/Miniconda3/Library/bin/libiio.dll'),
                   Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/libiio.dll']
    problems = []; seen = set()
    for path in candidates:
        key = str(path).lower()
        if key in seen or not path.is_file(): continue
        seen.add(key)
        try:
            if hasattr(os, 'add_dll_directory'): _handles.append(os.add_dll_directory(str(path.parent)))
            library = ctypes.CDLL(str(path))
            missing = [n for n in REQUIRED if not hasattr(library, n)]
            if missing: problems.append(str(path) + ': missing ' + missing[0]); continue
            return path.resolve()
        except (OSError, AttributeError) as exc: problems.append(str(path) + ': ' + str(exc))
    raise RuntimeError('未找到兼容libiio 0.x DLL（需要22项接口）。' + '; '.join(problems))


def environment(interpreter, hardware):
    updates = dict(PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    if hardware and os.name == 'nt':
        path = resolve(interpreter)
        updates['LIBIIO_LIBRARY'] = str(path)
        updates['PATH'] = str(path.parent) + os.pathsep + os.environ.get('PATH', '')
    return updates
