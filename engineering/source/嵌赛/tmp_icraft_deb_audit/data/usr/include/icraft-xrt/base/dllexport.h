#pragma once

/// @cond
#ifdef _WIN32
#ifdef XRT_DLL_EXPORTS
#define XRT_DLL _declspec(dllexport)
#else
#define XRT_DLL _declspec(dllimport)
#endif
#else
#define XRT_DLL
#endif
/// @endcond