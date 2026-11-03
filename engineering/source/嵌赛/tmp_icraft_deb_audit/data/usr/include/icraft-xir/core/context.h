#pragma once
#include <unordered_map>
#include <icraft-xir/core/node.h>
#include <icraft-xir/core/reflection.h>


namespace icraft::xir {

	/** 表示替换函数的类型 */
	using OverriveFunc = std::function<bool(const Node*, Node*, const ReduceVisitor&)>;


	class ContextNode : public NodeBase<ContextNode, Node> {
	public:
		std::unordered_map<std::string_view, OverriveFunc> overrive_func_map;		///< 该上下文的替换函数表

		virtual void accept(AttrVisitor& visitor) override {}
	};


	class Context : public HandleBase<Context, Handle, ContextNode> {
	public:
		/** 默认构造函数 */
		Context() = default;

		/**
		 * @brief 为上下文添加替换函数
		 * @tparam T	类型
		 * @param func	该类型的替换函数
		 * @return 自身
		 */
		template <typename T>
		Context& setFunction(std::function<bool(const T*, T*, const ReduceVisitor&)> func) {

			if (func) {
				auto wrapped_func = [=](const Node* lhs, Node* rhs, const ReduceVisitor& reduce) {
					return func(static_cast<const T*>(lhs), static_cast<T*>(rhs), reduce);
				};

				get_mutable()->overrive_func_map[T::type_key] = wrapped_func;
			}
			else {
				get_mutable()->overrive_func_map[T::type_key] = nullptr;
			}

			return *this;
		}

		/**
		 * @brief 获取当前上下文的替换函数
		 * @tparam T	类型
		 * @return		该类型的替换函数
		 */
		template <typename T>
		OverriveFunc getFunction() const {
			return getFunction<T::type_key>();
		}

		OverriveFunc getFunction(std::string_view key) const {

			if ((*this)->overrive_func_map.count(key)) {
				return (*this)->overrive_func_map.at(key);
			}

			return nullptr;
		}
	};


	/** 表示Clone上下文的类型 */
	class CloneContextNode : public NodeBase<CloneContextNode, ContextNode> {
	public:
		virtual void accept(AttrVisitor& visitor) override {};

		inline static std::unordered_map<std::string_view, OverriveFunc> default_overrive_func_map;
	};

	/** 表示Clone上下文的引用类 */
	class CloneContext : public HandleBase<CloneContext, Context, CloneContextNode> {
	public:
		/** 默认构造函数 */
		XIR_DLL CloneContext();

		/** 获取一个初始化的上下文*/
		XIR_DLL static CloneContext Init();

		/** 获取当前作用域下的上下文 */
		XIR_DLL static CloneContext& Current();

		XIR_DLL void _enterWithScope();
		XIR_DLL void _exitWithScope();
	};


	/** 表示Equal上下文的类型 */
	class EqualContextNode : public NodeBase<EqualContextNode, ContextNode> {
	public:
		virtual void accept(AttrVisitor& visitor) override {};

		inline static std::unordered_map<std::string_view, OverriveFunc> default_overrive_func_map;
	};

	/** 表示Equal上下文的引用类 */
	class EqualContext : public HandleBase<EqualContext, Context, EqualContextNode> {
	public:
		/** 默认构造函数 */
		XIR_DLL EqualContext();

		/** 获取一个初始化的上下文*/
		XIR_DLL static EqualContext Init();

		/** 获取当前作用域下的上下文 */
		XIR_DLL static EqualContext& Current();

		XIR_DLL void _enterWithScope();
		XIR_DLL void _exitWithScope();
	};

	template <typename T, typename U>
	bool OverideFunction(std::function<bool(const T*, T*, const ReduceVisitor&)> func) {

		auto wrapped_func = [=](const Node* lhs, Node* rhs, const ReduceVisitor& reduce) {
			return func(static_cast<const T*>(lhs), static_cast<T*>(rhs), reduce);
		};

		U::default_overrive_func_map[T::type_key] = wrapped_func;
		return true;
	}
}


#define ICRAFT_OVERRIDE_EQUAL(T)															\
	 ICRAFT_STR_CONCAT(static auto equal, __COUNTER__) = icraft::xir::OverideFunction<T, icraft::xir::EqualContextNode>


#define ICRAFT_OVERRIDE_CLONE(T)															\
	 ICRAFT_STR_CONCAT(static auto clone, __COUNTER__) = icraft::xir::OverideFunction<T, icraft::xir::CloneContextNode>
