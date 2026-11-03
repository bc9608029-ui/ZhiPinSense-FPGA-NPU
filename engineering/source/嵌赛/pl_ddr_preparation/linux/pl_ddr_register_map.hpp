#pragma once

#include <cstdint>

// Proposed relative register contract for the future PL-DDR integration.
// The absolute User_Reg base must be taken from the integrated BD Address
// Editor; it is intentionally not defined here.
namespace pl_ddr_regs {
constexpr std::uint64_t VERSION = 0x00;
constexpr std::uint64_t CONTROL = 0x04;
constexpr std::uint64_t STATUS = 0x08;
constexpr std::uint64_t IQ_BASE = 0x0c;
constexpr std::uint64_t IQ_BYTES = 0x10;
constexpr std::uint64_t TENSOR_BASE = 0x14;
constexpr std::uint64_t TENSOR_BYTES = 0x18;
constexpr std::uint64_t FRAME_COUNT = 0x1c;
constexpr std::uint64_t IQ_ACCEPTED = 0x20;
constexpr std::uint64_t TENSOR_ACCEPTED = 0x24;
constexpr std::uint64_t ERROR_CODE = 0x28;

constexpr std::uint32_t CONTROL_START = 1u << 0;
constexpr std::uint32_t CONTROL_CLEAR = 1u << 1;
constexpr std::uint32_t STATUS_BUSY = 1u << 0;
constexpr std::uint32_t STATUS_DONE = 1u << 1;
constexpr std::uint32_t STATUS_ERROR = 1u << 2;
}  // namespace pl_ddr_regs
