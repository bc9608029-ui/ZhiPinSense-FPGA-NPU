#pragma once
#include <icraft-xir/core/operation.h>

namespace icraft::xir {
    
    /** GatherElements算子 */
    class GatherElementsNode : public OpNodeBase<GatherElementsNode> {
    public:
        int64_t axis;                   ///< 沿哪个轴进行收集操作

        ICRAFT_DECLARE_ATTRS(GatherElementsNode) {
            ICRAFT_ATTR_FIELD(axis).set_default(0);
        }
        
        XIR_DLL virtual void validate() const override;
    };
    
    /** GatherElements算子引用类 */
    class GatherElements : public OpBase<GatherElements, GatherElementsNode> {
    public:
        /** 默认构造函数 */
        GatherElements() = default;

        /**
         * @brief 构造函数
         * @param input           输入张量
         * @param indices         索引张量
         * @param axis            沿哪个轴进行收集操作
         */
        XIR_DLL GatherElements(Value input, Value indices, int64_t axis = 0);
    };
}