#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "icraft_xir_serialize_flatbuffers" for configuration "Release"
set_property(TARGET icraft_xir_serialize_flatbuffers APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(icraft_xir_serialize_flatbuffers PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "Icraft::XIR"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libicraft_xir_serialize_flatbuffers.so"
  IMPORTED_SONAME_RELEASE "libicraft_xir_serialize_flatbuffers.so"
  )

list(APPEND _cmake_import_check_targets icraft_xir_serialize_flatbuffers )
list(APPEND _cmake_import_check_files_for_icraft_xir_serialize_flatbuffers "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libicraft_xir_serialize_flatbuffers.so" )

# Import target "Icraft::XIR" for configuration "Release"
set_property(TARGET Icraft::XIR APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(Icraft::XIR PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libicraft_xir.so"
  IMPORTED_SONAME_RELEASE "libicraft_xir.so"
  )

list(APPEND _cmake_import_check_targets Icraft::XIR )
list(APPEND _cmake_import_check_files_for_Icraft::XIR "${_IMPORT_PREFIX}/lib/aarch64-linux-gnu/libicraft_xir.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
