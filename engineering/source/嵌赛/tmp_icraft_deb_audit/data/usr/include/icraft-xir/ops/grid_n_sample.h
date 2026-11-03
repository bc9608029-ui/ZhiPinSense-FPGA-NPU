#pragma once
#include <icraft-xir/core/operation.h>

//using namespace icraft::xir;
namespace icraft::xir {

	/** GridNSample算子 */
	class GridNSampleNode : public OpNodeBase<GridNSampleNode> {
	public:
		/**
		 * @enum		Interpolation
		 * @brief	表示插值的类型
		 */
		int64_t interpolation_mode;
		int64_t padding_mode;
		bool align_corners;
		int64_t grid_divisor_h;
		int64_t grid_divisor_w;
		float scale_h;
		float scale_w;


		ICRAFT_DECLARE_ATTRS(GridNSampleNode) {
			ICRAFT_ATTR_FIELD(interpolation_mode);
			ICRAFT_ATTR_FIELD(padding_mode);
			ICRAFT_ATTR_FIELD(align_corners);
			ICRAFT_ATTR_FIELD(grid_divisor_h);
			ICRAFT_ATTR_FIELD(grid_divisor_w);
			ICRAFT_ATTR_FIELD(scale_h);
			ICRAFT_ATTR_FIELD(scale_w);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** GridNSample算子引用类 */
	class GridNSample : public OpBase<GridNSample, GridNSampleNode> {
	public:


		/** 默认构造函数 */
		GridNSample() = default;

		XIR_DLL GridNSample(
			Value input,
			Value grid,
			int64_t interpolation_mode,
			int64_t padding_mode,
			bool align_corners,
			int64_t grid_divisor_h,
			int64_t grid_divisor_w,
			float scale_h,
			float scale_w
		);
	};


	//ICRAFT_REGISTER_OP_NODE(GridNSampleNode)
	//	.set_tinfer<GridNSampleNode, HostTarget>([](const auto* op) {

	//	op->validate();

	//	Array<TensorType> ofms;
	//	for (auto ifm : op->inputs) {
	//		ofms.push_back(ifm.tensorType().clone(-1));
	//	}

	//	return ofms;
	//		});

}
