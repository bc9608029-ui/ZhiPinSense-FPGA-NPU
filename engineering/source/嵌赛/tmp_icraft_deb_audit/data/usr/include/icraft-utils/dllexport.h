#pragma once

/// @cond
#ifdef _WIN32
#ifdef UTILS_DLL_EXPORTS
#define UTILS_DLL _declspec(dllexport)
#else
#define UTILS_DLL _declspec(dllimport)
#endif
#else
#define UTILS_DLL
#endif
/// @endcond