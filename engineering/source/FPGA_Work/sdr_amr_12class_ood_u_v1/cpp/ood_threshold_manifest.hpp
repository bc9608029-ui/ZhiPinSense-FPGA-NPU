// Read-only OOD-U threshold manifest (C++ mirror of ood_u/manifest.py).
//
// The manifest freezes the score method, temperature, threshold, label order
// and model identity used by the CPU-side rejection module.  The loader is
// fail-closed: any missing, malformed, non-finite, or contract-violating field
// throws std::runtime_error.
#ifndef OOD_U_THRESHOLD_MANIFEST_HPP
#define OOD_U_THRESHOLD_MANIFEST_HPP

#include <string>
#include <vector>

struct OodThresholdManifest {
    std::string model_name;
    std::string model_sha256;
    std::string checkpoint_sha256;
    std::string score_method;
    std::string score_direction;
    double temperature = 1.0;
    double threshold = 0.0;
    std::vector<std::string> label_order;
    bool final_test_accessed = false;
};

// Parse and validate the OOD-U manifest JSON at ``path``.
OodThresholdManifest load_ood_u_manifest(const std::string& path);

#endif  // OOD_U_THRESHOLD_MANIFEST_HPP
