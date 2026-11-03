#pragma once
#include <icraft-xir/base/dllexport.h>
#include <icraft-xir/base/object.h>
#include <icraft-xir/base/type_trait.h>

#include <string_view>


namespace icraft::xir {

	class ReduceVisitor;
	class AttrVisitor;


	/**
	 * @brief	Node类是IR中所有Data、Operation和Network等主要类型的子类
	 * @note	Node中实现了访问者模式，可以方便的访问子类的属性
	 *			即声明了accept方法，可以接受任意AttrVisitor的访问
	 *			因此每一个子类都要实现accept方法
	 *			如果一个类型需要使用访问者模式，请使用NodeBase从Node派生
	 */
	class Node : public Object {
	public:
		static constexpr std::string_view type_key = detail::n<Node>();

		/** 获取Node的类型字符串 */
		virtual std::string_view typeKey() const override {
			return type_key;
		}

		virtual void accept(AttrVisitor& visitor) = 0;

		virtual bool reduceAccept(Node* other, const ReduceVisitor& reduce) const = 0;
		virtual bool parentReduceAccept(Node* other, const ReduceVisitor& reduce) const = 0;
	};

	XIR_DLL bool ExecOverriveFunc(const Node* self, Node* other, const ReduceVisitor& reduce, std::string_view type_key, bool& ans);

	/**
	 * @brief 声明Node派生类的CRTP辅助模板类
	 * @tparam ConcreteNode 派生类的类型
	 * @tparam BaseNode 派生类父类的类型
	 */
	template <typename ConcreteNode, typename BaseNode>
	class NodeBase : public BaseNode {
	public:
		using ParentNode = BaseNode;

		static constexpr std::string_view type_key = detail::n<ConcreteNode>();

		virtual std::string_view typeKey() const override {
			return type_key;
		}

		bool reduceAccept(ConcreteNode* other, const ReduceVisitor& reduce) const {
			return true;
		}

		virtual bool reduceAccept(Node* other, const ReduceVisitor& reduce) const override {

			bool ans = true;

			if (ExecOverriveFunc(this, other, reduce, ConcreteNode::type_key, ans)) {
				return ans;
			}
			else {
				return static_cast<const ConcreteNode*>(this)->
					reduceAccept(static_cast<ConcreteNode*>(other), reduce);
			}
		}

		virtual bool parentReduceAccept(Node* other, const ReduceVisitor& reduce) const override {

			if constexpr (std::is_same_v<ParentNode, Node>) {
				return true;
			}
			else {
				bool parent_result = ParentNode::parentReduceAccept(static_cast<BaseNode*>(other), reduce);

				bool ans = true;

				if (ExecOverriveFunc(this, other, reduce, ParentNode::type_key, ans)) {
					return parent_result && ans;
				}
				else {
					return parent_result && static_cast<const ParentNode*>(this)->
						reduceAccept(static_cast<ParentNode*>(other), reduce);
				}
			}
		}
	};


	/**
	 * @brief 声明Handle派生类的CRTP辅助模板类
	 * @tparam ConcreteNode 派生类的类型
	 * @tparam BaseNode 派生类父类的类型
	 */
	template <typename ConcreteType, typename BaseType, typename NodeObject>
	class VirtualBase : public BaseType {
	public:
		using NodeType = NodeObject;

		/** 从ObjectPtr<Object>创建一个ConcreteType的对象 */
		static ConcreteType Get(ObjectPtr<Object> node) {
			auto handle = ConcreteType();
			handle.data_ = std::move(node);
			return handle;
		}

		/** 获取Node的const裸指针 */
		const NodeType* operator->() const { return static_cast<const NodeType*>(ObjectRef::get()); }

		/** 获取Node的const裸指针 */
		const NodeType* get() const { return operator->(); }

		/**
		 * @brief 检查该Handle对象是否是指定的子类
		 * @tparam ChildType 目标子类类型
		 */
		template <typename ChildType,
			typename = typename std::enable_if_t<std::is_base_of_v<ConcreteType, ChildType>>>
		bool is() const {
			return (*this)->template isInstance<typename ChildType::NodeType>();
		}

		/**
		 * @brief 将该Handle对象转换为指定的子类对象
		 * @tparam ChildType 目标子类类型
		 */
		template <typename ChildType,
			typename = typename std::enable_if_t<std::is_base_of_v<ConcreteType, ChildType>>>
		ChildType cast() const {
			return Downcast<ChildType>(*this);
		}

		/** 克隆一份该对象 */
		ConcreteType clone(int64_t depth = 1) const {
			return Downcast<ConcreteType>(ObjectRef::clone(depth));
		}

	protected:

		/** 获取Node的可更改指针，用于子类的实现 */
		NodeType* get_mutable() const { return static_cast<NodeType*>(ObjectRef::get_mutable()); }
	};


	/**
	 * @brief 声明Handle派生类的CRTP辅助模板类
	 * @tparam ConcreteType 派生类的类型
	 * @tparam BaseType 派生类父类的类型
	 * @tparam NodeObject 派生类对应的Node的类型
	 */
	template <typename ConcreteType, typename BaseType, typename NodeObject>
	class HandleBase : public VirtualBase<ConcreteType, BaseType, NodeObject> {
	public:
		/**
		 * @brief 创建一个初始化(非空)ConcreteType
		 *        默认的ConcreteType构造函数得到的ConcreteType对象为空
		 */
		static ConcreteType Init() {
			auto node = make_object<NodeObject>();
			return VirtualBase<ConcreteType, BaseType, NodeObject>::Get(std::move(node));
		}
	};


	/**
	 * @brief 声明MutableHandle派生类的CRTP辅助模板类.
	 *		  该类型和HandleBase的区别是可以调用get_mutable方法获取可更改的指针.
	 * @tparam ConcreteType 派生类的类型
	 * @tparam BaseType 派生类父类的类型
	 * @tparam NodeObject 派生类对应的Node的类型
	 */
	template <typename ConcreteType, typename BaseType, typename NodeObject>
	class MutableHandleBase : public VirtualBase<ConcreteType, BaseType, NodeObject> {
	public:
		/**
		 * @brief 创建一个初始化(非空)ConcreteType
		 *        默认的ConcreteType构造函数得到的ConcreteType对象为空
		 */
		static ConcreteType Init() {
			auto node = make_object<NodeObject>();
			return VirtualBase<ConcreteType, BaseType, NodeObject>::Get(std::move(node));
		}

		using VirtualBase<ConcreteType, BaseType, NodeObject>::get_mutable;
	};


	/** Handle类是Node类的引用类型 */
	class Handle : public VirtualBase<Handle, ObjectRef, Node> {};
}
