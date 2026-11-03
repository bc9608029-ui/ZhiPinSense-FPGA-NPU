#pragma once
#include "result_frame_v2_parse.hpp"
namespace ui { inline ParseOutcome parse_result_frame_rml24(const std::string& line) { ParseOutcome o; detail::JsonReader r(line); o.ok=r.parse_record_rml24(o.frame,o.error); return o; } }
