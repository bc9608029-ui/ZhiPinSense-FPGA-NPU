#pragma once
#include <map>
#include <set>
#include <icraft-xir/base/map.h>
#include <icraft-xir/base/string.h>
#include <icraft-xir/core/attrs.h>
#include <icraft-xir/core/data.h>
#include <icraft-xir/core/compile_target.h>
#include <icraft-utils/midware/path.hpp>


#define ICRAFT_DECLARE_ATTRS(TypeKey)                   \
  template <typename FVisit>                            \
  void _accept(FVisit& _fvisit)


#define ICRAFT_ATTR_FIELD(FieldName) _fvisit(#FieldName, FieldName)


namespace icraft::xir {

	class NetworkNode;
	class Network;


	/** 表示IR中算子的类型 */
	class OperationNode : public NodeBase<OperationNode, Node> {
	public:
		int64_t op_id = -1;				///< 算子的ID
		std::string name;				///< 算子的名字
		Array<Value> inputs;			///< 算子的输入列表
		Array<Value> outputs;			///< 算子的输出列表
		CompileTarget compile_target;	///< 算子的编译目标
		Map<String, ObjectRef> tags;	///< 一些标记

	private:
		std::map<int64_t, std::set<int64_t>> inputs_index_map_;				///< 输入快查表：value_id, value_index

		const NetworkNode* network = nullptr;

		friend class Operation;
		template <typename, template <typename> typename...>
		friend class OpNodeBase;

	public:
		virtual void accept(AttrVisitor& visitor) override {}

		bool reduceAccept(OperationNode* other, const ReduceVisitor& reduce) const { 

			// 克隆时考虑，但判断相等时不考虑
			for (auto&& [k, v] : this->inputs_index_map_) {
				other->inputs_index_map_[k] = v;
			}

			return reduce(this->op_id, other->op_id)
				&& reduce(this->name, other->name)
				&& reduce(this->inputs, other->inputs)
				&& reduce(this->outputs, other->outputs)
				&& reduce(this->compile_target, other->compile_target)
				&& reduce(this->tags, other->tags);
		}
		/**
		 * @brief 检查算子中某个属性是否存在
		 * @param key 属性的字符串名称
		 * @param value 属性的值
		 * @return 如果存在则返回true
		 */
		virtual bool hasAttr(const std::string& key, const Any& value = Any()) const { return true; };

		/**
		 * @brief 获取算子中的某个属性
		 * @param key 属性的字符串名称
		 * @return Any表示的属性
		 */
		virtual Any getAttr(const std::string& key) const { return 0; };

		/**
		 * @brief 获取算子中所有属性的哈希表
		 * @return 所有属性
		 */
		#ifndef _BAREME
		virtual std::map<std::string_view, Any> attrs() const { return {}; };
		#endif
		
		/**
		 * @brief 获取算子中所有Params属性的列表
		 * @param is_defined	是否必须defined，默认不需要
		 * @return 所有Params属性
		 */
		virtual Array<Params> paramsAttrs(bool is_defined = false) const { return {}; };

		/**
		 * @brief 设置算子中某个属性的值
		 * @param key 属性的字符串名称
		 * @param value Any表示的属性
		 * @throw 如果属性不存在则抛出异常
		 */
		virtual void setAttr(const std::string& key, Any value) {};

		/**
		 * @brief 根据属性的哈希表设置属性值
		 * @param attrs 属性哈希表
		 * @throw 如果属性不存在则抛出异常
		 */
		virtual void setAttrs(const std::unordered_map<std::string_view, Any>& attrs) {};

		/** 获取算子中的属性信息列表 */
		virtual Array<AttrFieldInfo> listFieldInfo() const { return {}; };

		/**
		 * @brief 检查算子的属性是否都满足边界条件
		 * @throw 任意属性不满足边界条件则抛出异常
		 */
		virtual void checkBound() const {};

		/**
		 * @brief 检查算子的属性是否都不为空
		 * @throw 任意属性为空则抛出异常
		 */
		virtual void checkNull() const {};

		/** 验证算子是否符合规范 */
		XIR_DLL virtual void validate() const;

		/** 检查该算子是否是激活算子 */
		virtual bool isActivate() const { return false; }

		/** 析构函数 */
		virtual ~OperationNode() noexcept {}

	protected:
		ICRAFT_DECLARE_ATTRS(OperationNode) {
			_fvisit("op_id", op_id);
			_fvisit("name", name);
			_fvisit("inputs", inputs);
			_fvisit("outputs", outputs);
			_fvisit("compile_target", compile_target);
			_fvisit("tags", tags);
		}
	};


	/** 表示IR中算子的引用类 */
	class Operation : public VirtualBase<Operation, Handle, OperationNode> {
	public:
		/** 获取算子非Params的输入列表 */
		XIR_DLL Array<Value> nonParamsInputs() const;

		/** 获取算子Params的输入列表 */
		XIR_DLL Array<Params> paramsInputs() const;

		/**
		 * @brief 获取算子索引指定的输出
		 * @param index 索引（支持负数索引）
		 * @return 索引指定的输出
		 * @throw 如果索引值不小于输出的数量，则抛出异常
		 */
		XIR_DLL Value operator[](int64_t index) const;

		/**
		 * @brief 设置算子的编译目标
		 * @param	target	编译目标
		 * @return 自身
		 */
		XIR_DLL Operation& setCompileTarget(CompileTarget target);

		/**
		 * @brief 设置算子的标签
		 * @param	key		标签的键
		 * @param	value	标签的值
		 * @return 自身
		 */
		XIR_DLL Operation& setTag(const std::string& key, ObjectRef value);

		/**
		 * @brief 获取算子的标签
		 * @param	key		标签的建
		 * @return 标签的值（可选）
		 */
		XIR_DLL std::optional<ObjectRef> getTag(const std::string& key) const;

		/**
		 * @brief 删除算子的标签
		 * @param	key		标签的建
		 * @return 如果标签存在则返回true，否则返回false
		 */
		XIR_DLL bool removeTag(const std::string& key);

		/**
		 * @brief 给算子添加输入
		 * @param v 被添加的输入
		 * @return 自身
		 */
		XIR_DLL Operation& addInput(Value v);

		/**
		 * @brief 移除算子指定ID的输入
		 * @param v_id 输入的ID
		 * @return 自身
		 */
		XIR_DLL Operation& removeInputById(int64_t v_id);

		/**
		 * @brief 设置算子索引指定位置的值
		 * @param index 索引（支持负数索引）
		 * @param v 指定的输入值
		 * @return　自身
		 */
		XIR_DLL Operation& setInput(int64_t index, Value v);

		/**
		 * @brief 插入输入
		 * @param index		插入输入后的索引，比如输入为空时应指定index为0
		 * @param v			指定的输入值
		 * @return　自身
		 */
		XIR_DLL Operation& insertInput(int64_t index, Value v);

		/**
		 * @brief 替换输入
		 * @param old_input 老的输入
		 * @param new_input 新的输入
		 * @return　自身
		 */
		XIR_DLL Operation& replaceInput(Value old_input, Value new_input);

		/**
		 * @brief 连接输入, 将v作为Op的第index个输入
		 * @param index 索引
		 * @param v	被连接的输入Value
		 */
		XIR_DLL void connectInput(int64_t index, const Value& v);

		/**
		 * @brief 设置算子的输入序列
		 * @param inputs 指定的输入序列
		 * @return　自身
		 */
		XIR_DLL Operation& setInputs(Array<Value> inputs);

		/** 清除算子所有的输入 */
		XIR_DLL Operation& clearInputs();

		/**
		 * @brief 获取输入的索引，即v是Op的第几个输入
		 * @param v			指定的输入Value
		 * @param v_id		指定的输入Value的ID
		 * @return 输入的索引
		 * @throw  如果v不是Op的任何输入则抛出异常
		 */
		XIR_DLL std::set<int64_t> getInputIndex(const Value& v) const;
		XIR_DLL std::set<int64_t> getInputIndex(int64_t v_id) const;

		/**
		 * @brief 推断算子的输出类型，并获取输出
		 *		  该方法调用算子注册的TypeInfer函数来推断输出的类型
		 * @param	override		是否覆盖已有输出，默认为否，如果已有输出则不再推断
		 * @return	算子输出列表的const引用
		 * @throw 如果没有注册TypeInfer函数，则抛出异常
		 */
		XIR_DLL const Array<Value>& inferResults(bool override = false) const;

		/**
		 * @brief 根据指定的输出类型列表，获取算子的输出
		 * @param	dtypes			输出的数据类型列表
		 * @param	override		是否覆盖已有输出，默认为否，如果已有输出则不再推断
		 * @return	算子输出列表的const引用
		 */
		XIR_DLL const Array<Value>& inferResults(const Array<TensorType>& dtypes, bool override = false) const;

		/** 设置算子的输出 */
		XIR_DLL Operation& setOutputs(Array<Value> outputs);

		/**
		 * @brief 设置算子索引指定位置输出的值
		 * @param index 索引（支持负数索引）
		 * @param v 指定的输出值
		 * @return　自身
		 */
		XIR_DLL Operation& setOutput(int64_t index, Value v);

		/**
		 * @brief 设置算子的名字
		 * @param name 算子的名字
		 * @return 自身
		 */
		XIR_DLL Operation& setName(std::string name);

		/**
		 * @brief 设置算子的ID
		 * @param op_id 指定的ID
		 * @return 自身
		 */
		XIR_DLL Operation& setId(int64_t op_id);

		/**
		 * @brief 将算子绑定到指定的网络
		 * @param network 算子的名字
		 * @return 自身
		 */
		XIR_DLL Operation& bindNetwork(const Network& network);

		/** 检查算子是否绑定到了网络 */
		XIR_DLL bool isBoundToNetwork() const;

		/**
		 * @brief 获取算子绑定的网络
		 * @return 算子绑定的网络
		 */
		XIR_DLL Network network() const;

		/**
		 * @brief 获取该算子在其绑定的网络中的执行序
		 * @return 该算子在其绑定的网络中的执行序
		 * @throw 如果没有绑定到某个网络过，则抛出异常
		 */
		XIR_DLL uint64_t index() const;

		/** 获取算子执行序的上一个算子 */
		XIR_DLL Operation preOp() const;

		/** 获取算子执行序的下一个算子 */
		XIR_DLL Operation nextOp() const;

		/** 检查算子是否是所在网络中的第一个算子 */
		XIR_DLL bool isFirstOpOfNetwork() const;

		/** 检查算子是否是所在网络中的最后一个算子 */
		XIR_DLL bool isLastOpOfNetwork() const;

		/**
		 * @brief 获取算子的生产者算子列表
		 * @param sorted 是否按执行序排序
		 * @return 该算子的生产者算子列表
		 */
		XIR_DLL Array<Operation> producers(bool sorted = false) const;

		/**
		 * @brief 获取算子的消费者算子列表
		 * @param sorted 是否按执行序排序
		 * @return 该算子的消费者算子列表
		 */
		XIR_DLL Array<Operation> consumers(bool sorted = false) const;

		/**
		 * @brief 根据名字创建算子
		 * @param name		算子的名字
		 * @param dll_file	算子所在DLL路径(可选)
		 * @return 创建所得算子实例
		 */
#if !defined(_BAREME)
		XIR_DLL static Operation Create(const std::string& name, const std::filesystem::path& dll_file = {});
#endif
		XIR_DLL static Operation Create(const std::string& name, const icraft::midware::path& dll_file = {});
		/**
		 * @brief 设置算子中某个属性的值
		 * @param key 属性的字符串名称
		 * @param value Any表示的属性
		 * @throw 如果属性不存在则抛出异常
		 */
		XIR_DLL void setAttr(const std::string& key, Any value);

	private:
		/** 清空算子的输入使用信息 */
		void unRefPreValues();

		/** 重新记录算子的输入使用信息 */
		void reRefCurValues();

		/**
		 * @brief 修改输入快查表中项的key
		 * @param old_id 旧value_id
		 * @param new_id 新value_id
		 */
		void changeInputIndex(int64_t old_id, int64_t new_id);
		void setInputIndex(int64_t index, int64_t new_id);
		void setInputIndex(std::set<int64_t> index, int64_t new_id);

		/**
		 * @brief 从输入快查表删除项
		 * @param v_id	键：value_id
		 */
		void removeInputIndex(int64_t v_id);

		/** 清空输入快查表 */
		void clearInputIndex();

		friend class Value;
		friend class Network;
	};


	/**
	 * @brief 声明用于Op的Trait的CRTP辅助类
	 * @tparam OpType 算子的类型
	 */
	template <typename OpType>
	class OpTrait {};


	/** 标记算子是激活算子 */
	template <typename OpType>
	class IsActivate : public OpTrait<OpType> {};


	/**
	 * @brief 声明算子的CRTP辅助模板类
	 * @tparam ConcreteType 具体的算子类型
	 */
	template <typename ConcreteType, template <typename> typename... Traits>
	class OpNodeBase : public NodeBase<ConcreteType, OperationNode>, public Traits<ConcreteType>... {
	public:
		using ParentNode = OperationNode;

		/** 默认构造函数 */
		OpNodeBase() {

			auto visitor = AttrInitVisitor(ConcreteType::type_key);
			self()->_accept(visitor);
			this->compile_target = HostTarget::Init();
		}

		virtual void accept(AttrVisitor& v) override {

			AttrNormalVisitor visitor(v);
			self()->_accept(visitor);
			this->_accept(visitor);
		}

		bool reduceAccept(ConcreteType* other, const ReduceVisitor& reduce) const {

			auto map_visitor = AttrPtrMapVisitor();
			other->_accept(map_visitor);
			auto visitor = AttrReduceVisitor(map_visitor._attrs, reduce);
			self()->_accept(visitor);

			return visitor.result;
		}

		/** @see OperationNode::hasAttr */
		virtual bool hasAttr(const std::string& key, const Any& value = Any()) const override {
			auto visitor = AttrExistVisitor{ key, value };
			self()->_accept(visitor);
			return visitor._exist;
		}

		/** @see OperationNode::getAttr */
		virtual Any getAttr(const std::string& key) const override {
			auto visitor = AttrGetVisitor{ key };
			self()->_accept(visitor);
			return visitor._value;
		}

		/** @see OperationNode::attrs */
		#ifndef _BAREME
		virtual std::map<std::string_view, Any> attrs() const {
			auto visitor = AttrMapVisitor();
			self()->_accept(visitor);
			return visitor._attrs;
		}
		#endif

		/** @see OperationNode::paramsAttrs */
		virtual Array<Params> paramsAttrs(bool is_defined = false) const {
			auto visitor = VAttrMapVisitor<Params>();
			self()->_accept(visitor);

			Array<Params> ans;

			for (auto&& [k, v] : visitor._attrs) {
				for (auto&& p : v) {
					if (is_defined == false || p.defined()) {
						ans.push_back(p);
					}
				}
			}

			return ans;
		}

		/** @see OperationNode::setAttr */
		virtual void setAttr(const std::string& key, Any value) override {
			auto visitor = AttrSetVisitor{ key, value };
			self()->_accept(visitor);

			// 检查：
			ICRAFT_CHECK(visitor._exist).append("attr key: {} does not exist!", key);
		}

		/** @see OperationNode::setAttr */
		virtual void setAttrs(const std::unordered_map<std::string_view, Any>& attrs) override {
			auto visitor = AttrCloneVisitor(attrs);
			self()->_accept(visitor);
		}

		/** @see OperationNode::listFieldInfo */
		virtual Array<AttrFieldInfo> listFieldInfo() const override {

			AttrDocVisitor visitor;
			self()->_accept(visitor);

			return visitor._fields;
		}

		/** @see OperationNode::checkBound */
		virtual void checkBound() const override {
			auto visitor = AttrBoundVisitor(ConcreteType::type_key);
			self()->_accept(visitor);
		}

		/** @see OperationNode::checkNull */
		virtual void checkNull() const override {
			auto visitor = AttrNullVisitor();
			self()->_accept(visitor);
		}

		/** 检查该Op类型是否混入了某OpTrait */
		template <typename T,
			typename = typename std::enable_if_t<std::is_base_of_v<OpTrait<ConcreteType>, T>>>
			constexpr static bool HasOpTrait() {

			return std::is_base_of_v<T, ConcreteType>;
		}

		/** @see OperationNode::isActivate */
		virtual bool isActivate() const override { using ActivateTrait = IsActivate<ConcreteType>; return HasOpTrait<ActivateTrait>(); }


	private:
		/** 获取算子自身的指针 */
		ConcreteType* self() const {
			return const_cast<ConcreteType*>(static_cast<const ConcreteType*>(this));
		}
	};


	/**
	 * @brief 声明算子引用的CRTP辅助模板类
	 * @tparam OpType 算子引用类型
	 * @tparam OpNodeType 算子Node类型
	 */
	template <typename OpType, typename OpNodeType>
	class OpBase : public HandleBase<OpType, Operation, OpNodeType> {
	public:
		using HandleBase<OpType, Operation, OpNodeType>::get_mutable;
	};
}


/** 用于注册算子的宏 */
#define ICRAFT_REGISTER_OP_NODE(OpNodeName)													\
ICRAFT_REGISTER_NODE(OpNodeName)


/** 用于注册算子类型推断函数的宏 */
#define ICRAFT_REGISTER_TINFER(OpNodeName, TargetType, F)									\
ICRAFT_REGISTER_REFLECTION_VTABLE(OpNodeName).set_tinfer<OpNodeName, TargetType>(F);


namespace icraft::xir {

	/** 表示IR中输入算子 */
	class InputNode : public OpNodeBase<InputNode> {
	public:
		ICRAFT_DECLARE_ATTRS(InputNode) {}
	};


	/** 输入算子的引用 */
	class Input : public OpBase<Input, InputNode> {
	public:
		/** 默认构造函数 */
		Input() = default;

		/**
		 * @brief 构造函数，根据数据类型列表构造Input
		 *		  该方法会根据指定的数据类型创建Input的输出
		 * @param dtypes 数据类型列表
		 */
		XIR_DLL Input(const Array<TensorType>& dtypes);

		/**
		 * @brief 构造函数，根据数据类型列表构造Input
		 *		  该方法会根据指定的数据类型创建Input的输出
		 * @tparam Args 数据类型的类型，必须是TensorType或其子类
		 * @param dtypes 数据类型列表
		 */
		template <typename... Args,
			typename = typename std::enable_if_t<(std::is_base_of_v<TensorType, Args> && ...)>>
		Input(Args... dtypes) : Input(Array<TensorType>{ std::forward<Args>(dtypes)... }) {}
	};


	/** 表示IR中输出算子 */
	class OutputNode : public OpNodeBase<OutputNode> {
	public:
		ICRAFT_DECLARE_ATTRS(OutputNode) {}
	};


	/** 输出算子的引用 */
	class Output : public OpBase<Output, OutputNode> {
	public:
		/** 默认构造函数 */
		Output() = default;

		/**
		 * @brief 构造函数，根据Value列表构造Output
		 *		  该方法会将指定的Value列表作为Output的输入
		 * @param values Value列表
		 */
		XIR_DLL Output(Array<Value> values);

		/**
		 * @brief 构造函数，根据Value列表构造Output
		 *		  该方法会将指定的Value列表作为Output的输入
		 * @tparam Args 数据类型的类型
		 * @param values Value列表
		 */
		template <typename... Args>
		Output(Args... values) : Output(Array<Value>{ std::forward<Args>(values)... }) {}
	};
}
