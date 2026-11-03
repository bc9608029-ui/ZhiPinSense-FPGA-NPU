#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** 插值方式 */
	// enum class ResizeInterpolation {
	// 	INTER_NEAREST,		///< 最近邻插值
	// 	INTER_LINEAR		///< 双线性插值
	// };

	WISE_ENUM_CLASS(ResizeInterpolation, INTER_NEAREST, INTER_LINEAR);

	/** Resize算子 */
	class ResizeNode : public OpNodeBase<ResizeNode> {
	public:
		Array<int64_t> dsize;				///< 目标大小
		ResizeInterpolation interpolation;	///< 插值方式

		ICRAFT_DECLARE_ATTRS(ResizeNode) {
			ICRAFT_ATTR_FIELD(dsize);
			ICRAFT_ATTR_FIELD(interpolation).set_default(ResizeInterpolation::INTER_LINEAR);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Resize算子引用类 */
	class Resize : public OpBase<Resize, ResizeNode> {
	public:
		/** 默认构造函数 */
		Resize() = default;

		/**
		 * @brief 构造函数
		 * @param input				输入
		 * @param dsize				目标大小
		 * @param interpolation		插值方式
		 */
		XIR_DLL Resize(Value input, Array<int64_t> dsize, ResizeInterpolation interpolation = ResizeInterpolation::INTER_LINEAR);
	};
}
