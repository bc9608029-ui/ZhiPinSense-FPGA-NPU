#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "Icraft::Utils" for configuration "Release"
set_property(TARGET Icraft::Utils APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(Icraft::Utils PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libicraft_utils.so"
  IMPORTED_SONAME_RELEASE "libicraft_utils.so"
  )

list(APPEND _cmake_import_check_targets Icraft::Utils )
list(APPEND _cmake_import_check_files_for_Icraft::Utils "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libicraft_utils.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
