#include "ood_u_detector.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

#include "ood_u_contract.hpp"

namespace {

constexpr double LOG_EPS = 1e-12;

void softmax(const double* logits, int dim, double* probs) {
    double maximum = logits[0];
    for (int i = 1; i < dim; ++i) maximum = std::max(maximum, logits[i]);
    double sum = 0.0;
    for (int i = 0; i < dim; ++i) {
        probs[i] = std::exp(logits[i] - maximum);
        sum += probs[i];
    }
    for (int i = 0; i < dim; ++i) probs[i] /= sum;
}

double msp_score(const double* logits, int dim) {
    double probs[ood_u_contract::OUTPUT_DIM];
    softmax(logits, dim, probs);
    double max_prob = probs[0];
    for (int i = 1; i < dim; ++i) max_prob = std::max(max_prob, probs[i]);
    return 1.0 - max_prob;
}

double entropy_score(const double* logits, int dim) {
    double probs[ood_u_contract::OUTPUT_DIM];
    softmax(logits, dim, probs);
    double entropy = 0.0;
    for (int i = 0; i < dim; ++i) {
        if (probs[i] > 0.0) entropy -= probs[i] * std::log(std::max(probs[i], LOG_EPS));
    }
    return entropy;
}

double max_logit_score(const double* logits, int dim) {
    double maximum = logits[0];
    for (int i = 1; i < dim; ++i) maximum = std::max(maximum, logits[i]);
    return -maximum;
}

double logit_margin_score(const double* logits, int dim) {
    double top1 = logits[0];
    double top2 = -std::numeric_limits<double>::infinity();
    for (int i = 1; i < dim; ++i) {
        if (logits[i] >= top1) {
            top2 = top1;
            top1 = logits[i];
        } else if (logits[i] > top2) {
            top2 = logits[i];
        }
    }
    return -(top1 - top2);
}

double energy_score(const double* logits, int dim, double temperature) {
    double scaled[ood_u_contract::OUTPUT_DIM];
    double maximum = logits[0] / temperature;
    for (int i = 0; i < dim; ++i) {
        scaled[i] = logits[i] / temperature;
        maximum = std::max(maximum, scaled[i]);
    }
    double sum = 0.0;
    for (int i = 0; i < dim; ++i) sum += std::exp(scaled[i] - maximum);
    double logsumexp = maximum + std::log(sum);
    return -temperature * logsumexp;
}

bool all_finite(const double* logits, int dim) {
    for (int i = 0; i < dim; ++i) {
        if (!std::isfinite(logits[i])) return false;
    }
    return true;
}

}  // namespace

OodUDetector::OodUDetector(const OodThresholdManifest& manifest) : manifest_(manifest) {}

double OodUDetector::score(const double* logits, int dim) const {
    if (dim != ood_u_contract::OUTPUT_DIM) {
        throw std::invalid_argument("OOD-U score requires 12-d raw logits");
    }
    if (!all_finite(logits, dim)) {
        throw std::invalid_argument("OOD-U score got non-finite logits");
    }
    const std::string& m = manifest_.score_method;
    if (m == "msp") return msp_score(logits, dim);
    if (m == "entropy") return entropy_score(logits, dim);
    if (m == "max_logit") return max_logit_score(logits, dim);
    if (m == "logit_margin") return logit_margin_score(logits, dim);
    if (m == "energy") return energy_score(logits, dim, manifest_.temperature);
    throw std::runtime_error("unknown OOD-U score method: " + m);
}

OodDecision OodUDetector::classify_or_reject(const double* logits, int dim) const {
    if (dim != ood_u_contract::OUTPUT_DIM) {
        return error(manifest_.score_method, manifest_.threshold);
    }
    if (!all_finite(logits, dim)) {
        return error(manifest_.score_method, manifest_.threshold);
    }

    OodDecision d;
    d.valid = true;
    d.score_method = manifest_.score_method;
    d.threshold = manifest_.threshold;
    d.score = score(logits, dim);

    int argmax = 0;
    for (int i = 1; i < dim; ++i) {
        if (logits[i] > logits[argmax]) argmax = i;
    }

    if (d.score > manifest_.threshold) {
        d.known = false;
        d.class_index = -1;
        d.class_name = ood_u_contract::UNKNOWN;
    } else {
        d.known = true;
        d.class_index = argmax;
        d.class_name = manifest_.label_order[static_cast<std::size_t>(argmax)];
    }
    return d;
}

OodDecision OodUDetector::no_signal() {
    OodDecision d;
    d.known = false;
    d.valid = false;
    d.class_index = -1;
    d.class_name = ood_u_contract::NO_SIGNAL;
    return d;
}

OodDecision OodUDetector::error(const std::string& score_method, double threshold) {
    OodDecision d;
    d.known = false;
    d.valid = false;
    d.class_index = -1;
    d.score_method = score_method;
    d.threshold = threshold;
    d.class_name = ood_u_contract::ERROR;
    return d;
}
