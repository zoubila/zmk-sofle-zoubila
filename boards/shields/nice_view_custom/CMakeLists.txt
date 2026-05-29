if(CONFIG_ZMK_DISPLAY AND CONFIG_NICE_VIEW_WIDGET_STATUS)
  zephyr_library_include_directories(${CMAKE_SOURCE_DIR}/include)
  zephyr_library_sources(custom_status_screen.c)
  zephyr_library_sources(widgets/bolt.c)
  zephyr_library_sources(widgets/util.c)

  if(NOT CONFIG_ZMK_SPLIT OR CONFIG_ZMK_SPLIT_ROLE_CENTRAL)
    zephyr_library_sources(widgets/status.c)
  else()
    find_package(Python3 REQUIRED COMPONENTS Interpreter)

    file(GLOB NICE_VIEW_CUSTOM_IMAGES CONFIGURE_DEPENDS
      ${CMAKE_CURRENT_SOURCE_DIR}/images/*.png
    )

    set(NICE_VIEW_CUSTOM_ART_C ${CMAKE_CURRENT_BINARY_DIR}/nice_view_custom_art.c)
    set(NICE_VIEW_CUSTOM_ART_H ${CMAKE_CURRENT_BINARY_DIR}/nice_view_custom_art.h)

    execute_process(
      COMMAND
        ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/scripts/generate_art.py
        --output ${NICE_VIEW_CUSTOM_ART_C}
        --header ${NICE_VIEW_CUSTOM_ART_H}
        --images ${NICE_VIEW_CUSTOM_IMAGES}
      RESULT_VARIABLE NICE_VIEW_CUSTOM_ART_RESULT
    )

    if(NOT NICE_VIEW_CUSTOM_ART_RESULT EQUAL 0)
      message(FATAL_ERROR "Failed to generate nice_view_custom art")
    endif()

    zephyr_library_include_directories(${CMAKE_CURRENT_BINARY_DIR})
    zephyr_library_sources(${NICE_VIEW_CUSTOM_ART_C})
    zephyr_library_sources(widgets/peripheral_status.c)
  endif()
endif()
