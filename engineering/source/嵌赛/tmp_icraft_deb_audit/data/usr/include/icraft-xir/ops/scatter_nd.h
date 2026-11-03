#pragma once
#include <icraft-xir/core/operation.h>
#include <icraft-xir/ops/scatter_element.h>
namespace icraft::xir {

    /** ScatterND算子节点 */
    class ScatterNDNode : public OpNodeBase<ScatterNDNode> {
    public:
        Reduction reduction;     ///< 减少模式

        ICRAFT_DECLARE_ATTRS(ScatterNDNode) {
            ICRAFT_ATTR_FIELD(reduction).set_default(Reduction::NONE);
        }

        XIR_DLL virtual void validate() const override;
    };


    /** ScatterND算子引用类 */
    class ScatterND : public OpBase<ScatterND, ScatterNDNode> {
    public:

        /** 默认构造函数 */
        ScatterND() = default;

        /**
         * @brief 构造函数
         * @param data      输入数据张量
         * @param indices   索引张量
         * @param updates   更新值张量
         * @param reduction 减少模式
         */
        XIR_DLL ScatterND(Value data, Value indices, Value updates,
            Reduction reduction = Reduction::NONE);
    };

} // namespace icraft::xir
