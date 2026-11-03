#pragma once

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <vector>

namespace icraft {
namespace hostbackend {
namespace common {

enum class StorageType {
	kSInt8,
	kUInt8,
	kSInt16,
	kUInt16,
	kSInt32,
	kUInt32,
	kSInt64,
	kUInt64,
	kFloat16,
	kBFloat16,
	kFloat32,
	kFloat64
};

enum class InvalidValue {
	kZero,
	kOmitted
};

enum class RoundingMode {
	kNearestEven,
	kHalfAwayFromZero,
	kHalfUp
};

enum class UnaryKind {
	kIdentity,
	kAbs,
	kAcos,
	kAcosh,
	kAsin,
	kAsinh,
	kAtan,
	kAtanh,
	kCos,
	kCosh,
	kDivideScalar,
	kElu,
	kGelu,
	kHardSigmoid,
	kHardShrink,
	kHardSwish,
	kHardTanh,
	kLog,
	kLogSigmoid,
	kMish,
	kNeg,
	kNot,
	kRelu,
	kSigmoid,
	kSilu,
	kSin,
	kSinh,
	kSoftplus,
	kSoftshrink,
	kSoftsign,
	kSqrt,
	kTan,
	kTanh,
	kTanhShrink
};

struct UnarySpec {
	UnaryKind kind;
	double alpha;
	double beta;
	double minimum;
	double maximum;
	double threshold;

	explicit UnarySpec(UnaryKind unary_kind)
		: kind(unary_kind),
		  alpha(0.0),
		  beta(0.0),
		  minimum(0.0),
		  maximum(0.0),
		  threshold(0.0) {}
};

enum class BinaryKind {
	kAdd,
	kDivide,
	kEqual,
	kGreater,
	kGreaterEqual,
	kLess,
	kLessEqual,
	kMaximum,
	kMinimum,
	kMultiply,
	kNotEqual,
	kPow
};

struct BinarySpec {
	BinaryKind kind;
	std::vector<double> lhs_coefficients;
	std::vector<double> rhs_coefficients;
	char coefficient_axis;

	explicit BinarySpec(BinaryKind binary_kind)
		: kind(binary_kind), coefficient_axis('C') {
		lhs_coefficients.push_back(1.0);
		rhs_coefficients.push_back(1.0);
	}
};

enum class ReductionKind {
	kSum,
	kMean,
	kMaximum,
	kMinimum,
	kArgMaximum,
	kArgMinimum
};

struct ReductionSpec {
	ReductionKind kind;
	std::vector<int64_t> axes;
	bool keep_dimensions;

	explicit ReductionSpec(ReductionKind reduction_kind)
		: kind(reduction_kind), keep_dimensions(false) {}
};

enum class PoolKind {
	kMaximum,
	kAverage
};

struct PoolSpec {
	PoolKind kind;
	std::vector<int64_t> kernel;
	std::vector<int64_t> stride;
	std::vector<int64_t> pad_before;
	std::vector<int64_t> pad_after;
	std::vector<int64_t> dilation;
	bool count_include_pad;
	int64_t divisor_override;

	explicit PoolSpec(PoolKind pool_kind)
		: kind(pool_kind),
		  count_include_pad(false),
		  divisor_override(0) {}
};

enum class PaddingKind {
	kZeros,
	kReflect,
	kReplicate,
	kCircular
};

enum class PadKind {
	kConstant,
	kReflection,
	kReplication,
	kSymmetric
};

enum class ResizeKind {
	kNearest,
	kLinear,
	kCubic
};

enum class ScatterReduction {
	kNone,
	kAdd,
	kMultiply,
	kMaximum,
	kMinimum
};

struct ConvSpec {
	std::vector<int64_t> stride;
	std::vector<int64_t> pad_before;
	std::vector<int64_t> pad_after;
	std::vector<int64_t> dilation;
	int64_t groups;
	PaddingKind padding;

	ConvSpec()
		: groups(1),
		  padding(PaddingKind::kZeros) {}
};

struct ConvTransposeSpec {
	std::vector<int64_t> stride;
	std::vector<int64_t> pad_before;
	std::vector<int64_t> pad_after;
	std::vector<int64_t> dilation;
	std::vector<int64_t> output_padding;
	int64_t groups;

	ConvTransposeSpec() : groups(1) {}
};

struct UnfoldSpec {
	int64_t kernel_height;
	int64_t kernel_width;
	int64_t stride_height;
	int64_t stride_width;
	int64_t pad_top;
	int64_t pad_bottom;
	int64_t pad_left;
	int64_t pad_right;
	int64_t dilation_height;
	int64_t dilation_width;

	UnfoldSpec()
		: kernel_height(1),
		  kernel_width(1),
		  stride_height(1),
		  stride_width(1),
		  pad_top(0),
		  pad_bottom(0),
		  pad_left(0),
		  pad_right(0),
		  dilation_height(1),
		  dilation_width(1) {}
};

struct GridSampleSpec {
	int64_t interpolation_mode;
	int64_t padding_mode;
	bool align_corners;
	int64_t grid_divisor_height;
	int64_t grid_divisor_width;
	double scale_height;
	double scale_width;

	GridSampleSpec()
		: interpolation_mode(0),
		  padding_mode(0),
		  align_corners(false),
		  grid_divisor_height(1),
		  grid_divisor_width(1),
		  scale_height(1.0),
		  scale_width(1.0) {}
};

enum class ErrorCode {
	kOk,
	kInvalidArgument,
	kUnsupportedType,
	kShapeMismatch,
	kBufferTooSmall,
	kInvalidDistribution,
	kInvalidQuantization
};

struct Status {
	ErrorCode code;
	const char* message;

	Status() : code(ErrorCode::kOk), message("") {}
	Status(ErrorCode error_code, const char* error_message)
		: code(error_code), message(error_message) {}

	bool ok() const { return code == ErrorCode::kOk; }
};

struct AxisDistribution {
	std::vector<int64_t> axes;
	std::vector<uint8_t> valid_mask;
	InvalidValue invalid_value;

	AxisDistribution() : invalid_value(InvalidValue::kZero) {}
};

struct Quantization {
	bool enabled;
	int64_t axis;
	std::vector<float> scales;
	std::vector<int64_t> zero_points;
	RoundingMode rounding;

	Quantization()
		: enabled(false),
		  axis(-1),
		  rounding(RoundingMode::kNearestEven) {}
};

struct TensorDesc {
	void* data;
	std::size_t data_bytes;
	StorageType storage_type;
	std::vector<int64_t> shape;
	std::vector<char> layout;
	std::vector<AxisDistribution> distributions;
	Quantization quantization;

	TensorDesc()
		: data(NULL),
		  data_bytes(0U),
		  storage_type(StorageType::kFloat32) {}
};

inline std::size_t elementSize(StorageType type) {
	switch (type) {
	case StorageType::kSInt8:
	case StorageType::kUInt8:
		return 1U;
	case StorageType::kSInt16:
	case StorageType::kUInt16:
	case StorageType::kFloat16:
	case StorageType::kBFloat16:
		return 2U;
	case StorageType::kSInt32:
	case StorageType::kUInt32:
	case StorageType::kFloat32:
		return 4U;
	case StorageType::kSInt64:
	case StorageType::kUInt64:
	case StorageType::kFloat64:
		return 8U;
	}
	return 0U;
}

inline double roundValue(double value, RoundingMode mode) {
	if (!std::isfinite(value)) {
		return value;
	}

	if (mode == RoundingMode::kHalfAwayFromZero) {
		return value < 0.0 ? std::ceil(value - 0.5) : std::floor(value + 0.5);
	}
	if (mode == RoundingMode::kHalfUp) {
		return std::floor(value + 0.5);
	}

	const double base = std::floor(value);
	const double fraction = value - base;
	if (fraction < 0.5) {
		return base;
	}
	if (fraction > 0.5) {
		return base + 1.0;
	}
	return std::fmod(std::fabs(base), 2.0) == 0.0 ? base : base + 1.0;
}

namespace detail {

inline bool layoutEquals(const TensorDesc& desc, const char* expected) {
	const std::size_t length = std::strlen(expected);
	return desc.layout.size() == length &&
		std::equal(desc.layout.begin(), desc.layout.end(), expected);
}

inline bool findUniqueLayoutAxis(
	const TensorDesc& desc,
	char axis_name,
	std::size_t* axis) {
	std::size_t match = desc.layout.size();
	for (std::size_t index = 0U; index < desc.layout.size(); ++index) {
		if (desc.layout[index] != axis_name) {
			continue;
		}
		if (match != desc.layout.size()) {
			return false;
		}
		match = index;
	}
	if (match == desc.layout.size()) {
		return false;
	}
	*axis = match;
	return true;
}

inline bool channelLastActivationLayout(const TensorDesc& desc) {
	return (desc.shape.size() == 3U && layoutEquals(desc, "NLC")) ||
		(desc.shape.size() == 4U && layoutEquals(desc, "NHWC")) ||
		(desc.shape.size() == 5U && layoutEquals(desc, "NDHWC"));
}

inline bool checkedMultiply(std::size_t lhs, std::size_t rhs, std::size_t* result) {
	if (lhs != 0U &&
		rhs > (std::numeric_limits<std::size_t>::max)() / lhs) {
		return false;
	}
	*result = lhs * rhs;
	return true;
}

inline bool convTransposeOutputExtent(
	int64_t input_extent,
	int64_t kernel_extent,
	int64_t stride,
	int64_t pad_before,
	int64_t pad_after,
	int64_t dilation,
	int64_t output_padding,
	int64_t* output_extent) {
	if (input_extent <= 0 || kernel_extent <= 0 ||
		stride <= 0 || dilation <= 0 ||
		pad_before < 0 || pad_after < 0 || output_padding < 0) {
		return false;
	}
	const uint64_t maximum = static_cast<uint64_t>(
		(std::numeric_limits<int64_t>::max)());
	const uint64_t input_minus_one =
		static_cast<uint64_t>(input_extent - 1);
	const uint64_t kernel_minus_one =
		static_cast<uint64_t>(kernel_extent - 1);
	const uint64_t stride_value = static_cast<uint64_t>(stride);
	const uint64_t dilation_value = static_cast<uint64_t>(dilation);
	if (input_minus_one != 0U &&
		stride_value > maximum / input_minus_one) {
		return false;
	}
	if (kernel_minus_one != 0U &&
		dilation_value > maximum / kernel_minus_one) {
		return false;
	}
	const uint64_t input_term = input_minus_one * stride_value;
	const uint64_t kernel_term = kernel_minus_one * dilation_value;
	const uint64_t output_padding_value =
		static_cast<uint64_t>(output_padding);
	if (kernel_term > maximum - input_term) {
		return false;
	}
	const uint64_t base = input_term + kernel_term;
	if (base >= maximum ||
		output_padding_value > maximum - base - 1U) {
		return false;
	}
	const uint64_t expanded =
		base + output_padding_value + 1U;
	const uint64_t total_padding =
		static_cast<uint64_t>(pad_before) +
		static_cast<uint64_t>(pad_after);
	if (expanded < total_padding) {
		return false;
	}
	*output_extent = static_cast<int64_t>(expanded - total_padding);
	return true;
}

inline Status physicalElementCount(const TensorDesc& desc, std::size_t* count) {
	std::size_t result = desc.shape.empty() ? 0U : 1U;
	for (std::size_t i = 0; i < desc.shape.size(); ++i) {
		if (desc.shape[i] < 0) {
			return Status(ErrorCode::kInvalidArgument, "negative tensor dimension");
		}
		const uint64_t dimension = static_cast<uint64_t>(desc.shape[i]);
		if (dimension > static_cast<uint64_t>(
			(std::numeric_limits<std::size_t>::max)()) ||
			!checkedMultiply(
				result,
				static_cast<std::size_t>(dimension),
				&result)) {
			return Status(ErrorCode::kInvalidArgument, "tensor element count overflow");
		}
	}
	*count = result;
	return Status();
}

inline bool normalizeAxis(int64_t axis, std::size_t rank, std::size_t* normalized) {
	const int64_t rank_i64 = static_cast<int64_t>(rank);
	const int64_t value = axis < 0 ? axis + rank_i64 : axis;
	if (value < 0 || value >= rank_i64) {
		return false;
	}
	*normalized = static_cast<std::size_t>(value);
	return true;
}

inline bool mapPaddedCoordinate(
	int64_t coordinate,
	int64_t extent,
	PaddingKind padding,
	std::size_t* mapped) {
	if (coordinate >= 0 && coordinate < extent) {
		*mapped = static_cast<std::size_t>(coordinate);
		return true;
	}
	if (padding == PaddingKind::kZeros || extent <= 0) {
		return false;
	}
	if (padding == PaddingKind::kReplicate) {
		*mapped = static_cast<std::size_t>(
			coordinate < 0 ? 0 : extent - 1);
		return true;
	}
	if (padding == PaddingKind::kCircular) {
		const int64_t remainder = coordinate % extent;
		*mapped = static_cast<std::size_t>(
			remainder < 0 ? remainder + extent : remainder);
		return true;
	}
	if (extent <= 1) {
		return false;
	}
	const int64_t period = 2 * (extent - 1);
	int64_t reflected = coordinate % period;
	if (reflected < 0) {
		reflected += period;
	}
	if (reflected >= extent) {
		reflected = period - reflected;
	}
	*mapped = static_cast<std::size_t>(reflected);
	return true;
}

inline bool mapSymmetricCoordinate(
	int64_t coordinate,
	int64_t extent,
	std::size_t* mapped) {
	if (extent <= 0) {
		return false;
	}
	const int64_t period = 2 * extent;
	int64_t symmetric = coordinate % period;
	if (symmetric < 0) {
		symmetric += period;
	}
	if (symmetric >= extent) {
		symmetric = period - 1 - symmetric;
	}
	*mapped = static_cast<std::size_t>(symmetric);
	return true;
}

inline double resizeCoordinate(
	std::size_t output_coordinate,
	std::size_t input_extent,
	std::size_t output_extent,
	bool align_corners) {
	if (align_corners) {
		if (output_extent <= 1U) {
			return 0.0;
		}
		return static_cast<double>(output_coordinate) *
			static_cast<double>(input_extent - 1U) /
			static_cast<double>(output_extent - 1U);
	}
	return (static_cast<double>(output_coordinate) + 0.5) *
		static_cast<double>(input_extent) /
		static_cast<double>(output_extent) -
		0.5;
}

inline double reflectGridCoordinate(
	double coordinate,
	std::size_t extent,
	bool align_corners) {
	if (extent <= 1U) {
		return 0.0;
	}
	const double twice_low = align_corners ? 0.0 : -1.0;
	const double twice_high = align_corners
		? 2.0 * static_cast<double>(extent - 1U)
		: 2.0 * static_cast<double>(extent) - 1.0;
	const double minimum = twice_low * 0.5;
	const double span = (twice_high - twice_low) * 0.5;
	const double distance = std::fabs(coordinate - minimum);
	const double extra = std::fmod(distance, span);
	const double flips = std::floor(distance / span);
	return std::fmod(flips, 2.0) == 0.0
		? extra + minimum
		: span - extra + minimum;
}

inline double gridSourceCoordinate(
	double grid_value,
	double scale,
	int64_t divisor,
	std::size_t input_extent,
	bool align_corners) {
	const double normalized =
		2.0 * grid_value * scale /
		static_cast<double>((std::max)(int64_t(1), divisor)) -
		1.0;
	return align_corners
		? (normalized + 1.0) *
			static_cast<double>(input_extent - 1U) * 0.5
		: ((normalized + 1.0) *
			static_cast<double>(input_extent) - 1.0) * 0.5;
}

inline double cubicWeight(double distance) {
	const double absolute = std::fabs(distance);
	const double coefficient = -0.75;
	if (absolute <= 1.0) {
		return (coefficient + 2.0) * absolute * absolute * absolute -
			(coefficient + 3.0) * absolute * absolute +
			1.0;
	}
	if (absolute < 2.0) {
		return coefficient * absolute * absolute * absolute -
			5.0 * coefficient * absolute * absolute +
			8.0 * coefficient * absolute -
			4.0 * coefficient;
	}
	return 0.0;
}

inline double applyScatterReduction(
	ScatterReduction reduction,
	double current,
	double update) {
	switch (reduction) {
	case ScatterReduction::kNone:
		return update;
	case ScatterReduction::kAdd:
		return current + update;
	case ScatterReduction::kMultiply:
		return current * update;
	case ScatterReduction::kMaximum:
		return std::isnan(current) || std::isnan(update)
			? (std::numeric_limits<double>::quiet_NaN)()
			: (std::max)(current, update);
	case ScatterReduction::kMinimum:
		return std::isnan(current) || std::isnan(update)
			? (std::numeric_limits<double>::quiet_NaN)()
			: (std::min)(current, update);
	}
	return update;
}

inline bool validScatterReduction(ScatterReduction reduction) {
	return reduction == ScatterReduction::kNone ||
		reduction == ScatterReduction::kAdd ||
		reduction == ScatterReduction::kMultiply ||
		reduction == ScatterReduction::kMaximum ||
		reduction == ScatterReduction::kMinimum;
}

struct EinsumSubscript {
	std::vector<int> tokens;
	std::size_t explicit_labels;
	bool has_ellipsis;

	EinsumSubscript()
		: explicit_labels(0U), has_ellipsis(false) {}
};

inline Status parseEinsumSubscript(
	const std::string& text,
	EinsumSubscript* parsed) {
	parsed->tokens.clear();
	parsed->explicit_labels = 0U;
	parsed->has_ellipsis = false;
	for (std::size_t position = 0U; position < text.size();) {
		const char current = text[position];
		if (current >= 'a' && current <= 'z') {
			parsed->tokens.push_back(current - 'a');
			++parsed->explicit_labels;
			++position;
			continue;
		}
		if (current == '.' &&
			position + 2U < text.size() &&
			text[position + 1U] == '.' &&
			text[position + 2U] == '.' &&
			!parsed->has_ellipsis) {
			parsed->tokens.push_back(-1);
			parsed->has_ellipsis = true;
			position += 3U;
			continue;
		}
		return Status(
			ErrorCode::kInvalidArgument,
			"Einsum subscript contains an invalid token");
	}
	return Status();
}

inline std::size_t flattenAxes(
	const std::vector<int64_t>& shape,
	const std::vector<std::size_t>& axes,
	const std::vector<std::size_t>& coordinate) {
	std::size_t index = 0U;
	for (std::size_t i = 0; i < axes.size(); ++i) {
		index = index * static_cast<std::size_t>(shape[axes[i]]) + coordinate[axes[i]];
	}
	return index;
}

inline void decodeIndex(
	std::size_t linear,
	const std::vector<int64_t>& shape,
	std::vector<std::size_t>* coordinate) {
	coordinate->assign(shape.size(), 0U);
	for (std::size_t i = shape.size(); i > 0U; --i) {
		const std::size_t axis = i - 1U;
		const std::size_t dim = static_cast<std::size_t>(shape[axis]);
		if (dim != 0U) {
			(*coordinate)[axis] = linear % dim;
			linear /= dim;
		}
	}
}

inline std::size_t rowMajorIndex(
	const std::vector<int64_t>& shape,
	const std::vector<std::size_t>& coordinate) {
	std::size_t result = 0U;
	for (std::size_t i = 0; i < shape.size(); ++i) {
		result = result * static_cast<std::size_t>(shape[i]) + coordinate[i];
	}
	return result;
}

struct RuntimeDistribution {
	std::vector<std::size_t> original_axes;
	std::vector<std::size_t> sorted_axes;
	std::vector<std::size_t> sorted_dims;
	std::vector<std::vector<std::size_t> > prefix_counts;
	std::vector<std::vector<std::size_t> > prefix_less;
	std::vector<std::size_t> valid_rank;
	const AxisDistribution* source;

	RuntimeDistribution() : source(NULL) {}

	int sortedAxisPosition(std::size_t axis) const {
		for (std::size_t i = 0; i < sorted_axes.size(); ++i) {
			if (sorted_axes[i] == axis) {
				return static_cast<int>(i);
			}
		}
		return -1;
	}

	std::size_t prefixIndex(
		const std::vector<std::size_t>& coordinate,
		std::size_t level) const {
		std::size_t index = 0U;
		for (std::size_t i = 0; i < level; ++i) {
			index = index * sorted_dims[i] + coordinate[sorted_axes[i]];
		}
		return index;
	}

	std::size_t fixedLevel(std::size_t fixed_axis_count) const {
		std::size_t level = 0U;
		while (level < sorted_axes.size() && sorted_axes[level] < fixed_axis_count) {
			++level;
		}
		return level;
	}

	std::size_t countWithPrefix(
		const std::vector<std::size_t>& coordinate,
		std::size_t fixed_axis_count) const {
		const std::size_t level = fixedLevel(fixed_axis_count);
		return prefix_counts[level][prefixIndex(coordinate, level)];
	}

	std::size_t countCurrentLess(
		const std::vector<std::size_t>& coordinate,
		std::size_t axis) const {
		const int position = sortedAxisPosition(axis);
		if (position < 0) {
			return 0U;
		}
		const std::size_t level = static_cast<std::size_t>(position) + 1U;
		return prefix_less[level][prefixIndex(coordinate, level)];
	}
};

struct RuntimeTensor {
	const TensorDesc* desc;
	std::vector<RuntimeDistribution> omitted;
	std::vector<int> omitted_owner;
	std::size_t storage_elements;

	RuntimeTensor() : desc(NULL), storage_elements(0U) {}

	const RuntimeDistribution* omittedForAxis(std::size_t axis) const {
		if (axis >= omitted_owner.size() || omitted_owner[axis] < 0) {
			return NULL;
		}
		return &omitted[static_cast<std::size_t>(omitted_owner[axis])];
	}
};

inline Status normalizeDistributionAxes(
	const TensorDesc& desc,
	const AxisDistribution& distribution,
	std::vector<std::size_t>* axes,
	std::size_t* mask_elements) {
	if (distribution.axes.empty()) {
		return Status(ErrorCode::kInvalidDistribution, "distribution has no axes");
	}

	axes->clear();
	std::size_t elements = 1U;
	for (std::size_t i = 0; i < distribution.axes.size(); ++i) {
		std::size_t axis = 0U;
		if (!normalizeAxis(distribution.axes[i], desc.shape.size(), &axis)) {
			return Status(ErrorCode::kInvalidDistribution, "distribution axis out of range");
		}
		if (std::find(axes->begin(), axes->end(), axis) != axes->end()) {
			return Status(ErrorCode::kInvalidDistribution, "distribution contains duplicate axis");
		}
		axes->push_back(axis);
		if (!checkedMultiply(
				elements,
				static_cast<std::size_t>(desc.shape[axis]),
				&elements)) {
			return Status(ErrorCode::kInvalidDistribution, "distribution size overflow");
		}
	}
	if (elements != distribution.valid_mask.size()) {
		return Status(ErrorCode::kInvalidDistribution, "distribution mask size mismatch");
	}
	*mask_elements = elements;
	return Status();
}

inline Status buildRuntimeDistribution(
	const TensorDesc& desc,
	const AxisDistribution& distribution,
	RuntimeDistribution* runtime) {
	std::size_t mask_elements = 0U;
	Status status = normalizeDistributionAxes(
		desc, distribution, &runtime->original_axes, &mask_elements);
	if (!status.ok()) {
		return status;
	}

	runtime->source = &distribution;
	runtime->sorted_axes = runtime->original_axes;
	std::sort(runtime->sorted_axes.begin(), runtime->sorted_axes.end());
	runtime->sorted_dims.resize(runtime->sorted_axes.size());
	for (std::size_t i = 0; i < runtime->sorted_axes.size(); ++i) {
		runtime->sorted_dims[i] =
			static_cast<std::size_t>(desc.shape[runtime->sorted_axes[i]]);
	}

	runtime->prefix_counts.resize(runtime->sorted_axes.size() + 1U);
	runtime->prefix_less.resize(runtime->sorted_axes.size() + 1U);
	std::size_t prefix_size = 1U;
	for (std::size_t level = 0; level <= runtime->sorted_axes.size(); ++level) {
		runtime->prefix_counts[level].assign(prefix_size, 0U);
		runtime->prefix_less[level].assign(prefix_size, 0U);
		if (level < runtime->sorted_axes.size()) {
			if (!checkedMultiply(prefix_size, runtime->sorted_dims[level], &prefix_size)) {
				return Status(ErrorCode::kInvalidDistribution, "distribution prefix size overflow");
			}
		}
	}

	runtime->valid_rank.assign(
		mask_elements,
		(std::numeric_limits<std::size_t>::max)());
	std::vector<std::size_t> original_coordinate(runtime->original_axes.size(), 0U);
	std::vector<std::size_t> physical_coordinate(desc.shape.size(), 0U);
	std::size_t valid_count = 0U;
	for (std::size_t mask_index = 0; mask_index < mask_elements; ++mask_index) {
		std::size_t remaining = mask_index;
		for (std::size_t i = runtime->original_axes.size(); i > 0U; --i) {
			const std::size_t position = i - 1U;
			const std::size_t dim =
				static_cast<std::size_t>(desc.shape[runtime->original_axes[position]]);
			original_coordinate[position] = dim == 0U ? 0U : remaining % dim;
			if (dim != 0U) {
				remaining /= dim;
			}
			physical_coordinate[runtime->original_axes[position]] =
				original_coordinate[position];
		}

		if (distribution.valid_mask[mask_index] == 0U) {
			continue;
		}

		runtime->valid_rank[mask_index] = valid_count++;
		for (std::size_t level = 0; level <= runtime->sorted_axes.size(); ++level) {
			const std::size_t index = runtime->prefixIndex(physical_coordinate, level);
			++runtime->prefix_counts[level][index];
		}
	}

	for (std::size_t level = 1U; level <= runtime->sorted_axes.size(); ++level) {
		const std::size_t current_dim = runtime->sorted_dims[level - 1U];
		if (current_dim == 0U) {
			continue;
		}
		const std::size_t rows = runtime->prefix_counts[level].size() / current_dim;
		for (std::size_t row = 0; row < rows; ++row) {
			std::size_t sum = 0U;
			for (std::size_t value = 0; value < current_dim; ++value) {
				const std::size_t index = row * current_dim + value;
				runtime->prefix_less[level][index] = sum;
				sum += runtime->prefix_counts[level][index];
			}
		}
	}

	return Status();
}

inline Status validateTensor(const TensorDesc& desc, RuntimeTensor* runtime) {
	if (desc.shape.size() != desc.layout.size()) {
		return Status(ErrorCode::kShapeMismatch, "layout rank does not match shape rank");
	}
	if (elementSize(desc.storage_type) == 0U) {
		return Status(ErrorCode::kUnsupportedType, "unsupported storage type");
	}

	std::size_t physical_elements = 0U;
	Status status = physicalElementCount(desc, &physical_elements);
	if (!status.ok()) {
		return status;
	}
	if (physical_elements != 0U && desc.data == NULL) {
		return Status(ErrorCode::kInvalidArgument, "tensor data is null");
	}

	runtime->desc = &desc;
	runtime->omitted.clear();
	runtime->omitted_owner.assign(desc.shape.size(), -1);
	runtime->storage_elements = physical_elements;

	for (std::size_t i = 0; i < desc.distributions.size(); ++i) {
		const AxisDistribution& distribution = desc.distributions[i];
		std::vector<std::size_t> axes;
		std::size_t mask_elements = 0U;
		status = normalizeDistributionAxes(desc, distribution, &axes, &mask_elements);
		if (!status.ok()) {
			return status;
		}

		if (distribution.invalid_value != InvalidValue::kOmitted) {
			continue;
		}

		RuntimeDistribution built;
		status = buildRuntimeDistribution(desc, distribution, &built);
		if (!status.ok()) {
			return status;
		}
		const std::size_t owner = runtime->omitted.size();
		for (std::size_t axis_index = 0; axis_index < axes.size(); ++axis_index) {
			const std::size_t axis = axes[axis_index];
			if (runtime->omitted_owner[axis] >= 0) {
				return Status(
					ErrorCode::kInvalidDistribution,
					"omitted distributions overlap");
			}
			runtime->omitted_owner[axis] = static_cast<int>(owner);
		}

		const std::size_t valid_count = built.prefix_counts[0][0];
		if (mask_elements != 0U) {
			runtime->storage_elements /= mask_elements;
		}
		if (!checkedMultiply(runtime->storage_elements, valid_count, &runtime->storage_elements)) {
			return Status(ErrorCode::kInvalidDistribution, "stored element count overflow");
		}
		runtime->omitted.push_back(built);
	}

	std::size_t required_bytes = 0U;
	if (!checkedMultiply(
		runtime->storage_elements,
		elementSize(desc.storage_type),
		&required_bytes)) {
		return Status(ErrorCode::kBufferTooSmall, "tensor byte count overflow");
	}
	if (desc.data_bytes < required_bytes) {
		return Status(ErrorCode::kBufferTooSmall, "tensor buffer is too small");
	}

	if (desc.quantization.enabled) {
		std::size_t axis = 0U;
		if (!normalizeAxis(desc.quantization.axis, desc.shape.size(), &axis)) {
			return Status(ErrorCode::kInvalidQuantization, "quantization axis out of range");
		}
		if (desc.quantization.scales.empty()) {
			return Status(ErrorCode::kInvalidQuantization, "quantization scale is empty");
		}
		for (std::size_t i = 0; i < desc.quantization.scales.size(); ++i) {
			if (!std::isfinite(desc.quantization.scales[i]) ||
				desc.quantization.scales[i] == 0.0f) {
				return Status(ErrorCode::kInvalidQuantization, "invalid quantization scale");
			}
		}
	}

	return Status();
}

inline bool coordinateIsValid(
	const TensorDesc& desc,
	const std::vector<std::size_t>& coordinate,
	bool omitted_only) {
	for (std::size_t i = 0; i < desc.distributions.size(); ++i) {
		const AxisDistribution& distribution = desc.distributions[i];
		if (omitted_only && distribution.invalid_value != InvalidValue::kOmitted) {
			continue;
		}
		std::vector<std::size_t> axes;
		std::size_t ignored = 0U;
		if (!normalizeDistributionAxes(desc, distribution, &axes, &ignored).ok()) {
			return false;
		}
		const std::size_t mask_index = flattenAxes(desc.shape, axes, coordinate);
		if (distribution.valid_mask[mask_index] == 0U) {
			return false;
		}
	}
	return true;
}

inline std::size_t uncoveredSuffixElements(
	const RuntimeTensor& runtime,
	std::size_t current_axis) {
	std::size_t result = 1U;
	for (std::size_t axis = current_axis + 1U;
			axis < runtime.desc->shape.size();
			++axis) {
		if (runtime.omitted_owner[axis] < 0) {
			result *= static_cast<std::size_t>(runtime.desc->shape[axis]);
		}
	}
	return result;
}

inline bool storedIndex(
	const RuntimeTensor& runtime,
	const std::vector<std::size_t>& coordinate,
	std::size_t* index) {
	if (!coordinateIsValid(*runtime.desc, coordinate, true)) {
		return false;
	}
	if (runtime.omitted.empty()) {
		*index = rowMajorIndex(runtime.desc->shape, coordinate);
		return true;
	}

	std::size_t result = 0U;
	for (std::size_t axis = 0; axis < runtime.desc->shape.size(); ++axis) {
		if (coordinate[axis] == 0U) {
			continue;
		}

		std::size_t contribution = 1U;
		const RuntimeDistribution* owner = runtime.omittedForAxis(axis);
		if (owner != NULL) {
			contribution = owner->countCurrentLess(coordinate, axis);
		}
		else {
			contribution = coordinate[axis];
		}

		for (std::size_t i = 0; i < runtime.omitted.size(); ++i) {
			if (&runtime.omitted[i] == owner) {
				continue;
			}
			contribution *= runtime.omitted[i].countWithPrefix(coordinate, axis);
		}
		contribution *= uncoveredSuffixElements(runtime, axis);
		result += contribution;
	}
	*index = result;
	return true;
}

inline uint32_t floatToBits(float value) {
	uint32_t bits = 0U;
	std::memcpy(&bits, &value, sizeof(bits));
	return bits;
}

inline float bitsToFloat(uint32_t bits) {
	float value = 0.0f;
	std::memcpy(&value, &bits, sizeof(value));
	return value;
}

inline float bfloat16ToFloat(uint16_t value) {
	return bitsToFloat(static_cast<uint32_t>(value) << 16U);
}

inline uint16_t floatToBfloat16(float value) {
	const uint32_t bits = floatToBits(value);
	const uint32_t rounded =
		bits + 0x7FFFU + ((bits >> 16U) & 1U);
	return static_cast<uint16_t>(rounded >> 16U);
}

inline float float16ToFloat(uint16_t value) {
	const uint32_t sign = (static_cast<uint32_t>(value & 0x8000U)) << 16U;
	uint32_t exponent = (value >> 10U) & 0x1FU;
	uint32_t mantissa = value & 0x03FFU;
	uint32_t output = 0U;

	if (exponent == 0U) {
		if (mantissa == 0U) {
			output = sign;
		}
		else {
			int shift = 0;
			while ((mantissa & 0x0400U) == 0U) {
				mantissa <<= 1U;
				++shift;
			}
			mantissa &= 0x03FFU;
			const uint32_t exp32 = static_cast<uint32_t>(127 - 15 - shift);
			output = sign | (exp32 << 23U) | (mantissa << 13U);
		}
	}
	else if (exponent == 0x1FU) {
		output = sign | 0x7F800000U | (mantissa << 13U);
	}
	else {
		exponent = exponent + (127U - 15U);
		output = sign | (exponent << 23U) | (mantissa << 13U);
	}
	return bitsToFloat(output);
}

inline uint16_t floatToFloat16(float value) {
	const uint32_t bits = floatToBits(value);
	const uint32_t sign = (bits >> 16U) & 0x8000U;
	const uint32_t exponent = (bits >> 23U) & 0xFFU;
	const uint32_t mantissa = bits & 0x007FFFFFU;

	if (exponent == 0xFFU) {
		return static_cast<uint16_t>(
			sign | 0x7C00U | (mantissa == 0U ? 0U : 0x0200U));
	}

	const int32_t half_exponent = static_cast<int32_t>(exponent) - 127 + 15;
	if (half_exponent >= 0x1F) {
		return static_cast<uint16_t>(sign | 0x7C00U);
	}
	if (half_exponent <= 0) {
		if (half_exponent < -10) {
			return static_cast<uint16_t>(sign);
		}
		const uint32_t significand = mantissa | 0x00800000U;
		const uint32_t shift = static_cast<uint32_t>(14 - half_exponent);
		uint32_t half_mantissa = significand >> shift;
		const uint32_t remainder_mask = (1U << shift) - 1U;
		const uint32_t remainder = significand & remainder_mask;
		const uint32_t halfway = 1U << (shift - 1U);
		if (remainder > halfway ||
			(remainder == halfway && (half_mantissa & 1U) != 0U)) {
			++half_mantissa;
		}
		return static_cast<uint16_t>(sign | half_mantissa);
	}

	uint32_t half_mantissa = mantissa >> 13U;
	const uint32_t remainder = mantissa & 0x1FFFU;
	uint32_t half = sign |
		(static_cast<uint32_t>(half_exponent) << 10U) |
		half_mantissa;
	if (remainder > 0x1000U ||
		(remainder == 0x1000U && (half_mantissa & 1U) != 0U)) {
		++half;
	}
	return static_cast<uint16_t>(half);
}

template <typename T>
inline T loadValue(const void* data, std::size_t index) {
	T value;
	std::memcpy(
		&value,
		static_cast<const uint8_t*>(data) + index * sizeof(T),
		sizeof(T));
	return value;
}

template <typename T>
inline void storeValue(void* data, std::size_t index, T value) {
	std::memcpy(
		static_cast<uint8_t*>(data) + index * sizeof(T),
		&value,
		sizeof(T));
}

inline double loadRaw(const TensorDesc& desc, std::size_t index) {
	switch (desc.storage_type) {
	case StorageType::kSInt8:
		return static_cast<double>(loadValue<int8_t>(desc.data, index));
	case StorageType::kUInt8:
		return static_cast<double>(loadValue<uint8_t>(desc.data, index));
	case StorageType::kSInt16:
		return static_cast<double>(loadValue<int16_t>(desc.data, index));
	case StorageType::kUInt16:
		return static_cast<double>(loadValue<uint16_t>(desc.data, index));
	case StorageType::kSInt32:
		return static_cast<double>(loadValue<int32_t>(desc.data, index));
	case StorageType::kUInt32:
		return static_cast<double>(loadValue<uint32_t>(desc.data, index));
	case StorageType::kSInt64:
		return static_cast<double>(loadValue<int64_t>(desc.data, index));
	case StorageType::kUInt64:
		return static_cast<double>(loadValue<uint64_t>(desc.data, index));
	case StorageType::kFloat16:
		return static_cast<double>(float16ToFloat(loadValue<uint16_t>(desc.data, index)));
	case StorageType::kBFloat16:
		return static_cast<double>(bfloat16ToFloat(loadValue<uint16_t>(desc.data, index)));
	case StorageType::kFloat32:
		return static_cast<double>(loadValue<float>(desc.data, index));
	case StorageType::kFloat64:
		return loadValue<double>(desc.data, index);
	}
	return 0.0;
}

inline Status readIndex(
	const TensorDesc& desc,
	std::size_t index,
	int64_t* value) {
	if (desc.quantization.enabled) {
		return Status(
			ErrorCode::kUnsupportedType,
			"index tensors cannot be quantized");
	}
	switch (desc.storage_type) {
	case StorageType::kSInt8:
		*value = loadValue<int8_t>(desc.data, index);
		return Status();
	case StorageType::kUInt8:
		*value = loadValue<uint8_t>(desc.data, index);
		return Status();
	case StorageType::kSInt16:
		*value = loadValue<int16_t>(desc.data, index);
		return Status();
	case StorageType::kUInt16:
		*value = loadValue<uint16_t>(desc.data, index);
		return Status();
	case StorageType::kSInt32:
		*value = loadValue<int32_t>(desc.data, index);
		return Status();
	case StorageType::kUInt32:
		*value = loadValue<uint32_t>(desc.data, index);
		return Status();
	case StorageType::kSInt64:
		*value = loadValue<int64_t>(desc.data, index);
		return Status();
	case StorageType::kUInt64: {
		const uint64_t loaded = loadValue<uint64_t>(desc.data, index);
		if (loaded > static_cast<uint64_t>(
			(std::numeric_limits<int64_t>::max)())) {
			return Status(
				ErrorCode::kInvalidArgument,
				"unsigned index exceeds the signed index range");
		}
		*value = static_cast<int64_t>(loaded);
		return Status();
	}
	default:
		break;
	}
	const double loaded = loadRaw(desc, index);
	const long double extended = static_cast<long double>(loaded);
	if (!std::isfinite(loaded) ||
		std::trunc(loaded) != loaded ||
		extended < static_cast<long double>(
			(std::numeric_limits<int64_t>::min)()) ||
		extended > static_cast<long double>(
			(std::numeric_limits<int64_t>::max)())) {
		return Status(
			ErrorCode::kInvalidArgument,
			"floating-point index is not a finite integer");
	}
	*value = static_cast<int64_t>(loaded);
	return Status();
}

inline double clampFinite(double value, double minimum, double maximum) {
	if (std::isnan(value)) {
		return 0.0;
	}
	if (value < minimum) {
		return minimum;
	}
	if (value > maximum) {
		return maximum;
	}
	return value;
}

inline void storeRaw(
	const TensorDesc& desc,
	std::size_t index,
	double value,
	RoundingMode rounding) {
	switch (desc.storage_type) {
	case StorageType::kSInt8:
		storeValue<int8_t>(
			desc.data, index,
			static_cast<int8_t>(clampFinite(
				roundValue(value, rounding),
				static_cast<double>((std::numeric_limits<int8_t>::min)()),
				static_cast<double>((std::numeric_limits<int8_t>::max)()))));
		break;
	case StorageType::kUInt8:
		storeValue<uint8_t>(
			desc.data, index,
			static_cast<uint8_t>(clampFinite(
				roundValue(value, rounding),
				0.0,
				static_cast<double>((std::numeric_limits<uint8_t>::max)()))));
		break;
	case StorageType::kSInt16:
		storeValue<int16_t>(
			desc.data, index,
			static_cast<int16_t>(clampFinite(
				roundValue(value, rounding),
				static_cast<double>((std::numeric_limits<int16_t>::min)()),
				static_cast<double>((std::numeric_limits<int16_t>::max)()))));
		break;
	case StorageType::kUInt16:
		storeValue<uint16_t>(
			desc.data, index,
			static_cast<uint16_t>(clampFinite(
				roundValue(value, rounding),
				0.0,
				static_cast<double>((std::numeric_limits<uint16_t>::max)()))));
		break;
	case StorageType::kSInt32:
		storeValue<int32_t>(
			desc.data, index,
			static_cast<int32_t>(clampFinite(
				roundValue(value, rounding),
				static_cast<double>((std::numeric_limits<int32_t>::min)()),
				static_cast<double>((std::numeric_limits<int32_t>::max)()))));
		break;
	case StorageType::kUInt32:
		storeValue<uint32_t>(
			desc.data, index,
			static_cast<uint32_t>(clampFinite(
				roundValue(value, rounding),
				0.0,
				static_cast<double>((std::numeric_limits<uint32_t>::max)()))));
		break;
	case StorageType::kSInt64: {
		long double rounded = std::isnan(value)
			? 0.0L
			: static_cast<long double>(roundValue(value, rounding));
		const long double minimum =
			static_cast<long double>((std::numeric_limits<int64_t>::min)());
		const long double maximum =
			static_cast<long double>((std::numeric_limits<int64_t>::max)());
		rounded = (std::max)(minimum, (std::min)(maximum, rounded));
		storeValue<int64_t>(desc.data, index, static_cast<int64_t>(rounded));
		break;
	}
	case StorageType::kUInt64: {
		long double rounded = std::isnan(value)
			? 0.0L
			: static_cast<long double>(roundValue(value, rounding));
		const long double maximum =
			static_cast<long double>((std::numeric_limits<uint64_t>::max)());
		rounded = (std::max)(
			static_cast<long double>(0.0),
			(std::min)(maximum, rounded));
		storeValue<uint64_t>(desc.data, index, static_cast<uint64_t>(rounded));
		break;
	}
	case StorageType::kFloat16:
		storeValue<uint16_t>(
			desc.data, index, floatToFloat16(static_cast<float>(value)));
		break;
	case StorageType::kBFloat16:
		storeValue<uint16_t>(
			desc.data, index, floatToBfloat16(static_cast<float>(value)));
		break;
	case StorageType::kFloat32:
		storeValue<float>(desc.data, index, static_cast<float>(value));
		break;
	case StorageType::kFloat64:
		storeValue<double>(desc.data, index, value);
		break;
	}
}

inline std::size_t combinedAxisCoordinate(
	const TensorDesc& desc,
	const std::vector<std::size_t>& coordinate,
	std::size_t axis) {
	const char axis_name = desc.layout[axis];
	if (axis_name == '*') {
		return coordinate[axis];
	}
	const char upper = axis_name >= 'a' && axis_name <= 'z'
		? static_cast<char>(axis_name - 'a' + 'A')
		: axis_name;
	const char lower = static_cast<char>(upper - 'A' + 'a');
	std::size_t upper_axis = desc.layout.size();
	std::size_t lower_axis = desc.layout.size();
	for (std::size_t i = 0; i < desc.layout.size(); ++i) {
		if (desc.layout[i] == upper) {
			upper_axis = i;
		}
		else if (desc.layout[i] == lower) {
			lower_axis = i;
		}
	}
	if (upper_axis == desc.layout.size()) {
		return coordinate[axis];
	}
	if (lower_axis == desc.layout.size()) {
		return coordinate[upper_axis];
	}
	return coordinate[upper_axis] *
		static_cast<std::size_t>(desc.shape[lower_axis]) +
		coordinate[lower_axis];
}

inline const AxisDistribution* distributionForAxis(
	const TensorDesc& desc,
	std::size_t axis,
	std::vector<std::size_t>* normalized_axes) {
	for (std::size_t i = 0; i < desc.distributions.size(); ++i) {
		std::size_t ignored = 0U;
		if (!normalizeDistributionAxes(
			desc, desc.distributions[i], normalized_axes, &ignored).ok()) {
			continue;
		}
		if (std::find(normalized_axes->begin(), normalized_axes->end(), axis) !=
			normalized_axes->end()) {
			return &desc.distributions[i];
		}
	}
	return NULL;
}

inline Status quantizationIndex(
	const TensorDesc& desc,
	const std::vector<std::size_t>& coordinate,
	std::size_t* coefficient_index) {
	std::size_t axis = 0U;
	if (!normalizeAxis(desc.quantization.axis, desc.shape.size(), &axis)) {
		return Status(ErrorCode::kInvalidQuantization, "quantization axis out of range");
	}

	std::vector<std::size_t> distribution_axes;
	const AxisDistribution* distribution =
		distributionForAxis(desc, axis, &distribution_axes);
	if (distribution == NULL) {
		*coefficient_index = combinedAxisCoordinate(desc, coordinate, axis);
		return Status();
	}

	const std::size_t mask_index =
		flattenAxes(desc.shape, distribution_axes, coordinate);
	if (distribution->invalid_value == InvalidValue::kOmitted) {
		std::size_t valid_rank = 0U;
		for (std::size_t i = 0; i < mask_index; ++i) {
			if (distribution->valid_mask[i] != 0U) {
				++valid_rank;
			}
		}
		*coefficient_index = valid_rank;
	}
	else {
		*coefficient_index = mask_index;
	}
	return Status();
}

inline Status quantizationParameters(
	const TensorDesc& desc,
	const std::vector<std::size_t>& coordinate,
	double* scale,
	double* zero_point) {
	*scale = 1.0;
	*zero_point = 0.0;
	if (!desc.quantization.enabled) {
		return Status();
	}

	std::size_t coefficient_index = 0U;
	Status status = quantizationIndex(desc, coordinate, &coefficient_index);
	if (!status.ok()) {
		return status;
	}

	const std::size_t scale_index =
		desc.quantization.scales.size() == 1U ? 0U : coefficient_index;
	if (scale_index >= desc.quantization.scales.size()) {
		return Status(
			ErrorCode::kInvalidQuantization,
			"quantization scale does not cover the selected axis");
	}
	*scale = static_cast<double>(desc.quantization.scales[scale_index]);

	if (!desc.quantization.zero_points.empty()) {
		const std::size_t zero_index =
			desc.quantization.zero_points.size() == 1U ? 0U : coefficient_index;
		if (zero_index >= desc.quantization.zero_points.size()) {
			return Status(
				ErrorCode::kInvalidQuantization,
				"zero point does not cover the selected axis");
		}
		*zero_point =
			static_cast<double>(desc.quantization.zero_points[zero_index]);
	}
	return Status();
}

inline Status readExpressed(
	const TensorDesc& desc,
	std::size_t storage_index,
	const std::vector<std::size_t>& coordinate,
	double* value) {
	double scale = 1.0;
	double zero_point = 0.0;
	Status status = quantizationParameters(
		desc, coordinate, &scale, &zero_point);
	if (!status.ok()) {
		return status;
	}
	*value = (loadRaw(desc, storage_index) - zero_point) * scale;
	return Status();
}

inline Status readChannelParameter(
	const TensorDesc& parameter,
	const RuntimeTensor& runtime,
	std::size_t channel,
	std::size_t channel_count,
	bool allow_scalar,
	double* value) {
	const bool scalar = allow_scalar && runtime.storage_elements == 1U;
	if ((!scalar && runtime.storage_elements != channel_count) ||
		channel >= channel_count) {
		return Status(
			ErrorCode::kShapeMismatch,
			"channel parameter size does not match the activation channel axis");
	}
	const std::size_t parameter_index = scalar ? 0U : channel;
	std::vector<std::size_t> parameter_coordinate;
	decodeIndex(
		parameter_index,
		parameter.shape,
		&parameter_coordinate);
	return readExpressed(
		parameter,
		parameter_index,
		parameter_coordinate,
		value);
}

inline Status writeExpressed(
	const TensorDesc& desc,
	std::size_t storage_index,
	const std::vector<std::size_t>& coordinate,
	double value) {
	double scale = 1.0;
	double zero_point = 0.0;
	Status status = quantizationParameters(
		desc, coordinate, &scale, &zero_point);
	if (!status.ok()) {
		return status;
	}
	const double raw = desc.quantization.enabled
		? roundValue(value / scale, desc.quantization.rounding) + zero_point
		: value;
	storeRaw(desc, storage_index, raw, desc.quantization.rounding);
	return Status();
}

inline Status loadDenseExpressedValues(
	const TensorDesc& desc,
	std::vector<double>* values) {
	std::size_t elements = 0U;
	Status status = physicalElementCount(desc, &elements);
	if (!status.ok()) {
		return status;
	}
	values->assign(elements, 0.0);
	std::vector<std::size_t> coordinate;
	for (std::size_t index = 0U; index < elements; ++index) {
		decodeIndex(index, desc.shape, &coordinate);
		status = readExpressed(
			desc, index, coordinate, &(*values)[index]);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status storeDenseExpressedValues(
	TensorDesc& desc,
	const std::vector<double>& values) {
	std::size_t elements = 0U;
	Status status = physicalElementCount(desc, &elements);
	if (!status.ok()) {
		return status;
	}
	if (elements != values.size()) {
		return Status(
			ErrorCode::kShapeMismatch,
			"dense expressed-value buffer does not match the output shape");
	}
	std::vector<std::size_t> coordinate;
	for (std::size_t index = 0U; index < elements; ++index) {
		decodeIndex(index, desc.shape, &coordinate);
		status = writeExpressed(desc, index, coordinate, values[index]);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

struct AxisKey {
	char name;
	std::size_t occurrence;

	bool operator==(const AxisKey& other) const {
		return name == other.name && occurrence == other.occurrence;
	}
};

inline AxisKey axisKey(const TensorDesc& desc, std::size_t axis) {
	const char raw = desc.layout[axis];
	if (raw != '*') {
		const char upper = raw >= 'a' && raw <= 'z'
			? static_cast<char>(raw - 'a' + 'A')
			: raw;
		return AxisKey{upper, 0U};
	}
	std::size_t occurrence = 0U;
	for (std::size_t i = 0; i < axis; ++i) {
		if (desc.layout[i] == '*') {
			++occurrence;
		}
	}
	return AxisKey{'*', occurrence};
}

struct LogicalCoordinate {
	AxisKey key;
	std::size_t value;
};

inline std::size_t combinedAxisExtent(
	const TensorDesc& desc,
	const AxisKey& key);

inline void toLogical(
	const TensorDesc& desc,
	const std::vector<std::size_t>& physical,
	std::vector<LogicalCoordinate>* logical) {
	logical->clear();
	for (std::size_t axis = 0; axis < desc.layout.size(); ++axis) {
		const AxisKey key = axisKey(desc, axis);
		bool exists = false;
		for (std::size_t i = 0; i < logical->size(); ++i) {
			if ((*logical)[i].key == key) {
				exists = true;
				break;
			}
		}
		if (!exists) {
			logical->push_back(
				LogicalCoordinate{key, combinedAxisCoordinate(desc, physical, axis)});
		}
	}
}

inline bool logicalValue(
	const std::vector<LogicalCoordinate>& logical,
	const AxisKey& key,
	std::size_t* value) {
	for (std::size_t i = 0; i < logical.size(); ++i) {
		if (logical[i].key == key) {
			*value = logical[i].value;
			return true;
		}
	}
	return false;
}

inline bool fromLogical(
	const TensorDesc& desc,
	const std::vector<LogicalCoordinate>& logical,
	std::vector<std::size_t>* physical) {
	physical->assign(desc.shape.size(), 0U);
	for (std::size_t axis = 0; axis < desc.layout.size(); ++axis) {
		const char raw = desc.layout[axis];
		if (raw >= 'a' && raw <= 'z') {
			continue;
		}
		const AxisKey key = axisKey(desc, axis);
		std::size_t value = 0U;
		if (!logicalValue(logical, key, &value)) {
			return false;
		}

		if (raw == '*') {
			if (value >= static_cast<std::size_t>(desc.shape[axis])) {
				return false;
			}
			(*physical)[axis] = value;
			continue;
		}

		const char lower = static_cast<char>(raw - 'A' + 'a');
		std::size_t lower_axis = desc.layout.size();
		for (std::size_t i = 0; i < desc.layout.size(); ++i) {
			if (desc.layout[i] == lower) {
				lower_axis = i;
				break;
			}
		}
		if (lower_axis == desc.layout.size()) {
			if (value >= static_cast<std::size_t>(desc.shape[axis])) {
				return false;
			}
			(*physical)[axis] = value;
		}
		else {
			const std::size_t lower_dim =
				static_cast<std::size_t>(desc.shape[lower_axis]);
			if (lower_dim == 0U) {
				return false;
			}
			(*physical)[axis] = value / lower_dim;
			(*physical)[lower_axis] = value % lower_dim;
			if ((*physical)[axis] >= static_cast<std::size_t>(desc.shape[axis])) {
				return false;
			}
		}
	}
	return true;
}

inline bool fromLogicalBroadcast(
	const TensorDesc& desc,
	const std::vector<LogicalCoordinate>& logical,
	std::vector<std::size_t>* physical) {
	physical->assign(desc.shape.size(), 0U);
	for (std::size_t axis = 0; axis < desc.layout.size(); ++axis) {
		const char raw = desc.layout[axis];
		if (raw >= 'a' && raw <= 'z') {
			continue;
		}

		const AxisKey key = axisKey(desc, axis);
		const std::size_t extent = combinedAxisExtent(desc, key);
		std::size_t value = 0U;
		if (!logicalValue(logical, key, &value)) {
			if (extent != 1U) {
				return false;
			}
			value = 0U;
		}
		else if (extent == 1U) {
			value = 0U;
		}
		else if (value >= extent) {
			return false;
		}

		if (raw == '*') {
			(*physical)[axis] = value;
			continue;
		}

		const char lower = static_cast<char>(raw - 'A' + 'a');
		std::size_t lower_axis = desc.layout.size();
		for (std::size_t i = 0; i < desc.layout.size(); ++i) {
			if (desc.layout[i] == lower) {
				lower_axis = i;
				break;
			}
		}
		if (lower_axis == desc.layout.size()) {
			(*physical)[axis] = value;
		}
		else {
			const std::size_t lower_dim =
				static_cast<std::size_t>(desc.shape[lower_axis]);
			if (lower_dim == 0U) {
				return false;
			}
			(*physical)[axis] = value / lower_dim;
			(*physical)[lower_axis] = value % lower_dim;
			if ((*physical)[axis] >=
				static_cast<std::size_t>(desc.shape[axis])) {
				return false;
			}
		}
	}
	return true;
}

inline Status readBroadcastValue(
	const TensorDesc& input,
	const RuntimeTensor& runtime,
	const TensorDesc& output,
	const std::vector<std::size_t>& output_coordinate,
	double* value) {
	if (input.shape.size() > output.shape.size() ||
		output_coordinate.size() != output.shape.size()) {
		return Status(
			ErrorCode::kShapeMismatch,
			"input shape cannot broadcast to the output shape");
	}

	std::vector<std::size_t> input_coordinate(input.shape.size(), 0U);
	const std::size_t leading_axes = output.shape.size() - input.shape.size();
	for (std::size_t input_axis = 0U;
		input_axis < input.shape.size();
		++input_axis) {
		const std::size_t output_axis = leading_axes + input_axis;
		const std::size_t input_extent =
			static_cast<std::size_t>(input.shape[input_axis]);
		const std::size_t output_extent =
			static_cast<std::size_t>(output.shape[output_axis]);
		if (input_extent != 1U && input_extent != output_extent) {
			return Status(
				ErrorCode::kShapeMismatch,
				"input shape cannot broadcast to the output shape");
		}
		input_coordinate[input_axis] = input_extent == 1U
			? 0U
			: output_coordinate[output_axis];
	}
	if (!coordinateIsValid(input, input_coordinate, false)) {
		*value = 0.0;
		return Status();
	}

	std::size_t storage_index = 0U;
	if (!storedIndex(runtime, input_coordinate, &storage_index)) {
		*value = 0.0;
		return Status();
	}
	return readExpressed(input, storage_index, input_coordinate, value);
}

inline Status coefficientForCoordinate(
	const TensorDesc& output,
	const std::vector<std::size_t>& coordinate,
	const std::vector<double>& coefficients,
	char axis_name,
	double* coefficient) {
	if (coefficients.empty()) {
		return Status(
			ErrorCode::kInvalidArgument,
			"elementwise coefficient array is empty");
	}
	if (coefficients.size() == 1U) {
		*coefficient = coefficients[0];
		return Status();
	}

	const char upper = axis_name >= 'a' && axis_name <= 'z'
		? static_cast<char>(axis_name - 'a' + 'A')
		: axis_name;
	for (std::size_t axis = 0; axis < output.layout.size(); ++axis) {
		if (axisKey(output, axis) == AxisKey{upper, 0U}) {
			const std::size_t index =
				combinedAxisCoordinate(output, coordinate, axis);
			if (index >= coefficients.size()) {
				return Status(
					ErrorCode::kInvalidArgument,
					"elementwise coefficient does not cover the selected axis");
			}
			*coefficient = coefficients[index];
			return Status();
		}
	}
	return Status(
		ErrorCode::kInvalidArgument,
		"elementwise coefficient axis is absent from the output layout");
}

inline bool correspondingAxis(
	const TensorDesc& input,
	std::size_t input_axis,
	const TensorDesc& output,
	std::size_t* output_axis) {
	const AxisKey key = axisKey(input, input_axis);
	for (std::size_t i = 0; i < output.layout.size(); ++i) {
		if (axisKey(output, i) == key) {
			*output_axis = i;
			return true;
		}
	}
	return false;
}

inline std::size_t combinedAxisExtent(
	const TensorDesc& desc,
	const AxisKey& key) {
	std::size_t extent = 1U;
	for (std::size_t axis = 0; axis < desc.layout.size(); ++axis) {
		if (axisKey(desc, axis) == key) {
			extent *= static_cast<std::size_t>(desc.shape[axis]);
		}
	}
	return extent;
}

inline Status applyPruneMapping(
	const TensorDesc& input,
	const TensorDesc& output,
	const std::vector<std::size_t>& output_coordinate,
	const std::vector<std::size_t>& distribution_indices,
	std::vector<std::size_t>* input_coordinate) {
	for (std::size_t selection = 0;
		selection < distribution_indices.size();
		++selection) {
		const std::size_t distribution_index = distribution_indices[selection];
		if (distribution_index >= input.distributions.size()) {
			return Status(
				ErrorCode::kInvalidDistribution,
				"PruneAxis distribution index out of range");
		}
		const AxisDistribution& distribution =
			input.distributions[distribution_index];
		std::vector<std::size_t> input_axes;
		std::size_t mask_elements = 0U;
		Status status = normalizeDistributionAxes(
			input, distribution, &input_axes, &mask_elements);
		if (!status.ok()) {
			return status;
		}

		std::vector<AxisKey> mapped_keys;
		std::size_t compact_index = 0U;
		for (std::size_t i = 0; i < input_axes.size(); ++i) {
			const AxisKey key = axisKey(input, input_axes[i]);
			if (std::find_if(
					mapped_keys.begin(),
					mapped_keys.end(),
					[&key](const AxisKey& candidate) {
						return candidate == key;
					}) != mapped_keys.end()) {
				continue;
			}

			std::size_t output_axis = 0U;
			if (!correspondingAxis(input, input_axes[i], output, &output_axis)) {
				return Status(
					ErrorCode::kShapeMismatch,
					"PruneAxis output layout does not preserve a pruned axis");
			}
			mapped_keys.push_back(key);
			compact_index =
				compact_index * combinedAxisExtent(output, key) +
				combinedAxisCoordinate(output, output_coordinate, output_axis);
		}

		std::size_t valid_index = mask_elements;
		std::size_t valid_seen = 0U;
		for (std::size_t mask_index = 0; mask_index < mask_elements; ++mask_index) {
			if (distribution.valid_mask[mask_index] == 0U) {
				continue;
			}
			if (valid_seen == compact_index) {
				valid_index = mask_index;
				break;
			}
			++valid_seen;
		}
		if (valid_index == mask_elements) {
			return Status(
				ErrorCode::kShapeMismatch,
				"PruneAxis output is larger than the valid input region");
		}

		for (std::size_t i = input_axes.size(); i > 0U; --i) {
			const std::size_t position = i - 1U;
			const std::size_t dim =
				static_cast<std::size_t>(input.shape[input_axes[position]]);
			(*input_coordinate)[input_axes[position]] =
				dim == 0U ? 0U : valid_index % dim;
			if (dim != 0U) {
				valid_index /= dim;
			}
		}
	}
	return Status();
}

inline Status transform(
	const TensorDesc& input,
	TensorDesc& output,
	const std::vector<std::size_t>* prune_distributions) {
	RuntimeTensor input_runtime;
	RuntimeTensor output_runtime;
	Status status = validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}

	std::size_t output_physical_elements = 0U;
	status = physicalElementCount(output, &output_physical_elements);
	if (!status.ok()) {
		return status;
	}

	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate;
	std::vector<LogicalCoordinate> logical;
	std::size_t output_storage_index = 0U;
	for (std::size_t output_linear = 0;
		output_linear < output_physical_elements;
		++output_linear) {
		decodeIndex(output_linear, output.shape, &output_coordinate);
		if (!coordinateIsValid(output, output_coordinate, true)) {
			continue;
		}

		if (!coordinateIsValid(output, output_coordinate, false)) {
			storeRaw(
				output,
				output_storage_index++,
				0.0,
				output.quantization.rounding);
			continue;
		}

		toLogical(output, output_coordinate, &logical);
		const bool mapped = fromLogical(input, logical, &input_coordinate);
		if (mapped && prune_distributions != NULL) {
			status = applyPruneMapping(
				input,
				output,
				output_coordinate,
				*prune_distributions,
				&input_coordinate);
			if (!status.ok()) {
				return status;
			}
		}

		std::size_t input_storage_index = 0U;
		if (!mapped ||
			!coordinateIsValid(input, input_coordinate, false) ||
			!storedIndex(input_runtime, input_coordinate, &input_storage_index)) {
			status = writeExpressed(
				output, output_storage_index++, output_coordinate, 0.0);
			if (!status.ok()) {
				return status;
			}
			continue;
		}

		double value = 0.0;
		status = readExpressed(
			input, input_storage_index, input_coordinate, &value);
		if (!status.ok()) {
			return status;
		}
		status = writeExpressed(
			output, output_storage_index++, output_coordinate, value);
		if (!status.ok()) {
			return status;
		}
	}

	if (output_storage_index != output_runtime.storage_elements) {
		return Status(
			ErrorCode::kShapeMismatch,
			"output storage traversal did not cover the output buffer");
	}
	return Status();
}

inline double stableSigmoid(double value) {
	if (value >= 0.0) {
		const double exponential = std::exp(-value);
		return 1.0 / (1.0 + exponential);
	}
	const double exponential = std::exp(value);
	return exponential / (1.0 + exponential);
}

inline double stableSoftplus(double value, double beta, double threshold) {
	if (beta == 0.0) {
		return value;
	}
	const double scaled = beta * value;
	if (scaled > threshold) {
		return value;
	}
	if (scaled > 0.0) {
		return (scaled + std::log1p(std::exp(-scaled))) / beta;
	}
	return std::log1p(std::exp(scaled)) / beta;
}

inline Status applyUnaryValue(
	const UnarySpec& spec,
	double input,
	double* output) {
	switch (spec.kind) {
	case UnaryKind::kIdentity:
		*output = input;
		break;
	case UnaryKind::kAbs:
		*output = std::fabs(input);
		break;
	case UnaryKind::kAcos:
		*output = std::acos(input);
		break;
	case UnaryKind::kAcosh:
		*output = std::acosh(input);
		break;
	case UnaryKind::kAsin:
		*output = std::asin(input);
		break;
	case UnaryKind::kAsinh:
		*output = std::asinh(input);
		break;
	case UnaryKind::kAtan:
		*output = std::atan(input);
		break;
	case UnaryKind::kAtanh:
		*output = std::atanh(input);
		break;
	case UnaryKind::kCos:
		*output = std::cos(input);
		break;
	case UnaryKind::kCosh:
		*output = std::cosh(input);
		break;
	case UnaryKind::kDivideScalar:
		*output = input / spec.alpha;
		if (spec.beta == 1.0) {
			*output = std::trunc(*output);
		}
		else if (spec.beta == 2.0) {
			*output = std::floor(*output);
		}
		break;
	case UnaryKind::kElu:
		*output = input > 0.0 ? input : spec.alpha * std::expm1(input);
		break;
	case UnaryKind::kGelu:
		*output = 0.5 * input *
			(1.0 + std::erf(input / std::sqrt(2.0)));
		break;
	case UnaryKind::kHardSigmoid:
		*output = (std::max)(0.0, (std::min)(1.0, spec.alpha * input + spec.beta));
		break;
	case UnaryKind::kHardSwish: {
		const double gate =
			(std::max)(0.0, (std::min)(1.0, spec.alpha * input + spec.beta));
		*output = input * gate;
		break;
	}
	case UnaryKind::kHardShrink:
		*output = (input > spec.alpha || input < -spec.alpha)
			? input
			: 0.0;
		break;
	case UnaryKind::kHardTanh:
		*output = (std::max)(spec.minimum, (std::min)(spec.maximum, input));
		break;
	case UnaryKind::kLog:
		*output = std::log(input);
		break;
	case UnaryKind::kLogSigmoid:
		*output = input >= 0.0
			? -std::log1p(std::exp(-input))
			: input - std::log1p(std::exp(input));
		break;
	case UnaryKind::kMish:
		*output = input * std::tanh(stableSoftplus(input, 1.0, 20.0));
		break;
	case UnaryKind::kNeg:
		*output = -input;
		break;
	case UnaryKind::kNot:
		*output = input == 0.0 ? 1.0 : 0.0;
		break;
	case UnaryKind::kRelu:
		if (input >= spec.maximum) {
			*output = spec.maximum;
		}
		else if (input >= spec.threshold) {
			*output = input;
		}
		else {
			*output = spec.alpha * (input - spec.threshold);
		}
		break;
	case UnaryKind::kSigmoid:
		*output = stableSigmoid(input);
		break;
	case UnaryKind::kSilu:
		*output = input * stableSigmoid(input);
		break;
	case UnaryKind::kSin:
		*output = std::sin(input);
		break;
	case UnaryKind::kSinh:
		*output = std::sinh(input);
		break;
	case UnaryKind::kSoftplus:
		*output = stableSoftplus(input, spec.beta, spec.threshold);
		break;
	case UnaryKind::kSoftshrink:
		*output = input > spec.alpha
			? input - spec.alpha
			: (input < -spec.alpha ? input + spec.alpha : 0.0);
		break;
	case UnaryKind::kSoftsign:
		*output = input / (1.0 + std::fabs(input));
		break;
	case UnaryKind::kSqrt:
		*output = std::sqrt(input);
		break;
	case UnaryKind::kTan:
		*output = std::tan(input);
		break;
	case UnaryKind::kTanh:
		*output = std::tanh(input);
		break;
	case UnaryKind::kTanhShrink:
		*output = input - std::tanh(input);
		break;
	}
	return Status();
}

inline Status applyBinaryValue(
	const BinarySpec& spec,
	double lhs,
	double rhs,
	double lhs_coefficient,
	double rhs_coefficient,
	double* output) {
	switch (spec.kind) {
	case BinaryKind::kAdd:
		*output = lhs_coefficient * lhs + rhs_coefficient * rhs;
		break;
	case BinaryKind::kDivide:
		*output = lhs / rhs;
		break;
	case BinaryKind::kEqual:
		*output = lhs == rhs ? 1.0 : 0.0;
		break;
	case BinaryKind::kGreater:
		*output = lhs > rhs ? 1.0 : 0.0;
		break;
	case BinaryKind::kGreaterEqual:
		*output = lhs >= rhs ? 1.0 : 0.0;
		break;
	case BinaryKind::kLess:
		*output = lhs < rhs ? 1.0 : 0.0;
		break;
	case BinaryKind::kLessEqual:
		*output = lhs <= rhs ? 1.0 : 0.0;
		break;
	case BinaryKind::kMaximum:
		*output = std::isnan(lhs) || std::isnan(rhs)
			? (std::numeric_limits<double>::quiet_NaN)()
			: (std::max)(lhs, rhs);
		break;
	case BinaryKind::kMinimum:
		*output = std::isnan(lhs) || std::isnan(rhs)
			? (std::numeric_limits<double>::quiet_NaN)()
			: (std::min)(lhs, rhs);
		break;
	case BinaryKind::kMultiply:
		*output = lhs * rhs;
		break;
	case BinaryKind::kNotEqual:
		*output = lhs != rhs ? 1.0 : 0.0;
		break;
	case BinaryKind::kPow:
		*output = std::pow(lhs, rhs);
		break;
	}
	return Status();
}

template <typename CoordinateMapper>
inline Status transformCoordinates(
	const TensorDesc& input,
	TensorDesc& output,
	CoordinateMapper mapper) {
	RuntimeTensor input_runtime;
	RuntimeTensor output_runtime;
	Status status = validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}

	std::size_t output_physical_elements = 0U;
	status = physicalElementCount(output, &output_physical_elements);
	if (!status.ok()) {
		return status;
	}

	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate(input.shape.size(), 0U);
	std::size_t output_storage_index = 0U;
	for (std::size_t output_linear = 0U;
		output_linear < output_physical_elements;
		++output_linear) {
		decodeIndex(output_linear, output.shape, &output_coordinate);
		if (!coordinateIsValid(output, output_coordinate, true)) {
			continue;
		}
		if (!coordinateIsValid(output, output_coordinate, false)) {
			storeRaw(
				output,
				output_storage_index++,
				0.0,
				output.quantization.rounding);
			continue;
		}

		if (!mapper(output_coordinate, &input_coordinate)) {
			return Status(
				ErrorCode::kShapeMismatch,
				"coordinate transform is incompatible with tensor shapes");
		}

		double value = 0.0;
		std::size_t input_storage_index = 0U;
		if (coordinateIsValid(input, input_coordinate, false) &&
			storedIndex(input_runtime, input_coordinate, &input_storage_index)) {
			status = readExpressed(
				input, input_storage_index, input_coordinate, &value);
			if (!status.ok()) {
				return status;
			}
		}
		status = writeExpressed(
			output, output_storage_index++, output_coordinate, value);
		if (!status.ok()) {
			return status;
		}
	}

	if (output_storage_index != output_runtime.storage_elements) {
		return Status(
			ErrorCode::kShapeMismatch,
			"coordinate transform did not cover the output buffer");
	}
	return Status();
}

}  // namespace detail

inline Status cast(const TensorDesc& input, TensorDesc& output) {
	return detail::transform(input, output, NULL);
}

inline Status linearCopy(const TensorDesc& input, TensorDesc& output) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (input.storage_type != output.storage_type ||
		input_runtime.storage_elements != output_runtime.storage_elements) {
		return Status(
			ErrorCode::kShapeMismatch,
			"linear copy requires equal storage types and element counts");
	}
	const std::size_t bytes = input_runtime.storage_elements *
		elementSize(input.storage_type);
	std::memmove(output.data, input.data, bytes);
	return Status();
}

inline Status transpose(
	const TensorDesc& input,
	TensorDesc& output,
	const std::vector<int64_t>& dimensions) {
	if (input.shape.size() != output.shape.size() ||
		dimensions.size() != output.shape.size()) {
		return Status(
			ErrorCode::kShapeMismatch,
			"transpose rank does not match tensor rank");
	}
	std::vector<std::size_t> normalized(dimensions.size(), 0U);
	std::vector<uint8_t> used(dimensions.size(), 0U);
	for (std::size_t output_axis = 0U;
		output_axis < dimensions.size();
		++output_axis) {
		std::size_t input_axis = 0U;
		if (!detail::normalizeAxis(
				dimensions[output_axis], input.shape.size(), &input_axis) ||
			used[input_axis] != 0U ||
			output.shape[output_axis] != input.shape[input_axis]) {
			return Status(
				ErrorCode::kShapeMismatch,
				"transpose dimensions are not a valid permutation");
		}
		used[input_axis] = 1U;
		normalized[output_axis] = input_axis;
	}

	return detail::transformCoordinates(
		input,
		output,
		[&normalized](
			const std::vector<std::size_t>& output_coordinate,
			std::vector<std::size_t>* input_coordinate) {
			for (std::size_t output_axis = 0U;
				output_axis < normalized.size();
				++output_axis) {
				(*input_coordinate)[normalized[output_axis]] =
					output_coordinate[output_axis];
			}
			return true;
		});
}

inline Status reorderAxis(
	const TensorDesc& input,
	TensorDesc& output,
	int64_t axis,
	const std::vector<int64_t>& order) {
	if (input.shape != output.shape) {
		return Status(
			ErrorCode::kShapeMismatch,
			"axis reorder requires equal input and output shapes");
	}
	std::size_t normalized_axis = 0U;
	if (!detail::normalizeAxis(axis, input.shape.size(), &normalized_axis) ||
		order.size() !=
			static_cast<std::size_t>(input.shape[normalized_axis])) {
		return Status(
			ErrorCode::kInvalidArgument,
			"axis reorder metadata does not match the selected axis");
	}
	std::vector<uint8_t> used(order.size(), 0U);
	std::vector<std::size_t> normalized_order(order.size(), 0U);
	for (std::size_t i = 0U; i < order.size(); ++i) {
		if (order[i] < 0 ||
			static_cast<std::size_t>(order[i]) >= order.size() ||
			used[static_cast<std::size_t>(order[i])] != 0U) {
			return Status(
				ErrorCode::kInvalidArgument,
				"axis reorder indices are not a permutation");
		}
		normalized_order[i] = static_cast<std::size_t>(order[i]);
		used[normalized_order[i]] = 1U;
	}

	return detail::transformCoordinates(
		input,
		output,
		[normalized_axis, &normalized_order](
			const std::vector<std::size_t>& output_coordinate,
			std::vector<std::size_t>* input_coordinate) {
			*input_coordinate = output_coordinate;
			(*input_coordinate)[normalized_axis] =
				normalized_order[output_coordinate[normalized_axis]];
			return true;
		});
}

inline Status reduce(
	const TensorDesc& input,
	TensorDesc& output,
	const ReductionSpec& spec) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (!input.distributions.empty() || !output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable reduction does not yet support merged-axis distributions");
	}

	std::vector<uint8_t> reduced(input.shape.size(), 0U);
	if (spec.axes.empty()) {
		std::fill(reduced.begin(), reduced.end(), 1U);
	}
	else {
		for (std::size_t i = 0U; i < spec.axes.size(); ++i) {
			std::size_t axis = 0U;
			if (!detail::normalizeAxis(spec.axes[i], input.shape.size(), &axis) ||
				reduced[axis] != 0U) {
				return Status(
					ErrorCode::kInvalidArgument,
					"reduction axes are invalid or duplicated");
			}
			reduced[axis] = 1U;
		}
	}

	std::size_t reduced_count = 0U;
	for (std::size_t axis = 0U; axis < reduced.size(); ++axis) {
		reduced_count += reduced[axis] != 0U ? 1U : 0U;
	}
	if (reduced_count == 0U) {
		return Status(ErrorCode::kInvalidArgument, "reduction has no axes");
	}

	if (spec.keep_dimensions) {
		if (output.shape.size() != input.shape.size()) {
			return Status(
				ErrorCode::kShapeMismatch,
				"keepdim reduction output rank does not match input rank");
		}
		for (std::size_t axis = 0U; axis < input.shape.size(); ++axis) {
			const int64_t expected = reduced[axis] != 0U ? 1 : input.shape[axis];
			if (output.shape[axis] != expected) {
				return Status(
					ErrorCode::kShapeMismatch,
					"keepdim reduction output shape is invalid");
			}
		}
	}
	else if (reduced_count == input.shape.size()) {
		if (output.shape.size() != 1U || output.shape[0] != 1) {
			return Status(
				ErrorCode::kShapeMismatch,
				"full reduction output must have shape {1}");
		}
	}
	else {
		if (output.shape.size() != input.shape.size() - reduced_count) {
			return Status(
				ErrorCode::kShapeMismatch,
				"reduction output rank is invalid");
		}
		std::size_t output_axis = 0U;
		for (std::size_t input_axis = 0U;
			input_axis < input.shape.size();
			++input_axis) {
			if (reduced[input_axis] == 0U) {
				if (output.shape[output_axis++] != input.shape[input_axis]) {
					return Status(
						ErrorCode::kShapeMismatch,
						"reduction output shape is invalid");
				}
			}
		}
	}

	const bool is_argument =
		spec.kind == ReductionKind::kArgMaximum ||
		spec.kind == ReductionKind::kArgMinimum;
	if (is_argument && reduced_count != 1U && reduced_count != input.shape.size()) {
		return Status(
			ErrorCode::kInvalidArgument,
			"argument reduction supports one axis or a full reduction");
	}

	std::vector<double> accumulators(output_runtime.storage_elements, 0.0);
	std::vector<std::size_t> sample_counts(output_runtime.storage_elements, 0U);
	std::vector<std::size_t> argument_indices(output_runtime.storage_elements, 0U);
	std::vector<uint8_t> initialized(output_runtime.storage_elements, 0U);
	std::vector<std::size_t> input_coordinate;
	std::vector<std::size_t> output_coordinate;
	std::size_t argument_axis = input.shape.size();
	if (is_argument && reduced_count == 1U) {
		for (std::size_t axis = 0U; axis < reduced.size(); ++axis) {
			if (reduced[axis] != 0U) {
				argument_axis = axis;
				break;
			}
		}
	}

	std::size_t input_physical_elements = 0U;
	status = detail::physicalElementCount(input, &input_physical_elements);
	if (!status.ok()) {
		return status;
	}
	for (std::size_t input_linear = 0U;
		input_linear < input_physical_elements;
		++input_linear) {
		detail::decodeIndex(input_linear, input.shape, &input_coordinate);
		output_coordinate.clear();
		if (spec.keep_dimensions) {
			output_coordinate = input_coordinate;
			for (std::size_t axis = 0U; axis < reduced.size(); ++axis) {
				if (reduced[axis] != 0U) {
					output_coordinate[axis] = 0U;
				}
			}
		}
		else if (reduced_count == input.shape.size()) {
			output_coordinate.push_back(0U);
		}
		else {
			for (std::size_t axis = 0U; axis < reduced.size(); ++axis) {
				if (reduced[axis] == 0U) {
					output_coordinate.push_back(input_coordinate[axis]);
				}
			}
		}

		std::size_t output_index = 0U;
		for (std::size_t axis = 0U; axis < output_coordinate.size(); ++axis) {
			output_index = output_index *
				static_cast<std::size_t>(output.shape[axis]) +
				output_coordinate[axis];
		}
		double value = 0.0;
		status = detail::readExpressed(
			input, input_linear, input_coordinate, &value);
		if (!status.ok()) {
			return status;
		}

		const bool wants_maximum =
			spec.kind == ReductionKind::kMaximum ||
			spec.kind == ReductionKind::kArgMaximum;
		const bool wants_minimum =
			spec.kind == ReductionKind::kMinimum ||
			spec.kind == ReductionKind::kArgMinimum;
		const std::size_t candidate_argument =
			argument_axis == input.shape.size()
			? input_linear
			: input_coordinate[argument_axis];
		if (initialized[output_index] == 0U) {
			accumulators[output_index] = value;
			argument_indices[output_index] = candidate_argument;
			initialized[output_index] = 1U;
		}
		else if (wants_maximum &&
			((std::isnan(value) &&
			  !std::isnan(accumulators[output_index])) ||
			 value > accumulators[output_index])) {
			accumulators[output_index] = value;
			argument_indices[output_index] = candidate_argument;
		}
		else if (wants_minimum &&
			((std::isnan(value) &&
			  !std::isnan(accumulators[output_index])) ||
			 value < accumulators[output_index])) {
			accumulators[output_index] = value;
			argument_indices[output_index] = candidate_argument;
		}
		else if (!wants_maximum && !wants_minimum) {
			accumulators[output_index] += value;
		}
		++sample_counts[output_index];
	}

	for (std::size_t output_index = 0U;
		output_index < output_runtime.storage_elements;
		++output_index) {
		if (initialized[output_index] == 0U || sample_counts[output_index] == 0U) {
			return Status(
				ErrorCode::kInvalidArgument,
				"reduction cannot operate on an empty input region");
		}
		detail::decodeIndex(output_index, output.shape, &output_coordinate);
		double value = accumulators[output_index];
		if (spec.kind == ReductionKind::kMean) {
			value /= static_cast<double>(sample_counts[output_index]);
		}
		else if (is_argument) {
			value = static_cast<double>(argument_indices[output_index]);
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, value);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status softmax(
	const TensorDesc& input,
	TensorDesc& output,
	int64_t axis,
	bool logarithmic) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (input.shape != output.shape) {
		return Status(
			ErrorCode::kShapeMismatch,
			"softmax input and output shapes must match");
	}
	if (!input.distributions.empty() || !output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable softmax does not yet support merged-axis distributions");
	}
	std::size_t normalized_axis = 0U;
	if (!detail::normalizeAxis(axis, input.shape.size(), &normalized_axis)) {
		return Status(ErrorCode::kInvalidArgument, "softmax axis is invalid");
	}

	std::size_t outer = 1U;
	std::size_t inner = 1U;
	for (std::size_t i = 0U; i < normalized_axis; ++i) {
		if (!detail::checkedMultiply(
				outer, static_cast<std::size_t>(input.shape[i]), &outer)) {
			return Status(ErrorCode::kInvalidArgument, "softmax size overflow");
		}
	}
	for (std::size_t i = normalized_axis + 1U; i < input.shape.size(); ++i) {
		if (!detail::checkedMultiply(
				inner, static_cast<std::size_t>(input.shape[i]), &inner)) {
			return Status(ErrorCode::kInvalidArgument, "softmax size overflow");
		}
	}
	const std::size_t axis_extent =
		static_cast<std::size_t>(input.shape[normalized_axis]);
	if (axis_extent == 0U) {
		return Status(ErrorCode::kInvalidArgument, "softmax axis is empty");
	}

	std::vector<double> values(axis_extent, 0.0);
	std::vector<std::size_t> coordinate;
	for (std::size_t outer_index = 0U; outer_index < outer; ++outer_index) {
		for (std::size_t inner_index = 0U; inner_index < inner; ++inner_index) {
			double maximum = -(std::numeric_limits<double>::infinity)();
			for (std::size_t axis_index = 0U;
				axis_index < axis_extent;
				++axis_index) {
				const std::size_t storage_index =
					(outer_index * axis_extent + axis_index) * inner +
					inner_index;
				detail::decodeIndex(storage_index, input.shape, &coordinate);
				status = detail::readExpressed(
					input, storage_index, coordinate, &values[axis_index]);
				if (!status.ok()) {
					return status;
				}
				maximum = (std::max)(maximum, values[axis_index]);
			}

			double exponential_sum = 0.0;
			for (std::size_t axis_index = 0U;
				axis_index < axis_extent;
				++axis_index) {
				exponential_sum += std::exp(values[axis_index] - maximum);
			}
			const double log_sum = std::log(exponential_sum);
			for (std::size_t axis_index = 0U;
				axis_index < axis_extent;
				++axis_index) {
				const std::size_t storage_index =
					(outer_index * axis_extent + axis_index) * inner +
					inner_index;
				detail::decodeIndex(storage_index, output.shape, &coordinate);
				const double shifted = values[axis_index] - maximum;
				const double result = logarithmic
					? shifted - log_sum
					: std::exp(shifted) / exponential_sum;
				status = detail::writeExpressed(
					output, storage_index, coordinate, result);
				if (!status.ok()) {
					return status;
				}
			}
		}
	}
	return Status();
}

inline Status matmul(
	const TensorDesc& lhs,
	const TensorDesc& rhs,
	const TensorDesc* bias,
	TensorDesc& output) {
	detail::RuntimeTensor lhs_runtime;
	detail::RuntimeTensor rhs_runtime;
	detail::RuntimeTensor bias_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(lhs, &lhs_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(rhs, &rhs_runtime);
	if (!status.ok()) {
		return status;
	}
	if (bias != NULL) {
		status = detail::validateTensor(*bias, &bias_runtime);
		if (!status.ok()) {
			return status;
		}
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (!lhs.distributions.empty() ||
		!rhs.distributions.empty() ||
		(bias != NULL && !bias->distributions.empty()) ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable matmul does not yet support merged-axis distributions");
	}
	if (lhs.shape.empty() || rhs.shape.empty()) {
		return Status(
			ErrorCode::kShapeMismatch,
			"matmul operands must have rank one or greater");
	}

	const std::size_t lhs_rank = lhs.shape.size();
	const std::size_t rhs_rank = rhs.shape.size();
	const int64_t contraction_lhs = lhs.shape[lhs_rank - 1U];
	const int64_t contraction_rhs =
		rhs_rank == 1U ? rhs.shape[0] : rhs.shape[rhs_rank - 2U];
	if (contraction_lhs != contraction_rhs || contraction_lhs < 0) {
		return Status(
			ErrorCode::kShapeMismatch,
			"matmul contraction dimensions do not match");
	}

	std::vector<int64_t> expected_shape;
	std::size_t batch_rank = 0U;
	if (lhs_rank == 1U && rhs_rank == 1U) {
		expected_shape.push_back(1);
	}
	else if (lhs_rank == 1U) {
		expected_shape.assign(rhs.shape.begin(), rhs.shape.end() - 2);
		expected_shape.push_back(rhs.shape[rhs_rank - 1U]);
	}
	else if (rhs_rank == 1U) {
		expected_shape.assign(lhs.shape.begin(), lhs.shape.end() - 1);
	}
	else {
		const std::size_t lhs_batch_rank = lhs_rank - 2U;
		const std::size_t rhs_batch_rank = rhs_rank - 2U;
		batch_rank = (std::max)(lhs_batch_rank, rhs_batch_rank);
		expected_shape.assign(batch_rank, 1);
		for (std::size_t batch_axis = 0U;
			batch_axis < batch_rank;
			++batch_axis) {
			const bool has_lhs =
				batch_axis + lhs_batch_rank >= batch_rank;
			const bool has_rhs =
				batch_axis + rhs_batch_rank >= batch_rank;
			const int64_t lhs_extent = has_lhs
				? lhs.shape[batch_axis + lhs_batch_rank - batch_rank]
				: 1;
			const int64_t rhs_extent = has_rhs
				? rhs.shape[batch_axis + rhs_batch_rank - batch_rank]
				: 1;
			if (lhs_extent < 0 || rhs_extent < 0 ||
				(lhs_extent != rhs_extent &&
				 lhs_extent != 1 && rhs_extent != 1)) {
				return Status(
					ErrorCode::kShapeMismatch,
					"matmul batch dimensions cannot broadcast");
			}
			expected_shape[batch_axis] =
				(std::max)(lhs_extent, rhs_extent);
		}
		expected_shape.push_back(lhs.shape[lhs_rank - 2U]);
		expected_shape.push_back(rhs.shape[rhs_rank - 1U]);
	}
	if (output.shape != expected_shape) {
		return Status(
			ErrorCode::kShapeMismatch,
			"matmul output shape does not match operand shapes");
	}

	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	if (output_elements != output_runtime.storage_elements) {
		return Status(
			ErrorCode::kShapeMismatch,
			"matmul output storage does not match its physical shape");
	}

	const std::size_t contraction =
		static_cast<std::size_t>(contraction_lhs);
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> lhs_coordinate(lhs_rank, 0U);
	std::vector<std::size_t> rhs_coordinate(rhs_rank, 0U);
	for (std::size_t output_index = 0U;
		output_index < output_elements;
		++output_index) {
		detail::decodeIndex(
			output_index, output.shape, &output_coordinate);
		std::fill(lhs_coordinate.begin(), lhs_coordinate.end(), 0U);
		std::fill(rhs_coordinate.begin(), rhs_coordinate.end(), 0U);

		if (lhs_rank == 1U && rhs_rank > 1U) {
			for (std::size_t axis = 0U; axis + 2U < rhs_rank; ++axis) {
				rhs_coordinate[axis] =
					rhs.shape[axis] == 1 ? 0U : output_coordinate[axis];
			}
			rhs_coordinate[rhs_rank - 1U] = output_coordinate.back();
		}
		else if (lhs_rank > 1U && rhs_rank == 1U) {
			for (std::size_t axis = 0U; axis + 1U < lhs_rank; ++axis) {
				lhs_coordinate[axis] = output_coordinate[axis];
			}
		}
		else if (lhs_rank > 1U && rhs_rank > 1U) {
			const std::size_t lhs_batch_rank = lhs_rank - 2U;
			const std::size_t rhs_batch_rank = rhs_rank - 2U;
			for (std::size_t axis = 0U; axis < lhs_batch_rank; ++axis) {
				const std::size_t output_axis =
					batch_rank - lhs_batch_rank + axis;
				lhs_coordinate[axis] = lhs.shape[axis] == 1
					? 0U
					: output_coordinate[output_axis];
			}
			for (std::size_t axis = 0U; axis < rhs_batch_rank; ++axis) {
				const std::size_t output_axis =
					batch_rank - rhs_batch_rank + axis;
				rhs_coordinate[axis] = rhs.shape[axis] == 1
					? 0U
					: output_coordinate[output_axis];
			}
			lhs_coordinate[lhs_rank - 2U] =
				output_coordinate[batch_rank];
			rhs_coordinate[rhs_rank - 1U] =
				output_coordinate[batch_rank + 1U];
		}

		double accumulator = 0.0;
		for (std::size_t reduction_index = 0U;
			reduction_index < contraction;
			++reduction_index) {
			lhs_coordinate[lhs_rank - 1U] = reduction_index;
			if (rhs_rank == 1U) {
				rhs_coordinate[0] = reduction_index;
			}
			else {
				rhs_coordinate[rhs_rank - 2U] = reduction_index;
			}
			const std::size_t lhs_index =
				detail::rowMajorIndex(lhs.shape, lhs_coordinate);
			const std::size_t rhs_index =
				detail::rowMajorIndex(rhs.shape, rhs_coordinate);
			double lhs_value = 0.0;
			double rhs_value = 0.0;
			status = detail::readExpressed(
				lhs, lhs_index, lhs_coordinate, &lhs_value);
			if (!status.ok()) {
				return status;
			}
			status = detail::readExpressed(
				rhs, rhs_index, rhs_coordinate, &rhs_value);
			if (!status.ok()) {
				return status;
			}
			accumulator += lhs_value * rhs_value;
		}

		if (bias != NULL) {
			double bias_value = 0.0;
			status = detail::readBroadcastValue(
				*bias,
				bias_runtime,
				output,
				output_coordinate,
				&bias_value);
			if (!status.ok()) {
				return status;
			}
			accumulator += bias_value;
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, accumulator);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status matmulNBits(
	const TensorDesc& input,
	const TensorDesc& packed_weights,
	const TensorDesc& scales,
	const TensorDesc* packed_zero_points,
	TensorDesc& output,
	int64_t bits,
	int64_t group_count,
	int64_t group_size,
	int64_t input_channels,
	int64_t output_channels) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor weights_runtime;
	detail::RuntimeTensor scales_runtime;
	detail::RuntimeTensor zeros_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(packed_weights, &weights_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(scales, &scales_runtime);
	if (!status.ok()) {
		return status;
	}
	if (packed_zero_points != NULL) {
		status = detail::validateTensor(
			*packed_zero_points, &zeros_runtime);
		if (!status.ok()) {
			return status;
		}
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (bits != 4 || group_count <= 0 || group_size <= 0 ||
		input_channels <= 0 || output_channels <= 0 ||
		group_count > (std::numeric_limits<int64_t>::max)() / group_size ||
		group_count * group_size != input_channels) {
		return Status(
			ErrorCode::kInvalidArgument,
			"MatmulNBits requires a complete 4-bit grouped channel partition");
	}
	if (input.shape.size() < 2U ||
		output.shape.size() != input.shape.size() ||
		input.shape.back() != input_channels ||
		output.shape.back() != output_channels) {
		return Status(
			ErrorCode::kShapeMismatch,
			"MatmulNBits input or output shape is invalid");
	}
	for (std::size_t axis = 0U; axis + 1U < input.shape.size(); ++axis) {
		if (output.shape[axis] != input.shape[axis]) {
			return Status(
				ErrorCode::kShapeMismatch,
				"MatmulNBits must preserve input prefix dimensions");
		}
	}
	const uint64_t size_maximum = static_cast<uint64_t>(
		(std::numeric_limits<std::size_t>::max)());
	if (static_cast<uint64_t>(group_count) > size_maximum ||
		static_cast<uint64_t>(group_size) > size_maximum ||
		static_cast<uint64_t>(output_channels) > size_maximum) {
		return Status(
			ErrorCode::kInvalidArgument,
			"MatmulNBits dimensions exceed the addressable size range");
	}
	const std::size_t groups = static_cast<std::size_t>(group_count);
	const std::size_t group_width = static_cast<std::size_t>(group_size);
	const std::size_t output_width =
		static_cast<std::size_t>(output_channels);
	const int64_t packed_group_size =
		group_size / 2 + group_size % 2;
	std::size_t required_scales = 0U;
	if (!detail::checkedMultiply(output_width, groups, &required_scales)) {
		return Status(
			ErrorCode::kInvalidArgument,
			"MatmulNBits scale count overflow");
	}
	if (packed_weights.shape.size() != 3U ||
		packed_weights.shape[0] != output_channels ||
		packed_weights.shape[1] != group_count ||
		packed_weights.shape[2] != packed_group_size ||
		scales_runtime.storage_elements != required_scales) {
		return Status(
			ErrorCode::kShapeMismatch,
			"MatmulNBits weights or scales do not match N and group count");
	}
	if ((packed_weights.storage_type != StorageType::kUInt8 &&
		 packed_weights.storage_type != StorageType::kSInt8) ||
		packed_weights.quantization.enabled) {
		return Status(
			ErrorCode::kUnsupportedType,
			"MatmulNBits packed weights must use raw eight-bit storage");
	}
	const std::size_t zero_bytes_per_row =
		groups / 2U + groups % 2U;
	if (packed_zero_points != NULL) {
		std::size_t required_zeros = 0U;
		if (!detail::checkedMultiply(
				output_width, zero_bytes_per_row, &required_zeros)) {
			return Status(
				ErrorCode::kInvalidArgument,
				"MatmulNBits zero-point count overflow");
		}
		if ((packed_zero_points->storage_type != StorageType::kUInt8 &&
			 packed_zero_points->storage_type != StorageType::kSInt8) ||
			packed_zero_points->quantization.enabled ||
			zeros_runtime.storage_elements != required_zeros) {
			return Status(
				ErrorCode::kShapeMismatch,
				"MatmulNBits packed zero points have an invalid format");
		}
	}
	if (!input.distributions.empty() ||
		!packed_weights.distributions.empty() ||
		!scales.distributions.empty() ||
		(packed_zero_points != NULL &&
		 !packed_zero_points->distributions.empty()) ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable MatmulNBits does not support merged-axis distributions");
	}

	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	std::size_t packed_bytes_per_output = 0U;
	if (!detail::checkedMultiply(
			groups,
			static_cast<std::size_t>(packed_group_size),
			&packed_bytes_per_output)) {
		return Status(
			ErrorCode::kInvalidArgument,
			"MatmulNBits packed weight row size overflow");
	}
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate(input.shape.size(), 0U);
	std::vector<std::size_t> scale_coordinate;
	for (std::size_t output_index = 0U;
		output_index < output_elements;
		++output_index) {
		detail::decodeIndex(output_index, output.shape, &output_coordinate);
		for (std::size_t axis = 0U; axis + 1U < input.shape.size(); ++axis) {
			input_coordinate[axis] = output_coordinate[axis];
		}
		const std::size_t output_channel = output_coordinate.back();
		double accumulator = 0.0;
		for (std::size_t input_channel = 0U;
			input_channel < static_cast<std::size_t>(input_channels);
			++input_channel) {
			input_coordinate.back() = input_channel;
			double input_value = 0.0;
			status = detail::readExpressed(
				input,
				detail::rowMajorIndex(input.shape, input_coordinate),
				input_coordinate,
				&input_value);
			if (!status.ok()) {
				return status;
			}
			const std::size_t group = input_channel / group_width;
			const std::size_t within_group =
				input_channel % group_width;
			const std::size_t packed_index =
				output_channel * packed_bytes_per_output +
				group * static_cast<std::size_t>(packed_group_size) +
				within_group / 2U;
			const uint8_t packed = detail::loadValue<uint8_t>(
				packed_weights.data, packed_index);
			const uint8_t quantized = within_group % 2U == 0U
				? static_cast<uint8_t>(packed & 0x0FU)
				: static_cast<uint8_t>((packed >> 4U) & 0x0FU);
			const std::size_t scale_index =
				output_channel * groups + group;
			detail::decodeIndex(scale_index, scales.shape, &scale_coordinate);
			double scale = 0.0;
			status = detail::readExpressed(
				scales, scale_index, scale_coordinate, &scale);
			if (!status.ok()) {
				return status;
			}
			uint8_t zero_point = 8U;
			if (packed_zero_points != NULL) {
				const std::size_t zero_index =
					output_channel * zero_bytes_per_row + group / 2U;
				const uint8_t packed_zero = detail::loadValue<uint8_t>(
					packed_zero_points->data, zero_index);
				zero_point = group % 2U == 0U
					? static_cast<uint8_t>(packed_zero & 0x0FU)
					: static_cast<uint8_t>((packed_zero >> 4U) & 0x0FU);
			}
			const double weight =
				(static_cast<double>(quantized) -
				 static_cast<double>(zero_point)) * scale;
			accumulator += input_value * weight;
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, accumulator);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status einsum(
	const std::vector<TensorDesc>& inputs,
	TensorDesc& output,
	const std::string& equation) {
	if (inputs.empty()) {
		return Status(
			ErrorCode::kInvalidArgument,
			"Einsum requires at least one input");
	}
	std::vector<detail::RuntimeTensor> input_runtimes(inputs.size());
	Status status;
	for (std::size_t input_number = 0U;
		input_number < inputs.size();
		++input_number) {
		if (inputs[input_number].shape.empty()) {
			return Status(
				ErrorCode::kShapeMismatch,
				"portable Einsum does not support rank-zero tensor descriptors");
		}
		status = detail::validateTensor(
			inputs[input_number], &input_runtimes[input_number]);
		if (!status.ok()) {
			return status;
		}
		if (!inputs[input_number].distributions.empty()) {
			return Status(
				ErrorCode::kInvalidDistribution,
				"portable Einsum does not support merged-axis distributions");
		}
	}
	detail::RuntimeTensor output_runtime;
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable Einsum does not support merged-axis distributions");
	}
	if (output.shape.empty()) {
		return Status(
			ErrorCode::kShapeMismatch,
			"portable Einsum does not support rank-zero tensor descriptors");
	}

	std::string compact;
	compact.reserve(equation.size());
	for (std::size_t i = 0U; i < equation.size(); ++i) {
		if (equation[i] != ' ' && equation[i] != '\t' &&
			equation[i] != '\r' && equation[i] != '\n') {
			compact.push_back(equation[i]);
		}
	}
	const std::size_t arrow = compact.find("->");
	if (arrow != std::string::npos &&
		compact.find("->", arrow + 2U) != std::string::npos) {
		return Status(
			ErrorCode::kInvalidArgument,
			"Einsum equation contains multiple output arrows");
	}
	const std::string lhs = arrow == std::string::npos
		? compact
		: compact.substr(0U, arrow);
	const std::string rhs = arrow == std::string::npos
		? std::string()
		: compact.substr(arrow + 2U);
	std::vector<std::string> operand_texts;
	std::size_t operand_begin = 0U;
	for (std::size_t position = 0U; position <= lhs.size(); ++position) {
		if (position == lhs.size() || lhs[position] == ',') {
			operand_texts.push_back(
				lhs.substr(operand_begin, position - operand_begin));
			operand_begin = position + 1U;
		}
	}
	if (operand_texts.size() != inputs.size()) {
		return Status(
			ErrorCode::kInvalidArgument,
			"Einsum operand count does not match its equation");
	}

	std::vector<detail::EinsumSubscript> parsed(inputs.size());
	std::vector<std::size_t> ellipsis_ranks(inputs.size(), 0U);
	std::size_t maximum_ellipsis_rank = 0U;
	for (std::size_t input_number = 0U;
		input_number < inputs.size();
		++input_number) {
		status = detail::parseEinsumSubscript(
			operand_texts[input_number], &parsed[input_number]);
		if (!status.ok()) {
			return status;
		}
		const std::size_t rank = inputs[input_number].shape.size();
		if ((!parsed[input_number].has_ellipsis &&
			 parsed[input_number].explicit_labels != rank) ||
			(parsed[input_number].has_ellipsis &&
			 parsed[input_number].explicit_labels > rank)) {
			return Status(
				ErrorCode::kShapeMismatch,
				"Einsum subscript count does not match an input rank");
		}
		ellipsis_ranks[input_number] = parsed[input_number].has_ellipsis
			? rank - parsed[input_number].explicit_labels
			: 0U;
		maximum_ellipsis_rank = (std::max)(
			maximum_ellipsis_rank, ellipsis_ranks[input_number]);
	}
	const std::size_t label_count = 26U + maximum_ellipsis_rank;
	std::vector<int64_t> label_extents(label_count, 1);
	std::vector<uint8_t> label_seen(label_count, 0U);
	std::vector<std::size_t> named_occurrences(26U, 0U);
	std::vector<std::vector<std::size_t> > axis_labels(inputs.size());
	for (std::size_t input_number = 0U;
		input_number < inputs.size();
		++input_number) {
		const detail::EinsumSubscript& term = parsed[input_number];
		std::vector<std::size_t>& labels = axis_labels[input_number];
		labels.reserve(inputs[input_number].shape.size());
		std::vector<int64_t> local_named_extents(26U, -1);
		for (std::size_t token_number = 0U;
			token_number < term.tokens.size();
			++token_number) {
			const int token = term.tokens[token_number];
			if (token >= 0) {
				labels.push_back(static_cast<std::size_t>(token));
				++named_occurrences[static_cast<std::size_t>(token)];
				continue;
			}
			const std::size_t ellipsis_rank =
				ellipsis_ranks[input_number];
			const std::size_t leading =
				maximum_ellipsis_rank - ellipsis_rank;
			for (std::size_t ellipsis_axis = 0U;
				ellipsis_axis < ellipsis_rank;
				++ellipsis_axis) {
				labels.push_back(26U + leading + ellipsis_axis);
			}
		}
		if (labels.size() != inputs[input_number].shape.size()) {
			return Status(
				ErrorCode::kShapeMismatch,
				"Einsum ellipsis expansion does not match an input rank");
		}
		for (std::size_t axis = 0U; axis < labels.size(); ++axis) {
			const std::size_t label = labels[axis];
			const int64_t extent = inputs[input_number].shape[axis];
			if (label < 26U) {
				if (local_named_extents[label] >= 0 &&
					local_named_extents[label] != extent) {
					return Status(
						ErrorCode::kShapeMismatch,
						"Einsum repeated labels require equal dimensions");
				}
				local_named_extents[label] = extent;
			}
			if (label_seen[label] != 0U &&
				label_extents[label] != 1 && extent != 1 &&
				label_extents[label] != extent) {
				return Status(
					ErrorCode::kShapeMismatch,
					"Einsum label dimensions are not broadcast-compatible");
			}
			if (label_seen[label] == 0U || label_extents[label] == 1) {
				label_extents[label] = extent;
			}
			label_seen[label] = 1U;
		}
	}

	std::vector<std::size_t> output_labels;
	if (arrow == std::string::npos) {
		for (std::size_t ellipsis_axis = 0U;
			ellipsis_axis < maximum_ellipsis_rank;
			++ellipsis_axis) {
			output_labels.push_back(26U + ellipsis_axis);
		}
		for (std::size_t label = 0U; label < 26U; ++label) {
			if (named_occurrences[label] == 1U) {
				output_labels.push_back(label);
			}
		}
	}
	else {
		detail::EinsumSubscript output_term;
		status = detail::parseEinsumSubscript(rhs, &output_term);
		if (!status.ok()) {
			return status;
		}
		std::vector<uint8_t> output_seen(label_count, 0U);
		for (std::size_t token_number = 0U;
			token_number < output_term.tokens.size();
			++token_number) {
			const int token = output_term.tokens[token_number];
			if (token < 0) {
				for (std::size_t ellipsis_axis = 0U;
					ellipsis_axis < maximum_ellipsis_rank;
					++ellipsis_axis) {
					const std::size_t label = 26U + ellipsis_axis;
					if (output_seen[label] != 0U) {
						return Status(
							ErrorCode::kInvalidArgument,
							"Einsum output contains a duplicate ellipsis label");
					}
					output_seen[label] = 1U;
					output_labels.push_back(label);
				}
				continue;
			}
			const std::size_t label = static_cast<std::size_t>(token);
			if (label_seen[label] == 0U || output_seen[label] != 0U) {
				return Status(
					ErrorCode::kInvalidArgument,
					"Einsum output label is missing from inputs or duplicated");
			}
			output_seen[label] = 1U;
			output_labels.push_back(label);
		}
	}
	if (output.shape.size() != output_labels.size()) {
		return Status(
			ErrorCode::kShapeMismatch,
			"Einsum output rank does not match its equation");
	}
	std::vector<uint8_t> is_output_label(label_count, 0U);
	for (std::size_t output_axis = 0U;
		output_axis < output_labels.size();
		++output_axis) {
		const std::size_t label = output_labels[output_axis];
		if (output.shape[output_axis] != label_extents[label]) {
			return Status(
				ErrorCode::kShapeMismatch,
				"Einsum output shape does not match its labels");
		}
		is_output_label[label] = 1U;
	}
	std::vector<std::size_t> reduction_labels;
	std::vector<int64_t> reduction_shape;
	for (std::size_t label = 0U; label < label_count; ++label) {
		if (label_seen[label] != 0U && is_output_label[label] == 0U) {
			reduction_labels.push_back(label);
			reduction_shape.push_back(label_extents[label]);
		}
	}
	std::size_t reduction_elements = 1U;
	for (std::size_t axis = 0U; axis < reduction_shape.size(); ++axis) {
		if (!detail::checkedMultiply(
				reduction_elements,
				static_cast<std::size_t>(reduction_shape[axis]),
				&reduction_elements)) {
			return Status(
				ErrorCode::kInvalidArgument,
				"Einsum reduction size overflow");
		}
	}
	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> label_coordinate(label_count, 0U);
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> reduction_coordinate;
	std::vector<std::size_t> input_coordinate;
	for (std::size_t output_index = 0U;
		output_index < output_elements;
		++output_index) {
		detail::decodeIndex(
			output_index, output.shape, &output_coordinate);
		for (std::size_t output_axis = 0U;
			output_axis < output_labels.size();
			++output_axis) {
			label_coordinate[output_labels[output_axis]] =
				output_coordinate[output_axis];
		}
		double sum = 0.0;
		for (std::size_t reduction_index = 0U;
			reduction_index < reduction_elements;
			++reduction_index) {
			if (reduction_shape.empty()) {
				reduction_coordinate.clear();
			}
			else {
				detail::decodeIndex(
					reduction_index,
					reduction_shape,
					&reduction_coordinate);
			}
			for (std::size_t reduction_axis = 0U;
				reduction_axis < reduction_labels.size();
				++reduction_axis) {
				label_coordinate[reduction_labels[reduction_axis]] =
					reduction_coordinate[reduction_axis];
			}
			double product = 1.0;
			for (std::size_t input_number = 0U;
				input_number < inputs.size();
				++input_number) {
				input_coordinate.resize(inputs[input_number].shape.size());
				for (std::size_t axis = 0U;
					axis < input_coordinate.size();
					++axis) {
					input_coordinate[axis] =
						inputs[input_number].shape[axis] == 1
						? 0U
						: label_coordinate[axis_labels[input_number][axis]];
				}
				double value = 0.0;
				status = detail::readExpressed(
					inputs[input_number],
					detail::rowMajorIndex(
						inputs[input_number].shape, input_coordinate),
					input_coordinate,
					&value);
				if (!status.ok()) {
					return status;
				}
				product *= value;
			}
			sum += product;
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, sum);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status convolution(
	const TensorDesc& input,
	const TensorDesc& weights,
	const TensorDesc* bias,
	TensorDesc& output,
	const ConvSpec& spec) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor weights_runtime;
	detail::RuntimeTensor bias_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(weights, &weights_runtime);
	if (!status.ok()) {
		return status;
	}
	if (bias != NULL) {
		status = detail::validateTensor(*bias, &bias_runtime);
		if (!status.ok()) {
			return status;
		}
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (!input.distributions.empty() ||
		!weights.distributions.empty() ||
		(bias != NULL && !bias->distributions.empty()) ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable convolution does not yet support merged-axis distributions");
	}

	const std::size_t spatial_rank = spec.stride.size();
	if (spatial_rank == 0U ||
		input.shape.size() != spatial_rank + 2U ||
		weights.shape.size() != spatial_rank + 2U ||
		output.shape.size() != spatial_rank + 2U ||
		spec.pad_before.size() != spatial_rank ||
		spec.pad_after.size() != spatial_rank ||
		spec.dilation.size() != spatial_rank) {
		return Status(
			ErrorCode::kShapeMismatch,
			"convolution rank and parameter counts are inconsistent");
	}
	if (spec.groups <= 0) {
		return Status(
			ErrorCode::kInvalidArgument,
			"convolution groups must be positive");
	}
	const char* activation_layout = spatial_rank == 1U
		? "NLC"
		: (spatial_rank == 2U ? "NHWC" : "NDHWC");
	const char* weights_layout = spatial_rank == 1U
		? "WIO"
		: (spatial_rank == 2U ? "HWIO" : "DHWIO");
	if (spatial_rank > 3U ||
		!detail::layoutEquals(input, activation_layout) ||
		!detail::layoutEquals(output, activation_layout) ||
		!detail::layoutEquals(weights, weights_layout)) {
		return Status(
			ErrorCode::kShapeMismatch,
			"convolution tensor layouts are invalid");
	}

	const int64_t input_channels = input.shape.back();
	const int64_t kernel_input_channels =
		weights.shape[weights.shape.size() - 2U];
	const int64_t output_channels = weights.shape.back();
	if (input_channels != kernel_input_channels * spec.groups ||
		output_channels <= 0 ||
		output_channels % spec.groups != 0 ||
		output.shape.front() != input.shape.front() ||
		output.shape.back() != output_channels) {
		return Status(
			ErrorCode::kShapeMismatch,
			"convolution channel, group, batch, or output metadata is invalid");
	}

	std::vector<int64_t> kernel_shape(spatial_rank, 1);
	for (std::size_t axis = 0U; axis < spatial_rank; ++axis) {
		if (weights.shape[axis] <= 0 ||
			spec.stride[axis] <= 0 ||
			spec.dilation[axis] <= 0 ||
			spec.pad_before[axis] < 0 ||
			spec.pad_after[axis] < 0) {
			return Status(
				ErrorCode::kInvalidArgument,
				"convolution kernel, stride, dilation, or padding is invalid");
		}
		if (spec.padding == PaddingKind::kReflect &&
			(spec.pad_before[axis] >= input.shape[axis + 1U] ||
			 spec.pad_after[axis] >= input.shape[axis + 1U])) {
			return Status(
				ErrorCode::kInvalidArgument,
				"reflection padding must be smaller than its input extent");
		}
		kernel_shape[axis] = weights.shape[axis];
		const int64_t numerator =
			input.shape[axis + 1U] +
			spec.pad_before[axis] +
			spec.pad_after[axis] -
			spec.dilation[axis] * (weights.shape[axis] - 1) -
			1;
		const int64_t expected_extent =
			numerator < 0 ? 0 : numerator / spec.stride[axis] + 1;
		if (output.shape[axis + 1U] != expected_extent) {
			return Status(
				ErrorCode::kShapeMismatch,
				"convolution output spatial shape is invalid");
		}
	}

	std::size_t kernel_elements = 1U;
	for (std::size_t axis = 0U; axis < spatial_rank; ++axis) {
		if (!detail::checkedMultiply(
				kernel_elements,
				static_cast<std::size_t>(kernel_shape[axis]),
				&kernel_elements)) {
			return Status(
				ErrorCode::kInvalidArgument,
				"convolution kernel size overflow");
		}
	}
	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	if (output_elements != output_runtime.storage_elements) {
		return Status(
			ErrorCode::kShapeMismatch,
			"convolution output storage does not match its physical shape");
	}

	const std::size_t channels_per_group =
		static_cast<std::size_t>(kernel_input_channels);
	const std::size_t outputs_per_group =
		static_cast<std::size_t>(output_channels / spec.groups);
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate(input.shape.size(), 0U);
	std::vector<std::size_t> weights_coordinate(
		weights.shape.size(), 0U);
	std::vector<std::size_t> kernel_coordinate;
	for (std::size_t output_index = 0U;
		output_index < output_elements;
		++output_index) {
		detail::decodeIndex(
			output_index, output.shape, &output_coordinate);
		input_coordinate[0] = output_coordinate[0];
		const std::size_t output_channel = output_coordinate.back();
		const std::size_t group = output_channel / outputs_per_group;
		weights_coordinate.back() = output_channel;
		double accumulator = 0.0;
		if (bias != NULL) {
			status = detail::readBroadcastValue(
				*bias,
				bias_runtime,
				output,
				output_coordinate,
				&accumulator);
			if (!status.ok()) {
				return status;
			}
		}

		for (std::size_t kernel_index = 0U;
			kernel_index < kernel_elements;
			++kernel_index) {
			detail::decodeIndex(
				kernel_index, kernel_shape, &kernel_coordinate);
			bool padded_zero = false;
			for (std::size_t axis = 0U; axis < spatial_rank; ++axis) {
				weights_coordinate[axis] = kernel_coordinate[axis];
				const int64_t position =
					static_cast<int64_t>(output_coordinate[axis + 1U]) *
						spec.stride[axis] -
					spec.pad_before[axis] +
					static_cast<int64_t>(kernel_coordinate[axis]) *
						spec.dilation[axis];
				if (!detail::mapPaddedCoordinate(
					position,
					input.shape[axis + 1U],
					spec.padding,
					&input_coordinate[axis + 1U])) {
					padded_zero = true;
					break;
				}
			}
			if (padded_zero) {
				continue;
			}

			for (std::size_t input_channel = 0U;
				input_channel < channels_per_group;
				++input_channel) {
				input_coordinate.back() =
					group * channels_per_group + input_channel;
				weights_coordinate[weights.shape.size() - 2U] =
					input_channel;
				const std::size_t input_index =
					detail::rowMajorIndex(input.shape, input_coordinate);
				const std::size_t weights_index =
					detail::rowMajorIndex(
						weights.shape, weights_coordinate);
				double input_value = 0.0;
				double weights_value = 0.0;
				status = detail::readExpressed(
					input,
					input_index,
					input_coordinate,
					&input_value);
				if (!status.ok()) {
					return status;
				}
				status = detail::readExpressed(
					weights,
					weights_index,
					weights_coordinate,
					&weights_value);
				if (!status.ok()) {
					return status;
				}
				accumulator += input_value * weights_value;
			}
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, accumulator);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status convTranspose(
	const TensorDesc& input,
	const TensorDesc& weights,
	const TensorDesc* bias,
	TensorDesc& output,
	const ConvTransposeSpec& spec) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor weights_runtime;
	detail::RuntimeTensor bias_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(weights, &weights_runtime);
	if (!status.ok()) {
		return status;
	}
	if (bias != NULL) {
		status = detail::validateTensor(*bias, &bias_runtime);
		if (!status.ok()) {
			return status;
		}
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (!input.distributions.empty() ||
		!weights.distributions.empty() ||
		(bias != NULL && !bias->distributions.empty()) ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable transposed convolution does not support merged-axis distributions");
	}

	const std::size_t spatial_rank = spec.stride.size();
	if (spatial_rank == 0U || spatial_rank > 3U ||
		input.shape.size() != spatial_rank + 2U ||
		weights.shape.size() != spatial_rank + 2U ||
		output.shape.size() != spatial_rank + 2U ||
		spec.pad_before.size() != spatial_rank ||
		spec.pad_after.size() != spatial_rank ||
		spec.dilation.size() != spatial_rank ||
		spec.output_padding.size() != spatial_rank ||
		spec.groups <= 0) {
		return Status(
			ErrorCode::kShapeMismatch,
			"transposed convolution rank or parameter counts are inconsistent");
	}
	const char* activation_layout = spatial_rank == 1U
		? "NLC"
		: (spatial_rank == 2U ? "NHWC" : "NDHWC");
	const char* weights_layout = spatial_rank == 1U
		? "WOI"
		: (spatial_rank == 2U ? "HWOI" : "DHWOI");
	if (!detail::layoutEquals(input, activation_layout) ||
		!detail::layoutEquals(output, activation_layout) ||
		!detail::layoutEquals(weights, weights_layout)) {
		return Status(
			ErrorCode::kShapeMismatch,
			"transposed convolution tensor layouts are invalid");
	}
	const int64_t input_channels = input.shape.back();
	const int64_t outputs_per_group =
		weights.shape[weights.shape.size() - 2U];
	if (input_channels <= 0 ||
		weights.shape.back() != input_channels ||
		input_channels % spec.groups != 0 ||
		outputs_per_group <= 0 ||
		outputs_per_group >
			(std::numeric_limits<int64_t>::max)() / spec.groups) {
		return Status(
			ErrorCode::kShapeMismatch,
			"transposed convolution channel or group metadata is invalid");
	}
	const int64_t output_channels = outputs_per_group * spec.groups;
	if (output.shape.front() != input.shape.front() ||
		output.shape.back() != output_channels) {
		return Status(
			ErrorCode::kShapeMismatch,
			"transposed convolution batch or output channels are invalid");
	}
	for (std::size_t axis = 0U; axis < spatial_rank; ++axis) {
		if (spec.output_padding[axis] < 0 ||
			!(spec.output_padding[axis] < spec.stride[axis] ||
			  spec.output_padding[axis] < spec.dilation[axis])) {
			return Status(
				ErrorCode::kInvalidArgument,
				"transposed convolution output padding is invalid");
		}
		int64_t expected_extent = 0;
		if (!detail::convTransposeOutputExtent(
				input.shape[axis + 1U],
				weights.shape[axis],
				spec.stride[axis],
				spec.pad_before[axis],
				spec.pad_after[axis],
				spec.dilation[axis],
				spec.output_padding[axis],
				&expected_extent) ||
			output.shape[axis + 1U] != expected_extent) {
			return Status(
				ErrorCode::kShapeMismatch,
				"transposed convolution output spatial shape is invalid");
		}
	}

	std::vector<int64_t> kernel_shape(
		weights.shape.begin(), weights.shape.begin() + spatial_rank);
	std::size_t kernel_elements = 1U;
	for (std::size_t axis = 0U; axis < spatial_rank; ++axis) {
		if (!detail::checkedMultiply(
				kernel_elements,
				static_cast<std::size_t>(kernel_shape[axis]),
				&kernel_elements)) {
			return Status(
				ErrorCode::kInvalidArgument,
				"transposed convolution kernel size overflow");
		}
	}
	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	const std::size_t inputs_per_group =
		static_cast<std::size_t>(input_channels / spec.groups);
	const std::size_t outputs_per_group_size =
		static_cast<std::size_t>(outputs_per_group);
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate(input.shape.size(), 0U);
	std::vector<std::size_t> weights_coordinate(
		weights.shape.size(), 0U);
	std::vector<std::size_t> kernel_coordinate;
	for (std::size_t output_index = 0U;
		output_index < output_elements;
		++output_index) {
		detail::decodeIndex(
			output_index, output.shape, &output_coordinate);
		const std::size_t output_channel = output_coordinate.back();
		const std::size_t group =
			output_channel / outputs_per_group_size;
		weights_coordinate[weights.shape.size() - 2U] =
			output_channel % outputs_per_group_size;
		input_coordinate[0] = output_coordinate[0];
		double accumulator = 0.0;
		if (bias != NULL) {
			status = detail::readBroadcastValue(
				*bias,
				bias_runtime,
				output,
				output_coordinate,
				&accumulator);
			if (!status.ok()) {
				return status;
			}
		}
		for (std::size_t kernel_index = 0U;
			kernel_index < kernel_elements;
			++kernel_index) {
			detail::decodeIndex(
				kernel_index, kernel_shape, &kernel_coordinate);
			bool contributes = true;
			for (std::size_t axis = 0U;
				axis < spatial_rank;
				++axis) {
				weights_coordinate[axis] = kernel_coordinate[axis];
				const uint64_t target =
					static_cast<uint64_t>(output_coordinate[axis + 1U]) +
					static_cast<uint64_t>(spec.pad_before[axis]);
				const uint64_t kernel_offset =
					static_cast<uint64_t>(kernel_coordinate[axis]) *
					static_cast<uint64_t>(spec.dilation[axis]);
				if (target < kernel_offset) {
					contributes = false;
					break;
				}
				const uint64_t numerator = target - kernel_offset;
				const uint64_t stride =
					static_cast<uint64_t>(spec.stride[axis]);
				if (numerator % stride != 0U) {
					contributes = false;
					break;
				}
				const uint64_t input_position = numerator / stride;
				if (input_position >= static_cast<uint64_t>(
					input.shape[axis + 1U])) {
					contributes = false;
					break;
				}
				input_coordinate[axis + 1U] =
					static_cast<std::size_t>(input_position);
			}
			if (!contributes) {
				continue;
			}
			for (std::size_t group_input = 0U;
				group_input < inputs_per_group;
				++group_input) {
				const std::size_t input_channel =
					group * inputs_per_group + group_input;
				input_coordinate.back() = input_channel;
				weights_coordinate.back() = input_channel;
				double input_value = 0.0;
				double weight_value = 0.0;
				status = detail::readExpressed(
					input,
					detail::rowMajorIndex(
						input.shape, input_coordinate),
					input_coordinate,
					&input_value);
				if (!status.ok()) {
					return status;
				}
				status = detail::readExpressed(
					weights,
					detail::rowMajorIndex(
						weights.shape, weights_coordinate),
					weights_coordinate,
					&weight_value);
				if (!status.ok()) {
					return status;
				}
				accumulator += input_value * weight_value;
			}
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, accumulator);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status pool(
	const TensorDesc& input,
	TensorDesc& output,
	const PoolSpec& spec) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (!input.distributions.empty() || !output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable pooling does not yet support merged-axis distributions");
	}

	const std::size_t spatial_rank = spec.kernel.size();
	if (spatial_rank == 0U ||
		input.shape.size() != spatial_rank + 2U ||
		output.shape.size() != input.shape.size() ||
		spec.stride.size() != spatial_rank ||
		spec.pad_before.size() != spatial_rank ||
		spec.pad_after.size() != spatial_rank ||
		spec.dilation.size() != spatial_rank) {
		return Status(
			ErrorCode::kShapeMismatch,
			"pooling rank and parameter counts are inconsistent");
	}
	if (output.shape.front() != input.shape.front() ||
		output.shape.back() != input.shape.back()) {
		return Status(
			ErrorCode::kShapeMismatch,
			"pooling must preserve batch and channel dimensions");
	}
	const char* activation_layout = spatial_rank == 1U
		? "NLC"
		: (spatial_rank == 2U ? "NHWC" : "NDHWC");
	if (spatial_rank > 3U ||
		!detail::layoutEquals(input, activation_layout) ||
		!detail::layoutEquals(output, activation_layout)) {
		return Status(
			ErrorCode::kShapeMismatch,
			"pooling tensor layouts are invalid");
	}

	std::vector<int64_t> window_shape(spatial_rank, 1);
	for (std::size_t axis = 0U; axis < spatial_rank; ++axis) {
		if (spec.kernel[axis] <= 0 ||
			spec.stride[axis] <= 0 ||
			spec.dilation[axis] <= 0 ||
			spec.pad_before[axis] < 0 ||
			spec.pad_after[axis] < 0) {
			return Status(
				ErrorCode::kInvalidArgument,
				"pooling kernel, stride, dilation, or padding is invalid");
		}
		window_shape[axis] = spec.kernel[axis];
		const int64_t numerator =
			input.shape[axis + 1U] +
			spec.pad_before[axis] +
			spec.pad_after[axis] -
			spec.dilation[axis] * (spec.kernel[axis] - 1) -
			1;
		const int64_t expected_extent =
			numerator < 0 ? 0 : numerator / spec.stride[axis] + 1;
		if (output.shape[axis + 1U] != expected_extent) {
			return Status(
				ErrorCode::kShapeMismatch,
				"pooling output spatial shape is invalid");
		}
	}
	if (spec.divisor_override < 0) {
		return Status(
			ErrorCode::kInvalidArgument,
			"pooling divisor override cannot be negative");
	}

	std::size_t window_elements = 1U;
	for (std::size_t axis = 0U; axis < spatial_rank; ++axis) {
		if (!detail::checkedMultiply(
				window_elements,
				static_cast<std::size_t>(spec.kernel[axis]),
				&window_elements)) {
			return Status(
				ErrorCode::kInvalidArgument,
				"pooling window size overflow");
		}
	}

	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate(input.shape.size(), 0U);
	std::vector<std::size_t> window_coordinate;
	for (std::size_t output_index = 0U;
		output_index < output_elements;
		++output_index) {
		detail::decodeIndex(
			output_index, output.shape, &output_coordinate);
		input_coordinate[0] = output_coordinate[0];
		input_coordinate.back() = output_coordinate.back();
		double accumulator = 0.0;
		std::size_t valid_samples = 0U;
		bool initialized = false;

		for (std::size_t window_index = 0U;
			window_index < window_elements;
			++window_index) {
			detail::decodeIndex(
				window_index, window_shape, &window_coordinate);
			bool valid = true;
			for (std::size_t axis = 0U; axis < spatial_rank; ++axis) {
				const int64_t position =
					static_cast<int64_t>(output_coordinate[axis + 1U]) *
						spec.stride[axis] -
					spec.pad_before[axis] +
					static_cast<int64_t>(window_coordinate[axis]) *
						spec.dilation[axis];
				if (position < 0 || position >= input.shape[axis + 1U]) {
					valid = false;
					break;
				}
				input_coordinate[axis + 1U] =
					static_cast<std::size_t>(position);
			}
			if (!valid) {
				continue;
			}

			const std::size_t input_index =
				detail::rowMajorIndex(input.shape, input_coordinate);
			double value = 0.0;
			status = detail::readExpressed(
				input, input_index, input_coordinate, &value);
			if (!status.ok()) {
				return status;
			}
			if (spec.kind == PoolKind::kMaximum) {
				if (!initialized ||
					(std::isnan(value) && !std::isnan(accumulator)) ||
					value > accumulator) {
					accumulator = value;
				}
				initialized = true;
			}
			else {
				accumulator += value;
			}
			++valid_samples;
		}

		if (spec.kind == PoolKind::kMaximum) {
			if (!initialized) {
				return Status(
					ErrorCode::kInvalidArgument,
					"max pooling window contains no input samples");
			}
		}
		else {
			const std::size_t divisor = spec.divisor_override > 0
				? static_cast<std::size_t>(spec.divisor_override)
				: (spec.count_include_pad
					? window_elements
					: valid_samples);
			if (divisor == 0U) {
				return Status(
					ErrorCode::kInvalidArgument,
					"average pooling divisor is zero");
			}
			accumulator /= static_cast<double>(divisor);
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, accumulator);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status resize2d(
	const TensorDesc& input,
	TensorDesc& output,
	ResizeKind kind,
	bool align_corners) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (input.shape.size() != 4U ||
		output.shape.size() != 4U ||
		input.shape[0] != output.shape[0] ||
		input.shape[3] != output.shape[3] ||
		input.layout != std::vector<char>{'N', 'H', 'W', 'C'} ||
		output.layout != std::vector<char>{'N', 'H', 'W', 'C'}) {
		return Status(
			ErrorCode::kShapeMismatch,
			"resize2d expects NHWC tensors with preserved batch and channels");
	}
	if (kind != ResizeKind::kNearest &&
		kind != ResizeKind::kLinear &&
		kind != ResizeKind::kCubic) {
		return Status(
			ErrorCode::kInvalidArgument,
			"resize2d interpolation kind is invalid");
	}
	if (!input.distributions.empty() || !output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable resize does not support merged-axis distributions");
	}
	const std::size_t input_height =
		static_cast<std::size_t>(input.shape[1]);
	const std::size_t input_width =
		static_cast<std::size_t>(input.shape[2]);
	const std::size_t output_height =
		static_cast<std::size_t>(output.shape[1]);
	const std::size_t output_width =
		static_cast<std::size_t>(output.shape[2]);
	if (input_height == 0U || input_width == 0U ||
		output_height == 0U || output_width == 0U) {
		return Status(
			ErrorCode::kInvalidArgument,
			"resize2d spatial dimensions must be nonzero");
	}

	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate(4U, 0U);
	for (std::size_t output_index = 0U;
		output_index < output_elements;
		++output_index) {
		detail::decodeIndex(
			output_index, output.shape, &output_coordinate);
		input_coordinate[0] = output_coordinate[0];
		input_coordinate[3] = output_coordinate[3];
		double result = 0.0;
		if (kind == ResizeKind::kNearest) {
			input_coordinate[1] =
				(output_coordinate[1] * input_height) / output_height;
			input_coordinate[2] =
				(output_coordinate[2] * input_width) / output_width;
			status = detail::readExpressed(
				input,
				detail::rowMajorIndex(input.shape, input_coordinate),
				input_coordinate,
				&result);
			if (!status.ok()) {
				return status;
			}
		}
		else if (kind == ResizeKind::kLinear) {
			const double source_y = detail::resizeCoordinate(
				output_coordinate[1],
				input_height,
				output_height,
				align_corners);
			const double source_x = detail::resizeCoordinate(
				output_coordinate[2],
				input_width,
				output_width,
				align_corners);
			int64_t y0 = static_cast<int64_t>(std::floor(source_y));
			int64_t x0 = static_cast<int64_t>(std::floor(source_x));
			double y_weight = source_y - static_cast<double>(y0);
			double x_weight = source_x - static_cast<double>(x0);
			if (y0 < 0) {
				y0 = 0;
				y_weight = 0.0;
			}
			else if (y0 >= static_cast<int64_t>(input_height) - 1) {
				y0 = static_cast<int64_t>(input_height) - 1;
				y_weight = 0.0;
			}
			if (x0 < 0) {
				x0 = 0;
				x_weight = 0.0;
			}
			else if (x0 >= static_cast<int64_t>(input_width) - 1) {
				x0 = static_cast<int64_t>(input_width) - 1;
				x_weight = 0.0;
			}
			const std::size_t y1 = (std::min)(
				static_cast<std::size_t>(y0 + 1), input_height - 1U);
			const std::size_t x1 = (std::min)(
				static_cast<std::size_t>(x0 + 1), input_width - 1U);
			const std::size_t ys[2] = {
				static_cast<std::size_t>(y0), y1
			};
			const std::size_t xs[2] = {
				static_cast<std::size_t>(x0), x1
			};
			const double y_weights[2] = {
				1.0 - y_weight, y_weight
			};
			const double x_weights[2] = {
				1.0 - x_weight, x_weight
			};
			for (std::size_t yi = 0U; yi < 2U; ++yi) {
				for (std::size_t xi = 0U; xi < 2U; ++xi) {
					input_coordinate[1] = ys[yi];
					input_coordinate[2] = xs[xi];
					double value = 0.0;
					status = detail::readExpressed(
						input,
						detail::rowMajorIndex(
							input.shape, input_coordinate),
						input_coordinate,
						&value);
					if (!status.ok()) {
						return status;
					}
					result +=
						value * y_weights[yi] * x_weights[xi];
				}
			}
		}
		else {
			const double source_y = detail::resizeCoordinate(
				output_coordinate[1],
				input_height,
				output_height,
				align_corners);
			const double source_x = detail::resizeCoordinate(
				output_coordinate[2],
				input_width,
				output_width,
				align_corners);
			const int64_t base_y =
				static_cast<int64_t>(std::floor(source_y));
			const int64_t base_x =
				static_cast<int64_t>(std::floor(source_x));
			for (int64_t yi = -1; yi <= 2; ++yi) {
				const int64_t unclamped_y = base_y + yi;
				const int64_t clamped_y = (std::max)(
					int64_t(0),
					(std::min)(
						unclamped_y,
						static_cast<int64_t>(input_height) - 1));
				const double y_weight = detail::cubicWeight(
					source_y - static_cast<double>(unclamped_y));
				for (int64_t xi = -1; xi <= 2; ++xi) {
					const int64_t unclamped_x = base_x + xi;
					const int64_t clamped_x = (std::max)(
						int64_t(0),
						(std::min)(
							unclamped_x,
							static_cast<int64_t>(input_width) - 1));
					const double x_weight = detail::cubicWeight(
						source_x - static_cast<double>(unclamped_x));
					input_coordinate[1] =
						static_cast<std::size_t>(clamped_y);
					input_coordinate[2] =
						static_cast<std::size_t>(clamped_x);
					double value = 0.0;
					status = detail::readExpressed(
						input,
						detail::rowMajorIndex(
							input.shape, input_coordinate),
						input_coordinate,
						&value);
					if (!status.ok()) {
						return status;
					}
					result += value * y_weight * x_weight;
				}
			}
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, result);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status resize2d(
	const TensorDesc& input,
	TensorDesc& output,
	bool linear) {
	return resize2d(
		input,
		output,
		linear ? ResizeKind::kLinear : ResizeKind::kNearest,
		false);
}

inline Status gridSample2d(
	const TensorDesc& input,
	const TensorDesc& grid,
	TensorDesc& output,
	const GridSampleSpec& spec) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor grid_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(grid, &grid_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (input.shape.size() != 4U || grid.shape.size() != 4U ||
		output.shape.size() != 4U ||
		!detail::layoutEquals(input, "NHWC") ||
		!detail::layoutEquals(grid, "NHWC") ||
		!detail::layoutEquals(output, "NHWC") ||
		input.shape[0] != grid.shape[0] ||
		output.shape[0] != input.shape[0] ||
		output.shape[1] != grid.shape[1] ||
		output.shape[2] != grid.shape[2] ||
		output.shape[3] != input.shape[3] ||
		grid.shape[3] < 2) {
		return Status(
			ErrorCode::kShapeMismatch,
			"GridNSample input, grid, or output shape is invalid");
	}
	if ((spec.interpolation_mode != 0 &&
		 spec.interpolation_mode != 1) ||
		(spec.padding_mode < 0 || spec.padding_mode > 2) ||
		!std::isfinite(spec.scale_height) ||
		!std::isfinite(spec.scale_width)) {
		return Status(
			ErrorCode::kInvalidArgument,
			"GridNSample interpolation, padding, or scale is invalid");
	}
	if (!input.distributions.empty() ||
		!grid.distributions.empty() ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable GridNSample does not support merged-axis distributions");
	}
	const std::size_t input_height =
		static_cast<std::size_t>(input.shape[1]);
	const std::size_t input_width =
		static_cast<std::size_t>(input.shape[2]);
	if (input_height == 0U || input_width == 0U) {
		return Status(
			ErrorCode::kInvalidArgument,
			"GridNSample input spatial dimensions must be nonzero");
	}

	std::vector<std::size_t> input_coordinate(4U, 0U);
	auto sample = [&input, &input_coordinate, &status, &spec](
		std::size_t batch,
		int64_t y,
		int64_t x,
		std::size_t channel,
		double* value) -> Status {
		const int64_t height = input.shape[1];
		const int64_t width = input.shape[2];
		if (spec.padding_mode == 0 &&
			(y < 0 || y >= height || x < 0 || x >= width)) {
			*value = 0.0;
			return Status();
		}
		if (spec.padding_mode == 1) {
			y = (std::max)(int64_t(0), (std::min)(y, height - 1));
			x = (std::max)(int64_t(0), (std::min)(x, width - 1));
		}
		else if (spec.padding_mode == 2) {
			std::size_t mapped_y = 0U;
			std::size_t mapped_x = 0U;
			if (!detail::mapPaddedCoordinate(
					y, height, PaddingKind::kReflect, &mapped_y) ||
				!detail::mapPaddedCoordinate(
					x, width, PaddingKind::kReflect, &mapped_x)) {
				return Status(
					ErrorCode::kInvalidArgument,
					"GridNSample reflection padding is invalid");
			}
			y = static_cast<int64_t>(mapped_y);
			x = static_cast<int64_t>(mapped_x);
		}
		input_coordinate[0] = batch;
		input_coordinate[1] = static_cast<std::size_t>(y);
		input_coordinate[2] = static_cast<std::size_t>(x);
		input_coordinate[3] = channel;
		status = detail::readExpressed(
			input,
			detail::rowMajorIndex(input.shape, input_coordinate),
			input_coordinate,
			value);
		return status;
	};

	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> grid_coordinate(4U, 0U);
	for (std::size_t output_index = 0U;
		output_index < output_elements;
		++output_index) {
		detail::decodeIndex(
			output_index, output.shape, &output_coordinate);
		grid_coordinate[0] = output_coordinate[0];
		grid_coordinate[1] = output_coordinate[1];
		grid_coordinate[2] = output_coordinate[2];
		grid_coordinate[3] = 0U;
		double grid_x = 0.0;
		status = detail::readExpressed(
			grid,
			detail::rowMajorIndex(grid.shape, grid_coordinate),
			grid_coordinate,
			&grid_x);
		if (!status.ok()) {
			return status;
		}
		grid_coordinate[3] = 1U;
		double grid_y = 0.0;
		status = detail::readExpressed(
			grid,
			detail::rowMajorIndex(grid.shape, grid_coordinate),
			grid_coordinate,
			&grid_y);
		if (!status.ok()) {
			return status;
		}
		if (!std::isfinite(grid_x) || !std::isfinite(grid_y)) {
			return Status(
				ErrorCode::kInvalidArgument,
				"GridNSample grid contains a non-finite coordinate");
		}
		double source_x = detail::gridSourceCoordinate(
			grid_x,
			spec.scale_width,
			spec.grid_divisor_width,
			input_width,
			spec.align_corners);
		double source_y = detail::gridSourceCoordinate(
			grid_y,
			spec.scale_height,
			spec.grid_divisor_height,
			input_height,
			spec.align_corners);
		if (spec.padding_mode == 1) {
			source_x = (std::max)(
				0.0,
				(std::min)(source_x, static_cast<double>(input_width - 1U)));
			source_y = (std::max)(
				0.0,
				(std::min)(source_y, static_cast<double>(input_height - 1U)));
		}
		else if (spec.padding_mode == 2) {
			source_x = detail::reflectGridCoordinate(
				source_x, input_width, spec.align_corners);
			source_y = detail::reflectGridCoordinate(
				source_y, input_height, spec.align_corners);
			source_x = (std::max)(
				0.0,
				(std::min)(source_x, static_cast<double>(input_width - 1U)));
			source_y = (std::max)(
				0.0,
				(std::min)(source_y, static_cast<double>(input_height - 1U)));
		}
		double result = 0.0;
		const long double minimum_index = static_cast<long double>(
			(std::numeric_limits<int64_t>::min)());
		const long double maximum_index = static_cast<long double>(
			(std::numeric_limits<int64_t>::max)()) -
			(spec.interpolation_mode == 0 ? 1.0L : 0.0L);
		const long double extended_x = static_cast<long double>(source_x);
		const long double extended_y = static_cast<long double>(source_y);
		if (extended_x >= minimum_index && extended_x <= maximum_index &&
			extended_y >= minimum_index && extended_y <= maximum_index) {
			if (spec.interpolation_mode == 1) {
				const int64_t nearest_x = static_cast<int64_t>(
					roundValue(
						source_x, RoundingMode::kNearestEven));
				const int64_t nearest_y = static_cast<int64_t>(
					roundValue(
						source_y, RoundingMode::kNearestEven));
				status = sample(
					output_coordinate[0],
					nearest_y,
					nearest_x,
					output_coordinate[3],
					&result);
				if (!status.ok()) {
					return status;
				}
			}
			else {
				const int64_t y0 =
					static_cast<int64_t>(std::floor(source_y));
				const int64_t x0 =
					static_cast<int64_t>(std::floor(source_x));
				const double y_weight = source_y - static_cast<double>(y0);
				const double x_weight = source_x - static_cast<double>(x0);
				for (std::size_t yi = 0U; yi < 2U; ++yi) {
					for (std::size_t xi = 0U; xi < 2U; ++xi) {
						double value = 0.0;
						status = sample(
							output_coordinate[0],
							y0 + static_cast<int64_t>(yi),
							x0 + static_cast<int64_t>(xi),
							output_coordinate[3],
							&value);
						if (!status.ok()) {
							return status;
						}
						const double wy = yi == 0U
							? 1.0 - y_weight
							: y_weight;
						const double wx = xi == 0U
							? 1.0 - x_weight
							: x_weight;
						result += value * wy * wx;
					}
				}
			}
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, result);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status causalMask(
	const TensorDesc& input,
	const TensorDesc& config,
	TensorDesc& output,
	int64_t prefill_max,
	double fill_value) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor config_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(config, &config_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (input.shape.size() != 3U || output.shape.size() != 3U ||
		prefill_max <= 0 ||
		output.shape[0] != input.shape[0] ||
		output.shape[2] != prefill_max ||
		(output.shape[1] != 1 && output.shape[1] != prefill_max)) {
		return Status(
			ErrorCode::kShapeMismatch,
			"CausalMask input or output shape is invalid");
	}
	std::size_t required_config = 0U;
	if (!detail::checkedMultiply(
			static_cast<std::size_t>(input.shape[0]), 3U, &required_config) ||
		config_runtime.storage_elements < required_config) {
		return Status(
			ErrorCode::kShapeMismatch,
			"CausalMask dynamic configuration is too small");
	}
	if (!input.distributions.empty() ||
		!config.distributions.empty() ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable CausalMask does not support merged-axis distributions");
	}
	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> coordinate;
	for (std::size_t index = 0U; index < output_elements; ++index) {
		detail::decodeIndex(index, output.shape, &coordinate);
		status = detail::writeExpressed(
			output, index, coordinate, fill_value);
		if (!status.ok()) {
			return status;
		}
	}
	const std::size_t rows = static_cast<std::size_t>(output.shape[1]);
	const std::size_t width = static_cast<std::size_t>(prefill_max);
	for (std::size_t batch = 0U;
		batch < static_cast<std::size_t>(input.shape[0]);
		++batch) {
		int64_t token_length = 0;
		int64_t token_index = 0;
		int64_t history_length = 0;
		status = detail::readIndex(config, batch * 3U, &token_length);
		if (status.ok()) {
			status = detail::readIndex(
				config, batch * 3U + 1U, &token_index);
		}
		if (status.ok()) {
			status = detail::readIndex(
				config, batch * 3U + 2U, &history_length);
		}
		if (!status.ok()) {
			return status;
		}
		if (token_length < 0 || token_index < 0 || history_length < 0 ||
			history_length > prefill_max ||
			token_length > prefill_max - history_length) {
			return Status(
				ErrorCode::kInvalidArgument,
				"CausalMask dynamic lengths are invalid");
		}
		if (token_index == 0) {
			if (rows != width) {
				return Status(
					ErrorCode::kShapeMismatch,
					"CausalMask prefill output must be square");
			}
			for (std::size_t query = 0U;
				query < static_cast<std::size_t>(token_length);
				++query) {
				const std::size_t visible =
					static_cast<std::size_t>(history_length) + query + 1U;
				for (std::size_t key = 0U; key < visible; ++key) {
					coordinate = { batch, query, key };
					status = detail::writeExpressed(
						output,
						detail::rowMajorIndex(output.shape, coordinate),
						coordinate,
						0.0);
					if (!status.ok()) {
						return status;
					}
				}
			}
			for (std::size_t query = 0U; query < rows; ++query) {
				coordinate = { batch, query, 0U };
				status = detail::writeExpressed(
					output,
					detail::rowMajorIndex(output.shape, coordinate),
					coordinate,
					0.0);
				if (!status.ok()) {
					return status;
				}
			}
		}
		else {
			if (rows != 1U || token_index > prefill_max ||
				token_length > prefill_max - token_index) {
				return Status(
					ErrorCode::kShapeMismatch,
					"CausalMask decoder output or token index is invalid");
			}
			const std::size_t visible =
				static_cast<std::size_t>(token_length + token_index);
			for (std::size_t key = 0U; key < visible; ++key) {
				coordinate = { batch, 0U, key };
				status = detail::writeExpressed(
					output,
					detail::rowMajorIndex(output.shape, coordinate),
					coordinate,
					0.0);
				if (!status.ok()) {
					return status;
				}
			}
		}
	}
	return Status();
}

inline Status ropeDynamic(
	const TensorDesc& input,
	const TensorDesc& config,
	const TensorDesc& cosine_cache,
	const TensorDesc& sine_cache,
	TensorDesc& output,
	int64_t prefill_max) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor config_runtime;
	detail::RuntimeTensor cosine_runtime;
	detail::RuntimeTensor sine_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(config, &config_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(cosine_cache, &cosine_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(sine_cache, &sine_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	const bool prefill = input.shape.size() == 3U && input.shape[1] > 1;
	if (input.shape.size() != 3U ||
		cosine_cache.shape.size() != 2U ||
		sine_cache.shape != cosine_cache.shape ||
		output.shape.size() != 4U ||
		prefill_max <= 0 ||
		cosine_cache.shape[0] < prefill_max ||
		output.shape[0] != input.shape[0] ||
		output.shape[1] != 2 ||
		output.shape[2] != (prefill ? prefill_max : 1) ||
		output.shape[3] != cosine_cache.shape[1]) {
		return Status(
			ErrorCode::kShapeMismatch,
			"RopeDynamic input, cache, or output shape is invalid");
	}
	std::size_t required_config = 0U;
	if (!detail::checkedMultiply(
			static_cast<std::size_t>(input.shape[0]), 3U, &required_config) ||
		config_runtime.storage_elements < required_config) {
		return Status(
			ErrorCode::kShapeMismatch,
			"RopeDynamic dynamic configuration is too small");
	}
	if (!input.distributions.empty() ||
		!config.distributions.empty() ||
		!cosine_cache.distributions.empty() ||
		!sine_cache.distributions.empty() ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable RopeDynamic does not support merged-axis distributions");
	}
	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> coordinate;
	for (std::size_t index = 0U; index < output_elements; ++index) {
		detail::decodeIndex(index, output.shape, &coordinate);
		status = detail::writeExpressed(output, index, coordinate, 0.0);
		if (!status.ok()) {
			return status;
		}
	}
	std::vector<std::size_t> cache_coordinate(2U, 0U);
	std::vector<std::size_t> output_coordinate(4U, 0U);
	for (std::size_t batch = 0U;
		batch < static_cast<std::size_t>(input.shape[0]);
		++batch) {
		int64_t token_length = 0;
		int64_t token_index = 0;
		int64_t history_length = 0;
		status = detail::readIndex(config, batch * 3U, &token_length);
		if (status.ok()) {
			status = detail::readIndex(config, batch * 3U + 1U, &token_index);
		}
		if (status.ok()) {
			status = detail::readIndex(config, batch * 3U + 2U, &history_length);
		}
		if (!status.ok()) {
			return status;
		}
		if (token_length < 0 || token_index < 0 || history_length < 0) {
			return Status(
				ErrorCode::kInvalidArgument,
				"RopeDynamic configuration contains negative lengths");
		}
		std::size_t cache_begin = 0U;
		std::size_t copy_length = 0U;
		if (prefill) {
			if (token_index != 0 || token_length > input.shape[1] ||
				history_length > cosine_cache.shape[0] ||
				token_length > cosine_cache.shape[0] - history_length ||
				token_length > prefill_max) {
				return Status(
					ErrorCode::kInvalidArgument,
					"RopeDynamic prefill configuration exceeds the cache");
			}
			cache_begin = static_cast<std::size_t>(history_length);
			copy_length = static_cast<std::size_t>(token_length);
		}
		else {
			if (token_index == 0 || token_index > cosine_cache.shape[0] ||
				token_length > cosine_cache.shape[0] - token_index) {
				return Status(
					ErrorCode::kInvalidArgument,
					"RopeDynamic decoder position exceeds the cache");
			}
			cache_begin = static_cast<std::size_t>(
				token_length + token_index - 1);
			copy_length = 1U;
		}
		for (std::size_t token = 0U; token < copy_length; ++token) {
			for (std::size_t channel = 0U;
				channel < static_cast<std::size_t>(cosine_cache.shape[1]);
				++channel) {
				cache_coordinate = { cache_begin + token, channel };
				double cosine = 0.0;
				double sine = 0.0;
				status = detail::readExpressed(
					cosine_cache,
					detail::rowMajorIndex(
						cosine_cache.shape, cache_coordinate),
					cache_coordinate,
					&cosine);
				if (status.ok()) {
					status = detail::readExpressed(
						sine_cache,
						detail::rowMajorIndex(
							sine_cache.shape, cache_coordinate),
						cache_coordinate,
						&sine);
				}
				if (!status.ok()) {
					return status;
				}
				output_coordinate = { batch, 0U, token, channel };
				status = detail::writeExpressed(
					output,
					detail::rowMajorIndex(output.shape, output_coordinate),
					output_coordinate,
					cosine);
				if (status.ok()) {
					output_coordinate[1] = 1U;
					status = detail::writeExpressed(
						output,
						detail::rowMajorIndex(output.shape, output_coordinate),
						output_coordinate,
						sine);
				}
				if (!status.ok()) {
					return status;
				}
			}
		}
	}
	return Status();
}

inline Status sliceDynamic(
	const TensorDesc& input,
	const TensorDesc& config,
	const TensorDesc& cache,
	TensorDesc& output,
	int64_t prefill_max) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor config_runtime;
	detail::RuntimeTensor cache_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(config, &config_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(cache, &cache_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (input.shape.size() != 4U || cache.shape.size() != 4U ||
		output.shape != cache.shape || output.layout != cache.layout ||
		input.shape[0] != cache.shape[0] ||
		input.shape[1] != cache.shape[1] ||
		input.shape[3] != cache.shape[3] ||
		prefill_max <= 0 || cache.shape[2] != prefill_max) {
		return Status(
			ErrorCode::kShapeMismatch,
			"SliceDynamic input, cache, or output shape is invalid");
	}
	std::size_t required_config = 0U;
	if (!detail::checkedMultiply(
			static_cast<std::size_t>(input.shape[0]), 3U, &required_config) ||
		config_runtime.storage_elements < required_config) {
		return Status(
			ErrorCode::kShapeMismatch,
			"SliceDynamic configuration is too small");
	}
	if (!input.distributions.empty() ||
		!config.distributions.empty() ||
		!cache.distributions.empty() ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable SliceDynamic does not support merged-axis distributions");
	}
	status = linearCopy(cache, output);
	if (!status.ok()) {
		return status;
	}
	const std::size_t batches = static_cast<std::size_t>(input.shape[0]);
	const std::size_t heads = static_cast<std::size_t>(input.shape[1]);
	const std::size_t sequence = static_cast<std::size_t>(input.shape[2]);
	const std::size_t width = static_cast<std::size_t>(input.shape[3]);
	std::vector<std::size_t> input_coordinate(4U, 0U);
	std::vector<std::size_t> output_coordinate(4U, 0U);
	for (std::size_t batch = 0U; batch < batches; ++batch) {
		int64_t token_length = 0;
		int64_t token_index = 0;
		int64_t history_length = 0;
		status = detail::readIndex(config, batch * 3U, &token_length);
		if (status.ok()) {
			status = detail::readIndex(
				config, batch * 3U + 1U, &token_index);
		}
		if (status.ok()) {
			status = detail::readIndex(
				config, batch * 3U + 2U, &history_length);
		}
		if (!status.ok()) {
			return status;
		}
		if (token_length < 0 || token_index < 0 || history_length < 0 ||
			history_length > prefill_max) {
			return Status(
				ErrorCode::kInvalidArgument,
				"SliceDynamic configuration contains invalid lengths");
		}
		std::size_t source_count = 0U;
		std::size_t destination_begin = 0U;
		if (token_index == 0) {
			if (static_cast<uint64_t>(token_length) > sequence ||
				token_length > prefill_max - history_length) {
				return Status(
					ErrorCode::kInvalidArgument,
					"SliceDynamic prefill lengths exceed the tensors");
			}
			source_count = static_cast<std::size_t>(token_length);
			destination_begin = static_cast<std::size_t>(history_length);
		}
		else {
			if (sequence == 0U || token_index > prefill_max ||
				token_length > prefill_max - token_index) {
				return Status(
					ErrorCode::kInvalidArgument,
					"SliceDynamic decoder position exceeds the cache");
			}
			source_count = 1U;
			destination_begin =
				static_cast<std::size_t>(token_length + token_index - 1);
		}
		const std::size_t valid_end = destination_begin + source_count;
		for (std::size_t head = 0U; head < heads; ++head) {
			for (std::size_t token = 0U; token < source_count; ++token) {
				for (std::size_t channel = 0U; channel < width; ++channel) {
					input_coordinate = { batch, head, token, channel };
					output_coordinate = {
						batch, head, destination_begin + token, channel
					};
					double value = 0.0;
					status = detail::readExpressed(
						input,
						detail::rowMajorIndex(input.shape, input_coordinate),
						input_coordinate,
						&value);
					if (!status.ok()) {
						return status;
					}
					status = detail::writeExpressed(
						output,
						detail::rowMajorIndex(output.shape, output_coordinate),
						output_coordinate,
						value);
					if (!status.ok()) {
						return status;
					}
				}
			}
			for (std::size_t token = valid_end;
				token < static_cast<std::size_t>(prefill_max);
				++token) {
				for (std::size_t channel = 0U; channel < width; ++channel) {
					output_coordinate = { batch, head, token, channel };
					status = detail::writeExpressed(
						output,
						detail::rowMajorIndex(output.shape, output_coordinate),
						output_coordinate,
						0.0);
					if (!status.ok()) {
						return status;
					}
				}
			}
		}
	}
	return Status();
}

inline Status unfold(
	const TensorDesc& input,
	TensorDesc& output,
	const UnfoldSpec& spec) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (input.shape.size() != 4U ||
		output.shape.size() != 3U ||
		input.layout != std::vector<char>{'N', 'H', 'W', 'C'} ||
		output.layout != std::vector<char>{'N', 'L', 'C'}) {
		return Status(
			ErrorCode::kShapeMismatch,
			"Unfold expects NHWC input and NLC output tensors");
	}
	if (spec.kernel_height <= 0 || spec.kernel_width <= 0 ||
		spec.stride_height <= 0 || spec.stride_width <= 0 ||
		spec.dilation_height <= 0 || spec.dilation_width <= 0 ||
		spec.pad_top < 0 || spec.pad_bottom < 0 ||
		spec.pad_left < 0 || spec.pad_right < 0) {
		return Status(
			ErrorCode::kInvalidArgument,
			"Unfold kernel, stride, dilation, and padding are invalid");
	}
	if (!input.distributions.empty() || !output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable Unfold does not support merged-axis distributions");
	}

	const uint64_t maximum = static_cast<uint64_t>(
		(std::numeric_limits<int64_t>::max)());
	const uint64_t kernel_height =
		static_cast<uint64_t>(spec.kernel_height);
	const uint64_t kernel_width =
		static_cast<uint64_t>(spec.kernel_width);
	const uint64_t dilation_height =
		static_cast<uint64_t>(spec.dilation_height);
	const uint64_t dilation_width =
		static_cast<uint64_t>(spec.dilation_width);
	if ((kernel_height - 1U) > (maximum - 1U) / dilation_height ||
		(kernel_width - 1U) > (maximum - 1U) / dilation_width) {
		return Status(
			ErrorCode::kInvalidArgument,
			"Unfold effective kernel extent overflow");
	}
	const uint64_t effective_height =
		dilation_height * (kernel_height - 1U) + 1U;
	const uint64_t effective_width =
		dilation_width * (kernel_width - 1U) + 1U;
	const uint64_t input_height = static_cast<uint64_t>(input.shape[1]);
	const uint64_t input_width = static_cast<uint64_t>(input.shape[2]);
	const uint64_t vertical_padding =
		static_cast<uint64_t>(spec.pad_top) +
		static_cast<uint64_t>(spec.pad_bottom);
	const uint64_t horizontal_padding =
		static_cast<uint64_t>(spec.pad_left) +
		static_cast<uint64_t>(spec.pad_right);
	if (vertical_padding > maximum - input_height ||
		horizontal_padding > maximum - input_width) {
		return Status(
			ErrorCode::kInvalidArgument,
			"Unfold padded input extent overflow");
	}
	const uint64_t padded_height = input_height + vertical_padding;
	const uint64_t padded_width = input_width + horizontal_padding;
	const uint64_t output_height = padded_height < effective_height
		? 0U
		: (padded_height - effective_height) /
			static_cast<uint64_t>(spec.stride_height) + 1U;
	const uint64_t output_width = padded_width < effective_width
		? 0U
		: (padded_width - effective_width) /
			static_cast<uint64_t>(spec.stride_width) + 1U;
	std::size_t locations = 0U;
	std::size_t kernel_area = 0U;
	std::size_t output_channels = 0U;
	if (output_height > static_cast<uint64_t>(
			(std::numeric_limits<std::size_t>::max)()) ||
		output_width > static_cast<uint64_t>(
			(std::numeric_limits<std::size_t>::max)()) ||
		!detail::checkedMultiply(
			static_cast<std::size_t>(output_height),
			static_cast<std::size_t>(output_width),
			&locations) ||
		!detail::checkedMultiply(
			static_cast<std::size_t>(spec.kernel_height),
			static_cast<std::size_t>(spec.kernel_width),
			&kernel_area) ||
		!detail::checkedMultiply(
			static_cast<std::size_t>(input.shape[3]),
			kernel_area,
			&output_channels) ||
		locations > static_cast<std::size_t>(
			(std::numeric_limits<int64_t>::max)()) ||
		output_channels > static_cast<std::size_t>(
			(std::numeric_limits<int64_t>::max)())) {
		return Status(
			ErrorCode::kInvalidArgument,
			"Unfold output shape overflow");
	}
	if (output.shape[0] != input.shape[0] ||
		output.shape[1] != static_cast<int64_t>(locations) ||
		output.shape[2] != static_cast<int64_t>(output_channels)) {
		return Status(
			ErrorCode::kShapeMismatch,
			"Unfold output shape is invalid");
	}

	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	const std::size_t channels =
		static_cast<std::size_t>(input.shape[3]);
	const std::size_t kernel_width_size =
		static_cast<std::size_t>(spec.kernel_width);
	const std::size_t output_width_size =
		static_cast<std::size_t>(output_width);
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate(4U, 0U);
	for (std::size_t output_index = 0U;
		output_index < output_elements;
		++output_index) {
		detail::decodeIndex(
			output_index, output.shape, &output_coordinate);
		const std::size_t location = output_coordinate[1];
		const std::size_t output_y = output_width_size == 0U
			? 0U
			: location / output_width_size;
		const std::size_t output_x = output_width_size == 0U
			? 0U
			: location % output_width_size;
		const std::size_t combined_channel = output_coordinate[2];
		const std::size_t channel = combined_channel / kernel_area;
		const std::size_t kernel_offset = combined_channel % kernel_area;
		const std::size_t kernel_y = kernel_offset / kernel_width_size;
		const std::size_t kernel_x = kernel_offset % kernel_width_size;
		const int64_t input_y =
			static_cast<int64_t>(output_y) * spec.stride_height -
			spec.pad_top +
			static_cast<int64_t>(kernel_y) * spec.dilation_height;
		const int64_t input_x =
			static_cast<int64_t>(output_x) * spec.stride_width -
			spec.pad_left +
			static_cast<int64_t>(kernel_x) * spec.dilation_width;
		double value = 0.0;
		if (input_y >= 0 && input_y < input.shape[1] &&
			input_x >= 0 && input_x < input.shape[2]) {
			input_coordinate[0] = output_coordinate[0];
			input_coordinate[1] = static_cast<std::size_t>(input_y);
			input_coordinate[2] = static_cast<std::size_t>(input_x);
			input_coordinate[3] = channel;
			status = detail::readExpressed(
				input,
				detail::rowMajorIndex(input.shape, input_coordinate),
				input_coordinate,
				&value);
			if (!status.ok()) {
				return status;
			}
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, value);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status concatenate(
	const std::vector<TensorDesc>& inputs,
	TensorDesc& output,
	int64_t axis) {
	if (inputs.empty()) {
		return Status(
			ErrorCode::kInvalidArgument,
			"concatenate requires at least one input");
	}
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	std::size_t normalized_axis = 0U;
	if (!detail::normalizeAxis(axis, output.shape.size(), &normalized_axis) ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidArgument,
			"concatenate axis or output distribution is invalid");
	}
	std::vector<detail::RuntimeTensor> runtimes(inputs.size());
	int64_t concatenated_extent = 0;
	for (std::size_t input_index = 0U;
		input_index < inputs.size();
		++input_index) {
		status = detail::validateTensor(
			inputs[input_index], &runtimes[input_index]);
		if (!status.ok()) {
			return status;
		}
		if (!inputs[input_index].distributions.empty() ||
			inputs[input_index].shape.size() != output.shape.size()) {
			return Status(
				ErrorCode::kShapeMismatch,
				"concatenate input rank or distribution is invalid");
		}
		for (std::size_t current_axis = 0U;
			current_axis < output.shape.size();
			++current_axis) {
			if (current_axis != normalized_axis &&
				inputs[input_index].shape[current_axis] !=
					output.shape[current_axis]) {
				return Status(
					ErrorCode::kShapeMismatch,
					"concatenate non-axis dimensions must match");
			}
		}
		concatenated_extent +=
			inputs[input_index].shape[normalized_axis];
	}
	if (concatenated_extent != output.shape[normalized_axis]) {
		return Status(
			ErrorCode::kShapeMismatch,
			"concatenate output axis extent is invalid");
	}

	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate;
	for (std::size_t output_index = 0U;
		output_index < output_elements;
		++output_index) {
		detail::decodeIndex(
			output_index, output.shape, &output_coordinate);
		const std::size_t axis_coordinate =
			output_coordinate[normalized_axis];
		std::size_t offset = 0U;
		std::size_t selected = inputs.size();
		for (std::size_t input_index = 0U;
			input_index < inputs.size();
			++input_index) {
			const std::size_t extent = static_cast<std::size_t>(
				inputs[input_index].shape[normalized_axis]);
			if (axis_coordinate < offset + extent) {
				selected = input_index;
				break;
			}
			offset += extent;
		}
		if (selected == inputs.size()) {
			return Status(
				ErrorCode::kShapeMismatch,
				"concatenate coordinate is outside all inputs");
		}
		input_coordinate = output_coordinate;
		input_coordinate[normalized_axis] -= offset;
		double value = 0.0;
		status = detail::readExpressed(
			inputs[selected],
			detail::rowMajorIndex(
				inputs[selected].shape, input_coordinate),
			input_coordinate,
			&value);
		if (!status.ok()) {
			return status;
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, value);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status split(
	const TensorDesc& input,
	const std::vector<TensorDesc*>& outputs,
	const std::vector<int64_t>& sections,
	int64_t axis) {
	detail::RuntimeTensor input_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	std::size_t normalized_axis = 0U;
	if (outputs.empty() ||
		outputs.size() != sections.size() ||
		!detail::normalizeAxis(axis, input.shape.size(), &normalized_axis) ||
		!input.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidArgument,
			"split outputs, sections, axis, or distribution is invalid");
	}
	int64_t total_extent = 0;
	for (std::size_t output_index = 0U;
		output_index < outputs.size();
		++output_index) {
		if (outputs[output_index] == NULL || sections[output_index] < 0) {
			return Status(
				ErrorCode::kInvalidArgument,
				"split output or section is invalid");
		}
		detail::RuntimeTensor output_runtime;
		status = detail::validateTensor(
			*outputs[output_index], &output_runtime);
		if (!status.ok()) {
			return status;
		}
		if (!outputs[output_index]->distributions.empty() ||
			outputs[output_index]->shape.size() != input.shape.size()) {
			return Status(
				ErrorCode::kShapeMismatch,
				"split output rank or distribution is invalid");
		}
		for (std::size_t current_axis = 0U;
			current_axis < input.shape.size();
			++current_axis) {
			const int64_t expected = current_axis == normalized_axis
				? sections[output_index]
				: input.shape[current_axis];
			if (outputs[output_index]->shape[current_axis] != expected) {
				return Status(
					ErrorCode::kShapeMismatch,
					"split output shape does not match its section");
			}
		}
		total_extent += sections[output_index];
	}
	if (total_extent != input.shape[normalized_axis]) {
		return Status(
			ErrorCode::kShapeMismatch,
			"split sections do not cover the input axis");
	}

	std::size_t axis_offset = 0U;
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate;
	for (std::size_t output_number = 0U;
		output_number < outputs.size();
		++output_number) {
		std::size_t output_elements = 0U;
		status = detail::physicalElementCount(
			*outputs[output_number], &output_elements);
		if (!status.ok()) {
			return status;
		}
		for (std::size_t output_index = 0U;
			output_index < output_elements;
			++output_index) {
			detail::decodeIndex(
				output_index,
				outputs[output_number]->shape,
				&output_coordinate);
			input_coordinate = output_coordinate;
			input_coordinate[normalized_axis] += axis_offset;
			double value = 0.0;
			status = detail::readExpressed(
				input,
				detail::rowMajorIndex(input.shape, input_coordinate),
				input_coordinate,
				&value);
			if (!status.ok()) {
				return status;
			}
			status = detail::writeExpressed(
				*outputs[output_number],
				output_index,
				output_coordinate,
				value);
			if (!status.ok()) {
				return status;
			}
		}
		axis_offset +=
			static_cast<std::size_t>(sections[output_number]);
	}
	return Status();
}

inline Status gather(
	const TensorDesc& input,
	const TensorDesc& indices,
	TensorDesc& output,
	int64_t axis) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor indices_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(indices, &indices_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	std::size_t normalized_axis = 0U;
	if (!detail::normalizeAxis(axis, input.shape.size(), &normalized_axis)) {
		return Status(ErrorCode::kInvalidArgument, "gather axis is invalid");
	}
	if (!input.distributions.empty() ||
		!indices.distributions.empty() ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable gather does not support merged-axis distributions");
	}

	std::vector<int64_t> expected_shape;
	expected_shape.insert(
		expected_shape.end(),
		input.shape.begin(),
		input.shape.begin() + normalized_axis);
	expected_shape.insert(
		expected_shape.end(), indices.shape.begin(), indices.shape.end());
	expected_shape.insert(
		expected_shape.end(),
		input.shape.begin() + normalized_axis + 1U,
		input.shape.end());
	if (output.shape != expected_shape) {
		return Status(
			ErrorCode::kShapeMismatch,
			"gather output shape is invalid");
	}

	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate(input.shape.size(), 0U);
	std::vector<std::size_t> indices_coordinate(indices.shape.size(), 0U);
	for (std::size_t output_index = 0U;
		output_index < output_elements;
		++output_index) {
		detail::decodeIndex(
			output_index, output.shape, &output_coordinate);
		for (std::size_t input_axis = 0U;
			input_axis < normalized_axis;
			++input_axis) {
			input_coordinate[input_axis] = output_coordinate[input_axis];
		}
		for (std::size_t index_axis = 0U;
			index_axis < indices.shape.size();
			++index_axis) {
			indices_coordinate[index_axis] =
				output_coordinate[normalized_axis + index_axis];
		}
		for (std::size_t input_axis = normalized_axis + 1U;
			input_axis < input.shape.size();
			++input_axis) {
			input_coordinate[input_axis] = output_coordinate[
				input_axis - 1U + indices.shape.size()];
		}
		int64_t selected = 0;
		status = detail::readIndex(
			indices,
			detail::rowMajorIndex(indices.shape, indices_coordinate),
			&selected);
		if (!status.ok()) {
			return status;
		}
		const int64_t axis_extent = input.shape[normalized_axis];
		if (selected < 0) {
			selected += axis_extent;
		}
		if (selected < 0 || selected >= axis_extent) {
			return Status(
				ErrorCode::kInvalidArgument,
				"gather index is outside the selected axis");
		}
		input_coordinate[normalized_axis] =
			static_cast<std::size_t>(selected);
		double value = 0.0;
		status = detail::readExpressed(
			input,
			detail::rowMajorIndex(input.shape, input_coordinate),
			input_coordinate,
			&value);
		if (!status.ok()) {
			return status;
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, value);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status gatherElements(
	const TensorDesc& input,
	const TensorDesc& indices,
	TensorDesc& output,
	int64_t axis) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor indices_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(indices, &indices_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	std::size_t normalized_axis = 0U;
	if (!detail::normalizeAxis(axis, input.shape.size(), &normalized_axis) ||
		indices.shape != output.shape ||
		indices.shape.size() != input.shape.size()) {
		return Status(
			ErrorCode::kShapeMismatch,
			"GatherElements ranks, output shape, or axis is invalid");
	}
	for (std::size_t current_axis = 0U;
		current_axis < input.shape.size();
		++current_axis) {
		if (current_axis != normalized_axis &&
			input.shape[current_axis] != indices.shape[current_axis]) {
			return Status(
				ErrorCode::kShapeMismatch,
				"GatherElements non-axis dimensions must match");
		}
	}
	if (!input.distributions.empty() ||
		!indices.distributions.empty() ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable GatherElements does not support merged-axis distributions");
	}

	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> coordinate;
	std::vector<std::size_t> input_coordinate;
	for (std::size_t output_index = 0U;
		output_index < output_elements;
		++output_index) {
		detail::decodeIndex(output_index, output.shape, &coordinate);
		int64_t selected = 0;
		status = detail::readIndex(indices, output_index, &selected);
		if (!status.ok()) {
			return status;
		}
		const int64_t axis_extent = input.shape[normalized_axis];
		if (selected < 0) {
			selected += axis_extent;
		}
		if (selected < 0 || selected >= axis_extent) {
			return Status(
				ErrorCode::kInvalidArgument,
				"GatherElements index is outside the selected axis");
		}
		input_coordinate = coordinate;
		input_coordinate[normalized_axis] =
			static_cast<std::size_t>(selected);
		double value = 0.0;
		status = detail::readExpressed(
			input,
			detail::rowMajorIndex(input.shape, input_coordinate),
			input_coordinate,
			&value);
		if (!status.ok()) {
			return status;
		}
		status = detail::writeExpressed(
			output, output_index, coordinate, value);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status indexSelect(
	const TensorDesc& input,
	const TensorDesc& indices,
	TensorDesc& output,
	int64_t axis) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor indices_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(indices, &indices_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	std::size_t normalized_axis = 0U;
	if (input.shape.empty() || indices.shape.size() != 1U ||
		output.shape.size() != input.shape.size() ||
		input.layout != output.layout ||
		!detail::normalizeAxis(axis, input.shape.size(), &normalized_axis)) {
		return Status(
			ErrorCode::kShapeMismatch,
			"IndexSelect rank, axis, or layout is invalid");
	}
	for (std::size_t dimension = 0U;
		dimension < input.shape.size();
		++dimension) {
		const int64_t expected = dimension == normalized_axis
			? indices.shape[0]
			: input.shape[dimension];
		if (output.shape[dimension] != expected) {
			return Status(
				ErrorCode::kShapeMismatch,
				"IndexSelect output shape does not match its index count");
		}
	}
	if (!input.distributions.empty() ||
		!indices.distributions.empty() ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable IndexSelect does not support merged-axis distributions");
	}
	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate(input.shape.size(), 0U);
	for (std::size_t output_index = 0U;
		output_index < output_elements;
		++output_index) {
		detail::decodeIndex(output_index, output.shape, &output_coordinate);
		int64_t selected = 0;
		status = detail::readIndex(
			indices, output_coordinate[normalized_axis], &selected);
		if (!status.ok()) {
			return status;
		}
		if (selected < 0 || selected >= input.shape[normalized_axis]) {
			return Status(
				ErrorCode::kInvalidArgument,
				"IndexSelect index is outside the selected axis");
		}
		input_coordinate = output_coordinate;
		input_coordinate[normalized_axis] = static_cast<std::size_t>(selected);
		double value = 0.0;
		status = detail::readExpressed(
			input,
			detail::rowMajorIndex(input.shape, input_coordinate),
			input_coordinate,
			&value);
		if (!status.ok()) {
			return status;
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, value);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status slice(
	const TensorDesc& input,
	TensorDesc& output,
	const std::vector<int64_t>& begin,
	const std::vector<int64_t>& end,
	const std::vector<int64_t>& stride) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	const std::size_t rank = input.shape.size();
	if (output.shape.size() != rank ||
		begin.size() != rank ||
		end.size() != rank ||
		stride.size() != rank ||
		input.layout != output.layout) {
		return Status(
			ErrorCode::kShapeMismatch,
			"Slice rank, attributes, or layout are inconsistent");
	}
	if (!input.distributions.empty() || !output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable Slice does not support merged-axis distributions");
	}
	std::vector<std::size_t> starts(rank, 0U);
	std::vector<std::size_t> steps(rank, 1U);
	for (std::size_t axis = 0U; axis < rank; ++axis) {
		if (stride[axis] <= 0) {
			return Status(
				ErrorCode::kInvalidArgument,
				"Slice stride must be positive");
		}
		const int64_t extent = input.shape[axis];
		const int64_t start = (std::max)(
			int64_t(0), (std::min)(begin[axis], extent));
		const int64_t limit = (std::max)(
			int64_t(0), (std::min)(end[axis], extent));
		const int64_t expected = limit <= start
			? 0
			: 1 + (limit - start - 1) / stride[axis];
		if (output.shape[axis] != expected) {
			return Status(
				ErrorCode::kShapeMismatch,
				"Slice output shape does not match begin, end, and stride");
		}
		starts[axis] = static_cast<std::size_t>(start);
		steps[axis] = static_cast<std::size_t>(stride[axis]);
	}

	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate(rank, 0U);
	for (std::size_t output_index = 0U;
		output_index < output_elements;
		++output_index) {
		detail::decodeIndex(
			output_index, output.shape, &output_coordinate);
		for (std::size_t axis = 0U; axis < rank; ++axis) {
			input_coordinate[axis] =
				starts[axis] + output_coordinate[axis] * steps[axis];
		}
		double value = 0.0;
		status = detail::readExpressed(
			input,
			detail::rowMajorIndex(input.shape, input_coordinate),
			input_coordinate,
			&value);
		if (!status.ok()) {
			return status;
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, value);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status update(
	const TensorDesc& data,
	const TensorDesc& updates,
	TensorDesc& output,
	const std::vector<int64_t>& begin,
	const std::vector<int64_t>& end,
	const std::vector<int64_t>& stride) {
	detail::RuntimeTensor data_runtime;
	detail::RuntimeTensor updates_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(data, &data_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(updates, &updates_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	const std::size_t rank = data.shape.size();
	if (rank == 0U || output.shape != data.shape ||
		output.layout != data.layout || updates.shape.size() != rank ||
		begin.size() != rank || end.size() != rank || stride.size() != rank) {
		return Status(
			ErrorCode::kShapeMismatch,
			"Update rank, attributes, data, or output shape is inconsistent");
	}
	if (!data.distributions.empty() ||
		!updates.distributions.empty() ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable Update does not support merged-axis distributions");
	}
	std::vector<std::size_t> starts(rank, 0U);
	std::vector<std::size_t> steps(rank, 1U);
	for (std::size_t axis = 0U; axis < rank; ++axis) {
		if (stride[axis] <= 0) {
			return Status(
				ErrorCode::kInvalidArgument,
				"Update stride must be positive");
		}
		const int64_t extent = data.shape[axis];
		const int64_t start = (std::max)(
			int64_t(0), (std::min)(begin[axis], extent));
		const int64_t limit = (std::max)(
			int64_t(0), (std::min)(end[axis], extent));
		const int64_t expected = limit <= start
			? 0
			: 1 + (limit - start - 1) / stride[axis];
		if (updates.shape[axis] != expected) {
			return Status(
				ErrorCode::kShapeMismatch,
				"Update source shape does not match the selected slice");
		}
		starts[axis] = static_cast<std::size_t>(start);
		steps[axis] = static_cast<std::size_t>(stride[axis]);
	}
	status = linearCopy(data, output);
	if (!status.ok()) {
		return status;
	}
	std::size_t update_elements = 0U;
	status = detail::physicalElementCount(updates, &update_elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> update_coordinate;
	std::vector<std::size_t> output_coordinate(rank, 0U);
	for (std::size_t update_index = 0U;
		update_index < update_elements;
		++update_index) {
		detail::decodeIndex(
			update_index, updates.shape, &update_coordinate);
		for (std::size_t axis = 0U; axis < rank; ++axis) {
			output_coordinate[axis] =
				starts[axis] + update_coordinate[axis] * steps[axis];
		}
		double value = 0.0;
		status = detail::readExpressed(
			updates, update_index, update_coordinate, &value);
		if (!status.ok()) {
			return status;
		}
		status = detail::writeExpressed(
			output,
			detail::rowMajorIndex(output.shape, output_coordinate),
			output_coordinate,
			value);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status embedding(
	const TensorDesc& indices,
	const TensorDesc& weights,
	TensorDesc& output) {
	detail::RuntimeTensor indices_runtime;
	detail::RuntimeTensor weights_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(indices, &indices_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(weights, &weights_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (indices.shape.empty() ||
		weights.shape.size() != 2U ||
		output.shape.size() != indices.shape.size() + 1U) {
		return Status(
			ErrorCode::kShapeMismatch,
			"Embedding expects rank-two weights and one appended output axis");
	}
	for (std::size_t axis = 0U; axis < indices.shape.size(); ++axis) {
		if (output.shape[axis] != indices.shape[axis]) {
			return Status(
				ErrorCode::kShapeMismatch,
				"Embedding output prefix does not match the indices shape");
		}
	}
	if (output.shape.back() != weights.shape.back()) {
		return Status(
			ErrorCode::kShapeMismatch,
			"Embedding output width does not match its weights");
	}
	if (!indices.distributions.empty() ||
		!weights.distributions.empty() ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable Embedding does not support merged-axis distributions");
	}

	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	const std::size_t embedding_width =
		static_cast<std::size_t>(weights.shape[1]);
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> indices_coordinate(indices.shape.size(), 0U);
	std::vector<std::size_t> weights_coordinate(2U, 0U);
	for (std::size_t output_index = 0U;
		output_index < output_elements;
		++output_index) {
		detail::decodeIndex(
			output_index, output.shape, &output_coordinate);
		for (std::size_t axis = 0U;
			axis < indices.shape.size();
			++axis) {
			indices_coordinate[axis] = output_coordinate[axis];
		}
		const std::size_t indices_index = indices.shape.empty()
			? 0U
			: detail::rowMajorIndex(indices.shape, indices_coordinate);
		int64_t selected = 0;
		status = detail::readIndex(indices, indices_index, &selected);
		if (!status.ok()) {
			return status;
		}
		if (selected < 0 || selected >= weights.shape[0]) {
			return Status(
				ErrorCode::kInvalidArgument,
				"Embedding index is outside the weights table");
		}
		weights_coordinate[0] = static_cast<std::size_t>(selected);
		weights_coordinate[1] = embedding_width == 0U
			? 0U
			: output_coordinate.back();
		double value = 0.0;
		status = detail::readExpressed(
			weights,
			detail::rowMajorIndex(weights.shape, weights_coordinate),
			weights_coordinate,
			&value);
		if (!status.ok()) {
			return status;
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, value);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status topK(
	const TensorDesc& input,
	const TensorDesc& k_tensor,
	TensorDesc& values,
	TensorDesc& indices,
	int64_t axis,
	bool largest,
	bool sorted) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor k_runtime;
	detail::RuntimeTensor values_runtime;
	detail::RuntimeTensor indices_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(k_tensor, &k_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(values, &values_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(indices, &indices_runtime);
	if (!status.ok()) {
		return status;
	}
	std::size_t normalized_axis = 0U;
	if (input.shape.empty() ||
		!detail::normalizeAxis(axis, input.shape.size(), &normalized_axis) ||
		values.shape != indices.shape ||
		values.shape.size() != input.shape.size() ||
		input.layout != values.layout ||
		values.layout != indices.layout) {
		return Status(
			ErrorCode::kShapeMismatch,
			"TopK rank, axis, output shapes, or layouts are inconsistent");
	}
	if (k_runtime.storage_elements == 0U) {
		return Status(
			ErrorCode::kInvalidArgument,
			"TopK k tensor must contain at least one element");
	}
	int64_t k_value = 0;
	status = detail::readIndex(k_tensor, 0U, &k_value);
	if (!status.ok()) {
		return status;
	}
	if (k_value <= 0 || k_value > input.shape[normalized_axis]) {
		return Status(
			ErrorCode::kInvalidArgument,
			"TopK k is outside the selected axis");
	}
	for (std::size_t current_axis = 0U;
		current_axis < input.shape.size();
		++current_axis) {
		const int64_t expected = current_axis == normalized_axis
			? k_value
			: input.shape[current_axis];
		if (values.shape[current_axis] != expected) {
			return Status(
				ErrorCode::kShapeMismatch,
				"TopK output shape does not match k and axis");
		}
	}
	if (!input.distributions.empty() ||
		!k_tensor.distributions.empty() ||
		!values.distributions.empty() ||
		!indices.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable TopK does not support merged-axis distributions");
	}
	if (indices.quantization.enabled) {
		return Status(
			ErrorCode::kInvalidQuantization,
			"TopK indices output cannot be quantized");
	}

	struct RankedValue {
		double value;
		std::size_t index;
	};
	const std::size_t axis_extent =
		static_cast<std::size_t>(input.shape[normalized_axis]);
	const std::size_t selected_count =
		static_cast<std::size_t>(k_value);
	std::size_t input_elements = 0U;
	status = detail::physicalElementCount(input, &input_elements);
	if (!status.ok()) {
		return status;
	}
	const std::size_t group_count = input_elements / axis_extent;
	std::vector<int64_t> outer_shape = input.shape;
	outer_shape.erase(outer_shape.begin() + normalized_axis);
	std::vector<std::size_t> outer_coordinate;
	std::vector<std::size_t> coordinate(input.shape.size(), 0U);
	std::vector<RankedValue> ranked(axis_extent);
	for (std::size_t group = 0U; group < group_count; ++group) {
		if (outer_shape.empty()) {
			outer_coordinate.clear();
		}
		else {
			detail::decodeIndex(group, outer_shape, &outer_coordinate);
		}
		for (std::size_t current_axis = 0U, outer_axis = 0U;
			current_axis < coordinate.size();
			++current_axis) {
			if (current_axis == normalized_axis) {
				continue;
			}
			coordinate[current_axis] = outer_coordinate[outer_axis++];
		}
		for (std::size_t selected = 0U;
			selected < axis_extent;
			++selected) {
			coordinate[normalized_axis] = selected;
			double value = 0.0;
			status = detail::readExpressed(
				input,
				detail::rowMajorIndex(input.shape, coordinate),
				coordinate,
				&value);
			if (!status.ok()) {
				return status;
			}
			ranked[selected].value = value;
			ranked[selected].index = selected;
		}
		std::stable_sort(
			ranked.begin(),
			ranked.end(),
			[largest](const RankedValue& lhs, const RankedValue& rhs) {
				const bool lhs_nan = std::isnan(lhs.value);
				const bool rhs_nan = std::isnan(rhs.value);
				if (lhs_nan != rhs_nan) {
					return largest ? lhs_nan : !lhs_nan;
				}
				if (!lhs_nan && lhs.value != rhs.value) {
					return largest
						? lhs.value > rhs.value
						: lhs.value < rhs.value;
				}
				return lhs.index < rhs.index;
			});
		if (!sorted) {
			std::sort(
				ranked.begin(),
				ranked.begin() + selected_count,
				[](const RankedValue& lhs, const RankedValue& rhs) {
					return lhs.index < rhs.index;
				});
		}
		for (std::size_t selected = 0U;
			selected < selected_count;
			++selected) {
			coordinate[normalized_axis] = selected;
			const std::size_t output_index =
				detail::rowMajorIndex(values.shape, coordinate);
			status = detail::writeExpressed(
				values,
				output_index,
				coordinate,
				ranked[selected].value);
			if (!status.ok()) {
				return status;
			}
			status = detail::writeExpressed(
				indices,
				output_index,
				coordinate,
				static_cast<double>(ranked[selected].index));
			if (!status.ok()) {
				return status;
			}
		}
	}
	return Status();
}

inline Status scatterElement(
	const TensorDesc& data,
	const TensorDesc& indices,
	const TensorDesc& updates,
	TensorDesc& output,
	int64_t axis,
	ScatterReduction reduction) {
	detail::RuntimeTensor data_runtime;
	detail::RuntimeTensor indices_runtime;
	detail::RuntimeTensor updates_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(data, &data_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(indices, &indices_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(updates, &updates_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	std::size_t normalized_axis = 0U;
	if (!detail::normalizeAxis(axis, data.shape.size(), &normalized_axis) ||
		data.shape != output.shape ||
		data.layout != output.layout ||
		indices.shape != updates.shape ||
		indices.shape.size() != data.shape.size() ||
		!detail::validScatterReduction(reduction)) {
		return Status(
			ErrorCode::kShapeMismatch,
			"ScatterElement ranks, shapes, layouts, axis, or reduction are invalid");
	}
	for (std::size_t current_axis = 0U;
		current_axis < data.shape.size();
		++current_axis) {
		if (current_axis != normalized_axis &&
			indices.shape[current_axis] > data.shape[current_axis]) {
			return Status(
				ErrorCode::kShapeMismatch,
				"ScatterElement non-axis extent exceeds data extent");
		}
	}
	if (!data.distributions.empty() ||
		!indices.distributions.empty() ||
		!updates.distributions.empty() ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable ScatterElement does not support merged-axis distributions");
	}
	std::vector<double> accumulated;
	status = detail::loadDenseExpressedValues(data, &accumulated);
	if (!status.ok()) {
		return status;
	}
	std::size_t update_elements = 0U;
	status = detail::physicalElementCount(updates, &update_elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> update_coordinate;
	std::vector<std::size_t> output_coordinate;
	for (std::size_t update_index = 0U;
		update_index < update_elements;
		++update_index) {
		detail::decodeIndex(
			update_index, updates.shape, &update_coordinate);
		int64_t selected = 0;
		status = detail::readIndex(indices, update_index, &selected);
		if (!status.ok()) {
			return status;
		}
		const int64_t extent = data.shape[normalized_axis];
		if (selected < 0) {
			selected += extent;
		}
		if (selected < 0 || selected >= extent) {
			return Status(
				ErrorCode::kInvalidArgument,
				"ScatterElement index is outside the selected axis");
		}
		output_coordinate = update_coordinate;
		output_coordinate[normalized_axis] =
			static_cast<std::size_t>(selected);
		const std::size_t output_index =
			detail::rowMajorIndex(output.shape, output_coordinate);
		double update_value = 0.0;
		status = detail::readExpressed(
			updates, update_index, update_coordinate, &update_value);
		if (!status.ok()) {
			return status;
		}
		accumulated[output_index] = detail::applyScatterReduction(
			reduction, accumulated[output_index], update_value);
	}
	return detail::storeDenseExpressedValues(output, accumulated);
}

inline Status scatterND(
	const TensorDesc& data,
	const TensorDesc& indices,
	const TensorDesc& updates,
	TensorDesc& output,
	ScatterReduction reduction) {
	detail::RuntimeTensor data_runtime;
	detail::RuntimeTensor indices_runtime;
	detail::RuntimeTensor updates_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(data, &data_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(indices, &indices_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(updates, &updates_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (indices.shape.empty() ||
		indices.shape.back() <= 0 ||
		static_cast<std::size_t>(indices.shape.back()) > data.shape.size() ||
		data.shape != output.shape ||
		data.layout != output.layout ||
		!detail::validScatterReduction(reduction)) {
		return Status(
			ErrorCode::kShapeMismatch,
			"ScatterND data, indices, output, or reduction metadata is invalid");
	}
	const std::size_t index_depth =
		static_cast<std::size_t>(indices.shape.back());
	const std::size_t prefix_rank = indices.shape.size() - 1U;
	if (updates.shape.size() !=
		prefix_rank + data.shape.size() - index_depth) {
		return Status(
			ErrorCode::kShapeMismatch,
			"ScatterND updates rank is invalid");
	}
	for (std::size_t axis = 0U; axis < prefix_rank; ++axis) {
		if (updates.shape[axis] != indices.shape[axis]) {
			return Status(
				ErrorCode::kShapeMismatch,
				"ScatterND updates prefix is invalid");
		}
	}
	for (std::size_t data_axis = index_depth;
		data_axis < data.shape.size();
		++data_axis) {
		const std::size_t update_axis =
			prefix_rank + data_axis - index_depth;
		if (updates.shape[update_axis] != data.shape[data_axis]) {
			return Status(
				ErrorCode::kShapeMismatch,
				"ScatterND updates suffix is invalid");
		}
	}
	if (!data.distributions.empty() ||
		!indices.distributions.empty() ||
		!updates.distributions.empty() ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable ScatterND does not support merged-axis distributions");
	}
	std::vector<double> accumulated;
	status = detail::loadDenseExpressedValues(data, &accumulated);
	if (!status.ok()) {
		return status;
	}
	std::size_t update_elements = 0U;
	status = detail::physicalElementCount(updates, &update_elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> update_coordinate;
	std::vector<std::size_t> index_coordinate(indices.shape.size(), 0U);
	std::vector<std::size_t> output_coordinate(data.shape.size(), 0U);
	for (std::size_t update_index = 0U;
		update_index < update_elements;
		++update_index) {
		detail::decodeIndex(
			update_index, updates.shape, &update_coordinate);
		for (std::size_t prefix_axis = 0U;
			prefix_axis < prefix_rank;
			++prefix_axis) {
			index_coordinate[prefix_axis] = update_coordinate[prefix_axis];
		}
		for (std::size_t indexed_axis = 0U;
			indexed_axis < index_depth;
			++indexed_axis) {
			index_coordinate.back() = indexed_axis;
			int64_t selected = 0;
			status = detail::readIndex(
				indices,
				detail::rowMajorIndex(indices.shape, index_coordinate),
				&selected);
			if (!status.ok()) {
				return status;
			}
			const int64_t extent = data.shape[indexed_axis];
			if (selected < 0) {
				selected += extent;
			}
			if (selected < 0 || selected >= extent) {
				return Status(
					ErrorCode::kInvalidArgument,
					"ScatterND index is outside the data shape");
			}
			output_coordinate[indexed_axis] =
				static_cast<std::size_t>(selected);
		}
		for (std::size_t data_axis = index_depth;
			data_axis < data.shape.size();
			++data_axis) {
			output_coordinate[data_axis] = update_coordinate[
				prefix_rank + data_axis - index_depth];
		}
		const std::size_t output_index =
			detail::rowMajorIndex(output.shape, output_coordinate);
		double update_value = 0.0;
		status = detail::readExpressed(
			updates, update_index, update_coordinate, &update_value);
		if (!status.ok()) {
			return status;
		}
		accumulated[output_index] = detail::applyScatterReduction(
			reduction, accumulated[output_index], update_value);
	}
	return detail::storeDenseExpressedValues(output, accumulated);
}

inline Status tile(
	const TensorDesc& input,
	TensorDesc& output,
	const std::vector<int64_t>& repetitions) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (!input.distributions.empty() || !output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable Tile does not support merged-axis distributions");
	}
	const std::size_t output_rank =
		(std::max)(input.shape.size(), repetitions.size());
	if (output.shape.size() != output_rank) {
		return Status(
			ErrorCode::kShapeMismatch,
			"Tile output rank is invalid");
	}
	const std::size_t input_leading = output_rank - input.shape.size();
	const std::size_t repetition_leading =
		output_rank - repetitions.size();
	for (std::size_t axis = 0U; axis < output_rank; ++axis) {
		const int64_t input_extent = axis < input_leading
			? 1
			: input.shape[axis - input_leading];
		const int64_t repeat = axis < repetition_leading
			? 1
			: repetitions[axis - repetition_leading];
		if (repeat < 0 || output.shape[axis] != input_extent * repeat) {
			return Status(
				ErrorCode::kShapeMismatch,
				"Tile output shape or repetitions are invalid");
		}
	}
	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate(input.shape.size(), 0U);
	for (std::size_t output_index = 0U;
		output_index < output_elements;
		++output_index) {
		detail::decodeIndex(
			output_index, output.shape, &output_coordinate);
		for (std::size_t input_axis = 0U;
			input_axis < input.shape.size();
			++input_axis) {
			const std::size_t output_axis =
				input_leading + input_axis;
			const std::size_t extent =
				static_cast<std::size_t>(input.shape[input_axis]);
			if (extent == 0U) {
				return Status(
					ErrorCode::kInvalidArgument,
					"Tile cannot repeat an empty input dimension");
			}
			input_coordinate[input_axis] =
				output_coordinate[output_axis] % extent;
		}
		double value = 0.0;
		status = detail::readExpressed(
			input,
			detail::rowMajorIndex(input.shape, input_coordinate),
			input_coordinate,
			&value);
		if (!status.ok()) {
			return status;
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, value);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status pad(
	const TensorDesc& input,
	TensorDesc& output,
	const std::vector<int64_t>& padding,
	PadKind mode,
	double constant_value) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (padding.size() != input.shape.size() * 2U ||
		output.shape.size() != input.shape.size()) {
		return Status(
			ErrorCode::kShapeMismatch,
			"Pad parameter count or output rank is invalid");
	}
	if (!input.distributions.empty() || !output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable Pad does not support merged-axis distributions");
	}
	for (std::size_t axis = 0U; axis < input.shape.size(); ++axis) {
		if (output.shape[axis] !=
			input.shape[axis] + padding[axis * 2U] +
				padding[axis * 2U + 1U]) {
			return Status(
				ErrorCode::kShapeMismatch,
				"Pad output shape is invalid");
		}
		const int64_t before = padding[axis * 2U];
		const int64_t after = padding[axis * 2U + 1U];
		if (mode == PadKind::kReflection &&
			((before > 0 && before >= input.shape[axis]) ||
			 (after > 0 && after >= input.shape[axis]))) {
			return Status(
				ErrorCode::kInvalidArgument,
				"reflection padding must be smaller than its input extent");
		}
		if (mode == PadKind::kSymmetric &&
			((before > input.shape[axis]) ||
			 (after > input.shape[axis]))) {
			return Status(
				ErrorCode::kInvalidArgument,
				"symmetric padding cannot exceed its input extent");
		}
	}

	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate(input.shape.size(), 0U);
	for (std::size_t output_index = 0U;
		output_index < output_elements;
		++output_index) {
		detail::decodeIndex(
			output_index, output.shape, &output_coordinate);
		bool constant = false;
		for (std::size_t axis = 0U; axis < input.shape.size(); ++axis) {
			const int64_t coordinate =
				static_cast<int64_t>(output_coordinate[axis]) -
				padding[axis * 2U];
			if (coordinate >= 0 && coordinate < input.shape[axis]) {
				input_coordinate[axis] =
					static_cast<std::size_t>(coordinate);
				continue;
			}
			if (mode == PadKind::kConstant) {
				constant = true;
				break;
			}
			if (mode == PadKind::kReplication) {
				if (!detail::mapPaddedCoordinate(
					coordinate,
					input.shape[axis],
					PaddingKind::kReplicate,
					&input_coordinate[axis])) {
					return Status(
						ErrorCode::kInvalidArgument,
						"replication padding input extent is empty");
				}
			}
			else if (mode == PadKind::kReflection) {
				if (!detail::mapPaddedCoordinate(
					coordinate,
					input.shape[axis],
					PaddingKind::kReflect,
					&input_coordinate[axis])) {
					return Status(
						ErrorCode::kInvalidArgument,
						"reflection padding input extent is invalid");
				}
			}
			else if (!detail::mapSymmetricCoordinate(
				coordinate,
				input.shape[axis],
				&input_coordinate[axis])) {
				return Status(
					ErrorCode::kInvalidArgument,
					"symmetric padding input extent is empty");
			}
		}
		double value = constant_value;
		if (!constant) {
			status = detail::readExpressed(
				input,
				detail::rowMajorIndex(input.shape, input_coordinate),
				input_coordinate,
				&value);
			if (!status.ok()) {
				return status;
			}
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, value);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status roll(
	const TensorDesc& input,
	TensorDesc& output,
	const std::vector<int64_t>& shifts,
	const std::vector<int64_t>* dimensions) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (input.shape != output.shape || shifts.empty()) {
		return Status(
			ErrorCode::kShapeMismatch,
			"Roll input/output shapes or shifts are invalid");
	}
	if (!input.distributions.empty() || !output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable Roll does not support merged-axis distributions");
	}
	std::size_t elements = 0U;
	status = detail::physicalElementCount(input, &elements);
	if (!status.ok()) {
		return status;
	}
	if (elements == 0U) {
		return Status();
	}

	std::vector<int64_t> shifts_by_axis(input.shape.size(), 0);
	bool flattened = dimensions == NULL;
	if (!flattened) {
		if (dimensions->size() != shifts.size()) {
			return Status(
				ErrorCode::kInvalidArgument,
				"Roll shifts and dimensions must have equal lengths");
		}
		for (std::size_t i = 0U; i < dimensions->size(); ++i) {
			std::size_t axis = 0U;
			if (!detail::normalizeAxis(
				(*dimensions)[i], input.shape.size(), &axis)) {
				return Status(
					ErrorCode::kInvalidArgument,
					"Roll dimension is invalid");
			}
			shifts_by_axis[axis] += shifts[i];
		}
	}

	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate;
	for (std::size_t output_index = 0U;
		output_index < elements;
		++output_index) {
		detail::decodeIndex(
			output_index, output.shape, &output_coordinate);
		std::size_t input_index = 0U;
		if (flattened) {
			const int64_t extent = static_cast<int64_t>(elements);
			int64_t normalized_shift = shifts[0] % extent;
			if (normalized_shift < 0) {
				normalized_shift += extent;
			}
			input_index = (
				output_index + elements -
				static_cast<std::size_t>(normalized_shift)) % elements;
			detail::decodeIndex(
				input_index, input.shape, &input_coordinate);
		}
		else {
			input_coordinate = output_coordinate;
			for (std::size_t axis = 0U;
				axis < input.shape.size();
				++axis) {
				const int64_t extent = input.shape[axis];
				if (extent == 0) {
					continue;
				}
				int64_t normalized_shift =
					shifts_by_axis[axis] % extent;
				if (normalized_shift < 0) {
					normalized_shift += extent;
				}
				input_coordinate[axis] = (
					output_coordinate[axis] +
					static_cast<std::size_t>(extent) -
					static_cast<std::size_t>(normalized_shift)) %
					static_cast<std::size_t>(extent);
			}
			input_index =
				detail::rowMajorIndex(input.shape, input_coordinate);
		}
		double value = 0.0;
		status = detail::readExpressed(
			input, input_index, input_coordinate, &value);
		if (!status.ok()) {
			return status;
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, value);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status channelShuffle(
	const TensorDesc& input,
	TensorDesc& output,
	int64_t groups) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	std::size_t channel_axis = 0U;
	if (input.shape.size() != 4U ||
		input.shape != output.shape ||
		input.layout != output.layout ||
		!detail::findUniqueLayoutAxis(input, 'C', &channel_axis) ||
		groups <= 0 ||
		input.shape[channel_axis] <= 0 ||
		input.shape[channel_axis] % groups != 0) {
		return Status(
			ErrorCode::kShapeMismatch,
			"ChannelShuffle shape, layout, or groups are invalid");
	}
	if (!input.distributions.empty() || !output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable ChannelShuffle does not support merged-axis distributions");
	}
	const std::size_t group_count = static_cast<std::size_t>(groups);
	const std::size_t channels_per_group =
		static_cast<std::size_t>(input.shape[channel_axis] / groups);
	std::size_t elements = 0U;
	status = detail::physicalElementCount(output, &elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate;
	for (std::size_t output_index = 0U;
		output_index < elements;
		++output_index) {
		detail::decodeIndex(
			output_index, output.shape, &output_coordinate);
		input_coordinate = output_coordinate;
		const std::size_t output_channel = output_coordinate[channel_axis];
		input_coordinate[channel_axis] =
			(output_channel % group_count) * channels_per_group +
			output_channel / group_count;
		double value = 0.0;
		status = detail::readExpressed(
			input,
			detail::rowMajorIndex(input.shape, input_coordinate),
			input_coordinate,
			&value);
		if (!status.ok()) {
			return status;
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, value);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status pixelShuffle(
	const TensorDesc& input,
	TensorDesc& output,
	int64_t upscale_factor) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (input.shape.size() != 4U ||
		output.shape.size() != 4U ||
		!detail::layoutEquals(input, "NHWC") ||
		!detail::layoutEquals(output, "NHWC") ||
		upscale_factor <= 0) {
		return Status(
			ErrorCode::kShapeMismatch,
			"PixelShuffle expects NHWC tensors and a positive factor");
	}
	if (static_cast<uint64_t>(upscale_factor) >
		static_cast<uint64_t>(
			(std::numeric_limits<std::size_t>::max)())) {
		return Status(
			ErrorCode::kInvalidArgument,
			"PixelShuffle factor exceeds the platform size range");
	}
	const std::size_t factor =
		static_cast<std::size_t>(upscale_factor);
	std::size_t factor_squared = 0U;
	std::size_t scaled_height = 0U;
	std::size_t scaled_width = 0U;
	if (!detail::checkedMultiply(factor, factor, &factor_squared) ||
		factor_squared > static_cast<std::size_t>(
			(std::numeric_limits<int64_t>::max)()) ||
		!detail::checkedMultiply(
			static_cast<std::size_t>(input.shape[1]),
			factor,
			&scaled_height) ||
		!detail::checkedMultiply(
			static_cast<std::size_t>(input.shape[2]),
			factor,
			&scaled_width)) {
		return Status(
			ErrorCode::kInvalidArgument,
			"PixelShuffle output extent overflow");
	}
	const int64_t factor_squared_i64 =
		static_cast<int64_t>(factor_squared);
	if (input.shape[0] != output.shape[0] ||
		static_cast<std::size_t>(output.shape[1]) != scaled_height ||
		static_cast<std::size_t>(output.shape[2]) != scaled_width ||
		input.shape[3] % factor_squared_i64 != 0 ||
		output.shape[3] != input.shape[3] / factor_squared_i64) {
		return Status(
			ErrorCode::kShapeMismatch,
			"PixelShuffle output shape is invalid");
	}
	if (!input.distributions.empty() || !output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable PixelShuffle does not support merged-axis distributions");
	}
	std::size_t elements = 0U;
	status = detail::physicalElementCount(output, &elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate(4U, 0U);
	for (std::size_t output_index = 0U;
		output_index < elements;
		++output_index) {
		detail::decodeIndex(
			output_index, output.shape, &output_coordinate);
		input_coordinate[0] = output_coordinate[0];
		input_coordinate[1] = output_coordinate[1] / factor;
		input_coordinate[2] = output_coordinate[2] / factor;
		const std::size_t offset =
			(output_coordinate[1] % factor) * factor +
			(output_coordinate[2] % factor);
		input_coordinate[3] =
			output_coordinate[3] * factor * factor + offset;
		double value = 0.0;
		status = detail::readExpressed(
			input,
			detail::rowMajorIndex(input.shape, input_coordinate),
			input_coordinate,
			&value);
		if (!status.ok()) {
			return status;
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, value);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status stack(
	const std::vector<TensorDesc>& inputs,
	TensorDesc& output,
	int64_t dimension) {
	if (inputs.empty()) {
		return Status(
			ErrorCode::kInvalidArgument,
			"Stack requires at least one input");
	}
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	std::size_t axis = 0U;
	if (!detail::normalizeAxis(
		dimension, output.shape.size(), &axis) ||
		output.shape.size() != inputs[0].shape.size() + 1U ||
		output.shape[axis] != static_cast<int64_t>(inputs.size()) ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kShapeMismatch,
			"Stack output rank, dimension, or extent is invalid");
	}
	std::vector<int64_t> expected_shape = output.shape;
	expected_shape.erase(expected_shape.begin() + axis);
	std::vector<detail::RuntimeTensor> runtimes(inputs.size());
	for (std::size_t input_index = 0U;
		input_index < inputs.size();
		++input_index) {
		status = detail::validateTensor(
			inputs[input_index], &runtimes[input_index]);
		if (!status.ok()) {
			return status;
		}
		if (!inputs[input_index].distributions.empty() ||
			inputs[input_index].shape != expected_shape) {
			return Status(
				ErrorCode::kShapeMismatch,
				"Stack input shape or distribution is invalid");
		}
	}
	std::size_t output_elements = 0U;
	status = detail::physicalElementCount(output, &output_elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> output_coordinate;
	std::vector<std::size_t> input_coordinate;
	for (std::size_t output_index = 0U;
		output_index < output_elements;
		++output_index) {
		detail::decodeIndex(
			output_index, output.shape, &output_coordinate);
		const std::size_t selected = output_coordinate[axis];
		input_coordinate = output_coordinate;
		input_coordinate.erase(input_coordinate.begin() + axis);
		double value = 0.0;
		status = detail::readExpressed(
			inputs[selected],
			detail::rowMajorIndex(
				inputs[selected].shape, input_coordinate),
			input_coordinate,
			&value);
		if (!status.ok()) {
			return status;
		}
		status = detail::writeExpressed(
			output, output_index, output_coordinate, value);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status unstack(
	const TensorDesc& input,
	const std::vector<TensorDesc*>& outputs,
	int64_t dimension) {
	detail::RuntimeTensor input_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	std::size_t axis = 0U;
	if (outputs.empty() ||
		!detail::normalizeAxis(dimension, input.shape.size(), &axis) ||
		input.shape[axis] != static_cast<int64_t>(outputs.size()) ||
		!input.distributions.empty()) {
		return Status(
			ErrorCode::kShapeMismatch,
			"Unstack outputs, dimension, or extent is invalid");
	}
	std::vector<int64_t> expected_shape = input.shape;
	expected_shape.erase(expected_shape.begin() + axis);
	for (std::size_t output_number = 0U;
		output_number < outputs.size();
		++output_number) {
		if (outputs[output_number] == NULL) {
			return Status(
				ErrorCode::kInvalidArgument,
				"Unstack output is null");
		}
		detail::RuntimeTensor output_runtime;
		status = detail::validateTensor(
			*outputs[output_number], &output_runtime);
		if (!status.ok()) {
			return status;
		}
		if (!outputs[output_number]->distributions.empty() ||
			outputs[output_number]->shape != expected_shape) {
			return Status(
				ErrorCode::kShapeMismatch,
				"Unstack output shape or distribution is invalid");
		}
		std::size_t output_elements = 0U;
		status = detail::physicalElementCount(
			*outputs[output_number], &output_elements);
		if (!status.ok()) {
			return status;
		}
		std::vector<std::size_t> output_coordinate;
		std::vector<std::size_t> input_coordinate(input.shape.size(), 0U);
		for (std::size_t output_index = 0U;
			output_index < output_elements;
			++output_index) {
			detail::decodeIndex(
				output_index,
				outputs[output_number]->shape,
				&output_coordinate);
			for (std::size_t input_axis = 0U;
				input_axis < input.shape.size();
				++input_axis) {
				if (input_axis < axis) {
					input_coordinate[input_axis] =
						output_coordinate[input_axis];
				}
				else if (input_axis == axis) {
					input_coordinate[input_axis] = output_number;
				}
				else {
					input_coordinate[input_axis] =
						output_coordinate[input_axis - 1U];
				}
			}
			double value = 0.0;
			status = detail::readExpressed(
				input,
				detail::rowMajorIndex(input.shape, input_coordinate),
				input_coordinate,
				&value);
			if (!status.ok()) {
				return status;
			}
			status = detail::writeExpressed(
				*outputs[output_number],
				output_index,
				output_coordinate,
				value);
			if (!status.ok()) {
				return status;
			}
		}
	}
	return Status();
}

inline Status normalizeLp(
	const TensorDesc& input,
	TensorDesc& output,
	const std::vector<int64_t>& axes,
	double p,
	double eps) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (input.shape != output.shape) {
		return Status(
			ErrorCode::kShapeMismatch,
			"normalization input and output shapes must match");
	}
	if (!input.distributions.empty() || !output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable normalization does not yet support merged-axis distributions");
	}
	if (axes.empty() || eps < 0.0 || std::isnan(p)) {
		return Status(
			ErrorCode::kInvalidArgument,
			"normalization axes, exponent, or epsilon is invalid");
	}

	std::vector<uint8_t> reduced(input.shape.size(), 0U);
	std::vector<int64_t> group_shape = input.shape;
	for (std::size_t i = 0U; i < axes.size(); ++i) {
		std::size_t axis = 0U;
		if (!detail::normalizeAxis(axes[i], input.shape.size(), &axis) ||
			reduced[axis] != 0U) {
			return Status(
				ErrorCode::kInvalidArgument,
				"normalization axes are invalid or duplicated");
		}
		reduced[axis] = 1U;
		group_shape[axis] = 1;
	}
	std::size_t group_count = 1U;
	for (std::size_t axis = 0U; axis < group_shape.size(); ++axis) {
		if (!detail::checkedMultiply(
				group_count,
				static_cast<std::size_t>(group_shape[axis]),
				&group_count)) {
			return Status(
				ErrorCode::kInvalidArgument,
				"normalization group count overflow");
		}
	}

	const bool positive_infinity =
		std::isinf(p) && p > 0.0;
	const bool negative_infinity =
		std::isinf(p) && p < 0.0;
	std::vector<double> accumulators(
		group_count,
		negative_infinity
			? (std::numeric_limits<double>::infinity)()
			: 0.0);
	std::vector<std::size_t> coordinate;
	std::vector<std::size_t> group_coordinate(input.shape.size(), 0U);
	std::size_t input_elements = 0U;
	status = detail::physicalElementCount(input, &input_elements);
	if (!status.ok()) {
		return status;
	}
	for (std::size_t input_index = 0U;
		input_index < input_elements;
		++input_index) {
		detail::decodeIndex(input_index, input.shape, &coordinate);
		group_coordinate = coordinate;
		for (std::size_t axis = 0U; axis < reduced.size(); ++axis) {
			if (reduced[axis] != 0U) {
				group_coordinate[axis] = 0U;
			}
		}
		const std::size_t group_index =
			detail::rowMajorIndex(group_shape, group_coordinate);
		double value = 0.0;
		status = detail::readExpressed(
			input, input_index, coordinate, &value);
		if (!status.ok()) {
			return status;
		}
		const double magnitude = std::fabs(value);
		if (positive_infinity) {
			accumulators[group_index] =
				(std::max)(accumulators[group_index], magnitude);
		}
		else if (negative_infinity) {
			accumulators[group_index] =
				(std::min)(accumulators[group_index], magnitude);
		}
		else if (p == 0.0) {
			accumulators[group_index] += value == 0.0 ? 0.0 : 1.0;
		}
		else {
			accumulators[group_index] += std::pow(magnitude, p);
		}
	}
	for (std::size_t group_index = 0U;
		group_index < group_count;
		++group_index) {
		if (!positive_infinity && !negative_infinity && p != 0.0) {
			accumulators[group_index] =
				std::pow(accumulators[group_index], 1.0 / p);
		}
		accumulators[group_index] =
			(std::max)(accumulators[group_index], eps);
	}

	for (std::size_t output_index = 0U;
		output_index < input_elements;
		++output_index) {
		detail::decodeIndex(output_index, input.shape, &coordinate);
		group_coordinate = coordinate;
		for (std::size_t axis = 0U; axis < reduced.size(); ++axis) {
			if (reduced[axis] != 0U) {
				group_coordinate[axis] = 0U;
			}
		}
		const std::size_t group_index =
			detail::rowMajorIndex(group_shape, group_coordinate);
		double value = 0.0;
		status = detail::readExpressed(
			input, output_index, coordinate, &value);
		if (!status.ok()) {
			return status;
		}
		status = detail::writeExpressed(
			output,
			output_index,
			coordinate,
			value / accumulators[group_index]);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status layerNorm(
	const TensorDesc& input,
	const TensorDesc* gamma,
	const TensorDesc* beta,
	TensorDesc& output,
	const std::vector<int64_t>& axes,
	double eps,
	bool rms_only) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor gamma_runtime;
	detail::RuntimeTensor beta_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	if (gamma != NULL) {
		status = detail::validateTensor(*gamma, &gamma_runtime);
		if (!status.ok()) {
			return status;
		}
	}
	if (beta != NULL) {
		status = detail::validateTensor(*beta, &beta_runtime);
		if (!status.ok()) {
			return status;
		}
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (input.shape != output.shape) {
		return Status(
			ErrorCode::kShapeMismatch,
			"layer normalization input and output shapes must match");
	}
	if (!input.distributions.empty() ||
		(gamma != NULL && !gamma->distributions.empty()) ||
		(beta != NULL && !beta->distributions.empty()) ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable layer normalization does not support merged-axis distributions");
	}
	if (axes.empty() || eps < 0.0) {
		return Status(
			ErrorCode::kInvalidArgument,
			"layer normalization axes or epsilon is invalid");
	}

	std::vector<uint8_t> reduced(input.shape.size(), 0U);
	std::vector<std::size_t> normalized_axes;
	std::vector<int64_t> group_shape = input.shape;
	for (std::size_t i = 0U; i < axes.size(); ++i) {
		std::size_t axis = 0U;
		if (!detail::normalizeAxis(axes[i], input.shape.size(), &axis) ||
			reduced[axis] != 0U) {
			return Status(
				ErrorCode::kInvalidArgument,
				"layer normalization axes are invalid or duplicated");
		}
		reduced[axis] = 1U;
		normalized_axes.push_back(axis);
		group_shape[axis] = 1;
	}
	const TensorDesc* parameters[2] = { gamma, beta };
	for (std::size_t parameter_index = 0U;
		parameter_index < 2U;
		++parameter_index) {
		const TensorDesc* parameter = parameters[parameter_index];
		if (parameter == NULL) {
			continue;
		}
		if (parameter->shape.size() != normalized_axes.size()) {
			return Status(
				ErrorCode::kShapeMismatch,
				"layer normalization parameter rank is invalid");
		}
		for (std::size_t axis = 0U;
			axis < normalized_axes.size();
			++axis) {
			if (parameter->shape[axis] !=
				input.shape[normalized_axes[axis]]) {
				return Status(
					ErrorCode::kShapeMismatch,
					"layer normalization parameter shape is invalid");
			}
		}
	}

	std::size_t group_count = 1U;
	for (std::size_t axis = 0U; axis < group_shape.size(); ++axis) {
		if (!detail::checkedMultiply(
				group_count,
				static_cast<std::size_t>(group_shape[axis]),
				&group_count)) {
			return Status(
				ErrorCode::kInvalidArgument,
				"layer normalization group count overflow");
		}
	}
	std::vector<double> sums(group_count, 0.0);
	std::vector<double> square_sums(group_count, 0.0);
	std::vector<std::size_t> counts(group_count, 0U);
	std::vector<std::size_t> coordinate;
	std::vector<std::size_t> group_coordinate(input.shape.size(), 0U);
	std::size_t input_elements = 0U;
	status = detail::physicalElementCount(input, &input_elements);
	if (!status.ok()) {
		return status;
	}
	for (std::size_t input_index = 0U;
		input_index < input_elements;
		++input_index) {
		detail::decodeIndex(input_index, input.shape, &coordinate);
		group_coordinate = coordinate;
		for (std::size_t axis = 0U; axis < reduced.size(); ++axis) {
			if (reduced[axis] != 0U) {
				group_coordinate[axis] = 0U;
			}
		}
		const std::size_t group_index =
			detail::rowMajorIndex(group_shape, group_coordinate);
		double value = 0.0;
		status = detail::readExpressed(
			input, input_index, coordinate, &value);
		if (!status.ok()) {
			return status;
		}
		sums[group_index] += value;
		square_sums[group_index] += value * value;
		++counts[group_index];
	}

	std::vector<std::size_t> parameter_coordinate(
		normalized_axes.size(), 0U);
	for (std::size_t output_index = 0U;
		output_index < input_elements;
		++output_index) {
		detail::decodeIndex(output_index, input.shape, &coordinate);
		group_coordinate = coordinate;
		for (std::size_t axis = 0U; axis < reduced.size(); ++axis) {
			if (reduced[axis] != 0U) {
				group_coordinate[axis] = 0U;
			}
		}
		const std::size_t group_index =
			detail::rowMajorIndex(group_shape, group_coordinate);
		if (counts[group_index] == 0U) {
			return Status(
				ErrorCode::kInvalidArgument,
				"layer normalization group is empty");
		}
		const double count = static_cast<double>(counts[group_index]);
		const double mean = rms_only ? 0.0 : sums[group_index] / count;
		double variance = square_sums[group_index] / count;
		if (!rms_only) {
			variance -= mean * mean;
		}
		variance = (std::max)(variance, 0.0);
		double value = 0.0;
		status = detail::readExpressed(
			input, output_index, coordinate, &value);
		if (!status.ok()) {
			return status;
		}
		double result =
			(value - mean) / std::sqrt(variance + eps);
		for (std::size_t axis = 0U;
			axis < normalized_axes.size();
			++axis) {
			parameter_coordinate[axis] =
				coordinate[normalized_axes[axis]];
		}
		if (gamma != NULL) {
			double gamma_value = 0.0;
			status = detail::readExpressed(
				*gamma,
				detail::rowMajorIndex(
					gamma->shape, parameter_coordinate),
				parameter_coordinate,
				&gamma_value);
			if (!status.ok()) {
				return status;
			}
			result *= gamma_value;
		}
		if (beta != NULL) {
			double beta_value = 0.0;
			status = detail::readExpressed(
				*beta,
				detail::rowMajorIndex(
					beta->shape, parameter_coordinate),
				parameter_coordinate,
				&beta_value);
			if (!status.ok()) {
				return status;
			}
			result += beta_value;
		}
		status = detail::writeExpressed(
			output, output_index, coordinate, result);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status channelAffine(
	const TensorDesc& input,
	const TensorDesc* multiplier,
	const TensorDesc* addend,
	TensorDesc& output) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor multiplier_runtime;
	detail::RuntimeTensor addend_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	if (multiplier != NULL) {
		status = detail::validateTensor(
			*multiplier, &multiplier_runtime);
		if (!status.ok()) {
			return status;
		}
	}
	if (addend != NULL) {
		status = detail::validateTensor(*addend, &addend_runtime);
		if (!status.ok()) {
			return status;
		}
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (input.shape != output.shape ||
		!detail::channelLastActivationLayout(input) ||
		!detail::channelLastActivationLayout(output)) {
		return Status(
			ErrorCode::kShapeMismatch,
			"channel affine expects matching NLC, NHWC, or NDHWC tensors");
	}
	if (!input.distributions.empty() ||
		(multiplier != NULL && !multiplier->distributions.empty()) ||
		(addend != NULL && !addend->distributions.empty()) ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable channel affine does not support merged-axis distributions");
	}
	const std::size_t channels =
		static_cast<std::size_t>(input.shape.back());
	if (channels == 0U ||
		(multiplier != NULL &&
		 multiplier_runtime.storage_elements != channels) ||
		(addend != NULL && addend_runtime.storage_elements != channels)) {
		return Status(
			ErrorCode::kShapeMismatch,
			"channel affine parameters must contain one value per channel");
	}
	std::size_t elements = 0U;
	status = detail::physicalElementCount(output, &elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> coordinate;
	for (std::size_t index = 0U; index < elements; ++index) {
		detail::decodeIndex(index, output.shape, &coordinate);
		double input_value = 0.0;
		double multiplier_value = 1.0;
		double addend_value = 0.0;
		status = detail::readExpressed(
			input, index, coordinate, &input_value);
		if (status.ok() && multiplier != NULL) {
			status = detail::readChannelParameter(
				*multiplier,
				multiplier_runtime,
				coordinate.back(),
				channels,
				false,
				&multiplier_value);
		}
		if (status.ok() && addend != NULL) {
			status = detail::readChannelParameter(
				*addend,
				addend_runtime,
				coordinate.back(),
				channels,
				false,
				&addend_value);
		}
		if (!status.ok()) {
			return status;
		}
		status = detail::writeExpressed(
			output,
			index,
			coordinate,
			input_value * multiplier_value + addend_value);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status instanceNorm(
	const TensorDesc& input,
	const TensorDesc* gamma,
	const TensorDesc* beta,
	TensorDesc& output,
	double eps) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor gamma_runtime;
	detail::RuntimeTensor beta_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	if (gamma != NULL) {
		status = detail::validateTensor(*gamma, &gamma_runtime);
		if (!status.ok()) {
			return status;
		}
	}
	if (beta != NULL) {
		status = detail::validateTensor(*beta, &beta_runtime);
		if (!status.ok()) {
			return status;
		}
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	if (input.shape != output.shape ||
		!detail::channelLastActivationLayout(input) ||
		!detail::channelLastActivationLayout(output) ||
		!std::isfinite(eps) || eps < 0.0) {
		return Status(
			ErrorCode::kShapeMismatch,
			"InstanceNorm expects matching channel-last tensors and finite epsilon");
	}
	if (!input.distributions.empty() ||
		(gamma != NULL && !gamma->distributions.empty()) ||
		(beta != NULL && !beta->distributions.empty()) ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable InstanceNorm does not support merged-axis distributions");
	}
	const std::size_t batch =
		static_cast<std::size_t>(input.shape.front());
	const std::size_t channels =
		static_cast<std::size_t>(input.shape.back());
	if (batch == 0U || channels == 0U ||
		(gamma != NULL && gamma_runtime.storage_elements != channels) ||
		(beta != NULL && beta_runtime.storage_elements != channels)) {
		return Status(
			ErrorCode::kShapeMismatch,
			"InstanceNorm parameters must contain one value per channel");
	}
	std::size_t group_count = 0U;
	if (!detail::checkedMultiply(batch, channels, &group_count)) {
		return Status(
			ErrorCode::kInvalidArgument,
			"InstanceNorm group count overflow");
	}
	std::vector<double> sums(group_count, 0.0);
	std::vector<double> square_sums(group_count, 0.0);
	std::vector<std::size_t> counts(group_count, 0U);
	std::size_t elements = 0U;
	status = detail::physicalElementCount(input, &elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> coordinate;
	for (std::size_t index = 0U; index < elements; ++index) {
		detail::decodeIndex(index, input.shape, &coordinate);
		const std::size_t group =
			coordinate.front() * channels + coordinate.back();
		double value = 0.0;
		status = detail::readExpressed(
			input, index, coordinate, &value);
		if (!status.ok()) {
			return status;
		}
		sums[group] += value;
		square_sums[group] += value * value;
		++counts[group];
	}
	for (std::size_t index = 0U; index < elements; ++index) {
		detail::decodeIndex(index, input.shape, &coordinate);
		const std::size_t group =
			coordinate.front() * channels + coordinate.back();
		if (counts[group] == 0U) {
			return Status(
				ErrorCode::kInvalidArgument,
				"InstanceNorm group is empty");
		}
		const double count = static_cast<double>(counts[group]);
		const double mean = sums[group] / count;
		const double variance = (std::max)(
			square_sums[group] / count - mean * mean, 0.0);
		double value = 0.0;
		status = detail::readExpressed(
			input, index, coordinate, &value);
		if (!status.ok()) {
			return status;
		}
		double result = (value - mean) / std::sqrt(variance + eps);
		if (gamma != NULL) {
			double gamma_value = 0.0;
			status = detail::readChannelParameter(
				*gamma,
				gamma_runtime,
				coordinate.back(),
				channels,
				false,
				&gamma_value);
			if (!status.ok()) {
				return status;
			}
			result *= gamma_value;
		}
		if (beta != NULL) {
			double beta_value = 0.0;
			status = detail::readChannelParameter(
				*beta,
				beta_runtime,
				coordinate.back(),
				channels,
				false,
				&beta_value);
			if (!status.ok()) {
				return status;
			}
			result += beta_value;
		}
		status = detail::writeExpressed(
			output, index, coordinate, result);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status prelu(
	const TensorDesc& input,
	const TensorDesc& alpha,
	TensorDesc& output) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor alpha_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(alpha, &alpha_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	std::size_t channel_axis = 0U;
	if (input.shape != output.shape ||
		input.layout != output.layout ||
		!detail::findUniqueLayoutAxis(input, 'C', &channel_axis) ||
		input.shape[channel_axis] <= 0) {
		return Status(
			ErrorCode::kShapeMismatch,
			"PReLU expects matching layouts with one positive C axis");
	}
	if (!input.distributions.empty() ||
		!alpha.distributions.empty() ||
		!output.distributions.empty()) {
		return Status(
			ErrorCode::kInvalidDistribution,
			"portable PReLU does not support merged-axis distributions");
	}
	const std::size_t channels =
		static_cast<std::size_t>(input.shape[channel_axis]);
	if (alpha_runtime.storage_elements != 1U &&
		alpha_runtime.storage_elements != channels) {
		return Status(
			ErrorCode::kShapeMismatch,
			"PReLU alpha must be scalar or contain one value per channel");
	}
	std::size_t elements = 0U;
	status = detail::physicalElementCount(output, &elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> coordinate;
	for (std::size_t index = 0U; index < elements; ++index) {
		detail::decodeIndex(index, output.shape, &coordinate);
		double value = 0.0;
		double coefficient = 0.0;
		status = detail::readExpressed(
			input, index, coordinate, &value);
		if (status.ok()) {
			status = detail::readChannelParameter(
				alpha,
				alpha_runtime,
				coordinate[channel_axis],
				channels,
				true,
				&coefficient);
		}
		if (!status.ok()) {
			return status;
		}
		status = detail::writeExpressed(
			output,
			index,
			coordinate,
			value < 0.0 ? value * coefficient : value);
		if (!status.ok()) {
			return status;
		}
	}
	return Status();
}

inline Status alignAxis(const TensorDesc& input, TensorDesc& output) {
	return detail::transform(input, output, NULL);
}

inline Status pruneAxis(
	const TensorDesc& input,
	TensorDesc& output,
	const std::vector<std::size_t>& distribution_indices) {
	return detail::transform(input, output, &distribution_indices);
}

inline Status unaryElementwise(
	const TensorDesc& input,
	TensorDesc& output,
	const UnarySpec& spec) {
	detail::RuntimeTensor input_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(input, &input_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}

	std::size_t output_physical_elements = 0U;
	status = detail::physicalElementCount(output, &output_physical_elements);
	if (!status.ok()) {
		return status;
	}

	std::vector<std::size_t> output_coordinate;
	std::size_t output_storage_index = 0U;
	for (std::size_t output_linear = 0U;
		output_linear < output_physical_elements;
		++output_linear) {
		detail::decodeIndex(
			output_linear, output.shape, &output_coordinate);
		if (!detail::coordinateIsValid(output, output_coordinate, true)) {
			continue;
		}
		if (!detail::coordinateIsValid(output, output_coordinate, false)) {
			detail::storeRaw(
				output,
				output_storage_index++,
				0.0,
				output.quantization.rounding);
			continue;
		}

		double input_value = 0.0;
		status = detail::readBroadcastValue(
			input,
			input_runtime,
			output,
			output_coordinate,
			&input_value);
		if (!status.ok()) {
			return status;
		}
		double output_value = 0.0;
		status = detail::applyUnaryValue(spec, input_value, &output_value);
		if (!status.ok()) {
			return status;
		}
		status = detail::writeExpressed(
			output,
			output_storage_index++,
			output_coordinate,
			output_value);
		if (!status.ok()) {
			return status;
		}
	}

	if (output_storage_index != output_runtime.storage_elements) {
		return Status(
			ErrorCode::kShapeMismatch,
			"unary output traversal did not cover the output buffer");
	}
	return Status();
}

inline Status binaryElementwise(
	const TensorDesc& lhs,
	const TensorDesc& rhs,
	TensorDesc& output,
	const BinarySpec& spec) {
	detail::RuntimeTensor lhs_runtime;
	detail::RuntimeTensor rhs_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(lhs, &lhs_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(rhs, &rhs_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}

	std::size_t output_physical_elements = 0U;
	status = detail::physicalElementCount(output, &output_physical_elements);
	if (!status.ok()) {
		return status;
	}

	std::vector<std::size_t> output_coordinate;
	std::size_t output_storage_index = 0U;
	for (std::size_t output_linear = 0U;
		output_linear < output_physical_elements;
		++output_linear) {
		detail::decodeIndex(
			output_linear, output.shape, &output_coordinate);
		if (!detail::coordinateIsValid(output, output_coordinate, true)) {
			continue;
		}
		if (!detail::coordinateIsValid(output, output_coordinate, false)) {
			detail::storeRaw(
				output,
				output_storage_index++,
				0.0,
				output.quantization.rounding);
			continue;
		}

		double lhs_value = 0.0;
		double rhs_value = 0.0;
		status = detail::readBroadcastValue(
			lhs,
			lhs_runtime,
			output,
			output_coordinate,
			&lhs_value);
		if (!status.ok()) {
			return status;
		}
		status = detail::readBroadcastValue(
			rhs,
			rhs_runtime,
			output,
			output_coordinate,
			&rhs_value);
		if (!status.ok()) {
			return status;
		}

		double lhs_coefficient = 1.0;
		double rhs_coefficient = 1.0;
		status = detail::coefficientForCoordinate(
			output,
			output_coordinate,
			spec.lhs_coefficients,
			spec.coefficient_axis,
			&lhs_coefficient);
		if (!status.ok()) {
			return status;
		}
		status = detail::coefficientForCoordinate(
			output,
			output_coordinate,
			spec.rhs_coefficients,
			spec.coefficient_axis,
			&rhs_coefficient);
		if (!status.ok()) {
			return status;
		}

		double output_value = 0.0;
		status = detail::applyBinaryValue(
			spec,
			lhs_value,
			rhs_value,
			lhs_coefficient,
			rhs_coefficient,
			&output_value);
		if (!status.ok()) {
			return status;
		}
		status = detail::writeExpressed(
			output,
			output_storage_index++,
			output_coordinate,
			output_value);
		if (!status.ok()) {
			return status;
		}
	}

	if (output_storage_index != output_runtime.storage_elements) {
		return Status(
			ErrorCode::kShapeMismatch,
			"binary output traversal did not cover the output buffer");
	}
	return Status();
}

inline Status where(
	const TensorDesc& lhs,
	const TensorDesc& rhs,
	const TensorDesc& condition,
	TensorDesc& output) {
	detail::RuntimeTensor lhs_runtime;
	detail::RuntimeTensor rhs_runtime;
	detail::RuntimeTensor condition_runtime;
	detail::RuntimeTensor output_runtime;
	Status status = detail::validateTensor(lhs, &lhs_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(rhs, &rhs_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(condition, &condition_runtime);
	if (!status.ok()) {
		return status;
	}
	status = detail::validateTensor(output, &output_runtime);
	if (!status.ok()) {
		return status;
	}
	std::size_t output_physical_elements = 0U;
	status = detail::physicalElementCount(
		output, &output_physical_elements);
	if (!status.ok()) {
		return status;
	}
	std::vector<std::size_t> output_coordinate;
	std::size_t output_storage_index = 0U;
	for (std::size_t output_linear = 0U;
		output_linear < output_physical_elements;
		++output_linear) {
		detail::decodeIndex(
			output_linear, output.shape, &output_coordinate);
		if (!detail::coordinateIsValid(
			output, output_coordinate, true)) {
			continue;
		}
		if (!detail::coordinateIsValid(
			output, output_coordinate, false)) {
			detail::storeRaw(
				output,
				output_storage_index++,
				0.0,
				output.quantization.rounding);
			continue;
		}
		double condition_value = 0.0;
		status = detail::readBroadcastValue(
			condition,
			condition_runtime,
			output,
			output_coordinate,
			&condition_value);
		if (!status.ok()) {
			return status;
		}
		double selected_value = 0.0;
		if (condition_value != 0.0) {
			status = detail::readBroadcastValue(
				lhs,
				lhs_runtime,
				output,
				output_coordinate,
				&selected_value);
		}
		else {
			status = detail::readBroadcastValue(
				rhs,
				rhs_runtime,
				output,
				output_coordinate,
				&selected_value);
		}
		if (!status.ok()) {
			return status;
		}
		status = detail::writeExpressed(
			output,
			output_storage_index++,
			output_coordinate,
			selected_value);
		if (!status.ok()) {
			return status;
		}
	}
	if (output_storage_index != output_runtime.storage_elements) {
		return Status(
			ErrorCode::kShapeMismatch,
			"Where output traversal did not cover the output buffer");
	}
	return Status();
}

}  // namespace common
}  // namespace hostbackend
}  // namespace icraft
