#include "ood_threshold_manifest.hpp"

#include <cmath>
#include <fstream>
#include <sstream>
#include <stdexcept>

#include "minijson.hpp"
#include "ood_u_contract.hpp"

namespace {

bool is_sha256(const std::string& s) {
    if (s.size() != 64) return false;
    for (char c : s) {
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    }
    return true;
}

bool is_finite(double v) { return std::isfinite(v); }

}  // namespace

OodThresholdManifest load_ood_u_manifest(const std::string& path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("OOD-U manifest not found: " + path);
    std::ostringstream buf;
    buf << in.rdbuf();
    if (in.bad()) throw std::runtime_error("OOD-U manifest read error: " + path);

    minijson::Value root;
    try {
        root = minijson::parse(buf.str());
    } catch (const std::exception& e) {
        throw std::runtime_error("OOD-U manifest is not valid JSON: " + path + " (" + e.what() + ")");
    }

    OodThresholdManifest m;
    m.model_name = root.at("model_name").as_string();
    m.model_sha256 = root.at("model_sha256").as_string();
    m.checkpoint_sha256 = root.at("checkpoint_sha256").as_string();
    m.score_method = root.at("score_method").as_string();
    m.score_direction = root.at("score_direction").as_string();
    m.temperature = root.at("temperature").as_double();
    m.threshold = root.at("threshold").as_double();
    m.final_test_accessed = root.at("final_test_accessed").as_bool();

    for (const auto& name : root.at("label_order").as_array()) {
        m.label_order.push_back(name.as_string());
    }

    // Fail-closed validation against the frozen contract.
    if (m.model_name != ood_u_contract::MODEL_NAME) {
        throw std::runtime_error("OOD-U manifest model_name mismatch");
    }
    if (m.model_sha256 != ood_u_contract::MODEL_SHA256) {
        throw std::runtime_error("OOD-U manifest model_sha256 does not match the frozen NPU model");
    }
    if (!is_sha256(m.checkpoint_sha256)) {
        throw std::runtime_error("OOD-U manifest checkpoint_sha256 is not a valid SHA-256");
    }
    if (m.score_direction != ood_u_contract::DIRECTION) {
        throw std::runtime_error("OOD-U manifest score_direction must be higher_is_ood");
    }
    bool known_method = false;
    for (const auto& s : ood_u_contract::SCORE_METHODS) {
        if (s == m.score_method) known_method = true;
    }
    if (!known_method) {
        throw std::runtime_error("OOD-U manifest score_method is not one of the five frozen methods");
    }
    if (!is_finite(m.temperature) || m.temperature <= 0.0) {
        throw std::runtime_error("OOD-U manifest temperature must be finite and positive");
    }
    if (!is_finite(m.threshold)) {
        throw std::runtime_error("OOD-U manifest threshold is non-finite");
    }
    if (m.label_order.size() != ood_u_contract::LABEL_ORDER_12.size()) {
        throw std::runtime_error("OOD-U manifest label_order size is not 12");
    }
    for (std::size_t i = 0; i < m.label_order.size(); ++i) {
        if (m.label_order[i] != ood_u_contract::LABEL_ORDER_12[i]) {
            throw std::runtime_error("OOD-U manifest label_order does not match the frozen 12-class order");
        }
    }
    if (m.final_test_accessed) {
        throw std::runtime_error("OOD-U manifest final_test_accessed is true; the blind test already ran");
    }

    return m;
}
