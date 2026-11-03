#pragma once
#include <icraft-xir/base/array.h>
#include <icraft-xir/base/map.h>
#include <icraft-xir/base/string.h>
#include <icraft-xir/core/data_type.h>
#include <icraft-xir/core/mem_type.h>


namespace icraft::xir {

	/** DataNode表示IR的数据 */
	class DataNode : public NodeBase<DataNode, Node> {
	public:
		DataType dtype;		///< 数据类型
		MemType mtype;		///< 存储类型

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(DataNode* other, const ReduceVisitor& reduce) const;

	private:
		/** 获取数据的存储bits */
		virtual uint64_t storageBits() const { return 0; };

		friend class Data;
	};


	/** 数据的引用类 */
	class Data : public VirtualBase<Data, Handle, DataNode> {
	public:
		/** 默认构造函数 */
		Data() = default;

		/** 设置数据类型 */
		XIR_DLL Data& setDType(DataType dtype);

		/** 设置存储类型 */
		XIR_DLL Data& setMType(MemType mtype);

		/** 获取存储位数 */
		XIR_DLL uint64_t storageBits() const;

		/** 获取存储字节数 */
		XIR_DLL uint64_t storageBytes() const;
	};


	/** 表示标量立即数 */
	class ScalarImmNode : public NodeBase<ScalarImmNode, DataNode> {
	public:
		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

	private:
		XIR_DLL virtual uint64_t storageBits() const override;
	};


	/** 标量立即数的引用类 */
	class ScalarImm : public HandleBase<ScalarImm, Data, ScalarImmNode> {
	public:
		/** 默认构造函数 */
		ScalarImm() = default;

		/** 构造函数，从int构造 */
		XIR_DLL ScalarImm(int64_t value);

		/** 构造函数，从float构造 */
		XIR_DLL ScalarImm(float value);

		/** 获取ScalarType类型的数据类型 */
		XIR_DLL ScalarType scalarType() const;
	};


	/** 表示布尔立即数 */
	class BoolNode : public NodeBase<BoolNode, ScalarImmNode> {
	public:
		bool value;		///< 立即数的值

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(BoolNode* other, const ReduceVisitor& reduce) const;
	};


	/** 表示布尔值的引用类 */
	class Bool : public HandleBase<Bool, ScalarImm, BoolNode> {
	public:
		/** 默认构造函数 */
		Bool() = default;

		/** 构造函数 */
		XIR_DLL Bool(bool value);

		/** 重载逻辑非操作符 */
		XIR_DLL Bool operator!() const;

		/** 类型转换为bool */
		XIR_DLL operator bool() const;
	};


	/** 重载逻辑或操作符 */
	inline Bool operator||(const Bool& a, bool b) { return Bool(a.operator bool() || b); }
	/** 重载逻辑或操作符 */
	inline Bool operator||(bool a, const Bool& b) { return Bool(a || b.operator bool()); }
	/** 重载逻辑或操作符 */
	inline Bool operator||(const Bool& a, const Bool& b) {
		return Bool(a.operator bool() || b.operator bool());
	}

	/** 重载逻辑与操作符 */
	inline Bool operator&&(const Bool& a, bool b) { return Bool(a.operator bool() && b); }
	/** 重载逻辑与操作符 */
	inline Bool operator&&(bool a, const Bool& b) { return Bool(a && b.operator bool()); }
	/** 重载逻辑与操作符 */
	inline Bool operator&&(const Bool& a, const Bool& b) {
		return Bool(a.operator bool() && b.operator bool());
	}

	/** 重载等于操作符 */
	inline bool operator==(const Bool& a, bool b) { return a.operator bool() == b; }
	/** 重载等于操作符 */
	inline bool operator==(bool a, const Bool& b) { return a == b.operator bool(); }
	/** 重载等于操作符 */
	inline bool operator==(const Bool& a, const Bool& b) {
		return a.operator bool() == b.operator bool();
	}


	/** 表示整型立即数 */
	class IntImmNode : public NodeBase<IntImmNode, ScalarImmNode> {
	public:
		int64_t value;		///< 立即数的值

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(IntImmNode* other, const ReduceVisitor& reduce) const;
	};


	/** 整型立即数的引用类 */
	class IntImm : public HandleBase<IntImm, ScalarImm, IntImmNode> {
	public:
		/** 默认构造函数 */
		IntImm() = default;

		/**
		 * @brief 构造函数
		 * @param value 立即数的值
		 * @param dtype 立即数的数据类型
		 * @param mtype 立即数的存储类型
		 */
		XIR_DLL IntImm(int64_t value, ScalarType dtype, MemType mtype = HostMem::Init());

		/**
		 * @brief 构造函数，默认类型为sint(64)
		 * @param value 立即数的值
		 * @param mtype 立即数的存储类型
		 */
		IntImm(int64_t value, MemType mtype = HostMem::Init()) : IntImm(value, IntegerType::SInt64(), mtype) {}

		/** 将整型立即数转换为int64_t */
		XIR_DLL operator int64_t() const;
	};


	/** 表示浮点立即数 */
	class FloatImmNode : public NodeBase<FloatImmNode, ScalarImmNode> {
	public:
		float value;		///< 立即数的值

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(FloatImmNode* other, const ReduceVisitor& reduce) const;
	};


	/** 浮点立即数的引用类 */
	class FloatImm : public HandleBase<FloatImm, ScalarImm, FloatImmNode> {
	public:
		/** 默认构造函数 */
		FloatImm() = default;

		/**
		 * @brief 构造函数
		 * @param value 立即数的值
		 * @param dtype 立即数的数据类型
		 * @param mtype 立即数的存储类型
		 */
		XIR_DLL FloatImm(float value, ScalarType dtype, MemType mtype = HostMem::Init());

		/**
		 * @brief 构造函数，默认类型为fp(64)
		 * @param value 立即数的值
		 * @param mtype 立即数的存储类型
		 */
		FloatImm(float value, MemType mtype = HostMem::Init()) : FloatImm(value, FloatType::FP64(), mtype) {}

		/** 将浮点立即数转换为float */
		XIR_DLL operator float() const;
	};


	class OperationNode;
	class Operation;
	class Network;


	/** 表示IR中算子的输入输出的数据 */
	class ValueNode : public NodeBase<ValueNode, DataNode> {
	public:
		int64_t v_id = -1;					///< 数据的ID
		std::string name;					///< 数据的名字

		Map<String, ObjectRef> tags;		///< 一些标记

		/// @cond
		uint64_t _index;
		const OperationNode* _op = nullptr;
		/// @endcond

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(ValueNode* other, const ReduceVisitor& reduce) const;

	private:
		XIR_DLL virtual uint64_t storageBits() const override;
	};


	/** IR中算子的输入输出的数据的引用类 */
	class Value : public HandleBase<Value, Data, ValueNode> {
	public:
		/** 默认构造函数 */
		Value() = default;

		/**
		 * @brief 构造函数
		 * @param name 数据名字
		 * @param dtype 数据类型
		 * @param mtype 存储类型
		 */
		XIR_DLL Value(std::string name, TensorType dtype, MemType mtype = HostMem::Init());

		/**
		 * @brief 构造函数(默认名字为空)
		 * @param dtype 数据类型
		 * @param mtype 存储类型
		 */
		Value(TensorType dtype, MemType mtype = HostMem::Init()) : Value("", dtype, mtype) {}

		/** 获取TensorType类型的数据类型 */
		XIR_DLL TensorType tensorType() const;

		/** 检查该数据是否是Params */
		XIR_DLL bool isParams() const;

		/**
		 * @brief 设置数据的ID
		 * @param v_id 被设置的ID
		 * @return 数据本身的引用
		 */
		XIR_DLL Value& setId(int64_t v_id);

		/**
		 * @brief 设置数据的名字
		 * @param name 数据名字
		 */
		XIR_DLL Value& setName(std::string name);

		/**
		 * @brief 设置数据的标签
		 * @param	key		标签的键
		 * @param	value	标签的值
		 * @return 自身
		 */
		XIR_DLL Value& setTag(const std::string& key, ObjectRef value);

		XIR_DLL Value& setTags(Map<String, ObjectRef> tags);

		/**
		 * @brief 获取数据的标签
		 * @param	key		标签的建
		 * @return 标签的值（可选）
		 */
		XIR_DLL std::optional<ObjectRef> getTag(const std::string& key) const;

		/**
		 * @brief 删除数据的标签
		 * @param	key		标签的建
		 * @return 如果标签存在则返回true，否则返回false
		 */
		XIR_DLL bool removeTag(const std::string& key);

		/**
		 * @brief 数据绑定Operation
		 * @param op 被绑定的Op
		 * @param index 索引
		 */
		XIR_DLL Value& bindOp(const Operation& op, uint64_t index);

		/** 检查数据是否被绑定到了Op，即该数据是Op产生的 */
		XIR_DLL bool isBoundToOp() const;

		/**
		 * @brief 获取该数据绑定的算子
		 * @return 该算子绑定的算子
		 * @throw 如果没有绑定到某个算子过，则抛出异常
		 */
		XIR_DLL Operation op() const;

		/**
		 * @brief 获取该数据在其绑定的算子中的顺序
		 * @return 该数据在其绑定的算子中的顺序
		 * @throw 如果没有绑定到某个算子过，则抛出异常
		 */
		XIR_DLL uint64_t index() const;

		/**
		 * @brief 检查数据是否被绑定到了网络
		 *		  如果数据绑定到了网络，说明数据绑定了Op且该Op被添加到了网络
		 */
		XIR_DLL bool isBoundToNetwork() const;

		/** 获取该数据绑定的网络 */
		XIR_DLL Network network() const;

		/** 获取使用该数据作为输入的Op列表 */
		XIR_DLL Array<Operation> getUsesOp() const;

		/** 获取该数据被使用的次数 */
		XIR_DLL size_t getUsesNum() const;

		/** 验证Value是否符合规范 */
		XIR_DLL void validate() const;

	protected:
		/// @cond
		XIR_DLL static int64_t genId();
		/// @endcond
	};

	class NetworkNode;

	/** 表示IR中参数的类型 */
	class ParamsNode : public NodeBase<ParamsNode, ValueNode> {
	public:
		/// @cond
		std::shared_ptr<void> _data = nullptr;
		bool _lazy = false;
		bool _allow_no_data = false;
		const NetworkNode* network = nullptr;
		/// @endcond

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(ParamsNode* other, const ReduceVisitor& reduce) const;
	};


	/** IR中参数的引用类 */
	class Params : public HandleBase<Params, Value, ParamsNode> {
	public:
		/** 默认构造函数 */
		Params() = default;

		/**
		 * @brief 构造函数
		 * @tparam T 参数内部存储的数据类型，必须是POD
		 * @param data POD数据的指针
		 * @param name 参数的名字
		 * @param dtype 参数的数据类型
		 * @param mtype 参数的存储类型
		 */
		template <typename T, typename = typename std::enable_if_t<std::is_pod_v<T>>>
		Params(std::shared_ptr<T[]> data, std::string name, TensorType dtype, MemType mtype = HostMem::Init()) {

			auto node = make_object<ParamsNode>();

			node->_data = data;
			node->v_id = genId();
			node->name = std::move(name);
			node->dtype = std::move(dtype);
			node->mtype = std::move(mtype);

			data_ = std::move(node);
		}

		/**
		 * @brief 构造函数(默认数据为空)
		 * @param name 参数的名字
		 * @param dtype 参数的数据类型
		 * @param mtype 参数的存储类型
		 */
		Params(std::string name, TensorType dtype, MemType mtype = HostMem::Init())
			: Params(std::shared_ptr<char[]>(), std::move(name), std::move(dtype), std::move(mtype)) {}

		/**
		 * @brief 构造函数(默认数据和名字为空)
		 * @param dtype 参数的数据类型
		 */
		Params(TensorType dtype) : Params(std::shared_ptr<char[]>(), "", std::move(dtype)) {}

		/**
		 * @brief 设置参数的数据
		 * @tparam T 参数内部存储的数据类型，必须是POD
		 * @param data 被设置的数据指针
		 * @return 自身
		 */
		template <typename T, typename = typename std::enable_if_t<std::is_pod_v<T>>>
		Params& setData(std::shared_ptr<T[]> data) {
			get_mutable()->_data = data;
			return *this;
		}

		/**
		 * @brief 设置参数的数据
		 * @tparam T 参数内部存储的数据类型，必须是POD
		 * @param data 被设置的数据指针
		 * @return 自身
		 */
		template <typename T, typename = typename std::enable_if_t<std::is_pod_v<T>>>
		Params& setData(std::unique_ptr<T[]> data) {
			get_mutable()->_data = std::move(data);
			return *this;
		}

		/**
		 * @brief 设置参数的数据
		 * @param data 仅为了重载nullptr类型而存在
		 * @return 自身
		 */
		XIR_DLL Params& setData(nullptr_t data);

		/**
		 * @brief 复制别的数据作为参数数据
		 * @param data 被复制的数据指针
		 * @return 复制的数据量。如果data为空指针，返回0
		 */
		XIR_DLL uint64_t copyData(void* data);

		/**
		 * @brief 获取参数内部数据的const裸指针
		 * @tparam T 参数内部存储的数据类型，必须是POD
		 * @return 参数数据的指针
		 */
		template <typename T, typename = typename std::enable_if_t<std::is_pod_v<T>>>
		std::shared_ptr<T[]> data() const {
			return std::static_pointer_cast<T[]>((*this)->_data);
		}

		/** 清空参数的数据 */
		XIR_DLL Params& clearData();

		/** 设置标记该参数是被惰性加载的 */
		XIR_DLL Params& setLazy(bool lazy);

		/** 检查该参数是否是被惰性加载的 */
		XIR_DLL bool isLazyLoaded() const;

		/** 设置标记该参数是允许没有数据的 */
		XIR_DLL Params& setAllowNoData(bool allow_no_data);

		/** 检查该参数是否是允许没有数据的 */
		XIR_DLL bool isAllowNoData() const;

		XIR_DLL Params& bindNetwork(const Network& network);

		/**
		 * @brief 加载参数
		 * @note 如果该参数是被惰性加载的，那么load会将其加载到内存中
		 *		 如果该参数不是惰性加载的(即数据已在内存中)，那么load什么都不干
		 */
		XIR_DLL void load();

		/**
		 * @brief 填充数据
		 * @tparam	T	被填充数据的类型，必须是POD
		 * @param	f	数据的生成函数，以index作为参数返回对应的T
		 */
		template <typename T, typename = typename std::enable_if_t<std::is_pod_v<T>>>
		Params& fill(std::function<T(uint64_t)> f) {

			auto dtype = this->tensorType();
			auto etype = dtype->element_dtype;
			auto tbits = sizeof(T) * 8;
			auto sbits = (*this)->mtype->getStorageBits(etype.bits());

			// 检查：
			ICRAFT_CHECK(tbits == sbits)
				.append("sizeof(T) not match element_dtype, {} vs. {}", tbits, sbits);

			auto num_elements = dtype.numElements();
			auto filled_data = new T[num_elements];

			for (uint64_t i = 0; i < num_elements; i++) {
				filled_data[i] = f(i);
			}

			get_mutable()->_data = std::shared_ptr<T[]>(filled_data);

			return *this;
		}

		/** 检查参数是否包含数据 */
		XIR_DLL bool hasData() const;
	};
}
