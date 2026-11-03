#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "Icraft::HostBackend" for configuration "Release"
set_property(TARGET Icraft::HostBackend APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(Icraft::HostBackend PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libicraft_hostbackend.so"
  IMPORTED_SONAME_RELEASE "libicraft_hostbackend.so"
  )

list(APPEND _cmake_import_check_targets Icraft::HostBackend )
list(APPEND _cmake_import_check_files_for_Icraft::HostBackend "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libicraft_hostbackend.so" )

# Import target "Icraft::CudaDefault" for configuration "Release"
set_property(TARGET Icraft::CudaDefault APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(Icraft::CudaDefault PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libcudadefault.so"
  IMPORTED_SONAME_RELEASE "libcudadefault.so"
  )

list(APPEND _cmake_import_check_targets Icraft::CudaDefault )
list(APPEND _cmake_import_check_files_for_Icraft::CudaDefault "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libcudadefault.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
