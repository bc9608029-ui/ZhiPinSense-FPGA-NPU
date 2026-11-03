#pragma once
#include <chrono>
#include <functional>
#include <map>
#include <unordered_map>

#include <icraft-backends/hostbackend/port/common/tensor_ops.h>
#include <icraft-xir/ops/ops.h>

using namespace icraft::xrt;

ICRAFT_REGISTER_NODE(HostBackendNode);

void HostBackendNode::init(const NetworkView& network, const Device& device) {
	this->network_view = network;
	this->device = device;

	auto backend = GetRef<Backend>(this);
	for (auto&& op : network->ops) {
		ICRAFT_CHECK(backend.isOpSupported(op))
			.append("Op is not supported by HostBackend, op_id = {}, type_key = {}", op->op_id, op->typeKey());
		backend.initOp(op);
	}
}

void HostBackendNode::deinit() {
	this->deinited = true;
	ICRAFT_LOG_DEBUG() << "HostBackendNode is deiniting...\n";
}

Backend HostBackendNode::fork() {
	return GetRef<Backend>(this);
}

MergedOps HostBackendNode::autoMerge() {
	return {};
}

Operation HostBackendNode::serialize(int64_t op_id) {
	auto xir_op = this->network_view.getOpById(op_id);
	return xir_op.clone(-1);
}

void HostBackend::setFakeQf(bool fake_qf) {
	get_mutable()->fake_qf = fake_qf;
}

using namespace icraft::xir;
using namespace std::chrono;
using namespace std::chrono_literals;
static utils::Timer t;

// XRT's WL execution path invokes one backend-level forward function for a
// subgraph. Keep that ABI/policy layer shared by every delivered port while
// all operator math remains in the portable registrations below.
ICRAFT_REGISTER_FFUNC_TO_BACKEND(HostBackendNode)
.set_forward([](const NetworkView sub_network,
	const std::vector<Tensor>& input_tensors,
	const std::map<int64_t, Tensor>& output_tensors,
	Backend backend,
	const Device& device,
	uint8_t priority,
	uint64_t currIdx) -> std::vector<Tensor> {
	(void)device;
	(void)priority;
	(void)currIdx;
	std::unordered_map<int64_t, Tensor> tensor_map;
	std::size_t input_index = 0U;
	for (auto& input : sub_network.inputs()) {
		ICRAFT_CHECK(input_index < input_tensors.size(), 12011)
			.append("HostBackend subgraph is missing input tensor {}.", input_index);
		ICRAFT_CHECK(input_tensors[input_index].waitForReady(200s), 12011)
			.append("wait for tensor(vid:{}) ready timeout", input->v_id);
		tensor_map[input->v_id] = input_tensors[input_index++];
	}
	ICRAFT_CHECK(input_index == input_tensors.size(), 12011)
		.append("HostBackend subgraph received unexpected input tensors.");
	for (auto& entry : output_tensors) {
		tensor_map[entry.first] = entry.second;
	}

	for (auto& op : sub_network->ops) {
		utils::Timer timer;
		timer.tik();
		std::vector<Tensor> middle_inputs;
		std::vector<Tensor> net_outputs;
		for (auto& input : op->inputs) {
			if (!input.isParams()) {
				middle_inputs.push_back(tensor_map.at(input->v_id));
			}
		}
		for (auto& output : op->outputs) {
			if (tensor_map.find(output->v_id) != tensor_map.end()) {
				net_outputs.push_back(tensor_map.at(output->v_id));
			}
		}

		auto forward = backend.getForwardFunc(op).value();
		auto middle_outputs = forward(op, middle_inputs, net_outputs, backend);
		ICRAFT_CHECK(middle_outputs.size() == op->outputs.size(), 12011)
			.append(
				"HostBackend op {} returned {} tensors for {} declared outputs.",
				op->typeKey(), middle_outputs.size(), op->outputs.size());

		for (std::size_t output_index = 0U;
			output_index < op->outputs.size(); ++output_index) {
			const auto& output = op->outputs[output_index];
			if (tensor_map.find(output->v_id) == tensor_map.end()) {
				tensor_map[output->v_id] = middle_outputs[output_index];
			}
		}
		timer.tok();
		backend.setTimeElapses(
			op->op_id, 0, timer.elapsed<std::chrono::milliseconds>());
	}

	std::vector<Tensor> outputs;
	for (auto& output : sub_network.outputs()) {
		outputs.push_back(tensor_map.at(output->v_id).setReady(true));
	}
	return outputs;
});

ICRAFT_ADD_OP_TO_BACKEND(Input, HostBackend)
.set_init([](const Input& op, HostBackend backend) {
	})
	.set_forward([](const Input& op, const std::vector<Tensor>& inputs, const std::vector<Tensor>& outputs, HostBackend backend) -> std::vector<Tensor> {
	if (backend->time_profile) t.tik();
	if (backend->time_profile) {
		t.tok();
		auto elapse = t.elapsed<milliseconds>();
		backend.setTimeElapses(op->op_id, 0, elapse);
	}
	return inputs;
		});

ICRAFT_ADD_OP_TO_BACKEND(AlignAxis, HostBackend)
.set_init([](const AlignAxis& op, HostBackend backend) {
	})
	.set_forward([](const AlignAxis& op, const std::vector<Tensor>& inputs, const std::vector<Tensor>& outputs, HostBackend backend) -> std::vector<Tensor> {
	if (backend->time_profile) t.tik();
	auto result = icraft::hostbackend::port::forwardAlignAxis(op, inputs, outputs);
	if (backend->time_profile) {
		t.tok();
		auto elapse = t.elapsed<milliseconds>();
		backend.setTimeElapses(op->op_id, 0, elapse);
	}
	return result;
		});

ICRAFT_ADD_OP_TO_BACKEND(PruneAxis, HostBackend)
.set_init([](const PruneAxis& op, HostBackend backend) {
	})
	.set_forward([](const PruneAxis& op, const std::vector<Tensor>& inputs, const std::vector<Tensor>& outputs, HostBackend backend) -> std::vector<Tensor> {
	if (backend->time_profile) t.tik();
	auto result = icraft::hostbackend::port::forwardPruneAxis(op, inputs, outputs);
	if (backend->time_profile) {
		t.tok();
		auto elapse = t.elapsed<milliseconds>();
		backend.setTimeElapses(op->op_id, 0, elapse);
	}
	return result;
		});

ICRAFT_ADD_OP_TO_BACKEND(Cast, HostBackend)
.set_init([](const Cast& op, HostBackend backend) {
	})
	.set_forward([](const Cast& op, const std::vector<Tensor>& inputs, const std::vector<Tensor>& outputs, HostBackend backend) -> std::vector<Tensor> {
	if (backend->time_profile) t.tik();
	auto result = icraft::hostbackend::port::forwardCast(op, inputs, outputs);
	if (backend->time_profile) {
		t.tok();
		auto elapse = t.elapsed<milliseconds>();
		backend.setTimeElapses(op->op_id, 0, elapse);
	}
	return result;
		});

ICRAFT_ADD_OP_TO_BACKEND(Output, HostBackend)
.set_init([](const Output& op, HostBackend backend) {
	})
	.set_forward([](const Output& op, const std::vector<Tensor>& inputs, const std::vector<Tensor>& outputs, HostBackend backend) -> std::vector<Tensor> {
	if (backend->time_profile) t.tik();
	if (backend->time_profile) {
		t.tok();
		auto elapse = t.elapsed<milliseconds>();
		backend.setTimeElapses(op->op_id, 0, elapse);
	}
	return inputs;
		});

#define ICRAFT_REGISTER_PORTABLE_UNARY(OP_TYPE, KIND) \
	ICRAFT_ADD_OP_TO_BACKEND(OP_TYPE, HostBackend) \
	.set_init([](const OP_TYPE&, HostBackend) {}) \
	.set_forward([](const OP_TYPE& op, const std::vector<Tensor>& inputs, \
		const std::vector<Tensor>& outputs, HostBackend backend) \
		-> std::vector<Tensor> { \
		if (backend->time_profile) t.tik(); \
		const auto spec = icraft::hostbackend::port::unarySpec( \
			op, icraft::hostbackend::common::UnaryKind::KIND); \
		auto result = icraft::hostbackend::port::forwardUnary( \
			op, inputs, outputs, spec); \
		if (backend->time_profile) { \
			t.tok(); \
			backend.setTimeElapses( \
				op->op_id, 0, t.elapsed<milliseconds>()); \
		} \
		return result; \
	})

#define ICRAFT_REGISTER_PORTABLE_BINARY(OP_TYPE, KIND) \
	ICRAFT_ADD_OP_TO_BACKEND(OP_TYPE, HostBackend) \
	.set_init([](const OP_TYPE&, HostBackend) {}) \
	.set_forward([](const OP_TYPE& op, const std::vector<Tensor>& inputs, \
		const std::vector<Tensor>& outputs, HostBackend backend) \
		-> std::vector<Tensor> { \
		if (backend->time_profile) t.tik(); \
		const auto spec = icraft::hostbackend::port::binarySpec( \
			op, icraft::hostbackend::common::BinaryKind::KIND); \
		auto result = icraft::hostbackend::port::forwardBinary( \
			op, inputs, outputs, spec); \
		if (backend->time_profile) { \
			t.tok(); \
			backend.setTimeElapses( \
				op->op_id, 0, t.elapsed<milliseconds>()); \
		} \
		return result; \
	})

#define ICRAFT_REGISTER_PORTABLE_FORWARD(OP_TYPE, FORWARD_FN) \
	ICRAFT_ADD_OP_TO_BACKEND(OP_TYPE, HostBackend) \
	.set_init([](const OP_TYPE&, HostBackend) {}) \
	.set_forward([](const OP_TYPE& op, const std::vector<Tensor>& inputs, \
		const std::vector<Tensor>& outputs, HostBackend backend) \
		-> std::vector<Tensor> { \
		if (backend->time_profile) t.tik(); \
		auto result = icraft::hostbackend::port::FORWARD_FN( \
			op, inputs, outputs); \
		if (backend->time_profile) { \
			t.tok(); \
			backend.setTimeElapses( \
				op->op_id, 0, t.elapsed<milliseconds>()); \
		} \
		return result; \
	})

#define ICRAFT_REGISTER_PORTABLE_REDUCTION(OP_TYPE, KIND) \
	ICRAFT_ADD_OP_TO_BACKEND(OP_TYPE, HostBackend) \
	.set_init([](const OP_TYPE&, HostBackend) {}) \
	.set_forward([](const OP_TYPE& op, const std::vector<Tensor>& inputs, \
		const std::vector<Tensor>& outputs, HostBackend backend) \
		-> std::vector<Tensor> { \
		if (backend->time_profile) t.tik(); \
		const auto spec = icraft::hostbackend::port::reductionSpec( \
			op, icraft::hostbackend::common::ReductionKind::KIND); \
		auto result = icraft::hostbackend::port::forwardReduction( \
			op, inputs, outputs, spec); \
		if (backend->time_profile) { \
			t.tok(); \
			backend.setTimeElapses( \
				op->op_id, 0, t.elapsed<milliseconds>()); \
		} \
		return result; \
	})

#define ICRAFT_REGISTER_PORTABLE_POOL(OP_TYPE, KIND) \
	ICRAFT_ADD_OP_TO_BACKEND(OP_TYPE, HostBackend) \
	.set_init([](const OP_TYPE&, HostBackend) {}) \
	.set_forward([](const OP_TYPE& op, const std::vector<Tensor>& inputs, \
		const std::vector<Tensor>& outputs, HostBackend backend) \
		-> std::vector<Tensor> { \
		if (backend->time_profile) t.tik(); \
		const auto spec = icraft::hostbackend::port::poolSpec( \
			op, icraft::hostbackend::common::PoolKind::KIND); \
		auto result = icraft::hostbackend::port::forwardPool( \
			op, inputs, outputs, spec); \
		if (backend->time_profile) { \
			t.tok(); \
			backend.setTimeElapses( \
				op->op_id, 0, t.elapsed<milliseconds>()); \
		} \
		return result; \
	})

#define ICRAFT_REGISTER_PORTABLE_CONVOLUTION(OP_TYPE) \
	ICRAFT_ADD_OP_TO_BACKEND(OP_TYPE, HostBackend) \
	.set_init([](const OP_TYPE&, HostBackend) {}) \
	.set_forward([](const OP_TYPE& op, const std::vector<Tensor>& inputs, \
		const std::vector<Tensor>& outputs, HostBackend backend) \
		-> std::vector<Tensor> { \
		if (backend->time_profile) t.tik(); \
		const auto spec = icraft::hostbackend::port::convSpec(op); \
		auto result = icraft::hostbackend::port::forwardConvolution( \
			op, inputs, outputs, spec); \
		if (backend->time_profile) { \
			t.tok(); \
			backend.setTimeElapses( \
				op->op_id, 0, t.elapsed<milliseconds>()); \
		} \
		return result; \
	})

ICRAFT_REGISTER_PORTABLE_UNARY(Abs, kAbs);
ICRAFT_REGISTER_PORTABLE_UNARY(ACos, kAcos);
ICRAFT_REGISTER_PORTABLE_UNARY(ACosh, kAcosh);
ICRAFT_REGISTER_PORTABLE_UNARY(ASin, kAsin);
ICRAFT_REGISTER_PORTABLE_UNARY(ASinh, kAsinh);
ICRAFT_REGISTER_PORTABLE_UNARY(ATan, kAtan);
ICRAFT_REGISTER_PORTABLE_UNARY(ATanh, kAtanh);
ICRAFT_REGISTER_PORTABLE_UNARY(Cos, kCos);
ICRAFT_REGISTER_PORTABLE_UNARY(Cosh, kCosh);
ICRAFT_REGISTER_PORTABLE_UNARY(ClampScalar, kHardTanh);
ICRAFT_REGISTER_PORTABLE_UNARY(DivideScalar, kDivideScalar);
ICRAFT_REGISTER_PORTABLE_UNARY(ELU, kElu);
ICRAFT_REGISTER_PORTABLE_UNARY(Expand, kIdentity);
ICRAFT_REGISTER_PORTABLE_UNARY(GELU, kGelu);
ICRAFT_REGISTER_PORTABLE_UNARY(Hardshrink, kHardShrink);
ICRAFT_REGISTER_PORTABLE_UNARY(Hardsigmoid, kHardSigmoid);
ICRAFT_REGISTER_PORTABLE_UNARY(Hardswish, kHardSwish);
ICRAFT_REGISTER_PORTABLE_UNARY(Hardtanh, kHardTanh);
ICRAFT_REGISTER_PORTABLE_UNARY(Log, kLog);
ICRAFT_REGISTER_PORTABLE_UNARY(LogSigmoid, kLogSigmoid);
ICRAFT_REGISTER_PORTABLE_UNARY(Mish, kMish);
ICRAFT_REGISTER_PORTABLE_UNARY(Neg, kNeg);
ICRAFT_REGISTER_PORTABLE_UNARY(Not, kNot);
ICRAFT_REGISTER_PORTABLE_UNARY(ReLU, kRelu);
ICRAFT_REGISTER_PORTABLE_UNARY(Sigmoid, kSigmoid);
ICRAFT_REGISTER_PORTABLE_UNARY(SiLU, kSilu);
ICRAFT_REGISTER_PORTABLE_UNARY(Sin, kSin);
ICRAFT_REGISTER_PORTABLE_UNARY(Sinh, kSinh);
ICRAFT_REGISTER_PORTABLE_UNARY(Softplus, kSoftplus);
ICRAFT_REGISTER_PORTABLE_UNARY(Softshrink, kSoftshrink);
ICRAFT_REGISTER_PORTABLE_UNARY(Softsign, kSoftsign);
ICRAFT_REGISTER_PORTABLE_UNARY(Sqrt, kSqrt);
ICRAFT_REGISTER_PORTABLE_UNARY(Tan, kTan);
ICRAFT_REGISTER_PORTABLE_UNARY(Tanh, kTanh);
ICRAFT_REGISTER_PORTABLE_UNARY(Tanhshrink, kTanhShrink);

ICRAFT_REGISTER_PORTABLE_BINARY(Add, kAdd);
ICRAFT_REGISTER_PORTABLE_BINARY(Div, kDivide);
ICRAFT_REGISTER_PORTABLE_BINARY(Equal, kEqual);
ICRAFT_REGISTER_PORTABLE_BINARY(Greater, kGreater);
ICRAFT_REGISTER_PORTABLE_BINARY(GreaterEqual, kGreaterEqual);
ICRAFT_REGISTER_PORTABLE_BINARY(Less, kLess);
ICRAFT_REGISTER_PORTABLE_BINARY(LessEqual, kLessEqual);
ICRAFT_REGISTER_PORTABLE_BINARY(Maximum, kMaximum);
ICRAFT_REGISTER_PORTABLE_BINARY(Minimum, kMinimum);
ICRAFT_REGISTER_PORTABLE_BINARY(Multiply, kMultiply);
ICRAFT_REGISTER_PORTABLE_BINARY(NotEqual, kNotEqual);
ICRAFT_REGISTER_PORTABLE_BINARY(Pow, kPow);

ICRAFT_REGISTER_PORTABLE_FORWARD(Copy, forwardLinearCopy);
ICRAFT_REGISTER_PORTABLE_FORWARD(Reshape, forwardLinearCopy);
ICRAFT_REGISTER_PORTABLE_FORWARD(Squeeze, forwardLinearCopy);
ICRAFT_REGISTER_PORTABLE_FORWARD(Transpose, forwardTranspose);
ICRAFT_REGISTER_PORTABLE_FORWARD(SwapOrder, forwardSwapOrder);
ICRAFT_REGISTER_PORTABLE_FORWARD(Softmax, forwardSoftmax);
ICRAFT_REGISTER_PORTABLE_FORWARD(LogSoftmax, forwardLogSoftmax);
ICRAFT_REGISTER_PORTABLE_FORWARD(Matmul, forwardMatmul);
ICRAFT_REGISTER_PORTABLE_FORWARD(MatmulNBits, forwardMatmulNBits);
ICRAFT_REGISTER_PORTABLE_FORWARD(Einsum, forwardEinsum);
ICRAFT_REGISTER_PORTABLE_FORWARD(Resize, forwardResize);
ICRAFT_REGISTER_PORTABLE_FORWARD(Upsample, forwardUpsample);
ICRAFT_REGISTER_PORTABLE_FORWARD(Unfold, forwardUnfold);
ICRAFT_REGISTER_PORTABLE_FORWARD(GridNSample, forwardGridNSample);
ICRAFT_REGISTER_PORTABLE_FORWARD(Concat, forwardConcat);
ICRAFT_REGISTER_PORTABLE_FORWARD(Split, forwardSplit);
ICRAFT_REGISTER_PORTABLE_FORWARD(Gather, forwardGather);
ICRAFT_REGISTER_PORTABLE_FORWARD(GatherElements, forwardGatherElements);
ICRAFT_REGISTER_PORTABLE_FORWARD(IndexSelect, forwardIndexSelect);
ICRAFT_REGISTER_PORTABLE_FORWARD(Slice, forwardSlice);
ICRAFT_REGISTER_PORTABLE_FORWARD(Embedding, forwardEmbedding);
ICRAFT_REGISTER_PORTABLE_FORWARD(TopK, forwardTopK);
ICRAFT_REGISTER_PORTABLE_FORWARD(ScatterElement, forwardScatterElement);
ICRAFT_REGISTER_PORTABLE_FORWARD(ScatterND, forwardScatterND);
ICRAFT_REGISTER_PORTABLE_FORWARD(CausalMask, forwardCausalMask);
ICRAFT_REGISTER_PORTABLE_FORWARD(RopeDynamic, forwardRopeDynamic);
ICRAFT_REGISTER_PORTABLE_FORWARD(SliceDynamic, forwardSliceDynamic);
ICRAFT_REGISTER_PORTABLE_FORWARD(Update, forwardUpdate);
ICRAFT_REGISTER_PORTABLE_FORWARD(Where, forwardWhere);
ICRAFT_REGISTER_PORTABLE_FORWARD(Tile, forwardTile);
ICRAFT_REGISTER_PORTABLE_FORWARD(Pad, forwardPad);
ICRAFT_REGISTER_PORTABLE_FORWARD(Roll, forwardRoll);
ICRAFT_REGISTER_PORTABLE_FORWARD(
	ChannelShuffle, forwardChannelShuffle);
ICRAFT_REGISTER_PORTABLE_FORWARD(PixelShuffle, forwardPixelShuffle);
ICRAFT_REGISTER_PORTABLE_FORWARD(Stack, forwardStack);
ICRAFT_REGISTER_PORTABLE_FORWARD(Unstack, forwardUnstack);
ICRAFT_REGISTER_PORTABLE_FORWARD(Normalize, forwardNormalize);
ICRAFT_REGISTER_PORTABLE_FORWARD(LayerNorm, forwardLayerNorm);
ICRAFT_REGISTER_PORTABLE_FORWARD(
	SimplifiedLayerNorm, forwardSimplifiedLayerNorm);
ICRAFT_REGISTER_PORTABLE_FORWARD(BatchNorm1d, forwardBatchNorm);
ICRAFT_REGISTER_PORTABLE_FORWARD(BatchNorm2d, forwardBatchNorm);
ICRAFT_REGISTER_PORTABLE_FORWARD(BatchNorm3d, forwardBatchNorm);
ICRAFT_REGISTER_PORTABLE_FORWARD(InstanceNorm1d, forwardInstanceNorm);
ICRAFT_REGISTER_PORTABLE_FORWARD(InstanceNorm2d, forwardInstanceNorm);
ICRAFT_REGISTER_PORTABLE_FORWARD(InstanceNorm3d, forwardInstanceNorm);
ICRAFT_REGISTER_PORTABLE_FORWARD(PReLU, forwardPReLU);
ICRAFT_REGISTER_PORTABLE_FORWARD(ConvTranspose1d, forwardConvTranspose);
ICRAFT_REGISTER_PORTABLE_FORWARD(ConvTranspose2d, forwardConvTranspose);
ICRAFT_REGISTER_PORTABLE_FORWARD(ConvTranspose3d, forwardConvTranspose);

ICRAFT_REGISTER_PORTABLE_REDUCTION(Sum, kSum);
ICRAFT_REGISTER_PORTABLE_REDUCTION(Mean, kMean);
ICRAFT_REGISTER_PORTABLE_REDUCTION(Max, kMaximum);
ICRAFT_REGISTER_PORTABLE_REDUCTION(Min, kMinimum);
ICRAFT_REGISTER_PORTABLE_REDUCTION(Argmax, kArgMaximum);
ICRAFT_REGISTER_PORTABLE_REDUCTION(Argmin, kArgMinimum);

ICRAFT_REGISTER_PORTABLE_POOL(MaxPool1d, kMaximum);
ICRAFT_REGISTER_PORTABLE_POOL(MaxPool2d, kMaximum);
ICRAFT_REGISTER_PORTABLE_POOL(MaxPool3d, kMaximum);
ICRAFT_REGISTER_PORTABLE_POOL(AvgPool1d, kAverage);
ICRAFT_REGISTER_PORTABLE_POOL(AvgPool2d, kAverage);
ICRAFT_REGISTER_PORTABLE_POOL(AvgPool3d, kAverage);

ICRAFT_REGISTER_PORTABLE_CONVOLUTION(Conv1d);
ICRAFT_REGISTER_PORTABLE_CONVOLUTION(Conv2d);
ICRAFT_REGISTER_PORTABLE_CONVOLUTION(Conv3d);

#undef ICRAFT_REGISTER_PORTABLE_CONVOLUTION
#undef ICRAFT_REGISTER_PORTABLE_POOL
#undef ICRAFT_REGISTER_PORTABLE_REDUCTION
#undef ICRAFT_REGISTER_PORTABLE_FORWARD
#undef ICRAFT_REGISTER_PORTABLE_BINARY
#undef ICRAFT_REGISTER_PORTABLE_UNARY
