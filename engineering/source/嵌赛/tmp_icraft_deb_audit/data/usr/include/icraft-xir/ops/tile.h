#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Tile算子 */
	class TileNode : public OpNodeBase<TileNode> {
	public:
		Array<int64_t> dims;			///< 每个维度的重复次数

		ICRAFT_DECLARE_ATTRS(TileNode) {
			ICRAFT_ATTR_FIELD(dims);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Tile算子引用类 */
	class Tile : public OpBase<Tile, TileNode> {
	public:
		/** 默认构造函数 */
		Tile() = default;

		/**
		 * @brief 构造函数
		 * @param input	输入
		 * @param dims	每个维度的重复次数
		 */
		XIR_DLL Tile(Value input, Array<int64_t> dims);
	};
}
