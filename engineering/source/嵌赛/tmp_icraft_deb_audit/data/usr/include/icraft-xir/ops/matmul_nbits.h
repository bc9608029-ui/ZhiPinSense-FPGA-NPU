#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** MatmulNBits算子 */
	class MatmulNBitsNode : public OpNodeBase<MatmulNBitsNode> {
	public:
		int64_t group_size;			///< 通道上的每个组的尺寸
		int64_t group_cnt;			///< 通道上的分组数量，group_cnt=channel/group_size
		int64_t bits;			    ///< kernel的量化位宽，以bit维单位

		int64_t K;	//输入通道
		int64_t N;	//输出通道，如q k v

		Optional<Params> zero_points;
		Value weights;
		Value scales;

		ICRAFT_DECLARE_ATTRS(MatmulNBitsNode) {
			ICRAFT_ATTR_FIELD(group_size);
			ICRAFT_ATTR_FIELD(group_cnt);
			ICRAFT_ATTR_FIELD(bits);
			ICRAFT_ATTR_FIELD(K);
			ICRAFT_ATTR_FIELD(N);

			ICRAFT_ATTR_FIELD(zero_points);
			ICRAFT_ATTR_FIELD(weights);
			ICRAFT_ATTR_FIELD(scales);
		};

		XIR_DLL virtual void validate() const override;
	};


	/** MatmulNBits算子引用类 */
	class MatmulNBits : public OpBase<MatmulNBits, MatmulNBitsNode> {
	public:
		/** 默认构造函数 */
		MatmulNBits() = default;

		/**
		 * @brief 构造函数
		 * @input x 输入
		 * @param k 压缩后的kernel
		 * @param scale ，kernel的scale
		 * @param zero_points ，kernel的zero_points
		 * @param bits kernel的量化位宽
		 * @param group_cnt ，通道上的分组数量
		 * @param group_size ，通道上的每个组的尺寸
		 * @param K ，输入通道
		 * @param N ，输出通道
		 */
		XIR_DLL MatmulNBits(Value x, Value weights, Value scales, Optional<Value> zero_points, int64_t bits, int64_t group_cnt, int64_t group_size, int64_t K, int64_t N);

		//XIR_DLL MatmulNBits(Value x, Value k, Value scales, 
		//	Optional<Params> zero_points,
		//	int64_t bits, int64_t group_cnt, int64_t group_size);


	};
}
