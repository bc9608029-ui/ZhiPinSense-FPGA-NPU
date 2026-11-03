#pragma once

#include <chrono>
#include <limits>
#include <vector>

#include <icraft-backends/hostbackend/common/tensor_kernel.h>
#include <icraft-utils/osal/cache.hpp>
#include <icraft-xir/ops/align_axis.h>
#include <icraft-xir/ops/cast.h>
#include <icraft-xir/ops/prune_axis.h>
#include <icraft-xir/core/data.h>
#include <icraft-xir/ops/ops.h>
#include <icraft-xrt/core/tensor.h>
#include <icraft-xrt/dev/host_device.h>

namespace icraft {
namespace hostbackend {
namespace port {

inline common::RoundingMode roundingMode(const xir::CompileTarget& target) {
	if (target.is<xir::ZhugeTarget>() || target.is<xir::WolongTarget>()) {
		return common::RoundingMode::kHalfAwayFromZero;
	}
	return common::RoundingMode::kHalfUp;
}

inline common::Status storageType(
	const xir::ScalarType& scalar_type,
	common::StorageType* result) {
	if (scalar_type.isSInt8()) {
		*result = common::StorageType::kSInt8;
	}
	else if (scalar_type.isUInt8()) {
		*result = common::StorageType::kUInt8;
	}
	else if (scalar_type.isSInt16()) {
		*result = common::StorageType::kSInt16;
	}
	else if (scalar_type.isUInt16()) {
		*result = common::StorageType::kUInt16;
	}
	else if (scalar_type.isSInt32()) {
		*result = common::StorageType::kSInt32;
	}
	else if (scalar_type.isUInt32()) {
		*result = common::StorageType::kUInt32;
	}
	else if (scalar_type.isSInt64()) {
		*result = common::StorageType::kSInt64;
	}
	else if (scalar_type.isUInt64()) {
		*result = common::StorageType::kUInt64;
	}
	else if (scalar_type.isFP16()) {
		*result = common::StorageType::kFloat16;
	}
	else if (scalar_type.isBF16()) {
		*result = common::StorageType::kBFloat16;
	}
	else if (scalar_type.isFP32()) {
		*result = common::StorageType::kFloat32;
	}
	else if (scalar_type.isFP64()) {
		*result = common::StorageType::kFloat64;
	}
	else {
		return common::Status(
			common::ErrorCode::kUnsupportedType,
			"portable HostBackend does not support this storage type");
	}
	return common::Status();
}

inline common::Status describeTensor(
	void* data,
	std::size_t data_bytes,
	const xir::TensorType& dtype,
	common::RoundingMode rounding,
	common::TensorDesc* desc) {
	desc->data = data;
	desc->data_bytes = data_bytes;
	desc->shape.assign(dtype->shape.begin(), dtype->shape.end());
	desc->layout.clear();
	for (std::size_t i = 0; i < dtype->shape.size(); ++i) {
		desc->layout.push_back(
			dtype->layout.getAxisCharName(static_cast<int64_t>(i)));
	}

	common::Status status =
		storageType(dtype->element_dtype.getStorageType(), &desc->storage_type);
	if (!status.ok()) {
		return status;
	}

	desc->distributions.clear();
	for (std::size_t i = 0; i < dtype->merged_distrs.size(); ++i) {
		const xir::MergedAxisDistr& xir_distribution = dtype->merged_distrs[i];
		common::AxisDistribution distribution;
		distribution.axes.assign(
			xir_distribution->merged_axis.begin(),
			xir_distribution->merged_axis.end());
		distribution.valid_mask.reserve(
			xir_distribution->valid_mask.size());
		for (std::size_t mask_index = 0;
			mask_index < xir_distribution->valid_mask.size();
			++mask_index) {
			distribution.valid_mask.push_back(
				xir_distribution->valid_mask[mask_index] ? 1U : 0U);
		}
		distribution.invalid_value =
			xir_distribution->uvalue == xir::DistrUnvalidValue::NONE
			? common::InvalidValue::kOmitted
			: common::InvalidValue::kZero;
		desc->distributions.push_back(distribution);
	}

	desc->quantization = common::Quantization();
	if (dtype->element_dtype.is<xir::QuantizedType>()) {
		const xir::QuantizedType quantized =
			dtype->element_dtype.cast<xir::QuantizedType>();
		desc->quantization.enabled = true;
		desc->quantization.axis = quantized->scale->axis;
		desc->quantization.scales.assign(
			quantized->scale->origin_scale.begin(),
			quantized->scale->origin_scale.end());
		desc->quantization.zero_points.assign(
			quantized->zero_points.begin(),
			quantized->zero_points.end());
		desc->quantization.rounding =
			desc->quantization.zero_points.empty()
			? rounding
			: common::RoundingMode::kNearestEven;
	}
	else {
		desc->quantization.rounding = rounding;
	}

	return common::Status();
}

inline bool isCpuAddressable(const xrt::Tensor& tensor) {
	return tensor.data().ptype() != xrt::PtrType::ADDR;
}

inline std::vector<xrt::Tensor> materializeInputs(
	const xir::Array<xir::Value>& declared_inputs,
	const std::vector<xrt::Tensor>& runtime_inputs) {
	std::vector<xrt::Tensor> result;
	result.reserve(declared_inputs.size());
	std::size_t runtime_index = 0U;
	for (std::size_t i = 0; i < declared_inputs.size(); ++i) {
		const xir::Value value = declared_inputs[i];
		if (value.is<xir::Params>()) {
			const xir::Params params = value.cast<xir::Params>();
			ICRAFT_CHECK(params.hasData(), 12011)
				.append(
					"Portable HostBackend parameter input {} has no data.", i);
			result.push_back(xrt::Tensor(params));
			continue;
		}
		ICRAFT_CHECK(runtime_index < runtime_inputs.size(), 12011)
			.append(
				"Portable HostBackend is missing runtime input {}.",
				runtime_index);
		result.push_back(runtime_inputs[runtime_index++]);
	}
	ICRAFT_CHECK(runtime_index == runtime_inputs.size(), 12011)
		.append(
			"Portable HostBackend received {} unexpected runtime inputs.",
			runtime_inputs.size() - runtime_index);
	return result;
}

inline double scalarValue(const xir::ScalarImm& value) {
	if (value.is<xir::IntImm>()) {
		return static_cast<double>(value.cast<xir::IntImm>());
	}
	return static_cast<double>(value.cast<xir::FloatImm>());
}

inline std::vector<double> scalarValues(
	const xir::Array<xir::ScalarImm>& values) {
	std::vector<double> result;
	result.reserve(values.size());
	for (std::size_t i = 0; i < values.size(); ++i) {
		result.push_back(scalarValue(values[i]));
	}
	return result;
}

template <typename Op>
inline common::UnarySpec unarySpec(
	const Op&,
	common::UnaryKind kind) {
	return common::UnarySpec(kind);
}

inline common::UnarySpec unarySpec(
	const xir::ClampScalar& op,
	common::UnaryKind kind) {
	common::UnarySpec spec(kind);
	spec.minimum = static_cast<double>(op->min);
	spec.maximum = static_cast<double>(op->max);
	return spec;
}

inline common::UnarySpec unarySpec(
	const xir::DivideScalar& op,
	common::UnaryKind kind) {
	common::UnarySpec spec(kind);
	spec.alpha = static_cast<double>(op->divisor);
	if (op->rounding_mode == xir::DivideScalar::RoundingMode::TRUNC) {
		spec.beta = 1.0;
	}
	else if (op->rounding_mode == xir::DivideScalar::RoundingMode::FLOOR) {
		spec.beta = 2.0;
	}
	return spec;
}

inline common::UnarySpec unarySpec(
	const xir::ELU& op,
	common::UnaryKind kind) {
	common::UnarySpec spec(kind);
	spec.alpha = static_cast<double>(op->alpha);
	return spec;
}

inline common::UnarySpec unarySpec(
	const xir::Hardshrink& op,
	common::UnaryKind kind) {
	common::UnarySpec spec(kind);
	spec.alpha = static_cast<double>(op->lambda);
	return spec;
}

inline common::UnarySpec unarySpec(
	const xir::Hardsigmoid& op,
	common::UnaryKind kind) {
	common::UnarySpec spec(kind);
	spec.alpha = static_cast<double>(op->alpha);
	spec.beta = static_cast<double>(op->beta);
	return spec;
}

inline common::UnarySpec unarySpec(
	const xir::Hardswish&,
	common::UnaryKind kind) {
	common::UnarySpec spec(kind);
	spec.alpha = 1.0 / 6.0;
	spec.beta = 0.5;
	return spec;
}

inline common::UnarySpec unarySpec(
	const xir::Hardtanh& op,
	common::UnaryKind kind) {
	common::UnarySpec spec(kind);
	spec.minimum = static_cast<double>(op->min_val);
	spec.maximum = static_cast<double>(op->max_val);
	return spec;
}

inline common::UnarySpec unarySpec(
	const xir::ReLU& op,
	common::UnaryKind kind) {
	common::UnarySpec spec(kind);
	spec.alpha = static_cast<double>(op->alpha);
	spec.maximum = static_cast<double>(op->max_value);
	spec.threshold = static_cast<double>(op->threshold);
	return spec;
}

inline common::UnarySpec unarySpec(
	const xir::Softplus& op,
	common::UnaryKind kind) {
	common::UnarySpec spec(kind);
	spec.beta = static_cast<double>(op->beta);
	spec.threshold = static_cast<double>(op->threshold);
	return spec;
}

inline common::UnarySpec unarySpec(
	const xir::Softshrink& op,
	common::UnaryKind kind) {
	common::UnarySpec spec(kind);
	spec.alpha = static_cast<double>(op->lambda);
	return spec;
}

template <typename Op>
inline common::BinarySpec binarySpec(
	const Op&,
	common::BinaryKind kind) {
	return common::BinarySpec(kind);
}

inline common::BinarySpec binarySpec(
	const xir::Add& op,
	common::BinaryKind kind) {
	common::BinarySpec spec(kind);
	spec.lhs_coefficients = scalarValues(op->alpha);
	spec.rhs_coefficients = scalarValues(op->beta);
	return spec;
}

inline common::ReductionSpec reductionSpec(
	const xir::Sum& op,
	common::ReductionKind kind) {
	common::ReductionSpec spec(kind);
	spec.axes.assign(op->dim.begin(), op->dim.end());
	spec.keep_dimensions = op->keepdim;
	return spec;
}

inline common::ReductionSpec reductionSpec(
	const xir::Mean& op,
	common::ReductionKind kind) {
	common::ReductionSpec spec(kind);
	spec.axes.assign(op->dim.begin(), op->dim.end());
	spec.keep_dimensions = op->keepdim;
	return spec;
}

template <typename Op>
inline common::ReductionSpec optionalReductionSpec(
	const Op& op,
	common::ReductionKind kind) {
	common::ReductionSpec spec(kind);
	if (op->dim.has_value()) {
		spec.axes.push_back(static_cast<int64_t>(op->dim.value()));
	}
	spec.keep_dimensions = op->keepdim;
	return spec;
}

inline common::ReductionSpec reductionSpec(
	const xir::Max& op,
	common::ReductionKind kind) {
	return optionalReductionSpec(op, kind);
}

inline common::ReductionSpec reductionSpec(
	const xir::Min& op,
	common::ReductionKind kind) {
	return optionalReductionSpec(op, kind);
}

inline common::ReductionSpec reductionSpec(
	const xir::Argmax& op,
	common::ReductionKind kind) {
	return optionalReductionSpec(op, kind);
}

inline common::ReductionSpec reductionSpec(
	const xir::Argmin& op,
	common::ReductionKind kind) {
	return optionalReductionSpec(op, kind);
}

inline common::PoolSpec poolSpec(
	const xir::MaxPool1d& op,
	common::PoolKind kind) {
	common::PoolSpec spec(kind);
	spec.kernel.push_back(op->pool_width);
	spec.stride.push_back(op->stride_width);
	spec.pad_before.push_back(op->pad_left);
	spec.pad_after.push_back(op->pad_right);
	spec.dilation.push_back(op->dilation_width);
	return spec;
}

inline common::PoolSpec poolSpec(
	const xir::MaxPool2d& op,
	common::PoolKind kind) {
	common::PoolSpec spec(kind);
	spec.kernel = { op->pool_height, op->pool_width };
	spec.stride = { op->stride_height, op->stride_width };
	spec.pad_before = { op->pad_top, op->pad_left };
	spec.pad_after = { op->pad_bottom, op->pad_right };
	spec.dilation = { op->dilation_height, op->dilation_width };
	return spec;
}

inline common::PoolSpec poolSpec(
	const xir::MaxPool3d& op,
	common::PoolKind kind) {
	common::PoolSpec spec(kind);
	spec.kernel = {
		op->pool_depth, op->pool_height, op->pool_width
	};
	spec.stride = {
		op->stride_depth, op->stride_height, op->stride_width
	};
	spec.pad_before = {
		op->pad_front, op->pad_top, op->pad_left
	};
	spec.pad_after = {
		op->pad_back, op->pad_bottom, op->pad_right
	};
	spec.dilation = {
		op->dilation_depth, op->dilation_height, op->dilation_width
	};
	return spec;
}

inline common::PoolSpec poolSpec(
	const xir::AvgPool1d& op,
	common::PoolKind kind) {
	common::PoolSpec spec(kind);
	spec.kernel.push_back(op->pool_width);
	spec.stride.push_back(op->stride_width);
	spec.pad_before.push_back(op->pad_left);
	spec.pad_after.push_back(op->pad_right);
	spec.dilation.push_back(1);
	spec.count_include_pad = op->count_include_pad;
	spec.divisor_override = op->divisor_override;
	return spec;
}

inline common::PoolSpec poolSpec(
	const xir::AvgPool2d& op,
	common::PoolKind kind) {
	common::PoolSpec spec(kind);
	spec.kernel = { op->pool_height, op->pool_width };
	spec.stride = { op->stride_height, op->stride_width };
	spec.pad_before = { op->pad_top, op->pad_left };
	spec.pad_after = { op->pad_bottom, op->pad_right };
	spec.dilation = { 1, 1 };
	spec.count_include_pad = op->count_include_pad;
	spec.divisor_override = op->divisor_override;
	return spec;
}

inline common::PoolSpec poolSpec(
	const xir::AvgPool3d& op,
	common::PoolKind kind) {
	common::PoolSpec spec(kind);
	spec.kernel = {
		op->pool_depth, op->pool_height, op->pool_width
	};
	spec.stride = {
		op->stride_depth, op->stride_height, op->stride_width
	};
	spec.pad_before = {
		op->pad_front, op->pad_top, op->pad_left
	};
	spec.pad_after = {
		op->pad_back, op->pad_bottom, op->pad_right
	};
	spec.dilation = { 1, 1, 1 };
	spec.count_include_pad = op->count_include_pad;
	spec.divisor_override = op->divisor_override;
	return spec;
}

inline common::PaddingKind paddingKind(xir::PaddingMode mode) {
	if (mode == xir::PaddingMode::REFLECT) {
		return common::PaddingKind::kReflect;
	}
	if (mode == xir::PaddingMode::REPLICATE) {
		return common::PaddingKind::kReplicate;
	}
	if (mode == xir::PaddingMode::CIRCULAR) {
		return common::PaddingKind::kCircular;
	}
	return common::PaddingKind::kZeros;
}

inline common::PadKind padKind(xir::Pad::Mode mode) {
	if (mode == xir::Pad::Mode::REFLECTION) {
		return common::PadKind::kReflection;
	}
	if (mode == xir::Pad::Mode::REPLICATION) {
		return common::PadKind::kReplication;
	}
	if (mode == xir::Pad::Mode::SYMMETRIC) {
		return common::PadKind::kSymmetric;
	}
	return common::PadKind::kConstant;
}

inline bool scatterReduction(
	xir::Reduction reduction,
	common::ScatterReduction* converted) {
	if (reduction == xir::Reduction::NONE) {
		*converted = common::ScatterReduction::kNone;
		return true;
	}
	if (reduction == xir::Reduction::ADD) {
		*converted = common::ScatterReduction::kAdd;
		return true;
	}
	if (reduction == xir::Reduction::MULTIPLY) {
		*converted = common::ScatterReduction::kMultiply;
		return true;
	}
	if (reduction == xir::Reduction::MAX) {
		*converted = common::ScatterReduction::kMaximum;
		return true;
	}
	if (reduction == xir::Reduction::MIN) {
		*converted = common::ScatterReduction::kMinimum;
		return true;
	}
	return false;
}

inline common::ConvSpec convSpec(const xir::Conv1d& op) {
	common::ConvSpec spec;
	spec.stride.push_back(op->stride_width);
	spec.pad_before.push_back(op->pad_left);
	spec.pad_after.push_back(op->pad_right);
	spec.dilation.push_back(op->dilation_width);
	spec.groups = op->groups;
	spec.padding = paddingKind(op->padding_mode);
	return spec;
}

inline common::ConvSpec convSpec(const xir::Conv2d& op) {
	common::ConvSpec spec;
	spec.stride = { op->stride_height, op->stride_width };
	spec.pad_before = { op->pad_top, op->pad_left };
	spec.pad_after = { op->pad_bottom, op->pad_right };
	spec.dilation = { op->dilation_height, op->dilation_width };
	spec.groups = op->groups;
	spec.padding = paddingKind(op->padding_mode);
	return spec;
}

inline common::ConvSpec convSpec(const xir::Conv3d& op) {
	common::ConvSpec spec;
	spec.stride = {
		op->stride_depth, op->stride_height, op->stride_width
	};
	spec.pad_before = {
		op->pad_front, op->pad_top, op->pad_left
	};
	spec.pad_after = {
		op->pad_back, op->pad_bottom, op->pad_right
	};
	spec.dilation = {
		op->dilation_depth, op->dilation_height, op->dilation_width
	};
	spec.groups = op->groups;
	spec.padding = paddingKind(op->padding_mode);
	return spec;
}

inline common::ConvTransposeSpec convTransposeSpec(
	const xir::ConvTranspose1d& op) {
	common::ConvTransposeSpec spec;
	spec.stride = { op->stride_width };
	spec.pad_before = { op->pad_left };
	spec.pad_after = { op->pad_right };
	spec.dilation = { op->dilation_width };
	spec.output_padding = { op->output_pad_width };
	spec.groups = op->groups;
	return spec;
}

inline common::ConvTransposeSpec convTransposeSpec(
	const xir::ConvTranspose2d& op) {
	common::ConvTransposeSpec spec;
	spec.stride = { op->stride_height, op->stride_width };
	spec.pad_before = { op->pad_top, op->pad_left };
	spec.pad_after = { op->pad_bottom, op->pad_right };
	spec.dilation = { op->dilation_height, op->dilation_width };
	spec.output_padding = {
		op->output_pad_height, op->output_pad_width
	};
	spec.groups = op->groups;
	return spec;
}

inline common::ConvTransposeSpec convTransposeSpec(
	const xir::ConvTranspose3d& op) {
	common::ConvTransposeSpec spec;
	spec.stride = {
		op->stride_depth, op->stride_height, op->stride_width
	};
	spec.pad_before = {
		op->pad_front, op->pad_top, op->pad_left
	};
	spec.pad_after = {
		op->pad_back, op->pad_bottom, op->pad_right
	};
	spec.dilation = {
		op->dilation_depth, op->dilation_height, op->dilation_width
	};
	spec.output_padding = {
		op->output_pad_depth,
		op->output_pad_height,
		op->output_pad_width
	};
	spec.groups = op->groups;
	return spec;
}

struct PreparedOutput {
	xrt::Tensor tensor;
	bool copy_to_user = false;
};

inline PreparedOutput prepareOutput(
	const xir::TensorType& output_type,
	const std::vector<xrt::Tensor>& inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(!inputs.empty(), 12011)
		.append("Portable HostBackend operator expects at least one input tensor.");
	for (std::size_t i = 0; i < inputs.size(); ++i) {
		ICRAFT_CHECK(inputs[i].hasData(), 12011)
			.append("Portable HostBackend input tensor {} has no allocated data.", i);
	}

	if (!user_outputs.empty()) {
		ICRAFT_CHECK(user_outputs.size() == 1U, 12011)
			.append("Portable HostBackend operator expects one user output tensor.");
		ICRAFT_CHECK(user_outputs[0].hasData(), 12011)
			.append("Portable HostBackend user output tensor has no allocated data.");
		ICRAFT_CHECK(user_outputs[0].dtype().bytes() == output_type.bytes(), 12011)
			.append(
				"Portable HostBackend user output bytes {} do not match expected bytes {}.",
				user_outputs[0].dtype().bytes(),
				output_type.bytes());
		ICRAFT_CHECK(user_outputs[0].dtype() == output_type, 12011)
			.append(
				"Portable HostBackend user output dtype/layout does not match the declared output.");
		if (isCpuAddressable(user_outputs[0])) {
			PreparedOutput result;
			result.tensor = user_outputs[0];
			return result;
		}
	}

	PreparedOutput result;
	result.tensor = xrt::Tensor(output_type);
	result.tensor.mallocOn(xrt::HostDevice::MemRegion());
	result.copy_to_user = !user_outputs.empty();
	return result;
}

inline xrt::Tensor synchronizeInput(const xrt::Tensor& input) {
	const std::chrono::milliseconds timeout(10000);
	const std::chrono::milliseconds poll_interval(0);
	ICRAFT_CHECK(input.hasData(), 12011)
		.append("Portable HostBackend input tensor has no allocated data.");
	ICRAFT_CHECK(input.waitForReady(timeout, poll_interval), 12011)
		.append("Portable HostBackend input tensor synchronization timed out.");

	const xrt::PtrType pointer_type = input.data().ptype();
	if (pointer_type == xrt::PtrType::ADDR) {
		// Tensor::to delegates the transfer to the source and target MemRegion
		// implementations, so the physical-memory access remains OS-specific.
		return input.to(xrt::HostDevice::MemRegion());
	}
	if (pointer_type == xrt::PtrType::BOTH) {
		icraft::osal::cache::invalidate_range(
			input.data().cptr(),
			static_cast<std::size_t>(input.dtype().bytes()));
	}
	return input;
}

inline xrt::Tensor publishOutput(
	const PreparedOutput& output,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(isCpuAddressable(output.tensor), 12011)
		.append("Portable HostBackend compute output is not CPU-addressable.");
	if (output.tensor.data().ptype() == xrt::PtrType::BOTH) {
		icraft::osal::cache::flush_range(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()));
	}
	if (!output.copy_to_user) {
		return output.tensor;
	}

	ICRAFT_CHECK(user_outputs.size() == 1U, 12011)
		.append("Portable HostBackend copy-back expects one user output tensor.");
	xrt::Tensor user_output = user_outputs[0];
	user_output.copyFrom(
		0, output.tensor, 0, output.tensor.dtype().bytes());
	return user_output;
}

inline common::Status describeInputOutput(
	const xrt::Tensor& input,
	xrt::Tensor& output,
	const xir::TensorType& input_type,
	const xir::TensorType& output_type,
	common::RoundingMode rounding,
	common::TensorDesc* input_desc,
	common::TensorDesc* output_desc) {
	common::Status status = describeTensor(
		input.data().cptr(),
		static_cast<std::size_t>(input.dtype().bytes()),
		input_type,
		rounding,
		input_desc);
	if (!status.ok()) {
		return status;
	}
	return describeTensor(
		output.data().cptr(),
		static_cast<std::size_t>(output.dtype().bytes()),
		output_type,
		rounding,
		output_desc);
}

template <typename Op>
inline std::vector<xrt::Tensor> forwardUnary(
	const Op& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs,
	const common::UnarySpec& spec) {
	ICRAFT_CHECK(op->inputs.size() == 1U, 12011)
		.append("{} must declare one input.", op->typeKey());
	ICRAFT_CHECK(op->outputs.size() == 1U, 12011)
		.append("{} must declare one output.", op->typeKey());
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	ICRAFT_CHECK(materialized.size() == 1U, 12011)
		.append("{} must materialize one input.", op->typeKey());
	const xrt::Tensor input = synchronizeInput(materialized[0]);

	const xir::TensorType input_type = op->inputs[0].tensorType();
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		input_type,
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} tensor description failed: {}",
			op->typeKey(),
			status.message);

	status = common::unaryElementwise(input_desc, output_desc, spec);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} portable kernel failed: {}",
			op->typeKey(),
			status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

template <typename Op>
inline std::vector<xrt::Tensor> forwardBinary(
	const Op& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs,
	const common::BinarySpec& spec) {
	ICRAFT_CHECK(op->inputs.size() == 2U, 12011)
		.append("{} must declare two inputs.", op->typeKey());
	ICRAFT_CHECK(op->outputs.size() == 1U, 12011)
		.append("{} must declare one output.", op->typeKey());
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	ICRAFT_CHECK(materialized.size() == 2U, 12011)
		.append("{} must materialize two inputs.", op->typeKey());
	const xrt::Tensor lhs = synchronizeInput(materialized[0]);
	const xrt::Tensor rhs = synchronizeInput(materialized[1]);

	const xir::TensorType lhs_type = op->inputs[0].tensorType();
	const xir::TensorType rhs_type = op->inputs[1].tensorType();
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	common::TensorDesc lhs_desc;
	common::TensorDesc rhs_desc;
	common::TensorDesc output_desc;
	const common::RoundingMode rounding = roundingMode(op->compile_target);
	common::Status status = describeTensor(
		lhs.data().cptr(),
		static_cast<std::size_t>(lhs.dtype().bytes()),
		lhs_type,
		rounding,
		&lhs_desc);
	if (status.ok()) {
		status = describeTensor(
			rhs.data().cptr(),
			static_cast<std::size_t>(rhs.dtype().bytes()),
			rhs_type,
			rounding,
			&rhs_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} tensor description failed: {}",
			op->typeKey(),
			status.message);

	status = common::binaryElementwise(
		lhs_desc, rhs_desc, output_desc, spec);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} portable kernel failed: {}",
			op->typeKey(),
			status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

template <typename Op>
inline std::vector<xrt::Tensor> forwardReduction(
	const Op& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs,
	const common::ReductionSpec& spec) {
	ICRAFT_CHECK(op->inputs.size() == 1U, 12011)
		.append("{} must declare one input.", op->typeKey());
	ICRAFT_CHECK(op->outputs.size() == 1U, 12011)
		.append("{} must declare one output.", op->typeKey());
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xir::TensorType input_type = op->inputs[0].tensorType();
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		input_type,
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} tensor description failed: {}",
			op->typeKey(),
			status.message);
	status = common::reduce(input_desc, output_desc, spec);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} portable kernel failed: {}",
			op->typeKey(),
			status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardMatmul(
	const xir::Matmul& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(
		op->inputs.size() == 2U || op->inputs.size() == 3U, 12011)
		.append("Matmul must declare two inputs and an optional bias.");
	ICRAFT_CHECK(op->outputs.size() == 1U, 12011)
		.append("Matmul must declare one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	std::vector<xrt::Tensor> synchronized;
	synchronized.reserve(materialized.size());
	for (std::size_t i = 0U; i < materialized.size(); ++i) {
		synchronized.push_back(synchronizeInput(materialized[i]));
	}

	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	common::TensorDesc lhs_desc;
	common::TensorDesc rhs_desc;
	common::TensorDesc bias_desc;
	common::TensorDesc output_desc;
	common::Status status = describeTensor(
		synchronized[0].data().cptr(),
		static_cast<std::size_t>(synchronized[0].dtype().bytes()),
		op->inputs[0].tensorType(),
		rounding,
		&lhs_desc);
	if (status.ok()) {
		status = describeTensor(
			synchronized[1].data().cptr(),
			static_cast<std::size_t>(synchronized[1].dtype().bytes()),
			op->inputs[1].tensorType(),
			rounding,
			&rhs_desc);
	}
	if (status.ok() && synchronized.size() == 3U) {
		status = describeTensor(
			synchronized[2].data().cptr(),
			static_cast<std::size_t>(synchronized[2].dtype().bytes()),
			op->inputs[2].tensorType(),
			rounding,
			&bias_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Matmul tensor description failed: {}", status.message);
	const common::TensorDesc* bias =
		synchronized.size() == 3U ? &bias_desc : NULL;
	status = common::matmul(lhs_desc, rhs_desc, bias, output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Matmul portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardEinsum(
	const xir::Einsum& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(!op->inputs.empty() && op->outputs.size() == 1U, 12011)
		.append("Einsum must declare inputs and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	std::vector<xrt::Tensor> synchronized;
	synchronized.reserve(materialized.size());
	for (std::size_t i = 0U; i < materialized.size(); ++i) {
		synchronized.push_back(synchronizeInput(materialized[i]));
	}
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	std::vector<common::TensorDesc> input_descs(materialized.size());
	common::TensorDesc output_desc;
	common::Status status;
	for (std::size_t i = 0U; i < synchronized.size(); ++i) {
		status = describeTensor(
			synchronized[i].data().cptr(),
			static_cast<std::size_t>(synchronized[i].dtype().bytes()),
			op->inputs[i].tensorType(),
			rounding,
			&input_descs[i]);
		if (!status.ok()) {
			break;
		}
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Einsum tensor description failed: {}", status.message);
	status = common::einsum(input_descs, output_desc, op->equation);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Einsum portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

template <typename Op>
inline std::vector<xrt::Tensor> forwardConvolution(
	const Op& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs,
	const common::ConvSpec& spec) {
	ICRAFT_CHECK(
		op->inputs.size() == 2U || op->inputs.size() == 3U, 12011)
		.append(
			"{} must declare input, weights, and an optional bias.",
			op->typeKey());
	ICRAFT_CHECK(op->outputs.size() == 1U, 12011)
		.append("{} must declare one output.", op->typeKey());
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	std::vector<xrt::Tensor> synchronized;
	synchronized.reserve(materialized.size());
	for (std::size_t i = 0U; i < materialized.size(); ++i) {
		synchronized.push_back(synchronizeInput(materialized[i]));
	}

	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	common::TensorDesc input_desc;
	common::TensorDesc weights_desc;
	common::TensorDesc bias_desc;
	common::TensorDesc output_desc;
	common::Status status = describeTensor(
		synchronized[0].data().cptr(),
		static_cast<std::size_t>(synchronized[0].dtype().bytes()),
		op->inputs[0].tensorType(),
		rounding,
		&input_desc);
	if (status.ok()) {
		status = describeTensor(
			synchronized[1].data().cptr(),
			static_cast<std::size_t>(synchronized[1].dtype().bytes()),
			op->inputs[1].tensorType(),
			rounding,
			&weights_desc);
	}
	if (status.ok() && synchronized.size() == 3U) {
		status = describeTensor(
			synchronized[2].data().cptr(),
			static_cast<std::size_t>(synchronized[2].dtype().bytes()),
			op->inputs[2].tensorType(),
			rounding,
			&bias_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} tensor description failed: {}",
			op->typeKey(),
			status.message);
	const common::TensorDesc* bias =
		synchronized.size() == 3U ? &bias_desc : NULL;
	status = common::convolution(
		input_desc, weights_desc, bias, output_desc, spec);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} portable kernel failed: {}",
			op->typeKey(),
			status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

template <typename Op>
inline std::vector<xrt::Tensor> forwardConvTranspose(
	const Op& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(
		op->inputs.size() == 2U || op->inputs.size() == 3U, 12011)
		.append(
			"{} must declare input, weights, and an optional bias.",
			op->typeKey());
	ICRAFT_CHECK(op->outputs.size() == 1U, 12011)
		.append("{} must declare one output.", op->typeKey());
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	std::vector<xrt::Tensor> synchronized;
	synchronized.reserve(materialized.size());
	for (std::size_t i = 0U; i < materialized.size(); ++i) {
		synchronized.push_back(synchronizeInput(materialized[i]));
	}
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	common::TensorDesc input_desc;
	common::TensorDesc weights_desc;
	common::TensorDesc bias_desc;
	common::TensorDesc output_desc;
	common::Status status = describeTensor(
		synchronized[0].data().cptr(),
		static_cast<std::size_t>(synchronized[0].dtype().bytes()),
		op->inputs[0].tensorType(),
		rounding,
		&input_desc);
	if (status.ok()) {
		status = describeTensor(
			synchronized[1].data().cptr(),
			static_cast<std::size_t>(synchronized[1].dtype().bytes()),
			op->inputs[1].tensorType(),
			rounding,
			&weights_desc);
	}
	if (status.ok() && synchronized.size() == 3U) {
		status = describeTensor(
			synchronized[2].data().cptr(),
			static_cast<std::size_t>(synchronized[2].dtype().bytes()),
			op->inputs[2].tensorType(),
			rounding,
			&bias_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} tensor description failed: {}",
			op->typeKey(),
			status.message);
	const common::TensorDesc* bias =
		synchronized.size() == 3U ? &bias_desc : NULL;
	status = common::convTranspose(
		input_desc,
		weights_desc,
		bias,
		output_desc,
		convTransposeSpec(op));
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} portable kernel failed: {}",
			op->typeKey(),
			status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

template <typename Op>
inline std::vector<xrt::Tensor> forwardPool(
	const Op& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs,
	const common::PoolSpec& spec) {
	ICRAFT_CHECK(op->inputs.size() == 1U, 12011)
		.append("{} must declare one input.", op->typeKey());
	ICRAFT_CHECK(op->outputs.size() == 1U, 12011)
		.append("{} must declare one output.", op->typeKey());
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xir::TensorType input_type = op->inputs[0].tensorType();
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		input_type,
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} tensor description failed: {}",
			op->typeKey(),
			status.message);
	status = common::pool(input_desc, output_desc, spec);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} portable kernel failed: {}",
			op->typeKey(),
			status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardResize(
	const xir::Resize& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append("Resize must declare one input and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xir::TensorType input_type = op->inputs[0].tensorType();
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		input_type,
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Resize tensor description failed: {}", status.message);
	ICRAFT_CHECK(op->dsize.size() == output_desc.shape.size(), 12011)
		.append("Resize dsize rank does not match its declared output.");
	for (std::size_t axis = 0U; axis < output_desc.shape.size(); ++axis) {
		ICRAFT_CHECK(op->dsize[axis] == output_desc.shape[axis], 12011)
			.append(
				"Resize dsize does not match its declared output at axis {}.",
				axis);
	}
	ICRAFT_CHECK(
		op->interpolation == xir::ResizeInterpolation::INTER_NEAREST ||
		op->interpolation == xir::ResizeInterpolation::INTER_LINEAR,
		12011)
		.append("Resize interpolation mode is unsupported.");
	const bool linear =
		op->interpolation == xir::ResizeInterpolation::INTER_LINEAR;
	status = common::resize2d(input_desc, output_desc, linear);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Resize portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardUpsample(
	const xir::Upsample& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append("Upsample must declare one input and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		op->inputs[0].tensorType(),
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Upsample tensor description failed: {}", status.message);
	ICRAFT_CHECK(
		output_desc.shape.size() == 4U &&
		output_desc.shape[1] == op->height &&
		output_desc.shape[2] == op->width, 12011)
		.append("Upsample output shape does not match height and width.");
	common::ResizeKind kind = common::ResizeKind::kNearest;
	if (op->interpolation == xir::Upsample::Interpolation::BILINEAR) {
		kind = common::ResizeKind::kLinear;
	}
	else if (op->interpolation == xir::Upsample::Interpolation::BICUBIC) {
		ICRAFT_CHECK(!op->align_corners, 12011)
			.append(
				"Upsample align_corners is unsupported for bicubic mode.");
		kind = common::ResizeKind::kCubic;
	}
	else {
		ICRAFT_CHECK(
			op->interpolation == xir::Upsample::Interpolation::NEAREST,
			12011)
			.append("Upsample interpolation mode is unsupported.");
	}
	status = common::resize2d(
		input_desc,
		output_desc,
		kind,
		op->align_corners);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Upsample portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardUnfold(
	const xir::Unfold& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append("Unfold must declare one input and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		op->inputs[0].tensorType(),
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Unfold tensor description failed: {}", status.message);
	common::UnfoldSpec spec;
	spec.kernel_height = op->kernel_height;
	spec.kernel_width = op->kernel_width;
	spec.stride_height = op->stride_height;
	spec.stride_width = op->stride_width;
	spec.pad_top = op->pad_top;
	spec.pad_bottom = op->pad_bottom;
	spec.pad_left = op->pad_left;
	spec.pad_right = op->pad_right;
	spec.dilation_height = op->dilation_height;
	spec.dilation_width = op->dilation_width;
	status = common::unfold(input_desc, output_desc, spec);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Unfold portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardGridNSample(
	const xir::GridNSample& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 2U && op->outputs.size() == 1U, 12011)
		.append("GridNSample must declare input, grid, and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xrt::Tensor grid = synchronizeInput(materialized[1]);
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	common::TensorDesc input_desc;
	common::TensorDesc grid_desc;
	common::TensorDesc output_desc;
	common::Status status = describeTensor(
		input.data().cptr(),
		static_cast<std::size_t>(input.dtype().bytes()),
		op->inputs[0].tensorType(),
		rounding,
		&input_desc);
	if (status.ok()) {
		status = describeTensor(
			grid.data().cptr(),
			static_cast<std::size_t>(grid.dtype().bytes()),
			op->inputs[1].tensorType(),
			rounding,
			&grid_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append("GridNSample tensor description failed: {}", status.message);
	common::GridSampleSpec spec;
	spec.interpolation_mode = op->interpolation_mode;
	spec.padding_mode = op->padding_mode;
	spec.align_corners = op->align_corners;
	spec.grid_divisor_height = op->grid_divisor_h;
	spec.grid_divisor_width = op->grid_divisor_w;
	spec.scale_height = static_cast<double>(op->scale_h);
	spec.scale_width = static_cast<double>(op->scale_w);
	status = common::gridSample2d(
		input_desc, grid_desc, output_desc, spec);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("GridNSample portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardConcat(
	const xir::Concat& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(!op->inputs.empty() && op->outputs.size() == 1U, 12011)
		.append("Concat must declare inputs and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	std::vector<xrt::Tensor> synchronized;
	synchronized.reserve(materialized.size());
	for (std::size_t i = 0U; i < materialized.size(); ++i) {
		synchronized.push_back(synchronizeInput(materialized[i]));
	}
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	std::vector<common::TensorDesc> input_descs(materialized.size());
	common::TensorDesc output_desc;
	common::Status status;
	for (std::size_t i = 0U; i < synchronized.size(); ++i) {
		status = describeTensor(
			synchronized[i].data().cptr(),
			static_cast<std::size_t>(synchronized[i].dtype().bytes()),
			op->inputs[i].tensorType(),
			rounding,
			&input_descs[i]);
		if (!status.ok()) {
			break;
		}
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Concat tensor description failed: {}", status.message);
	status = common::concatenate(input_descs, output_desc, op->axis);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Concat portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardSplit(
	const xir::Split& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U, 12011)
		.append("Split must declare one input.");
	ICRAFT_CHECK(
		op->outputs.size() == op->sections.size() &&
		!op->outputs.empty(), 12011)
		.append("Split outputs must match its sections.");
	ICRAFT_CHECK(
		user_outputs.empty() ||
		user_outputs.size() == op->outputs.size(), 12011)
		.append("Split user outputs must be empty or cover every output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	common::TensorDesc input_desc;
	common::Status status = describeTensor(
		input.data().cptr(),
		static_cast<std::size_t>(input.dtype().bytes()),
		op->inputs[0].tensorType(),
		rounding,
		&input_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Split input description failed: {}", status.message);

	std::vector<PreparedOutput> prepared_outputs;
	std::vector<common::TensorDesc> output_descs(op->outputs.size());
	std::vector<common::TensorDesc*> output_desc_pointers;
	prepared_outputs.reserve(op->outputs.size());
	output_desc_pointers.reserve(op->outputs.size());
	for (std::size_t i = 0U; i < op->outputs.size(); ++i) {
		std::vector<xrt::Tensor> selected_user_output;
		if (!user_outputs.empty()) {
			selected_user_output.push_back(user_outputs[i]);
		}
		prepared_outputs.push_back(prepareOutput(
			op->outputs[i].tensorType(),
			materialized,
			selected_user_output));
		status = describeTensor(
			prepared_outputs.back().tensor.data().cptr(),
			static_cast<std::size_t>(
				prepared_outputs.back().tensor.dtype().bytes()),
			op->outputs[i].tensorType(),
			rounding,
			&output_descs[i]);
		ICRAFT_CHECK(status.ok(), 12011)
			.append(
				"Split output {} description failed: {}",
				i,
				status.message);
		output_desc_pointers.push_back(&output_descs[i]);
	}
	const std::vector<int64_t> sections(
		op->sections.begin(), op->sections.end());
	status = common::split(
		input_desc, output_desc_pointers, sections, op->axis);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Split portable kernel failed: {}", status.message);

	std::vector<xrt::Tensor> results;
	results.reserve(prepared_outputs.size());
	for (std::size_t i = 0U; i < prepared_outputs.size(); ++i) {
		std::vector<xrt::Tensor> selected_user_output;
		if (!user_outputs.empty()) {
			selected_user_output.push_back(user_outputs[i]);
		}
		results.push_back(publishOutput(
			prepared_outputs[i], selected_user_output));
	}
	return results;
}

template <typename Op>
inline std::vector<xrt::Tensor> forwardGatherImpl(
	const Op& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs,
	bool elementwise) {
	ICRAFT_CHECK(op->inputs.size() == 2U && op->outputs.size() == 1U, 12011)
		.append("{} must declare two inputs and one output.", op->typeKey());
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xrt::Tensor indices = synchronizeInput(materialized[1]);
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	common::TensorDesc input_desc;
	common::TensorDesc indices_desc;
	common::TensorDesc output_desc;
	common::Status status = describeTensor(
		input.data().cptr(),
		static_cast<std::size_t>(input.dtype().bytes()),
		op->inputs[0].tensorType(),
		rounding,
		&input_desc);
	if (status.ok()) {
		status = describeTensor(
			indices.data().cptr(),
			static_cast<std::size_t>(indices.dtype().bytes()),
			op->inputs[1].tensorType(),
			rounding,
			&indices_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} tensor description failed: {}",
			op->typeKey(),
			status.message);
	status = elementwise
		? common::gatherElements(
			input_desc, indices_desc, output_desc, op->axis)
		: common::gather(
			input_desc, indices_desc, output_desc, op->axis);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} portable kernel failed: {}",
			op->typeKey(),
			status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardGather(
	const xir::Gather& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	return forwardGatherImpl(op, runtime_inputs, user_outputs, false);
}

inline std::vector<xrt::Tensor> forwardGatherElements(
	const xir::GatherElements& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	return forwardGatherImpl(op, runtime_inputs, user_outputs, true);
}

inline std::vector<xrt::Tensor> forwardSlice(
	const xir::Slice& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append("Slice must declare one input and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		op->inputs[0].tensorType(),
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Slice tensor description failed: {}", status.message);
	const std::vector<int64_t> begin(op->begin.begin(), op->begin.end());
	const std::vector<int64_t> end(op->end.begin(), op->end.end());
	const std::vector<int64_t> stride(
		op->stride.begin(), op->stride.end());
	status = common::slice(
		input_desc, output_desc, begin, end, stride);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Slice portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardEmbedding(
	const xir::Embedding& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append("Embedding must declare one input and one output.");
	ICRAFT_CHECK(op->weights.hasData(), 12011)
		.append("Embedding weights parameter has no data.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor indices = synchronizeInput(materialized[0]);
	const xrt::Tensor weights =
		synchronizeInput(xrt::Tensor(op->weights));
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	common::TensorDesc indices_desc;
	common::TensorDesc weights_desc;
	common::TensorDesc output_desc;
	common::Status status = describeTensor(
		indices.data().cptr(),
		static_cast<std::size_t>(indices.dtype().bytes()),
		op->inputs[0].tensorType(),
		rounding,
		&indices_desc);
	if (status.ok()) {
		status = describeTensor(
			weights.data().cptr(),
			static_cast<std::size_t>(weights.dtype().bytes()),
			op->weights.tensorType(),
			rounding,
			&weights_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Embedding tensor description failed: {}", status.message);
	status = common::embedding(indices_desc, weights_desc, output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Embedding portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardTopK(
	const xir::TopK& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 2U && op->outputs.size() == 2U, 12011)
		.append("TopK must declare input, k, values, and indices.");
	ICRAFT_CHECK(user_outputs.empty() || user_outputs.size() == 2U, 12011)
		.append("TopK user outputs must be empty or contain two tensors.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xrt::Tensor k_tensor = synchronizeInput(materialized[1]);
	std::vector<xrt::Tensor> values_user_output;
	std::vector<xrt::Tensor> indices_user_output;
	if (!user_outputs.empty()) {
		values_user_output.push_back(user_outputs[0]);
		indices_user_output.push_back(user_outputs[1]);
	}
	PreparedOutput values = prepareOutput(
		op->outputs[0].tensorType(), materialized, values_user_output);
	PreparedOutput indices = prepareOutput(
		op->outputs[1].tensorType(), materialized, indices_user_output);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	common::TensorDesc input_desc;
	common::TensorDesc k_desc;
	common::TensorDesc values_desc;
	common::TensorDesc indices_desc;
	common::Status status = describeTensor(
		input.data().cptr(),
		static_cast<std::size_t>(input.dtype().bytes()),
		op->inputs[0].tensorType(),
		rounding,
		&input_desc);
	if (status.ok()) {
		status = describeTensor(
			k_tensor.data().cptr(),
			static_cast<std::size_t>(k_tensor.dtype().bytes()),
			op->inputs[1].tensorType(),
			rounding,
			&k_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			values.tensor.data().cptr(),
			static_cast<std::size_t>(values.tensor.dtype().bytes()),
			op->outputs[0].tensorType(),
			rounding,
			&values_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			indices.tensor.data().cptr(),
			static_cast<std::size_t>(indices.tensor.dtype().bytes()),
			op->outputs[1].tensorType(),
			rounding,
			&indices_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append("TopK tensor description failed: {}", status.message);
	status = common::topK(
		input_desc,
		k_desc,
		values_desc,
		indices_desc,
		op->axis,
		op->largest,
		op->sorted);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("TopK portable kernel failed: {}", status.message);
	std::vector<xrt::Tensor> results;
	results.reserve(2U);
	results.push_back(publishOutput(values, values_user_output));
	results.push_back(publishOutput(indices, indices_user_output));
	return results;
}

template <typename Op>
inline std::vector<xrt::Tensor> forwardScatter(
	const Op& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs,
	bool nd,
	int64_t axis) {
	ICRAFT_CHECK(op->inputs.size() == 3U && op->outputs.size() == 1U, 12011)
		.append("{} must declare data, indices, updates, and output.", op->typeKey());
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	std::vector<xrt::Tensor> synchronized;
	synchronized.reserve(3U);
	for (std::size_t i = 0U; i < materialized.size(); ++i) {
		synchronized.push_back(synchronizeInput(materialized[i]));
	}
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	std::vector<common::TensorDesc> input_descs(3U);
	common::TensorDesc output_desc;
	common::Status status;
	for (std::size_t i = 0U; i < synchronized.size(); ++i) {
		status = describeTensor(
			synchronized[i].data().cptr(),
			static_cast<std::size_t>(synchronized[i].dtype().bytes()),
			op->inputs[i].tensorType(),
			rounding,
			&input_descs[i]);
		if (!status.ok()) {
			break;
		}
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} tensor description failed: {}",
			op->typeKey(),
			status.message);
	common::ScatterReduction reduction = common::ScatterReduction::kNone;
	ICRAFT_CHECK(scatterReduction(op->reduction, &reduction), 12011)
		.append("{} reduction mode is unsupported.", op->typeKey());
	if (nd) {
		status = common::scatterND(
			input_descs[0],
			input_descs[1],
			input_descs[2],
			output_desc,
			reduction);
	}
	else {
		status = common::scatterElement(
			input_descs[0],
			input_descs[1],
			input_descs[2],
			output_desc,
			axis,
			reduction);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} portable kernel failed: {}",
			op->typeKey(),
			status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardScatterElement(
	const xir::ScatterElement& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	return forwardScatter(
		op, runtime_inputs, user_outputs, false, op->axis);
}

inline std::vector<xrt::Tensor> forwardScatterND(
	const xir::ScatterND& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	return forwardScatter(op, runtime_inputs, user_outputs, true, 0);
}

inline std::vector<xrt::Tensor> forwardWhere(
	const xir::Where& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 3U && op->outputs.size() == 1U, 12011)
		.append("Where must declare lhs, rhs, condition, and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	std::vector<xrt::Tensor> synchronized;
	synchronized.reserve(materialized.size());
	for (std::size_t i = 0U; i < materialized.size(); ++i) {
		synchronized.push_back(synchronizeInput(materialized[i]));
	}
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	std::vector<common::TensorDesc> input_descs(3U);
	common::TensorDesc output_desc;
	common::Status status;
	for (std::size_t i = 0U; i < synchronized.size(); ++i) {
		status = describeTensor(
			synchronized[i].data().cptr(),
			static_cast<std::size_t>(synchronized[i].dtype().bytes()),
			op->inputs[i].tensorType(),
			rounding,
			&input_descs[i]);
		if (!status.ok()) {
			break;
		}
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Where tensor description failed: {}", status.message);
	status = common::where(
		input_descs[0], input_descs[1], input_descs[2], output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Where portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardTile(
	const xir::Tile& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append("Tile must declare one input and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		op->inputs[0].tensorType(),
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Tile tensor description failed: {}", status.message);
	const std::vector<int64_t> repetitions(
		op->dims.begin(), op->dims.end());
	status = common::tile(input_desc, output_desc, repetitions);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Tile portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardPad(
	const xir::Pad& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append("Pad must declare one input and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		op->inputs[0].tensorType(),
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Pad tensor description failed: {}", status.message);
	const std::vector<int64_t> padding(
		op->padding.begin(), op->padding.end());
	status = common::pad(
		input_desc,
		output_desc,
		padding,
		padKind(op->mode),
		scalarValue(op->value));
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Pad portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardRoll(
	const xir::Roll& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append("Roll must declare one input and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		op->inputs[0].tensorType(),
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Roll tensor description failed: {}", status.message);
	const std::vector<int64_t> shifts(
		op->shifts.begin(), op->shifts.end());
	std::vector<int64_t> dimensions;
	const std::vector<int64_t>* dimension_pointer = NULL;
	if (op->dims.has_value()) {
		dimensions.assign(
			op->dims.value().begin(), op->dims.value().end());
		dimension_pointer = &dimensions;
	}
	status = common::roll(
		input_desc,
		output_desc,
		shifts,
		dimension_pointer);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Roll portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardChannelShuffle(
	const xir::ChannelShuffle& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append("ChannelShuffle must declare one input and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		op->inputs[0].tensorType(),
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"ChannelShuffle tensor description failed: {}",
			status.message);
	status = common::channelShuffle(
		input_desc, output_desc, op->groups);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"ChannelShuffle portable kernel failed: {}",
			status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardPixelShuffle(
	const xir::PixelShuffle& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append("PixelShuffle must declare one input and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		op->inputs[0].tensorType(),
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"PixelShuffle tensor description failed: {}",
			status.message);
	status = common::pixelShuffle(
		input_desc, output_desc, op->upscale_factor);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"PixelShuffle portable kernel failed: {}",
			status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardStack(
	const xir::Stack& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() >= 2U && op->outputs.size() == 1U, 12011)
		.append("Stack must declare at least two inputs and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	std::vector<xrt::Tensor> synchronized;
	synchronized.reserve(materialized.size());
	for (std::size_t i = 0U; i < materialized.size(); ++i) {
		synchronized.push_back(synchronizeInput(materialized[i]));
	}
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	std::vector<common::TensorDesc> input_descs(materialized.size());
	common::TensorDesc output_desc;
	common::Status status;
	for (std::size_t i = 0U; i < synchronized.size(); ++i) {
		status = describeTensor(
			synchronized[i].data().cptr(),
			static_cast<std::size_t>(synchronized[i].dtype().bytes()),
			op->inputs[i].tensorType(),
			rounding,
			&input_descs[i]);
		if (!status.ok()) {
			break;
		}
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Stack tensor description failed: {}", status.message);
	status = common::stack(input_descs, output_desc, op->dim);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Stack portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardUnstack(
	const xir::Unstack& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && !op->outputs.empty(), 12011)
		.append("Unstack must declare one input and outputs.");
	ICRAFT_CHECK(
		user_outputs.empty() ||
		user_outputs.size() == op->outputs.size(), 12011)
		.append("Unstack user outputs must be empty or cover every output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	common::TensorDesc input_desc;
	common::Status status = describeTensor(
		input.data().cptr(),
		static_cast<std::size_t>(input.dtype().bytes()),
		op->inputs[0].tensorType(),
		rounding,
		&input_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Unstack input description failed: {}", status.message);

	std::vector<PreparedOutput> prepared_outputs;
	std::vector<common::TensorDesc> output_descs(op->outputs.size());
	std::vector<common::TensorDesc*> output_desc_pointers;
	prepared_outputs.reserve(op->outputs.size());
	output_desc_pointers.reserve(op->outputs.size());
	for (std::size_t i = 0U; i < op->outputs.size(); ++i) {
		std::vector<xrt::Tensor> selected_user_output;
		if (!user_outputs.empty()) {
			selected_user_output.push_back(user_outputs[i]);
		}
		prepared_outputs.push_back(prepareOutput(
			op->outputs[i].tensorType(),
			materialized,
			selected_user_output));
		status = describeTensor(
			prepared_outputs.back().tensor.data().cptr(),
			static_cast<std::size_t>(
				prepared_outputs.back().tensor.dtype().bytes()),
			op->outputs[i].tensorType(),
			rounding,
			&output_descs[i]);
		ICRAFT_CHECK(status.ok(), 12011)
			.append(
				"Unstack output {} description failed: {}",
				i,
				status.message);
		output_desc_pointers.push_back(&output_descs[i]);
	}
	status = common::unstack(input_desc, output_desc_pointers, op->dim);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Unstack portable kernel failed: {}", status.message);
	std::vector<xrt::Tensor> results;
	results.reserve(prepared_outputs.size());
	for (std::size_t i = 0U; i < prepared_outputs.size(); ++i) {
		std::vector<xrt::Tensor> selected_user_output;
		if (!user_outputs.empty()) {
			selected_user_output.push_back(user_outputs[i]);
		}
		results.push_back(publishOutput(
			prepared_outputs[i], selected_user_output));
	}
	return results;
}

inline std::vector<xrt::Tensor> forwardNormalize(
	const xir::Normalize& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append("Normalize must declare one input and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xir::TensorType input_type = op->inputs[0].tensorType();
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		input_type,
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Normalize tensor description failed: {}", status.message);
	const std::vector<int64_t> axes(op->axis.begin(), op->axis.end());
	status = common::normalizeLp(
		input_desc,
		output_desc,
		axes,
		static_cast<double>(op->p),
		static_cast<double>(op->eps));
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Normalize portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardLayerNorm(
	const xir::LayerNorm& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append("LayerNorm must declare one input and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	std::vector<xrt::Tensor> parameters;
	std::size_t gamma_index = (std::numeric_limits<std::size_t>::max)();
	std::size_t beta_index = (std::numeric_limits<std::size_t>::max)();
	if (op->gamma.has_value()) {
		const xir::Params gamma = op->gamma.value();
		ICRAFT_CHECK(gamma.hasData(), 12011)
			.append("LayerNorm gamma parameter has no data.");
		gamma_index = parameters.size();
		parameters.push_back(synchronizeInput(xrt::Tensor(gamma)));
	}
	if (op->beta.has_value()) {
		const xir::Params beta = op->beta.value();
		ICRAFT_CHECK(beta.hasData(), 12011)
			.append("LayerNorm beta parameter has no data.");
		beta_index = parameters.size();
		parameters.push_back(synchronizeInput(xrt::Tensor(beta)));
	}

	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	common::TensorDesc input_desc;
	common::TensorDesc gamma_desc;
	common::TensorDesc beta_desc;
	common::TensorDesc output_desc;
	common::Status status = describeTensor(
		input.data().cptr(),
		static_cast<std::size_t>(input.dtype().bytes()),
		op->inputs[0].tensorType(),
		rounding,
		&input_desc);
	if (status.ok() && gamma_index !=
		(std::numeric_limits<std::size_t>::max)()) {
		status = describeTensor(
			parameters[gamma_index].data().cptr(),
			static_cast<std::size_t>(
				parameters[gamma_index].dtype().bytes()),
			op->gamma.value().tensorType(),
			rounding,
			&gamma_desc);
	}
	if (status.ok() && beta_index !=
		(std::numeric_limits<std::size_t>::max)()) {
		status = describeTensor(
			parameters[beta_index].data().cptr(),
			static_cast<std::size_t>(
				parameters[beta_index].dtype().bytes()),
			op->beta.value().tensorType(),
			rounding,
			&beta_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append("LayerNorm tensor description failed: {}", status.message);
	const common::TensorDesc* gamma = gamma_index ==
		(std::numeric_limits<std::size_t>::max)()
		? NULL
		: &gamma_desc;
	const common::TensorDesc* beta = beta_index ==
		(std::numeric_limits<std::size_t>::max)()
		? NULL
		: &beta_desc;
	const std::vector<int64_t> axes(op->axis.begin(), op->axis.end());
	status = common::layerNorm(
		input_desc,
		gamma,
		beta,
		output_desc,
		axes,
		static_cast<double>(op->eps),
		false);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("LayerNorm portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardSimplifiedLayerNorm(
	const xir::SimplifiedLayerNorm& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append(
			"SimplifiedLayerNorm must declare one input and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	std::vector<xrt::Tensor> parameters;
	if (op->gamma.has_value()) {
		const xir::Params gamma = op->gamma.value();
		ICRAFT_CHECK(gamma.hasData(), 12011)
			.append("SimplifiedLayerNorm gamma parameter has no data.");
		parameters.push_back(synchronizeInput(xrt::Tensor(gamma)));
	}
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	common::TensorDesc input_desc;
	common::TensorDesc gamma_desc;
	common::TensorDesc output_desc;
	common::Status status = describeTensor(
		input.data().cptr(),
		static_cast<std::size_t>(input.dtype().bytes()),
		op->inputs[0].tensorType(),
		rounding,
		&input_desc);
	if (status.ok() && !parameters.empty()) {
		status = describeTensor(
			parameters[0].data().cptr(),
			static_cast<std::size_t>(parameters[0].dtype().bytes()),
			op->gamma.value().tensorType(),
			rounding,
			&gamma_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"SimplifiedLayerNorm tensor description failed: {}",
			status.message);
	ICRAFT_CHECK(!input_desc.shape.empty(), 12011)
		.append("SimplifiedLayerNorm input must have rank one or greater.");
	const std::vector<int64_t> axes(
		1U, static_cast<int64_t>(input_desc.shape.size()) - 1);
	status = common::layerNorm(
		input_desc,
		parameters.empty() ? NULL : &gamma_desc,
		NULL,
		output_desc,
		axes,
		static_cast<double>(op->eps),
		true);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"SimplifiedLayerNorm portable kernel failed: {}",
			status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

template <typename Op>
inline std::vector<xrt::Tensor> forwardInstanceNorm(
	const Op& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append("{} must declare one input and one output.", op->typeKey());
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	std::vector<xrt::Tensor> parameters;
	std::size_t gamma_index = (std::numeric_limits<std::size_t>::max)();
	std::size_t beta_index = (std::numeric_limits<std::size_t>::max)();
	if (op->gamma.has_value()) {
		const xir::Params gamma = op->gamma.value();
		ICRAFT_CHECK(gamma.hasData(), 12011)
			.append("{} gamma parameter has no data.", op->typeKey());
		gamma_index = parameters.size();
		parameters.push_back(synchronizeInput(xrt::Tensor(gamma)));
	}
	if (op->beta.has_value()) {
		const xir::Params beta = op->beta.value();
		ICRAFT_CHECK(beta.hasData(), 12011)
			.append("{} beta parameter has no data.", op->typeKey());
		beta_index = parameters.size();
		parameters.push_back(synchronizeInput(xrt::Tensor(beta)));
	}

	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	common::TensorDesc input_desc;
	common::TensorDesc gamma_desc;
	common::TensorDesc beta_desc;
	common::TensorDesc output_desc;
	common::Status status = describeTensor(
		input.data().cptr(),
		static_cast<std::size_t>(input.dtype().bytes()),
		op->inputs[0].tensorType(),
		rounding,
		&input_desc);
	if (status.ok() && gamma_index !=
		(std::numeric_limits<std::size_t>::max)()) {
		status = describeTensor(
			parameters[gamma_index].data().cptr(),
			static_cast<std::size_t>(
				parameters[gamma_index].dtype().bytes()),
			op->gamma.value().tensorType(),
			rounding,
			&gamma_desc);
	}
	if (status.ok() && beta_index !=
		(std::numeric_limits<std::size_t>::max)()) {
		status = describeTensor(
			parameters[beta_index].data().cptr(),
			static_cast<std::size_t>(
				parameters[beta_index].dtype().bytes()),
			op->beta.value().tensorType(),
			rounding,
			&beta_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} tensor description failed: {}",
			op->typeKey(),
			status.message);
	const common::TensorDesc* gamma = gamma_index ==
		(std::numeric_limits<std::size_t>::max)()
		? NULL
		: &gamma_desc;
	const common::TensorDesc* beta = beta_index ==
		(std::numeric_limits<std::size_t>::max)()
		? NULL
		: &beta_desc;
	status = common::instanceNorm(
		input_desc,
		gamma,
		beta,
		output_desc,
		static_cast<double>(op->eps));
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} portable kernel failed: {}",
			op->typeKey(),
			status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

template <typename Op>
inline std::vector<xrt::Tensor> forwardBatchNorm(
	const Op& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append("{} must declare one input and one output.", op->typeKey());
	ICRAFT_CHECK(op->variance.hasData() && op->mean.hasData(), 12011)
		.append("{} affine parameters have no data.", op->typeKey());
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xrt::Tensor multiplier =
		synchronizeInput(xrt::Tensor(op->variance));
	const xrt::Tensor addend =
		synchronizeInput(xrt::Tensor(op->mean));
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	common::TensorDesc input_desc;
	common::TensorDesc multiplier_desc;
	common::TensorDesc addend_desc;
	common::TensorDesc output_desc;
	common::Status status = describeTensor(
		input.data().cptr(),
		static_cast<std::size_t>(input.dtype().bytes()),
		op->inputs[0].tensorType(),
		rounding,
		&input_desc);
	if (status.ok()) {
		status = describeTensor(
			multiplier.data().cptr(),
			static_cast<std::size_t>(multiplier.dtype().bytes()),
			op->variance.tensorType(),
			rounding,
			&multiplier_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			addend.data().cptr(),
			static_cast<std::size_t>(addend.dtype().bytes()),
			op->mean.tensorType(),
			rounding,
			&addend_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} tensor description failed: {}",
			op->typeKey(),
			status.message);
	status = common::channelAffine(
		input_desc, &multiplier_desc, &addend_desc, output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} portable kernel failed: {}",
			op->typeKey(),
			status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardPReLU(
	const xir::PReLU& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append("PReLU must declare one input and one output.");
	ICRAFT_CHECK(op->alpha.hasData(), 12011)
		.append("PReLU alpha parameter has no data.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xrt::Tensor alpha =
		synchronizeInput(xrt::Tensor(op->alpha));
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	common::TensorDesc input_desc;
	common::TensorDesc alpha_desc;
	common::TensorDesc output_desc;
	common::Status status = describeTensor(
		input.data().cptr(),
		static_cast<std::size_t>(input.dtype().bytes()),
		op->inputs[0].tensorType(),
		rounding,
		&input_desc);
	if (status.ok()) {
		status = describeTensor(
			alpha.data().cptr(),
			static_cast<std::size_t>(alpha.dtype().bytes()),
			op->alpha.tensorType(),
			rounding,
			&alpha_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append("PReLU tensor description failed: {}", status.message);
	status = common::prelu(input_desc, alpha_desc, output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("PReLU portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardIndexSelect(
	const xir::IndexSelect& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 2U && op->outputs.size() == 1U, 12011)
		.append("IndexSelect must declare data, indices, and output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xrt::Tensor indices = synchronizeInput(materialized[1]);
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding = roundingMode(op->compile_target);
	common::TensorDesc input_desc;
	common::TensorDesc indices_desc;
	common::TensorDesc output_desc;
	common::Status status = describeTensor(
		input.data().cptr(),
		static_cast<std::size_t>(input.dtype().bytes()),
		op->inputs[0].tensorType(),
		rounding,
		&input_desc);
	if (status.ok()) {
		status = describeTensor(
			indices.data().cptr(),
			static_cast<std::size_t>(indices.dtype().bytes()),
			op->inputs[1].tensorType(),
			rounding,
			&indices_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append("IndexSelect tensor description failed: {}", status.message);
	status = common::indexSelect(
		input_desc, indices_desc, output_desc, op->dim);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("IndexSelect portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardUpdate(
	const xir::Update& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 2U && op->outputs.size() == 1U, 12011)
		.append("Update must declare data, updates, and output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor data = synchronizeInput(materialized[0]);
	const xrt::Tensor updates = synchronizeInput(materialized[1]);
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding = roundingMode(op->compile_target);
	common::TensorDesc data_desc;
	common::TensorDesc updates_desc;
	common::TensorDesc output_desc;
	common::Status status = describeTensor(
		data.data().cptr(),
		static_cast<std::size_t>(data.dtype().bytes()),
		op->inputs[0].tensorType(),
		rounding,
		&data_desc);
	if (status.ok()) {
		status = describeTensor(
			updates.data().cptr(),
			static_cast<std::size_t>(updates.dtype().bytes()),
			op->inputs[1].tensorType(),
			rounding,
			&updates_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Update tensor description failed: {}", status.message);
	const std::vector<int64_t> begin(op->begin.begin(), op->begin.end());
	const std::vector<int64_t> end(op->end.begin(), op->end.end());
	const std::vector<int64_t> stride(op->stride.begin(), op->stride.end());
	status = common::update(
		data_desc, updates_desc, output_desc, begin, end, stride);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Update portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardMatmulNBits(
	const xir::MatmulNBits& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(
		op->inputs.size() == 3U || op->inputs.size() == 4U,
		12011)
		.append(
			"MatmulNBits must declare input, weights, scales, and optional zero points.");
	ICRAFT_CHECK(op->outputs.size() == 1U, 12011)
		.append("MatmulNBits must declare one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	std::vector<xrt::Tensor> synchronized;
	synchronized.reserve(materialized.size());
	for (std::size_t i = 0U; i < materialized.size(); ++i) {
		synchronized.push_back(synchronizeInput(materialized[i]));
	}
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding = roundingMode(op->compile_target);
	std::vector<common::TensorDesc> input_descs(synchronized.size());
	common::TensorDesc output_desc;
	common::Status status;
	for (std::size_t i = 0U; i < synchronized.size(); ++i) {
		status = describeTensor(
			synchronized[i].data().cptr(),
			static_cast<std::size_t>(synchronized[i].dtype().bytes()),
			op->inputs[i].tensorType(),
			rounding,
			&input_descs[i]);
		if (!status.ok()) {
			break;
		}
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append("MatmulNBits tensor description failed: {}", status.message);
	const common::TensorDesc* zero_points = input_descs.size() == 4U
		? &input_descs[3]
		: NULL;
	status = common::matmulNBits(
		input_descs[0],
		input_descs[1],
		input_descs[2],
		zero_points,
		output_desc,
		op->bits,
		op->group_cnt,
		op->group_size,
		op->K,
		op->N);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("MatmulNBits portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardRopeDynamic(
	const xir::RopeDynamic& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 2U && op->outputs.size() == 1U, 12011)
		.append("RopeDynamic must declare input, configuration, and output.");
	ICRAFT_CHECK(op->cos_cache.hasData() && op->sin_cache.hasData(), 12011)
		.append("RopeDynamic sine or cosine cache parameter has no data.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xrt::Tensor config = synchronizeInput(materialized[1]);
	const xrt::Tensor cosine =
		synchronizeInput(xrt::Tensor(op->cos_cache));
	const xrt::Tensor sine =
		synchronizeInput(xrt::Tensor(op->sin_cache));
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding = roundingMode(op->compile_target);
	common::TensorDesc input_desc;
	common::TensorDesc config_desc;
	common::TensorDesc cosine_desc;
	common::TensorDesc sine_desc;
	common::TensorDesc output_desc;
	common::Status status = describeTensor(
		input.data().cptr(),
		static_cast<std::size_t>(input.dtype().bytes()),
		op->inputs[0].tensorType(),
		rounding,
		&input_desc);
	if (status.ok()) {
		status = describeTensor(
			config.data().cptr(),
			static_cast<std::size_t>(config.dtype().bytes()),
			op->inputs[1].tensorType(),
			rounding,
			&config_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			cosine.data().cptr(),
			static_cast<std::size_t>(cosine.dtype().bytes()),
			op->cos_cache.tensorType(),
			rounding,
			&cosine_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			sine.data().cptr(),
			static_cast<std::size_t>(sine.dtype().bytes()),
			op->sin_cache.tensorType(),
			rounding,
			&sine_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append("RopeDynamic tensor description failed: {}", status.message);
	status = common::ropeDynamic(
		input_desc,
		config_desc,
		cosine_desc,
		sine_desc,
		output_desc,
		op->prefill_max);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("RopeDynamic portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardCausalMask(
	const xir::CausalMask& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 2U && op->outputs.size() == 1U, 12011)
		.append("CausalMask must declare input, configuration, and output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xrt::Tensor config = synchronizeInput(materialized[1]);
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	common::TensorDesc input_desc;
	common::TensorDesc config_desc;
	common::TensorDesc output_desc;
	common::Status status = describeTensor(
		input.data().cptr(),
		static_cast<std::size_t>(input.dtype().bytes()),
		op->inputs[0].tensorType(),
		rounding,
		&input_desc);
	if (status.ok()) {
		status = describeTensor(
			config.data().cptr(),
			static_cast<std::size_t>(config.dtype().bytes()),
			op->inputs[1].tensorType(),
			rounding,
			&config_desc);
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append("CausalMask tensor description failed: {}", status.message);
	status = common::causalMask(
		input_desc,
		config_desc,
		output_desc,
		op->prefill_max,
		static_cast<double>(op->fill_value));
	ICRAFT_CHECK(status.ok(), 12011)
		.append("CausalMask portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardSliceDynamic(
	const xir::SliceDynamic& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 3U && op->outputs.size() == 1U, 12011)
		.append(
			"SliceDynamic must declare input, configuration, cache, and output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	std::vector<xrt::Tensor> synchronized;
	synchronized.reserve(materialized.size());
	for (std::size_t i = 0U; i < materialized.size(); ++i) {
		synchronized.push_back(synchronizeInput(materialized[i]));
	}
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	const common::RoundingMode rounding =
		roundingMode(op->compile_target);
	std::vector<common::TensorDesc> input_descs(synchronized.size());
	common::TensorDesc output_desc;
	common::Status status;
	for (std::size_t i = 0U; i < synchronized.size(); ++i) {
		status = describeTensor(
			synchronized[i].data().cptr(),
			static_cast<std::size_t>(synchronized[i].dtype().bytes()),
			op->inputs[i].tensorType(),
			rounding,
			&input_descs[i]);
		if (!status.ok()) {
			break;
		}
	}
	if (status.ok()) {
		status = describeTensor(
			output.tensor.data().cptr(),
			static_cast<std::size_t>(output.tensor.dtype().bytes()),
			output_type,
			rounding,
			&output_desc);
	}
	ICRAFT_CHECK(status.ok(), 12011)
		.append("SliceDynamic tensor description failed: {}", status.message);
	status = common::sliceDynamic(
		input_descs[0],
		input_descs[1],
		input_descs[2],
		output_desc,
		op->prefill_max);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("SliceDynamic portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

template <typename Op>
inline std::vector<xrt::Tensor> forwardLinearCopy(
	const Op& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U, 12011)
		.append("{} must declare one input.", op->typeKey());
	ICRAFT_CHECK(op->outputs.size() == 1U, 12011)
		.append("{} must declare one output.", op->typeKey());
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xir::TensorType input_type = op->inputs[0].tensorType();
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		input_type,
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} tensor description failed: {}",
			op->typeKey(),
			status.message);
	status = common::linearCopy(input_desc, output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} portable kernel failed: {}",
			op->typeKey(),
			status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardTranspose(
	const xir::Transpose& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append("Transpose must declare one input and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xir::TensorType input_type = op->inputs[0].tensorType();
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		input_type,
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Transpose tensor description failed: {}", status.message);
	std::vector<int64_t> dimensions(op->dims.begin(), op->dims.end());
	status = common::transpose(input_desc, output_desc, dimensions);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Transpose portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardSwapOrder(
	const xir::SwapOrder& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append("SwapOrder must declare one input and one output.");
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xir::TensorType input_type = op->inputs[0].tensorType();
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		input_type,
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("SwapOrder tensor description failed: {}", status.message);
	std::vector<int64_t> order(op->order.begin(), op->order.end());
	status = common::reorderAxis(input_desc, output_desc, op->axis, order);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("SwapOrder portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

template <typename Op>
inline std::vector<xrt::Tensor> forwardSoftmaxImpl(
	const Op& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs,
	bool logarithmic) {
	ICRAFT_CHECK(op->inputs.size() == 1U && op->outputs.size() == 1U, 12011)
		.append("{} must declare one input and one output.", op->typeKey());
	const std::vector<xrt::Tensor> materialized =
		materializeInputs(op->inputs, runtime_inputs);
	const xrt::Tensor input = synchronizeInput(materialized[0]);
	const xir::TensorType input_type = op->inputs[0].tensorType();
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output =
		prepareOutput(output_type, materialized, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		input_type,
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} tensor description failed: {}",
			op->typeKey(),
			status.message);
	status = common::softmax(input_desc, output_desc, op->axis, logarithmic);
	ICRAFT_CHECK(status.ok(), 12011)
		.append(
			"{} portable kernel failed: {}",
			op->typeKey(),
			status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardSoftmax(
	const xir::Softmax& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	return forwardSoftmaxImpl(op, runtime_inputs, user_outputs, false);
}

inline std::vector<xrt::Tensor> forwardLogSoftmax(
	const xir::LogSoftmax& op,
	const std::vector<xrt::Tensor>& runtime_inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	return forwardSoftmaxImpl(op, runtime_inputs, user_outputs, true);
}

inline std::vector<xrt::Tensor> forwardAlignAxis(
	const xir::AlignAxis& op,
	const std::vector<xrt::Tensor>& inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(inputs.size() == 1U, 12011)
		.append("AlignAxis must have one input.");
	ICRAFT_CHECK(op->outputs.size() == 1U, 12011)
		.append("AlignAxis must have one output.");
	const xrt::Tensor input = synchronizeInput(inputs[0]);

	const xir::TensorType input_type = op->inputs[0].tensorType();
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output = prepareOutput(output_type, inputs, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		input_type,
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("AlignAxis tensor description failed: {}", status.message);

	status = common::alignAxis(input_desc, output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("AlignAxis portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardPruneAxis(
	const xir::PruneAxis& op,
	const std::vector<xrt::Tensor>& inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(inputs.size() == 1U, 12011)
		.append("PruneAxis must have one input.");
	ICRAFT_CHECK(op->outputs.size() == 1U, 12011)
		.append("PruneAxis must have one output.");
	const xrt::Tensor input = synchronizeInput(inputs[0]);

	const xir::TensorType input_type = op->inputs[0].tensorType();
	const xir::TensorType output_type = op->outputs[0].tensorType();
	PreparedOutput output = prepareOutput(output_type, inputs, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		input_type,
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("PruneAxis tensor description failed: {}", status.message);

	std::vector<std::size_t> distribution_indices;
	distribution_indices.reserve(op->index.size());
	for (std::size_t i = 0; i < op->index.size(); ++i) {
		const int64_t distribution_count =
			static_cast<int64_t>(input_type->merged_distrs.size());
		const int64_t normalized =
			op->index[i] < 0 ? op->index[i] + distribution_count : op->index[i];
		ICRAFT_CHECK(
			normalized >= 0 && normalized < distribution_count,
			12011)
			.append("PruneAxis distribution index {} is out of range.", op->index[i]);
		distribution_indices.push_back(static_cast<std::size_t>(normalized));
	}

	status = common::pruneAxis(
		input_desc, output_desc, distribution_indices);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("PruneAxis portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

inline std::vector<xrt::Tensor> forwardCast(
	const xir::Cast& op,
	const std::vector<xrt::Tensor>& inputs,
	const std::vector<xrt::Tensor>& user_outputs) {
	ICRAFT_CHECK(inputs.size() == 1U, 12011)
		.append("Cast must have one input.");
	const xrt::Tensor input = synchronizeInput(inputs[0]);

	const xir::TensorType input_type = op->inputs[0].tensorType();
	const xir::TensorType output_type =
		op->outputs.empty() ? op->target_dtype : op->outputs[0].tensorType();
	PreparedOutput output = prepareOutput(output_type, inputs, user_outputs);
	common::TensorDesc input_desc;
	common::TensorDesc output_desc;
	common::Status status = describeInputOutput(
		input,
		output.tensor,
		input_type,
		output_type,
		roundingMode(op->compile_target),
		&input_desc,
		&output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Cast tensor description failed: {}", status.message);

	status = common::cast(input_desc, output_desc);
	ICRAFT_CHECK(status.ok(), 12011)
		.append("Cast portable kernel failed: {}", status.message);
	return std::vector<xrt::Tensor>(
		1U, publishOutput(output, user_outputs));
}

}  // namespace port
}  // namespace hostbackend
}  // namespace icraft
