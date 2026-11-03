#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	class HardOpNode;


	/** HardOp算子引用类 */
	class HardOp : public OpBase<HardOp, HardOpNode> {
	public:
		/** 默认构造函数 */
		HardOp() = default;

		/**
		 * @brief 构造函数
		 * @param input 输入
		 * @param instr 指令
		 * @param params 参数
		 * @param origin_ops_id 原始的Op ID列表
		 * @param device_info 设备信息
		 * @param layer_count 硬件layer_count信息
		 * @param sub_hard_ops SpeedMode时合并前的HardOp们
		 */
		XIR_DLL HardOp(
			Array<Value> inputs,
			Array<Params> instr,
			Array<Params> params,
			Array<int64_t> origin_ops_id,
			Map<String, IntImm> device_info,
			int64_t layer_count = 0,
			Array<HardOp> sub_hard_ops = {}
		);

		HardOp(
			Array<Value> inputs,
			Params instr,
			Params params,
			Array<int64_t> origin_ops_id,
			Map<String, IntImm> device_info,
			int64_t layer_count = 0,
			Array<HardOp> sub_hard_ops = {}
		) : HardOp(
			inputs,
			Array<Params>{ instr  },
			Array<Params>{ params },
			origin_ops_id,
			device_info,
			layer_count,
			sub_hard_ops
		) {}
	};


	/** HardOp算子 */
	class HardOpNode : public OpNodeBase<HardOpNode> {
	public:
		Array<Params> instr;				///< 指令
		Array<Params> params;				///< 参数
		Array<int64_t> origin_ops_id;		///< 原始的Op ID列表
		Map<String, IntImm> device_info;	///< 设备信息

		int64_t layer_count;				///< 硬件layer_count信息
		Array<HardOp> sub_hard_ops;			///< SpeedMode时合并前的HardOp们

		ICRAFT_DECLARE_ATTRS(HardOpNode) {
			ICRAFT_ATTR_FIELD(instr);
			ICRAFT_ATTR_FIELD(params);
			ICRAFT_ATTR_FIELD(origin_ops_id);
			ICRAFT_ATTR_FIELD(device_info);
			ICRAFT_ATTR_FIELD(layer_count).set_default(0);
			ICRAFT_ATTR_FIELD(sub_hard_ops);
		}

		XIR_DLL virtual void validate() const override;
	};
}
