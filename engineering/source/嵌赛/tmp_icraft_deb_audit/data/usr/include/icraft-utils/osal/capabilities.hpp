#pragma once

namespace icraft::osal {

struct CapabilitySet {
    bool has_filesystem = false;
    bool has_directory_iteration = false;
    bool has_dynamic_module = false;
    bool has_env_var = false;
    bool has_process_info = false;
    bool has_console_ansi = false;
    bool has_console_utf8 = false;
    bool has_real_file_view = false;
    bool has_file_view_writeback = false;
};

namespace detail {

#if defined(_BAREME)
inline constexpr CapabilitySet kCapabilities{
    true,
    true,
    false,
    false,
    false,
    false,
    false,
    false,
    true,
};
#elif defined(_FREERTOS)
inline constexpr CapabilitySet kCapabilities{
    true,
    true,
    false,
    false,
    false,
    false,
    false,
    false,
    true,
};
#elif defined(_REWORKS)
inline constexpr CapabilitySet kCapabilities{
    true,
    true,
    false,
    true,
    true,
    false,
    false,
    false,
    true,
};
#elif defined(_ACOREOS)
inline constexpr CapabilitySet kCapabilities{
    true,
    true,
    false,
    false,
    false,
    false,
    false,
    false,
    true,
};
#elif defined(_SYLIXOS)
inline constexpr CapabilitySet kCapabilities{
    true,
    true,
    false,
    true,
    true,
    false,
    false,
    false,
    true,
};
#else
inline constexpr CapabilitySet kCapabilities{
    true,
    true,
    true,
    true,
    true,
    true,
    true,
    true,
    true,
};
#endif

}  // namespace detail

inline const CapabilitySet& capabilities() noexcept {
    return detail::kCapabilities;
}

}  // namespace icraft::osal
