#pragma once
#include <icraft-xir/core/layout.h>
#include <icraft-xir/core/data_type_attr.h>


namespace icraft::xir {

	/** 表示IR中数据类型的类型 */
	class DataTypeNode : public NodeBase<DataTypeNode, Node> {
	public:
		virtual void accept(AttrVisitor& visitor) override {}

	private:
		/** 获取数据的bits */
		virtual uint64_t bits() const { return 0; };

		/** 获取数据的元素数量 */
		virtual uint64_t numElements() const { return 0; };

		friend class DataType;
	};


	class ScalarType;
	class QuantizedScaleArray;


	/** IR中表示数据类型的引用类 */
	class DataType : public VirtualBase<DataType, Handle, DataTypeNode> {
	public:
		/** 获取该数据类型所占位数 */
		XIR_DLL uint64_t bits() const;

		/**
		 * @brief 获取该数据类型所占字节数
		 * @return 所占位数除八，向上取整
		 */
		XIR_DLL uint64_t bytes() const;

		/** 获取数据类型的元素个数 */
		XIR_DLL uint64_t numElements() const;

		/**
		 * @brief 获取(可选的)归一化系数
		 * @return 如果该DataType是NormalizedType或NormalizedQuantizedType，则返回相应的归一化系数，否则返回NullOpt
		 */
		XIR_DLL Optional<NormratioArray> getNormratio() const;

		/**
		 * @brief 尝试设置归一化系数（兼容性接口，默认axis = -1）
		 * @param normratio 归一化系数
		 * @return 如果该DataType是 NormalizedType 或 NormalizedQuantizedType,
		 *			则设置相应的归一化系数并返回true，否则返回false
		 */
		XIR_DLL bool setNormratio(Array<float> normratio);

		/**
		 * @brief 尝试设置归一化系数.
		 * @param normratio 归一化系数
		 * @return 如果该DataType是 NormalizedType 或 NormalizedQuantizedType,
		 *			则设置相应的归一化系数并返回true，否则返回false
		 */
		XIR_DLL bool setNormratio(NormratioArray normratio);

		/**
		 * @brief 获取(可选的)量化缩放因子
		 * @return 如果该DataType是QuantizedType，则返回相应的量化缩放因子，否则返回NullOpt
		 */
		XIR_DLL Optional<QuantizedScaleArray> getScale() const;

		/**
		 * @brief 尝试设置量化缩放因子
		 * @return 如果该DataType是QuantizedType，则设置相应的量化缩放因子并返回true，否则返回false
		 */
		XIR_DLL bool setScale(QuantizedScaleArray scale);

		/**
		 * @brief 获取(可选的)量化的零点
		 * @return 如果该DataType是QuantizedType，则返回相应的量化的零点，否则返回NullOpt
		 */
		XIR_DLL Optional<Array<int64_t>> getZeroPoints() const;

		/**
		 * @brief 尝试设置量化的零点
		 * @return 如果该DataType是QuantizedType，则设置相应的量化的零点并返回true，否则返回false
		 */
		XIR_DLL bool setZeroPoints(Array<int64_t> zero_points);

		/**
		 * @brief 获取存储类型
		 * @return  如果该DataType是非量化类型，则返回本身；
		 *			如果该DataType是量化类型，则返回相应的storage_dtype；
		 *			如果该DataType是TensorType，对其element_dtype做以上处理
		 */
		XIR_DLL ScalarType getStorageType() const;

		/**
		 * @brief 设置存储类型
		 * @return  如果该DataType是非量化类型，则设置本身；
		 *			如果该DataType是量化类型，则设置相应的storage_dtype；
		 *			如果该DataType是TensorType，对其element_dtype做以上处理
		 */
		XIR_DLL void setStorageType(ScalarType type);
	};


	/** IR中表示标量数据类型 */
	class ScalarTypeNode : public NodeBase<ScalarTypeNode, DataTypeNode> {
	public:
		/** 获取数据的元素数量 */
		XIR_DLL virtual uint64_t numElements() const override;
	};


	/** IR中标量数据类型的引用类 */
	class ScalarType : public VirtualBase<ScalarType, DataType, ScalarTypeNode> {
	public:
		/** 检查是否是有符号的整数 */
		XIR_DLL bool isSigned() const;

		/** 检查是否是N位的sint */
		XIR_DLL bool isSInt(uint64_t N) const;

		/** 检查是否是N位的uint */
		XIR_DLL bool isUInt(uint64_t N) const;

		/** 检查是否是sint8 */
		XIR_DLL bool isSInt8() const;

		/** 检查是否是uint8 */
		XIR_DLL bool isUInt8() const;

		/** 检查是否是sint16 */
		XIR_DLL bool isSInt16() const;

		/** 检查是否是uint16 */
		XIR_DLL bool isUInt16() const;

		/** 检查是否是sint32 */
		XIR_DLL bool isSInt32() const;

		/** 检查是否是uint32 */
		XIR_DLL bool isUInt32() const;

		/** 检查是否是sint64 */
		XIR_DLL bool isSInt64() const;

		/** 检查是否是uint64 */
		XIR_DLL bool isUInt64() const;

		/** 检查是否是bool */
		XIR_DLL bool isBool() const;

		/** 检查该浮点类型是否是bf16 */
		XIR_DLL bool isBF16() const;

		/** 检查该浮点类型是否是fpe7m8 */
		XIR_DLL bool isFPE7M8() const;

		/** 检查该浮点类型是否是fpe6m9 */
		XIR_DLL bool isFPE6M9() const;

		/** 检查该浮点类型是否是fp16 */
		XIR_DLL bool isFP16() const;

		/** 检查该浮点类型是否是fp32 */
		XIR_DLL bool isFP32() const;

		/** 检查该浮点类型是否是fp64 */
		XIR_DLL bool isFP64() const;

		/** 检查该浮点类型是否是tf32 */
		XIR_DLL bool isTF32() const;
	};


	/** IR中表示布尔数据类型的类型 */
	class BoolTypeNode : public NodeBase<BoolTypeNode, ScalarTypeNode> {
	public:
		friend class BoolType;

	public:
		BoolTypeNode() = default;

		virtual void accept(AttrVisitor& visitor) override {};
	};


	/** 布尔数据类型的引用类 */
	class BoolType : public HandleBase<BoolType, ScalarType, BoolTypeNode> {
	public:
		/** 默认构造函数 */
		BoolType() = default;
	};


	/** IR中表示整型数据类型的类型 */
	class IntegerTypeNode : public NodeBase<IntegerTypeNode, ScalarTypeNode> {
	public:
		bool sign;			///< 整型的符号，为true表示有符号，false表示无符号
		uint64_t ibits;		///< 整型位数

		friend class IntegerType;

	public:
		IntegerTypeNode() = default;
		IntegerTypeNode(bool sign, uint64_t ibits) : sign(sign), ibits(ibits) {}

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(IntegerTypeNode* other, const ReduceVisitor& reduce) const;

	private:
		/** 获取数据类型的位数 */
		XIR_DLL virtual uint64_t bits() const override;
	};


	/** 整型数据类型的引用类 */
	class IntegerType : public HandleBase<IntegerType, ScalarType, IntegerTypeNode> {
	public:
		/** 默认构造函数 */
		IntegerType() = default;

		/**
		 * @brief 构造函数
		 * @param sign 整型的符号
		 * @param bits 整型的位数
		 */
		XIR_DLL IntegerType(bool sign, int bits);

		/**
		 * @brief 创建一个指定位数的sint
		 * @param N sint的位数
		 * @return 创建所得到的sint
		 */
		XIR_DLL static IntegerType SInt(uint64_t N);

		/**
		 * @brief 创建一个指定位数的uint
		 * @param N uint的位数
		 * @return 创建所得到的uint
		 */
		XIR_DLL static IntegerType UInt(uint64_t N);

		/** 创建一个sint8 */
		XIR_DLL static IntegerType SInt8();

		/** 创建一个uint8 */
		XIR_DLL static IntegerType UInt8();

		/** 创建一个sint16 */
		XIR_DLL static IntegerType SInt16();

		/** 创建一个uint16 */
		XIR_DLL static IntegerType UInt16();

		/** 创建一个sint32 */
		XIR_DLL static IntegerType SInt32();

		/** 创建一个uint32 */
		XIR_DLL static IntegerType UInt32();

		/** 创建一个sint64 */
		XIR_DLL static IntegerType SInt64();

		/** 创建一个uint64 */
		XIR_DLL static IntegerType UInt64();
	};


	/** IR中表示浮点数据类型的类型 */
	class FloatTypeNode : public NodeBase<FloatTypeNode, ScalarTypeNode> {
	public:
		int64_t emax;			///< 指数的最大值
		int64_t emin;			///< 指数的最小值
		uint64_t precision;		///< 尾数的精度(位数)
		uint64_t fbits;			///< 浮点数的位数

		friend class FloatType;

	public:
		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(FloatTypeNode* other, const ReduceVisitor& reduce) const;

	private:
		/** 获取数据类型的位数 */
		XIR_DLL virtual uint64_t bits() const override;
	};


	/** 浮点数据类型的引用类 */
	class FloatType : public HandleBase<FloatType, ScalarType, FloatTypeNode> {
	public:
		/** 表示浮点语义的结构体 */
		class Semantics {
		public:
			int64_t emax;			///< 指数的最大值
			int64_t emin;			///< 指数的最小值
			uint64_t precision;		///< 尾数的精度(位数)
			uint64_t bits;			///< 浮点数的位数

			/** 检查该Semantics是否和另一个相等 */
			XIR_DLL bool operator==(const Semantics& other);
		};

		/** 默认构造函数 */
		FloatType() = default;

		/**
		 * @brief 构造函数
		 * @param emax 指数的最大值
		 * @param emin 指数的最小值
		 * @param precision 尾数的精度(位数)
		 * @param bits 浮点数的位数
		 */
		XIR_DLL FloatType(int emax, int emin, int precision, int bits);

		/**
		 * @brief 构造函数
		 * @param sem 浮点语义
		 */
		FloatType(const Semantics& sem) : FloatType(sem.emax, sem.emin, sem.precision, sem.bits) {}

		/** 获取该浮点类型的浮点语义 */
		XIR_DLL Semantics semantics() const;

		/** 创建一个bf16 */
		XIR_DLL static FloatType BF16();

		/** 创建一个fpe7m8 */
		XIR_DLL static FloatType FPE7M8();

		/** 创建一个fpe6m9 */
		XIR_DLL static FloatType FPE6M9();

		/** 创建一个fp16 */
		XIR_DLL static FloatType FP16();

		/** 创建一个fp32 */
		XIR_DLL static FloatType FP32();

		/** 创建一个fp64 */
		XIR_DLL static FloatType FP64();

		/** 创建一个tf32 */
		XIR_DLL static FloatType TF32();

		/// @cond
		inline static const Semantics BF16_SEM = { 127, -126, 8, 16 };

		inline static const Semantics FPE7M8_SEM = { 63, -64, 9, 16 };
		inline static const Semantics FPE6M9_SEM = { 31, -32, 10, 16 };

		inline static const Semantics FP16_SEM = { 15, -14, 11, 16 };
		inline static const Semantics FP32_SEM = { 127, -126, 24, 32 };
		inline static const Semantics FP64_SEM = { 1023, -1022, 53, 64 };

		inline static const Semantics TF32_SEM = { 127, -126, 11, 19 };
		/// @endcond
	};


	/** 表示张量数据类型 */
	class TensorTypeNode : public NodeBase<TensorTypeNode, DataTypeNode> {
	public:
		ScalarType element_dtype;				///< 张量元素的数据类型
		Array<int64_t> shape;					///< 张量的形状
		Layout layout;							///< 张量的排布
		Array<MergedAxisDistr> merged_distrs;	///< 维度的分布

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(TensorTypeNode* other, const ReduceVisitor& reduce) const;

	private:
		/** 获取张量总的bits */
		XIR_DLL virtual uint64_t bits() const override;

		/**
		 * @brief 获取张量的元素数量
		 * @return 张量各维度相乘
		 * @throw 各维度必须为正整数，否则抛出异常
		 */
		XIR_DLL virtual uint64_t numElements() const override;
	};


	/** 张量数据类型的引用类 */
	class TensorType : public HandleBase<TensorType, DataType, TensorTypeNode> {
	public:
		/** 默认构造函数 */
		TensorType() = default;

		/**
		 * @brief构造函数
		 * @param element_type	元素类型
		 * @param shape			张量的形状
		 * @param layout		张量的排布
		 * @param merged_distrs	维度的分布
		 */
		XIR_DLL TensorType(ScalarType element_type, Array<int64_t> shape, Layout layout, Array<MergedAxisDistr> merged_distrs = {});

		/**
		 * @brief 获取维度大小
		 * @param combine 组合，大小写字母合并后的完整维度
		 * @return 维度大小
		 */
		XIR_DLL uint64_t dimSize(bool combine = false) const;

		/**
		 * @brief 获取张量索引指定的维度
		 * @param index 索引（支持负数索引）
		 * @param combine 组合，大小写字母合并后的完整维度
		 * @return 索引对应的维度
		 * @throw 如果索引越界则抛出异常
		 */
		XIR_DLL int64_t getDim(int64_t index, bool combine = false) const;

		/**
		 * @brief 获取张量排布中的指定轴的维度
		 * @param c 字符表示的张量排布中的坐标轴
		 * @param combine 组合，大小写字母合并后的完整维度
		 * @return 该坐标轴上的维度
		 * @throw 指定的坐标轴不能为'*'，否则抛出异常
		 */
		XIR_DLL int64_t getDimByAxis(char c, bool combine = false) const;

		/**
		 * @brief 设置张量排布中的指定轴的维度
		 * @param c		字符表示的张量排布中的坐标轴
		 * @param dim	被设置的维度
		 * @return 自身
		 * @throw 指定的坐标轴不能为'*'，否则抛出异常
		 */
		XIR_DLL TensorType& setDimByAxis(char c, int64_t dim);

		/** 设置元素数据类型 */
		XIR_DLL TensorType& setElementDtype(ScalarType dtype);

		/** 设置形状 */
		XIR_DLL TensorType& setShape(Array<int64_t> shape);

		/** 设置Layout */
		XIR_DLL TensorType& setLayout(Layout layout);

		/** 设置维度分布 */
		XIR_DLL TensorType& setMergedDistrs(Array<MergedAxisDistr> merged_distrs);

		/**
		 * @brief 创建并添加维度分布, 默认融合分布所有元素全有效
		 * @param merged_axis		维度索引列表
		 * @return					创建的维度分布
		 * @throw 如果相应维度的分布已经存在则抛出异常
		 */
		XIR_DLL MergedAxisDistr createAddMergedDistr(Array<int64_t> merged_axis);

		/**
		 * @brief 获取融合维度的分布
		 * @param merged_axis		维度索引列表
		 * @return					指定融合维度的分布，如果不存在则返回NullOpt
		 */
		XIR_DLL Optional<MergedAxisDistr> getMergedDistr(const Array<int64_t>& merged_axis) const;

		/**
		 * @brief 获取融合维度的分布的下标
		 * @param merged_axis		维度索引列表
		 * @return					指定融合维度的分布的下标，如果不存在则返回std::nullopt
		 */
		XIR_DLL std::optional<int64_t> getMergedDistrIndex(const Array<int64_t>& merged_axis) const;

		/**
		 * @brief 调节指定分布
		 * @param merged_axis		维度索引列表
		 * @param start				范围开始(包含)
		 * @param end				范围结束(不包含)
		 * @param value				值
		 * @return					自身
		 */
		XIR_DLL TensorType& mutateMergedDistr(const Array<int64_t>& merged_axis, int64_t start, int64_t end, bool value);

		/** 检查是否有维度的尺寸是负的 */
		XIR_DLL bool hasNegativeDim() const;

		/** 判断是否是Layout后的张量数据类型 */
		XIR_DLL bool isLayouted() const;

		/** 获取通道数 */
		XIR_DLL int64_t getChannel() const;

		/** 验证TensorType是否符合规范 */
		XIR_DLL void validate() const;

	private:
		int64_t getNoneNuminDim(int64_t axis) const;
	};


	/* ---- 以下数据类型量化相关 ----*/


	/** 表示基本的量化类型 */
	class BaseQuantizedTypeNode : public NodeBase<BaseQuantizedTypeNode, ScalarTypeNode> {
	public:
		ScalarType storage_dtype;		///< 存储类型，即量化的目标类型
		ScalarType expressed_dtype;		///< 表达类型，即数据的原始类型

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(BaseQuantizedTypeNode* other, const ReduceVisitor& reduce) const;
	};


	/** 基本量化类型的引用类 */
	class BaseQuantizedType : public HandleBase<BaseQuantizedType, ScalarType, BaseQuantizedTypeNode> {};


	/** 表示校准后的数据类型 */
	class CalibratedTypeNode : public NodeBase<CalibratedTypeNode, BaseQuantizedTypeNode> {
	public:
		Array<float> min;		///< 统计的最小值
		Array<float> max;		///< 统计的最大值
		Array<float> sat;		///< 统计的饱和点

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(CalibratedTypeNode* other, const ReduceVisitor& reduce) const;

		/** 获取数据总的bits */
		XIR_DLL virtual uint64_t bits() const override;
	};


	/** 校准后的数据类型的引用类 */
	class CalibratedType : public HandleBase<CalibratedType, BaseQuantizedType, CalibratedTypeNode> {
	public:
		/** 默认构造函数 */
		CalibratedType() = default;

		/**
		 * @brief 构造函数
		 * @param min				统计最小值
		 * @param max				统计最大值
		 * @param sat				统计饱和点
		 * @param storage_dtype		存储类型，即量化的目标类型
		 * @param expressed_dtype	表达类型，即数据的原始类型
		 */
		XIR_DLL CalibratedType(float min, float max, float sat, ScalarType storage_dtype, ScalarType expressed_dtype = FloatType::FP32());

		/**
		 * @brief 构造函数
		 * @param min				统计最小值
		 * @param max				统计最大值
		 * @param sat				统计饱和点
		 * @param storage_dtype		存储类型，即量化的目标类型
		 * @param expressed_dtype	表达类型，即数据的原始类型
		 */
		XIR_DLL CalibratedType(Array<float> min, Array<float> max, Array<float> sat, ScalarType storage_dtype, ScalarType expressed_dtype = FloatType::FP32());

		/**
		 * @brief 构造函数.
		 * @param storage_dtype		存储类型，即量化的目标类型
		 * @param expressed_dtype	表达类型，即数据的原始类型
		 */
		XIR_DLL CalibratedType(ScalarType storage_dtype, ScalarType expressed_dtype = FloatType::FP32())
			: CalibratedType(Array<float>(), Array<float>(), Array<float>(), std::move(storage_dtype), std::move(expressed_dtype)) {}
	};


	/** 表示归一化后的数据类型 */
	class NormalizedTypeNode : public NodeBase<NormalizedTypeNode, BaseQuantizedTypeNode> {
	public:
		NormratioArray normratio;		///< 归一化系数

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(NormalizedTypeNode* other, const ReduceVisitor& reduce) const;

		/** 获取数据总的bits */
		XIR_DLL virtual uint64_t bits() const override;
	};


	/** 归一化后数据类型的引用类 */
	class NormalizedType : public HandleBase<NormalizedType, BaseQuantizedType, NormalizedTypeNode> {
	public:
		/** 默认构造函数 */
		NormalizedType() = default;

		/**
		 * @brief 构造函数
		 * @param normratio			归一化系数
		 * @param storage_dtype		存储类型，即量化的目标类型
		 * @param expressed_dtype	表达类型，即数据的原始类型
		 */
		XIR_DLL NormalizedType(Array<float> normratio, ScalarType storage_dtype, ScalarType expressed_dtype = FloatType::FP32());

		/**
		 * @brief 构造函数.
		 * @param normratio			归一化系数
		 * @param storage_dtype		存储类型，即量化的目标类型
		 * @param expressed_dtype	表达类型，即数据的原始类型
		 */
		XIR_DLL NormalizedType(NormratioArray normratio, ScalarType storage_dtype, ScalarType expressed_dtype = FloatType::FP32());
	};


	/** 表示量化后的数据类型 */
	class QuantizedTypeNode : public NodeBase<QuantizedTypeNode, BaseQuantizedTypeNode> {
	public:
		QuantizedScaleArray scale;		///< 量化的缩放因子
		Array<int64_t> zero_points;		///< 量化的零点

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(QuantizedTypeNode* other, const ReduceVisitor& reduce) const;

		/** 获取数据总的bits */
		XIR_DLL virtual uint64_t bits() const override;
	};


	/** 表示量化后的数据类型的引用类 */
	class QuantizedType : public HandleBase<QuantizedType, BaseQuantizedType, QuantizedTypeNode> {
	public:
		/** 默认构造函数 */
		QuantizedType() = default;

		/**
		 * @brief 构造函数
		 * @param scale				量化的缩放因子
		 * @param storage_dtype		存储类型，即量化的目标类型
		 * @param expressed_dtype	表达类型，即数据的原始类型
		 */
		XIR_DLL QuantizedType(QuantizedScaleArray scale, ScalarType storage_dtype, ScalarType expressed_dtype = FloatType::FP32());

		/**
		 * @brief 构造函数
		 * @param scale				量化的缩放因子
		 * @param zero_points		量化的零点
		 * @param storage_dtype		存储类型，即量化的目标类型
		 * @param expressed_dtype	表达类型，即数据的原始类型
		 */
		XIR_DLL QuantizedType(
			QuantizedScaleArray scale,
			Array<int64_t> zero_points,
			ScalarType storage_dtype,
			ScalarType expressed_dtype = FloatType::FP32()
		);
	};


	/** 表示采用归一化的量化类型 */
	class NormalizedQuantizedTypeNode : public NodeBase<NormalizedQuantizedTypeNode, QuantizedTypeNode> {
	public:
		NormratioArray normratio;		///< 归一化系数

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(NormalizedQuantizedTypeNode* other, const ReduceVisitor& reduce) const;
	};


	/** 表示采用归一化的量化类型的引用类 */
	class NormalizedQuantizedType : public HandleBase<NormalizedQuantizedType, QuantizedType, NormalizedQuantizedTypeNode> {
	public:
		/** 默认构造函数 */
		NormalizedQuantizedType() = default;

		/**
		 * @brief 构造函数（兼容性接口，默认axis = -1）
		 * @param normratio			归一化系数
		 * @param scale				量化的缩放因子
		 * @param storage_dtype		存储类型，即量化的目标类型
		 * @param expressed_dtype	表达类型，即数据的原始类型
		 */
		XIR_DLL NormalizedQuantizedType(Array<float> normratio, QuantizedScaleArray scale,
			ScalarType storage_dtype, ScalarType expressed_dtype = FloatType::FP32());

		/**
		 * @brief 构造函数.
		 * @param normratio			归一化系数
		 * @param scale				量化的缩放因子
		 * @param storage_dtype		存储类型，即量化的目标类型
		 * @param expressed_dtype	表达类型，即数据的原始类型
		 */
		XIR_DLL NormalizedQuantizedType(NormratioArray normratio, QuantizedScaleArray scale,
			ScalarType storage_dtype, ScalarType expressed_dtype = FloatType::FP32());

		/**
		 * @brief 构造函数
		 * @param nomalized			归一化类型的对象
		 * @param scale				量化的缩放因子
		 */
		XIR_DLL NormalizedQuantizedType(NormalizedType nomalized, QuantizedScaleArray scale);

		/** 转换为NomalizedType类型 */
		XIR_DLL operator NormalizedType();
	};
}
