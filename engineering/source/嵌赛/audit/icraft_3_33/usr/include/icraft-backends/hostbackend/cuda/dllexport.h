#pragma once

/// @cond
#ifdef _WIN32
#ifdef  CUDADEV_DLL_EXPORTS
#define CUDADEV_DLL _declspec(dllexport)
#else
#define CUDADEV_DLL _declspec(dllimport)
#endif
#else
#define CUDADEV_DLL
#endif
/// @endcond