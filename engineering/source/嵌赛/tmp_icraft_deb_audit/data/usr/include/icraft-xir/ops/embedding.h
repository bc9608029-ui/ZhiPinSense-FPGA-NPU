#pragma once
#include <icraft-xir/core/operation.h>


namespace icraft::xir {

	/** Embedding算子 */
	class EmbeddingNode : public OpNodeBase<EmbeddingNode> {
	public:
		Params weights;

		ICRAFT_DECLARE_ATTRS(EmbeddingNode) {
			ICRAFT_ATTR_FIELD(weights);
		}

		XIR_DLL virtual void validate() const override;
	};


	/** Embedding算子引用类 */
	class Embedding : public OpBase<Embedding, EmbeddingNode> {
	public:
		/** 默认构造函数 */
		Embedding() = default;

		/**
		 * @brief 构造函数
		 * @param input	输入
		 * @param weights
		 */
		XIR_DLL Embedding(Value input, Params weights);
	};
}
