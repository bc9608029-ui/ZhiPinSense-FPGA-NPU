#pragma once
#include <icraft-xir/core/operation.h>

namespace icraft::xir {
    /** TopK算子 */
    class TopKNode : public OpNodeBase<TopKNode> {
    public:
        int64_t axis;                   ///< 沿哪个轴进行操作
        bool largest;                   ///< 是否选择最大的元素（否则选择最小的）
        bool sorted;                    ///< 结果是否排序

        ICRAFT_DECLARE_ATTRS(TopKNode) {
            ICRAFT_ATTR_FIELD(axis).set_default(-1);
            ICRAFT_ATTR_FIELD(largest).set_default(true);
            ICRAFT_ATTR_FIELD(sorted).set_default(true);
        }
        
        XIR_DLL virtual void validate() const override;
    };
    
    /** TopK算子引用类 */
    class TopK : public OpBase<TopK, TopKNode> {
    public:
        /** 默认构造函数 */
        TopK() = default;

        /**
         * @brief 构造函数
         * @param input           输入张量
         * @param k               要选择的顶部元素数量
         * @param axis            沿哪个轴进行操作
         * @param largest         是否选择最大的元素
         * @param sorted          结果是否排序
         */
        XIR_DLL TopK(Value input, Value k, int64_t axis = -1, 
                     bool largest = true, bool sorted = true);
        
        // /** 获取值输出 */
        // Value values() const { return this->operator[](0); }
        
        // /** 获取索引输出 */
        // Value indices() const { return this->operator[](1); }
    };
}