#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Upsample算子 */
	class UpsampleNode : public OpNodeBase<UpsampleNode> {
	public:
		/**
		 * @enum		Interpolation
		 * @brief	表示插值的类型
		 */
		// enum class Interpolation {
		// 	NEAREST,		///< 最近邻插值
		// 	BILINEAR,		///< 双线性插值
		// 	BICUBIC			///< 双三次插值
		// };
		WISE_ENUM_CLASS_MEMBER(Interpolation, NEAREST, BILINEAR, BICUBIC);

		int64_t height;					///< 上采样高度
		int64_t width;					///< 上采样宽度
		Interpolation interpolation;	///< 插值方式，默认为最近邻插值
		bool align_corners;				///< 是否对齐四角，默认为false，最近邻插值时该参数无效

		ICRAFT_DECLARE_ATTRS(UpsampleNode) {
			ICRAFT_ATTR_FIELD(height).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(width).set_lower_bound(1);
			ICRAFT_ATTR_FIELD(interpolation).set_default(Interpolation::NEAREST);
			ICRAFT_ATTR_FIELD(align_corners).set_default(false);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Upsample算子引用类 */
	class Upsample : public OpBase<Upsample, UpsampleNode> {
	public:
		using Interpolation = UpsampleNode::Interpolation;

		/** 默认构造函数 */
		Upsample() = default;

		/**
		 * @brief 构造函数
		 * @param input				输入
		 * @param height			上采样高度
		 * @param width				上采样宽度
		 * @param interpolation		插值方式，默认为最近邻插值
		 * @param align_corners		是否对齐四角，默认为false，最近邻插值时该参数无效
		 */
		XIR_DLL Upsample(
			Value input,
			int64_t height,
			int64_t width,
			Interpolation interpolation = Interpolation::NEAREST,
			bool align_corners = false
		);
	};
}
