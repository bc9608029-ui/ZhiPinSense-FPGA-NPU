#pragma once
#include <icraft-xir/core/operation.h>

namespace icraft::xir {
    /**
         * @enum    Reduction
         * @brief   减少模式（可选）
         */
         /*enum class Reduction {
             NONE,       ///< 无减少操作
             ADD,        ///< 添加模式
             MULTIPLY,   ///< 相乘模式
             MAX,        ///< 最大值模式
             MIN         ///< 最小值模式
         };*/
    WISE_ENUM_CLASS(Reduction, NONE, ADD, MULTIPLY, MAX, MIN);

    /** ScatterElement算子节点 */
    class ScatterElementNode : public OpNodeBase<ScatterElementNode> {
    public:
        int64_t axis;	///< 指定ScatterElement的维度（支持负数索引），默认为-1，表示最后一维

        Reduction reduction;     ///< 减少模式

        ICRAFT_DECLARE_ATTRS(ScatterNDNode) {
            ICRAFT_ATTR_FIELD(reduction).set_default(Reduction::NONE);
            ICRAFT_ATTR_FIELD(axis).set_default(-1).set_lower_bound(-1);
        }

        XIR_DLL virtual void validate() const override;
    };


    /** ScatterElement算子引用类 */
    class ScatterElement : public OpBase<ScatterElement, ScatterElementNode> {
    public:

        /** 默认构造函数 */
        ScatterElement() = default;

        /**
         * @brief 构造函数
         * @param data      输入数据张量
         * @param indices   索引张量
         * @param updates   更新值张量
         * @param reduction 减少模式
         */
        XIR_DLL ScatterElement(Value data, Value indices, Value updates, int64_t axis = -1,
            Reduction reduction = Reduction::NONE);
    };

} // namespace icraft::xir
