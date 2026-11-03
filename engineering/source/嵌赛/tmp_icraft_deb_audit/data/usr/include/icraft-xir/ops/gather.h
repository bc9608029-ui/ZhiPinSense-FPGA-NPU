#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

    /** Gather算子 */
    class GatherNode : public OpNodeBase<GatherNode> {
    public:
        int64_t axis;	///< Gather的索引维度，默认为0

        ICRAFT_DECLARE_ATTRS(GatherNode) {
            ICRAFT_ATTR_FIELD(axis).set_default(0);
        }

        XIR_DLL virtual void validate() const override;
    };

    /** Gather算子引用类 */
    class Gather : public OpBase<Gather, GatherNode> {
    public:
        /** 默认构造函数 */
        Gather() = default;

        /**
         * @brief 构造函数
         * @param input		输入
         * @param indices	索引
         * @param axis		索引维度
         */
        XIR_DLL Gather(Value input, Value indices, int64_t axis);
    };
}