#pragma once
#include <any>
#include <optional>
#include <icraft-utils/logging.h>
#include <icraft-xir/base/object.h>
#include <icraft-xir/base/type_trait.h>


namespace icraft::xir {

	/** 表达任意类型的Object */
	class AnyNode : public Object {
	public:
		using ContainerType = std::any;

		/** 获取所表达类型的字符串 */
		XIR_DLL std::string_view type_name() const;

		/**
		 * @brief 赋予具体的对象
		 * @tparam T 要赋予对象的类型
		 * @param v 要赋予对象的实例
		 */
		template <typename T>
		void emplace(T&& v) {
			data_ = v;
		}

		/**
		 * @brief 将内部对象转换到指定类型
		 * @tparam U 目标类型
		 * @return 转换后的实例
		 */
		template <typename U>
		U cast() {
			try {
				return std::any_cast<U>(data_);
			}
			catch (std::exception& e) {
				ICRAFT_LOG(EXCEPT).append("cast type mismatch, source type is {}, but target type is {}",
					type_name(), TypeName<U>());

				return std::any_cast<U>(data_);
			}
		}

		/**
		 * @brief 将内部对象转换到指定类型的Optional对象
		 * @tparam U 目标类型
		 * @return 转换后的实例的std::optional
		 */
		template <typename U>
		std::optional<U> cast_opt() {
			if (auto value = std::any_cast<U>(&data_)) {
				return *value;
			}
			return std::nullopt;
		}

		/** 检查是否有值 */
		XIR_DLL bool has_value() const;

	private:
		ContainerType data_;
		friend class Any;
	};


	/** 表达任意类型 */
	class Any : public ObjectRef {
	public:
		using NodeType = AnyNode;

		/** 默认构造函数 */
		XIR_DLL Any();

		/**
		 * @brief 构造函数, 从任意对象构造
		 * @tparam T 对象的类型
		 * @param v 对象的实例
		 */
		template <typename T>
		Any(T v) : Any() {
			getAnyNode()->emplace(std::move(v));
		}

		/**
		 * @brief 构造函数, 从std::any对象构造
		 * @param v 对象的实例
		 */
		XIR_DLL explicit Any(std::any v) : Any(){
			getAnyNode()->data_ = std::move(v);
		}

		/** 获取内部对象的类型名 */
		XIR_DLL std::string_view type_name() const;

		/**
		 * @brief 将内部对象转换到指定类型
		 * @tparam U 目标类型
		 * @return 转换后的实例
		 */
		template <typename U>
		U cast() const {
			return getAnyNode()->cast<U>();
		}

		template <typename U>
		U cast() {
			return getAnyNode()->cast<U>();
		}

		/**
		 * @brief 将内部对象转换到指定类型的Optional对象
		 * @tparam U 目标类型
		 * @return 转换后的实例的std::optional
		 */
		template <typename U>
		std::optional<U> cast_opt() const {
			return getAnyNode()->cast_opt<U>();
		}

		/** 检查是否有值 */
		XIR_DLL bool has_value() const;

		/**
		 * @brief 获取内部对象或默认值
		 * @tparam U 对象的类型
		 * @param v 默认值
		 * @return 若有值则返回内部对象，否则返回默认值
		 */
		template <typename U>
		U value_or(U v) const {
			if (has_value()) {
				return cast<U>();
			}
			else {
				return v;
			}
		}

	private:
		XIR_DLL AnyNode* getAnyNode() const;
	};
}


namespace std {
    template<>
    struct is_copy_constructible<icraft::xir::Any> : true_type {};

    template<>
    struct is_copy_assignable<icraft::xir::Any> : true_type {};
}

