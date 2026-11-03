#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "Fireby-NNX" for configuration "Release"
set_property(TARGET Fireby-NNX APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(Fireby-NNX PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libFireby-NNX.so"
  IMPORTED_SONAME_RELEASE "libFireby-NNX.so"
  )

list(APPEND _cmake_import_check_targets Fireby-NNX )
list(APPEND _cmake_import_check_files_for_Fireby-NNX "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libFireby-NNX.so" )

# Import target "Fireby-Easy" for configuration "Release"
set_property(TARGET Fireby-Easy APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(Fireby-Easy PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libFireby-Easy.so"
  IMPORTED_SONAME_RELEASE "libFireby-Easy.so"
  )

list(APPEND _cmake_import_check_targets Fireby-Easy )
list(APPEND _cmake_import_check_files_for_Fireby-Easy "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libFireby-Easy.so" )

# Import target "icraft_buyi_sim" for configuration "Release"
set_property(TARGET icraft_buyi_sim APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(icraft_buyi_sim PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libicraft_buyi_sim.so"
  IMPORTED_SONAME_RELEASE "libicraft_buyi_sim.so"
  )

list(APPEND _cmake_import_check_targets icraft_buyi_sim )
list(APPEND _cmake_import_check_files_for_icraft_buyi_sim "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libicraft_buyi_sim.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
