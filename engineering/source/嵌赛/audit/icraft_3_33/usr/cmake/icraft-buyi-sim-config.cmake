
####### Expanded from @PACKAGE_INIT@ by configure_package_config_file() #######
####### Any changes to this file will be overwritten by the next CMake run ####
####### The input file was icraft-buyi-sim-config.cmake.in                            ########

get_filename_component(PACKAGE_PREFIX_DIR "${CMAKE_CURRENT_LIST_DIR}/../" ABSOLUTE)

macro(set_and_check _var _file)
  set(${_var} "${_file}")
  if(NOT EXISTS "${_file}")
    message(FATAL_ERROR "File or directory ${_file} referenced by variable ${_var} does not exist !")
  endif()
endmacro()

macro(check_required_components _NAME)
  foreach(comp ${${_NAME}_FIND_COMPONENTS})
    if(NOT ${_NAME}_${comp}_FOUND)
      if(${_NAME}_FIND_REQUIRED_${comp})
        set(${_NAME}_FOUND FALSE)
      endif()
    endif()
  endforeach()
endmacro()

####################################################################################

if (NOT TARGET icraft::bysim)
	if(UNIX)
		if(CMAKE_C_COMPILER_ID STREQUAL "GNU" AND CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64")
			include(${CMAKE_CURRENT_LIST_DIR}/icraft-buyi-sim-targets-aarch64.cmake)
		else()
			include(${CMAKE_CURRENT_LIST_DIR}/icraft-buyi-sim-targets-x64.cmake)
		endif()
	else()
		include(${CMAKE_CURRENT_LIST_DIR}/icraft-buyi-sim-targets-win.cmake)
	endif()
endif()
