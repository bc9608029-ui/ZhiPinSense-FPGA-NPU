#pragma once

/// @cond
#ifdef _WIN32
#ifdef XIR_DLL_EXPORTS
#define XIR_DLL _declspec(dllexport)
#else
#define XIR_DLL _declspec(dllimport)
#endif
#else
#define XIR_DLL
#endif
/// @endcond
