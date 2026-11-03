#pragma once

/// @cond
#ifdef _WIN32
#ifdef  HOSTBKND_DLL_EXPORTS
#define HOSTBKND_DLL _declspec(dllexport)
#else
#define HOSTBKND_DLL _declspec(dllimport)
#endif
#else
#define HOSTBKND_DLL
#endif
/// @endcond