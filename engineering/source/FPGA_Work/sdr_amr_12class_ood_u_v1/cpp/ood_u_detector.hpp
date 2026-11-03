// CPU-side OOD-U rejection module (C++ mirror of ood/scores.py).
//
// Given the raw 12-d fp32 logits from the NPU (no softmax), compute the frozen
// OOD score and compare it to the frozen threshold.  ``known == false`` means
// the frame is rejected as UNKNOWN.  The score computation matches
// ood/scores.py exactly (MSP / Entropy / MaxLogit / LogitMargin / Energy, all
// "higher = more OOD").
#ifndef OOD_U_DETECTOR_HPP
#define OOD_U_DETECTOR_HPP

#include <string>

#include "ood_threshold_manifest.hpp"

struct OodDecision {
    bool known = false;         // true = accept as a known class; false = UNKNOWN
    bool valid = false;         // false only for ERROR (non-finite logits)
    int class_index = -1;       // argmax 0..11 (meaningful only when known)
    double score = 0.0;         // OOD anomaly score (higher = more OOD)
    double threshold = 0.0;     // frozen threshold
    std::string score_method;   // frozen score method name
    std::string class_name;     // "UNKNOWN" / "NO_SIGNAL" / "ERROR" / known class
};

class OodUDetector {
public:
    explicit OodUDetector(const OodThresholdManifest& manifest);

    // Compute the OOD score for one 12-d raw logit vector.  Throws on wrong dim.
    double score(const double* logits, int dim) const;

    // Classify or reject one 12-d raw logit vector.  Non-finite logits produce
    // an ERROR decision (valid=false), never a silent UNKNOWN.
    OodDecision classify_or_reject(const double* logits, int dim) const;

    // Static decision builders for the distinct non-class states.
    static OodDecision no_signal();
    static OodDecision error(const std::string& score_method, double threshold);

    const std::string& score_method() const { return manifest_.score_method; }
    double threshold() const { return manifest_.threshold; }

private:
    OodThresholdManifest manifest_;
};

#endif  // OOD_U_DETECTOR_HPP
