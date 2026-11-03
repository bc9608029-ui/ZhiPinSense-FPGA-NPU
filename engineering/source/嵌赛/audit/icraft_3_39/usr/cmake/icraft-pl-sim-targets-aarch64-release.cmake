#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "icraft_pl_sim" for configuration "Release"
set_property(TARGET icraft_pl_sim APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(icraft_pl_sim PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libicraft_pl_sim.so"
  IMPORTED_SONAME_RELEASE "libicraft_pl_sim.so"
  )

list(APPEND _cmake_import_check_targets icraft_pl_sim )
list(APPEND _cmake_import_check_files_for_icraft_pl_sim "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libicraft_pl_sim.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
