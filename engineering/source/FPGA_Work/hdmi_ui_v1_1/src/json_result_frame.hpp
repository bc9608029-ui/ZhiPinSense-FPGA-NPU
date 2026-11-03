#pragma once
// JSON-Lines <-> ResultFrame conversion.  The only Qt-dependent part of the
// contract layer (uses QJsonDocument, available in Qt 5 and 6).
//
// The parser accepts two shapes and normalises both into ResultFrame:
//   * V1.1: contract_version / model_id / class_names / scores /
//           predicted_index / predicted_class;
//   * V1  (legacy replay): schema_version / class_id / class_name /
//           probabilities over the frozen 8-class order.
#include <QByteArray>
#include <optional>
#include <string>

#include "contracts/result_frame.hpp"

namespace hdmiui {

// Parse one JSON object (a single line) into a ResultFrame.  Returns
// std::nullopt and sets *error on malformed JSON or a failed validate().
std::optional<ResultFrame> parse_result_frame(const QByteArray& line, std::string* error);

// Serialize a ResultFrame as one compact V1.1 JSON object (no trailing newline).
QByteArray to_json(const ResultFrame& f);

}  // namespace hdmiui
