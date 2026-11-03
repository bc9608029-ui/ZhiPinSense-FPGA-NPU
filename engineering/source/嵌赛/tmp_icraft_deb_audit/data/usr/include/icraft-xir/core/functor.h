#pragma once
#include <functional>
#include <unordered_map>
#include <icraft-utils/logging.h>


namespace icraft::xir {

	/// @cond
	template <typename FType>
	class NodeFunctor;
	/// @endcond


	/**
	 * @brief 用于根据函数的第一个参数进行动态分发的辅助模板类
	 *        利用NodeFunctor可以很方便的对不同的Node派生类进行接口方法的注册和分发
	 *        分发函数的原型为 R(H n, Args...)
	 * @tparam R        分发函数的返回值类型
	 * @tparam H        分发函数的第一个参数类型
	 * @tparam Args...  分发函数的其余参数的类型
	 */
	template <typename R, typename H, typename... Args>
	class NodeFunctor<R(H n, Args...)> {
	public:
		using FType = std::function<R(H n, Args... args)>;
		using result_type = R;

	private:
		using TSelf = NodeFunctor<R(H n, Args...)>;
		std::unordered_map<std::string_view, FType> func_;

	public:
		/**
		 * @brief 检查该functor是否能够分发指定的Handle
		 * @param n 被分发的Handle
		 */
		bool canDispatch(H n) const {
			auto type_key = n->typeKey();
			return func_.find(type_key) != func_.end() && func_.at(type_key) != nullptr;
		}

		/**
		 * @brief 调用该functor，对Handle n进行分发
		 * @param n 被分发的Handle
		 * @param args 函数额外的参数
		 * @return 函数调用的结果
		 */
		R operator()(H n, Args... args) const {
			if (!canDispatch(n)) {
				ICRAFT_LOG(EXCEPT) << "NodeFunctor calls un-registered function on type " << n->typeKey();
			}
			return func_.at(n->typeKey())(n, std::forward<Args>(args)...);
		}

		/**
		 * @brief 对TNode类型设置分发函数
		 * @tparam TNode 被分发的Handle类型
		 * @param f 被分发的函数
		 * @return 自身
		 */
		template <typename TNode>
		TSelf& setDispatch(std::function<R(H n, Args... args)> f) {  // NOLINT(*)
			auto type_key = TNode::NodeType::type_key;
			func_[type_key] = f;
			return *this;
		}

		/**
		 * @brief 对TNode类型清除分发函数
		 * @tparam TNode 被清除的Handle类型
		 * @return 自身
		 */
		template <typename TNode>
		TSelf& clearDispatch() {  // NOLINT(*)
			auto type_key = TNode::type_key;
			func_.erase(type_key);
			return *this;
		}

		/// @cond
		const std::unordered_map<std::string_view, FType>& _getFuncMap() const {
			return func_;
		}
		/// @endcond
	};


	/// @cond
	template <typename ConcreteType, typename HandleType, typename FType>
	class TraitFunctor;
	/// @endcond


	/**
	 * @brief 基于@ref NodeFunctor实现的trait辅助类
	 *        可以通过从TraitFunctor派生来定义一个trait接口，并使用Impl方法为HandleType添加实现
	 * @tparam ConcreteType trait接口本身的类型
	 * @tparam HandleType   trait接口的分发目标类型，分发函数的原型为R(const HandleType&, Args...)
	 */
	template <typename ConcreteType, typename HandleType, typename R, typename... Args>
	class TraitFunctor<ConcreteType, HandleType, R(const HandleType&, Args...)> {
	public:
		/** 默认复制构造函数 */
		TraitFunctor(const TraitFunctor&) = default;

		/** 默认移动构造函数 */
		TraitFunctor(TraitFunctor&&) = default;

		/** 默认复制赋值函数 */
		TraitFunctor& operator=(const TraitFunctor&) = default;

		/** 默认移动赋值函数 */
		TraitFunctor& operator=(TraitFunctor&&) = default;

		/**
		 * @brief 构造函数
		 * @param t HandleType的对象
		 */
		explicit TraitFunctor(HandleType t) : container(std::move(t)) {}

		using FunctorType = NodeFunctor<R(const HandleType&, Args...)>;

	private:
		HandleType container;

	public:
		/**
		 * @brief 为目标类型添加实现
		 * @tparam TNode 分发目标类型
		 * @param f 实现函数
		 */
		template <typename TNode>
		static bool Impl(std::function<R(const TNode& n, Args... args)> f) {
			auto func = [=](const HandleType& n, Args... args) -> R {
				auto& t = static_cast<const TNode&>(n);
				return f(t, std::forward<Args>(args)...);
			};
			Accessor::VTable().template setDispatch<TNode>(func);
			return true;
		}

		/** 检查某个对象是否有该trait接口的实现 */
		static bool HasImplOf(const HandleType& n) {
			return Accessor::VTable().canDispatch(n);
		}

		/** 检查对象是否有该trait接口的实现 */
		bool hasImpl() {
			return Accessor::VTable().canDispatch(container);
		}

		/** 调用对象的实现函数 */
		R operator()(Args... args) const {
			return Accessor::VTable()(container, std::forward<Args>(args)...);
		}

		/// @cond
		static const auto& _GetFuncMap() {
			return Accessor::VTable()._getFuncMap();
		}
		/// @endcond

	private:
		struct Accessor : ConcreteType {
			using ConcreteType::VTable;
		};
		static FunctorType& VTable() {
			static FunctorType vtable;
			return vtable;
		}
	};


	template <typename ConcreteType, typename FType>
	class OpTraitFunctor;


	class Operation;


	/**
	 * @brief Operation类型的trait接口类
	 *        其函数原型为R(const Operation& op, Args...)
	 */
	template <typename ConcreteType, typename R, typename... Args>
	class OpTraitFunctor<ConcreteType, R(const Operation& op, Args...)>
		: public TraitFunctor<ConcreteType, Operation, R(const Operation& op, Args...)> {
	public:
		using TParent = TraitFunctor<ConcreteType, Operation, R(const Operation& op, Args...)>;
		OpTraitFunctor(const OpTraitFunctor&) = default;
		OpTraitFunctor(OpTraitFunctor&&) = default;
		OpTraitFunctor& operator=(const OpTraitFunctor&) = default;
		OpTraitFunctor& operator=(OpTraitFunctor&&) = default;

		template <typename T>
		OpTraitFunctor(T t) : TParent(std::move(t)) {}
	};


/// @cond
#define ICRAFT_TRAIT_IMPL_VAR_DEF \
  static ICRAFT_ATTRIBUTE_UNUSED auto __make_functor_impl


#define ICRAFT_IMPL_FUNCTOR(FunctorType) \
ICRAFT_STR_CONCAT(ICRAFT_TRAIT_IMPL_VAR_DEF, __COUNTER__) = FunctorType::Impl
}
/// @endcond