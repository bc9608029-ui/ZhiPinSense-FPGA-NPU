#pragma once
#include <icraft-xir/base/array.h>
#include <icraft-xir/base/dllexport.h>
#include <icraft-xir/base/type_trait.h>
#include <icraft-xir/core/node.h>
#include <icraft-xir/core/functor.h>
#include <icraft-xir/utils/wise_enum.h>

#include <cstdint>
#include <string>


namespace icraft::xir {

	/**
	 * @brief 表示属性访问者的类型
	 *		  AttrVisitor中实现了对所有类型的访问，访问某个Node的属性会根据类型匹配相应的方法
	 */
	class AttrVisitor {
	private:
		virtual void _visit(std::string_view key, float& value) = 0;
		virtual void _visit(std::string_view key, int64_t& value) = 0;
		virtual void _visit(std::string_view key, uint64_t& value) = 0;
		virtual void _visit(std::string_view key, int& value) = 0;
		virtual void _visit(std::string_view key, bool& value) = 0;
		virtual void _visit(std::string_view key, std::string& value, std::string_view tinfo = "") = 0;
		virtual void _visit(std::string_view key, ObjectRef& value, std::string_view tinfo = TypeName<ObjectRef>()) = 0;

	public:
		template<typename E>
		void visit(std::string_view key, E& value) {
			if constexpr (std::is_base_of_v<ObjectRef, E>) {
				this->_visit(key, value, TypeName<E>());
			}
			else {
				this->_visit(key, value);
			}
		}


		template <typename  Enum, typename = typename std::enable_if_t<std::is_enum_v<Enum>>>
		void _visit(std::string_view key, Enum& value) {

			auto enum_name = std::string(wise_enum::to_string(value));
			this->_visit(key, enum_name, TypeName<Enum>());



			auto v = wise_enum::from_string<Enum>(enum_name.c_str());

			// 检查：
			ICRAFT_CHECK(v.has_value())
				.append("can't cast {}", enum_name);

			value = v.value();
		}

		virtual ~AttrVisitor() = default;
	};


	class Context;


	/** 归约访问，用于实现相等和复制的访问者类型 */
	class ReduceVisitor {
	public:
		virtual const Context& getContext() const = 0;
		virtual bool operator()(const float& lhs, float& rhs) const = 0;
		virtual bool operator()(const int64_t& lhs, int64_t& rhs) const = 0;
		virtual	bool operator()(const uint64_t& lhs, uint64_t& rhs) const = 0;
		virtual	bool operator()(const int& lhs, int& rhs) const = 0;
		virtual bool operator()(const bool& lhs, bool& rhs) const = 0;
		virtual bool operator()(const std::string& lhs, std::string& rhs) const = 0;
		virtual bool operator()(const ObjectRef& lhs, ObjectRef& rhs) const = 0;

		template <typename ENum, typename = typename std::enable_if_t<std::is_enum_v<ENum>>>
		bool operator()(const ENum& lhs, ENum& rhs) const {
			return  operator()(reinterpret_cast<const int&>(lhs), reinterpret_cast<int&>(rhs));
		}

		virtual ~ReduceVisitor() = default;

		mutable int64_t clone_depth = 1;
	};


	class OperationNode;
	class TensorType;
	class Pass;


	/**
	 * @brief IR中反射机制所实现的虚函数表
	 *        该表中注册了Node的创建、序列化和反序列方法，以及算子的TypeInfer方法
	 */
	class ReflectionTable {
	public:
		using FDefaultCreate = std::function<ObjectPtr<Node>()>;
		using FReprCreate = std::function<ObjectPtr<Node>(const std::string&)>;
		using FRepr = std::function<std::string(const Object*)>;
		using FTypeInfer = std::function<Array<TensorType>(const OperationNode*)>;

		/**
		 * @brief 根据类型字符串来创建一个空Node
		 * @param type_key 类型字符串
		 * @return 所创建Node的智能指针
		 */
		XIR_DLL ObjectPtr<Node> createInitObject(std::string_view type_key) const;

		/**
		 * @brief 根据序列化字符串来创建一个Node
		 * @param repr_bytes 表达Node类型和内容的序列化字符串
		 * @return 所创建Node的智能指针
		 */
		XIR_DLL ObjectPtr<Node> createReprObject(const std::string& repr_bytes) const;

		/**
		 * @brief 获取某个Node的序列化字符串
		 * @param self 某个Node自身
		 * @return 表示该Node的序列化字符串
		 */
		XIR_DLL std::string getReprBytes(const Node* self) const;

		/**
		 * @brief 检查指定的Node是否注册了序列化方法
		 * @param self 某个Node自身
		 * @return 如果注册了则返回true
		 */
		XIR_DLL bool hasReprOf(const Node* self) const;

		/**
		 * @brief 检查指定的Node是否注册了默认构造方法
		 * @param type_key 某个Node自身
		 * @return 如果注册了则返回true
		 */
		XIR_DLL bool hasDefaultCreatorOf(const std::string& type_key) const;

		/**
		 * @brief 调用指定OpNode的TypeInfer方法
		 * @param self 某个OpNode自身
		 * @return 调用TypeInfer方法后得到的输出类型
		 */
		XIR_DLL Array<TensorType> typeInfer(const OperationNode* self) const;

		/**
		 * @brief 检查指定的OpNode是否注册TypeInfer方法
		 * @param self 某个OpNode自身
		 * @return 如果注册了则返回true
		 */
		XIR_DLL bool hasTypeInfer(const OperationNode* self) const;

		/** 获取虚函数表的全局单例 */
		XIR_DLL static ReflectionTable& Global();

		class Registry;

		/// @cond
		/**
		 * @brief 注册某个类型
		 * @tparam T 被注册的类型
		 */
		template <typename T>
		inline Registry _register();

		/* ---- 以下方法只用于开发调试 ---- */
		XIR_DLL const std::unordered_map<std::string_view, FDefaultCreate>& _getDefaultCreateTable() const;
		XIR_DLL const std::unordered_map<std::string_view, FReprCreate>& _getReprCreateTable() const;
		XIR_DLL const std::unordered_map<std::string_view, FRepr>& _getReprTable() const;
		XIR_DLL const std::unordered_map<std::string_view, std::string_view>& _getAliasTable() const;
		XIR_DLL const std::unordered_map<std::string_view, std::string_view>& _getParentTable() const;
		XIR_DLL const std::unordered_map<std::string_view, std::vector<std::string_view>>& _getChildTable() const;
		XIR_DLL const std::unordered_map<
			std::string_view,
			std::unordered_map<std::string_view, FTypeInfer>
		>& _getTInferTable() const;
		/// @endcond

	private:
		std::unordered_map<std::string_view, FDefaultCreate> fdefault_create_;
		std::unordered_map<std::string_view, FReprCreate> frepr_create_;
		std::unordered_map<std::string_view, FRepr> frepr_;
		std::unordered_map<std::string_view, std::string_view> alias_;
		std::unordered_map<std::string_view, std::string_view> parent_table_;
		std::unordered_map<std::string_view, std::vector<std::string_view>> child_table_;
		std::unordered_map<
			std::string_view,
			std::unordered_map<std::string_view, FTypeInfer>
		> ftinfer_;
	};


	/** 虚函数表的注册类 */
	class ReflectionTable::Registry {
	public:
		/**
		 * @brief 构造函数
		 * @param parent 所属的虚函数表
		 * @param type_key 被注册的类型字符串
		 */
		Registry(ReflectionTable* parent, std::string_view type_key, std::string_view parent_type_key)
			: parent_(parent), type_key_(type_key), parent_type_key_(parent_type_key) {}

		/**
		 * @brief 注册创建函数
		 * @tparam TNode 被注册的类型
		 * @param f 该类型的创建函数
		 */
		template <typename TNode>
		Registry& set_creator(std::function<ObjectPtr<TNode>(const std::string&)> f) {

			auto fcreate = [=](const std::string& repr_bytes) {
				ObjectPtr<Node> node = f(repr_bytes);
				return node;
			};

			parent_->frepr_create_[type_key_] = fcreate;

			return *this;
		}

		/**
		 * @brief 注册默认创建函数
		 * @tparam TNode 被注册的类型
		 * @param f 该类型的默认创建函数
		 */
		template <typename TNode>
		Registry& set_default_creator(std::function<ObjectPtr<TNode>()> f) {

			auto fcreate = [=]() {
				ObjectPtr<Node> node = f();
				return node;
			};

			parent_->fdefault_create_[type_key_] = fcreate;
			parent_->parent_table_[type_key_] = parent_type_key_;

			// 如果是空的，新建一个
			if (parent_->child_table_.find(parent_type_key_) == parent_->child_table_.end()) {
				parent_->child_table_[parent_type_key_] = { type_key_ };
			}
			else {
				parent_->child_table_[parent_type_key_].push_back(type_key_);
			}

			return *this;
		}

		/**
		 * @brief 注册序列化函数
		 * @tparam TNode 被注册的类型
		 * @param f 该类型的序列化函数
		 */
		template <typename TNode>
		Registry& set_repr(std::function<std::string(const TNode*)> f) {  // NOLINT(*)

			auto frepr = [=](const Object* object) {
				auto node = static_cast<const TNode*>(object);
				return f(node);
			};

			parent_->frepr_[type_key_] = frepr;

			return *this;
		}

		/**
		 * @brief 注册别名
		 *        为某个类型注册别名后，就可以可以使用别名反射到该类型
		 * @param alias_name 被注册的别名
		 */
		XIR_DLL Registry& set_alias(std::string_view alias_name);

		/**
		 * @brief 注册TypeInfer函数
		 * @tparam TOpNode 被注册的算子
		 * @tparam TTarget 被注册的编译目标类型
		 * @param f 该类型和编译目标的类型推断函数
		 */
		template <typename TOpNode, typename TTarget>
		Registry& set_tinfer(std::function<Array<TensorType>(const TOpNode*)> f) {

			auto target = TTarget::NodeType::type_key;
			auto ftinter = [=](const OperationNode* op) {
				auto op_node = static_cast<const TOpNode*>(op);
				return f(op_node);
			};

			parent_->ftinfer_[type_key_][target] = ftinter;

			return *this;
		}

	private:
		ReflectionTable* parent_;
		std::string_view type_key_;
		std::string_view parent_type_key_;
	};

	template <typename T>
	inline ReflectionTable::Registry ReflectionTable::_register() {

		std::string_view type_key = T::type_key;
		std::string_view parent_type_key = T::ParentNode::type_key;

		return Registry(this, type_key, parent_type_key);
	}


	/** 获取指定Handle的序列化字符串 */
	XIR_DLL std::string GetReprBytes(const Handle& ref);


	/** 检查指定Handle是否注册了序列化方法 */
	XIR_DLL bool HasReprOf(const Handle& ref);


	class Pass;


	/** Pass的注册辅助类型 */
	class PassRegistry {
	public:
		class Manager;

		/** Pass创建函数的原型 */
		using FCreator = std::function<Pass()>;

		/** 设置Pass创建函数 */
		XIR_DLL PassRegistry& set_creator(FCreator f);

		/**
		 * @brief 注册Pass
		 * @param name			Pass的名字
		 * @param can_override	是否允许覆盖, 默认为否
		 */
		XIR_DLL static PassRegistry& Register(const std::string& name, bool can_override = false);

		/**
		 * @brief 注册Pass
		 * @param f				Pass创建函数
		 * @param can_override	是否允许覆盖, 默认为否
		 */
		XIR_DLL static PassRegistry& Register(FCreator f, bool can_override = false);

		/**
		 * @brief 移除注册的Pass
		 * @param name	Pass的名字
		 * @return 如果Pass不存在返回false, 否则返回true
		 */
		XIR_DLL static bool Remove(const std::string& name);

		/**
		 * @brief 获取注册的Pass
		 * @param name	Pass的名字
		 * @return Pass创建函数的Optional
		 */
		XIR_DLL static std::optional<FCreator> Get(const std::string& name);

		/** 获取所有注册Pass的名称列表 */
		XIR_DLL std::vector<std::string_view> ListNames();

	private:
		std::string name_;
		FCreator fcreator_;
	};
}


/** 注册表生成宏 */
#define ICRAFT_REFLECTION_REG_VAR_DEF														\
static ICRAFT_ATTRIBUTE_UNUSED ::icraft::xir::ReflectionTable::Registry __make_reflection


/** 注册类型辅助宏 */
#define ICRAFT_REGISTER_REFLECTION_VTABLE(TypeName)											\
 ICRAFT_STR_CONCAT(ICRAFT_REFLECTION_REG_VAR_DEF, __COUNTER__) =							\
      ::icraft::xir::ReflectionTable::Global()._register<TypeName>()


/** 注册Node辅助宏, 该宏注册的Node会有一个默认的创建函数 */
#define ICRAFT_REGISTER_NODE(NodeName)														\
ICRAFT_REGISTER_REFLECTION_VTABLE(NodeName)													\
    .set_default_creator<NodeName>([]() {													\
		return ::icraft::xir::make_object<NodeName>();										\
    })


/** Pass注册生成宏 */
#define ICRAFT_PASS_REG_VAR_DEF																\
static ICRAFT_ATTRIBUTE_UNUSED ::icraft::xir::PassRegistry __make_pass


/** Pass注册辅助宏 */
#define ICRAFT_REGISTER_PASS(FuncName)														\
 ICRAFT_STR_CONCAT(ICRAFT_PASS_REG_VAR_DEF, __COUNTER__) =									\
      ::icraft::xir::PassRegistry::Register(FuncName)
