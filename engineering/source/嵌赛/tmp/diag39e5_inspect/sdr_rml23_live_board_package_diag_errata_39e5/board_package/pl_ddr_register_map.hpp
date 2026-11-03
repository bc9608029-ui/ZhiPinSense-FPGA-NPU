#pragma once

#include <cstdint>

// Relative register contract for the PL-DDR Mandatory Core data path.
// VERIFIED against pl_ddr_mandatory_core_regs.sv (VERSION_VALUE=0x20260929).
// The absolute User_Reg base is 0x400C0000 (confirmed by the BD Address Editor
// and the board-PASS ps_pl_ctrl_smoke); it is passed at run time, not baked in.
namespace pl_ddr_regs {
constexpr std::uint32_t VERSION_VALUE = 0x20260929u;
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
