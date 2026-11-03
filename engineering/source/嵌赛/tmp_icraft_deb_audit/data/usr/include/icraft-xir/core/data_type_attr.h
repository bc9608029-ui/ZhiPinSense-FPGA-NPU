#pragma once
#include <icraft-xir/utils/wise_enum.h>

namespace icraft::xir {
	 /*enum class DistrUnvalidValue {
	 	ZERO,
	 	NONE
	 };*/
	WISE_ENUM_CLASS(DistrUnvalidValue, ZERO, NONE);

	/**
	 * @brief 表示通道分布的类
	 *		MergedAxisDistr使用掩码来表示多个维度融合后元素是否有效，掩码的数量和融合后元素数相同
	 *		当掩码为1时表示该通道有效，为0表示无效
	 *		当元素无效时，其值可能是ZERO，即0；也可能是NONE，即不存在；元素无效值由uvalue指定
	 */
	class MergedAxisDistrNode : public NodeBase<MergedAxisDistrNode, Node> {
	public:
		Array<int64_t> merged_axis;			///< 融合的维度索引列表
		Array<bool> valid_mask;				///< 元素掩码列表
		DistrUnvalidValue uvalue;			///< 无效元素的值

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(MergedAxisDistrNode* other, const ReduceVisitor& reduce) const;
	};


	/** 表示通道分布的引用类 */
	class MergedAxisDistr : public HandleBase<MergedAxisDistr, Handle, MergedAxisDistrNode> {
	public:
		/** 默认构造函数 */
		MergedAxisDistr() = default;

		/**
		 * @brief 构造函数
		 * @param merged_axis	坐标轴索引
		 * @param element_num	元素的数量
		 * @param init			valid_mask的初始值，默认为true
		 */
		XIR_DLL MergedAxisDistr(Array<int64_t> merged_axis, int64_t element_num = 0, bool init = true);

		/**
		 * @brief 设置融合坐标
		 * @param merged_axis	坐标轴索引
		 * @return 自身
		 */
		XIR_DLL MergedAxisDistr& setMergedAxis(Array<int64_t> merged_axis);

		/**
		 * @brief 向AxisDistr中添加通道
		 * @param element_num	通道数量
		 * @param valid			添加的通道是否有效
		 * @return 自身
		 */
		XIR_DLL MergedAxisDistr& append(int64_t element_num, bool valid);

		/**
		 * @brief 合并另一个valid_mask
		 * @param other_valid_mask  数组表示的有效掩码
		 * @return 自身
		 */
		XIR_DLL MergedAxisDistr& append(const Array<bool>& other_valid_mask);

		/** 标记[start, end)范围有效 */
		XIR_DLL MergedAxisDistr& setValid(int64_t start, int64_t end);

		/** 标记[start, end)范围无效 */
		XIR_DLL MergedAxisDistr& setUnvalid(int64_t start, int64_t end);

		/** 设置无效元素的值 */
		XIR_DLL MergedAxisDistr& setUValue(DistrUnvalidValue uvalue);

		/**
		 * @brief 获取所有的片段
		 * @return 表示片段的vector，其中每个元素为一个tuple，
		 *		   tuple的三个元素分别表示该片段的[开始, 结束)以及是否有效
		 */
		XIR_DLL std::vector<std::tuple<uint64_t, uint64_t, bool>> allSections() const;

		/**
		 * @brief 获取所有的有效片段
		 * @return 表示有效片段的vector，其中每个元素为一个pair，
		 *		   表示[pair.first, pair.second)范围是有效的
		 */
		XIR_DLL std::vector<std::pair<uint64_t, uint64_t>> validSections() const;

		/**
		 * @brief 获取所有的无效片段
		 * @return 表示有效片段的vector，其中每个元素为一个pair，
		 *		   表示[pair.first, pair.second)范围是无效的
		 */
		XIR_DLL std::vector<std::pair<uint64_t, uint64_t>> unvalidSections() const;

		/** 获取总的有效元素数 */
		XIR_DLL uint64_t totalValidNum() const;

		/** 获取总的无效元素数 */
		XIR_DLL uint64_t totalUnvalidNum() const;

		/** 获取总的元素数 */
		XIR_DLL uint64_t totalNum() const;

		/**
		 * @brief 检查指定的元素是否有效
		 * @param index 索引（支持负数索引）
		 * @return 如果有效则返回true
		 */
		XIR_DLL bool isValid(int64_t index) const;
	};


	/** 表示归一化系数列表 */
	class NormratioArrayNode : public NodeBase<NormratioArrayNode, Node> {

	public:
		int64_t axis = -1;				///< normratio系数对应的维度，默认为-1，表示最后一维
		Array<float> data;				///< 归一化系数列表

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(NormratioArrayNode* other, const ReduceVisitor& reduce) const;
	};


	/** 归一化系数列表的引用类 */
	class NormratioArray : public HandleBase<NormratioArray, Handle, NormratioArrayNode> {
	public:
		/** 默认构造函数 */
		XIR_DLL NormratioArray();

		/**
		 * @brief 构造函数.
		 * @param data  归一化系数列表
		 * @param axis  normratio系数对应的维度，默认为-1，表示最后一维
		 */
		XIR_DLL explicit NormratioArray(Array<float> data, int64_t axis = -1);

		/**
		 * @brief 通过索引访问元素
		 * @param index 索引（支持负数索引）
		 * @return 索引指定元素的拷贝
		 */
		XIR_DLL const float operator[](int64_t index) const;

		/**
		 * @brief 修改系数对应的维度
		 * @param axis 维度（支持负数索引）
		 * @return 自身
		 */
		XIR_DLL NormratioArray& setAxis(int64_t axis);
	};


	/** 表示量化缩放系数 */
	class QuantizedScaleNode : public NodeBase<QuantizedScaleNode, Node> {
	public:
		float origin_scale;		///< 未适配硬件的原始浮点缩放系数

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(QuantizedScaleNode* other, const ReduceVisitor& reduce) const;
	};


	/** 量化缩放系数的引用类 */
	class QuantizedScale : public HandleBase<QuantizedScale, Handle, QuantizedScaleNode> {
	public:
		/** 默认构造函数 */
		QuantizedScale() = default;

		/**
		 * @brief 构造函数
		 * @param origin_scale  未适配硬件的原始浮点缩放系数
		 */
		XIR_DLL explicit QuantizedScale(float origin_scale);
	};


	class QuantizedScaleArray;


	/** 表示量化缩放系数列表 */
	class QuantizedScaleArrayNode : public NodeBase<QuantizedScaleArrayNode, Node> {

		friend class QuantizedScaleArray;

	public:
		int64_t axis = -1;					///< origin_scale系数对应的维度，默认为-1，表示最后一维
		Array<float> origin_scale;			///< 未适配硬件的原始浮点缩放系数列表

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(QuantizedScaleArrayNode* other, const ReduceVisitor& reduce) const;

	private:
		XIR_DLL virtual const QuantizedScale operator[](int64_t index) const;

		XIR_DLL virtual const QuantizedScale front() const;

		XIR_DLL virtual const QuantizedScale back() const;

		XIR_DLL virtual QuantizedScaleArray split(int64_t begin, int64_t end, int64_t stride = 1) const;
	};


	/** 量化缩放系数列表的引用类 */
	class QuantizedScaleArray : public HandleBase<QuantizedScaleArray, Handle, QuantizedScaleArrayNode> {
	public:
		/** 默认构造函数 */
		XIR_DLL QuantizedScaleArray();

		/**
		 * @brief 构造函数
		 * @param origin_scale  未适配硬件的原始浮点缩放系数列表
		 * @param axis  origin_scale系数对应的维度，默认为-1，表示最后一维
		 */
		XIR_DLL explicit QuantizedScaleArray(Array<float> origin_scale, int64_t axis = -1);

		/**
		 * @brief 构造函数
		 * @param lhs			待拼接输入1
		 * @param rhs			待拼接输入2
		 */
		XIR_DLL QuantizedScaleArray(QuantizedScaleArray lhs, QuantizedScaleArray rhs);

		/**
		 * @brief 构造函数，从初始值构造
		 * @param n 元素数量
		 * @param val 初始值
		 */
		XIR_DLL QuantizedScaleArray(const size_t n, const QuantizedScale& val);

		/** 获取Array的大小  */
		XIR_DLL const size_t size() const;

		/** 检查Array是否为空  */
		XIR_DLL bool empty() const;

		/**
		 * @brief 通过索引访问元素
		 * @param index 索引（支持负数索引）
		 * @return 索引指定元素的拷贝
		 */
		XIR_DLL const QuantizedScale operator[](int64_t index) const;

		/** 获取存储的第一个元素 */
		XIR_DLL const QuantizedScale front() const;

		/** 获取存储的最后一个元素 */
		XIR_DLL const QuantizedScale back() const;

		/**
		 * @brief 通过索引访问子列表
		 * @param begin 起始元素的索引（包含）
		 * @param end   结束元素的索引（不包含）
		 * @return 索引指定子列表的拷贝
		 */
		XIR_DLL QuantizedScaleArray split(int64_t begin, int64_t end, int64_t stride = 1) const;

		/**
		 * @brief 修改系数对应的维度
		 * @param axis 维度（支持负数索引）
		 * @return 自身
		 */
		XIR_DLL QuantizedScaleArray& setAxis(int64_t axis);
	};


	/** m*2^(-exp)形式的量化缩放系数 */
	class ExpQuantizedScaleNode : public NodeBase<ExpQuantizedScaleNode, QuantizedScaleNode> {
	public:
		int64_t m;		///< m*2^(-exp)中的m
		int64_t exp;	///< m*2^(-exp)中的exp

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(ExpQuantizedScaleNode* other, const ReduceVisitor& reduce) const;
	};


	/** m*2^(-exp)形式的量化缩放系数的引用类 */
	class ExpQuantizedScale : public HandleBase<ExpQuantizedScale, QuantizedScale, ExpQuantizedScaleNode> {
	public:
		/** 默认构造函数 */
		ExpQuantizedScale() = default;

		/**
		 * @brief 构造函数
		 * @param m				m*2^(-exp)中的m
		 * @param exp			m*2^(-exp)中的exp
		 * @param origin_scale	未适配硬件的原始浮点缩放系数
		 */
		XIR_DLL ExpQuantizedScale(int64_t m, int64_t exp, float origin_scale);
	};


	/** m*2^(-exp)形式的量化缩放系数列表 */
	class ExpQuantizedScaleArrayNode : public NodeBase<ExpQuantizedScaleArrayNode, QuantizedScaleArrayNode> {
	public:
		Array<int64_t> m;		///< m*2^(-exp)中的m列表
		Array<int64_t> exp;		///< m*2^(-exp)中的exp列表

		friend class QuantizedScaleArrayNode;

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(ExpQuantizedScaleArrayNode* other, const ReduceVisitor& reduce) const;

		XIR_DLL virtual const QuantizedScale operator[](int64_t index) const override;

		XIR_DLL virtual const QuantizedScale front() const override;

		XIR_DLL virtual const QuantizedScale back() const override;

		XIR_DLL virtual QuantizedScaleArray split(int64_t begin, int64_t end, int64_t stride = 1) const override;
	};


	/** m*2^(-exp)形式的量化缩放系数列表的引用类 */
	class ExpQuantizedScaleArray : public HandleBase<ExpQuantizedScaleArray, QuantizedScaleArray, ExpQuantizedScaleArrayNode> {
	public:
		/** 默认构造函数 */
		XIR_DLL ExpQuantizedScaleArray();

		/**
		 * @brief 构造函数
		 * @param m				m*2^(-exp)中的m列表
		 * @param exp			m*2^(-exp)中的exp列表
		 * @param origin_scale	未适配硬件的原始浮点缩放系数列表
		 * @param axis	三种系数对应的维度，默认为-1，表示最后一维
		 */
		XIR_DLL ExpQuantizedScaleArray(Array<int64_t> m, Array<int64_t> exp, Array<float> origin_scale, int64_t axis = -1);

		/**
		 * @brief 构造函数
		 * @param lhs			待拼接输入1
		 * @param rhs			待拼接输入2
		 */
		XIR_DLL ExpQuantizedScaleArray(QuantizedScaleArray lhs, QuantizedScaleArray rhs);

		/**
		 * @brief 构造函数，从初始值构造
		 * @param n 元素数量
		 * @param val 初始值
		 */
		XIR_DLL ExpQuantizedScaleArray(const size_t n, QuantizedScale val);

		/**
		 * @brief 修改系数对应的维度
		 * @param axis 维度（支持负数索引）
		 * @return 自身
		 */
		XIR_DLL ExpQuantizedScaleArray& setAxis(int64_t axis);
	};
}
