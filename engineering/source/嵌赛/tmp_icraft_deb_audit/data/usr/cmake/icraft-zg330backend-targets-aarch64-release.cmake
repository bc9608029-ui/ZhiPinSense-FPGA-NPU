#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "Icraft::ZG330Backend" for configuration "Release"
set_property(TARGET Icraft::ZG330Backend APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(Icraft::ZG330Backend PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libicraft_zg330backend.so"
  IMPORTED_SONAME_RELEASE "libicraft_zg330backend.so"
  )

list(APPEND _cmake_import_check_targets Icraft::ZG330Backend )
list(APPEND _cmake_import_check_files_for_Icraft::ZG330Backend "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libicraft_zg330backend.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
