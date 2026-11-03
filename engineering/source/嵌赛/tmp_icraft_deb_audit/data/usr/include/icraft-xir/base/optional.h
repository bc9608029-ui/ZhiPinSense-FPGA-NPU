#pragma once
#include <optional>
#include <icraft-utils/logging.h>
#include <icraft-xir/base/object.h>


namespace icraft::xir{

	/** 表达Optional为空的类型  */
	struct NullOptType {};

	/**
	 * @brief Optional容器，表示一个可能为空的ObjectRef
	 * @tparam T 内部ObjectRef的类型
	 */
	template <typename T>
	class Optional : public ObjectRef {
	public:
		using ContainerType = typename T::NodeType;
		using NodeType = typename T::NodeType;
		static_assert(std::is_base_of_v<ObjectRef, T>, "Optional is only defined for ObjectRef");

		/** 默认构造函数 */
		Optional() = default;

		/** 从std::optional构造 */
		Optional(const std::optional<T>& opt) : ObjectRef(opt.value_or(T())) {}

		/** 默认复制构造函数 */
		Optional(const Optional<T>&) = default;

		/** 默认移动构造函数 */
		Optional(Optional<T>&&) = default;

		/** 默认复制赋值函数 */
		Optional<T>& operator=(const Optional<T>&) = default;

		/** 默认移动赋值函数 */
		Optional<T>& operator=(Optional<T>&&) = default;

		explicit Optional(ObjectPtr<Object> ptr) : ObjectRef(ptr) {}
		static Optional Get(ObjectPtr<Object> ptr) { return Optional(ptr); }

		/** 构造函数，从NullOpt构造 */
		Optional(NullOptType) {}

		/** 构造函数，从nullptr构造 */
		explicit Optional(std::nullptr_t) {}

		/** 赋值函数，处理nullptr */
		Optional<T>& operator=(std::nullptr_t) {
			data_ = nullptr;
			return *this;
		}

		/** 构造函数，从任意ObjectRef实例构造 */
		Optional(T other)
			: ObjectRef(std::move(other)) {}

		/** 赋值函数，任意ObjectRef实例的赋值 */
		Optional<T>& operator=(T other) {
			ObjectRef::operator=(std::move(other));
			return *this;
		}

		explicit Optional(int val) = delete;
		Optional<T>& operator=(int val) = delete;

		/**
		 * @return 返回Optional代表的非空值
		 * @throw 如果值为空则抛出异常
		 */
		T value() const {

			// 检查：
			ICRAFT_CHECK(data_ != nullptr);

			return T::Get(data_);
		}

		/** 获取Optional代表的值的裸指针 */
		const ContainerType* get() const { return static_cast<ContainerType*>(data_.get()); }

		/** 检查Optional是否有值 */
		bool has_value() const { return data_ != nullptr; }

		/** 转为std::optional */
		operator std::optional<T>() const { return has_value() ? std::optional<T>(value()) : std::nullopt; }

		/**
		 * @brief 获取内部对象或默认值
		 * @tparam T 对象的类型
		 * @param v 默认值
		 * @return 若有值则返回内部对象，否则返回默认值
		 */
		T value_or(T v) const { return data_ != nullptr ? T::Get(data_) : v; }

		/** 检查是否有值 */
		explicit operator bool() const { return *this != nullptr; }

		/** 重载等于操作符 */
		bool operator==(std::nullptr_t) const { return data_ == nullptr; }

		/** 重载不等操作符 */
		bool operator!=(std::nullptr_t) const { return data_ != nullptr; }

		/** 重载等于操作符 */
		auto operator==(const Optional<T>& other) const {
			using RetType = decltype(value() == other.value());
			if (same_as(other)) return RetType(true);
			if (*this != nullptr && other != nullptr) {
				return value() == other.value();
			}
			else {
				return RetType(false);
			}
		}

		/** 重载不等操作符 */
		auto operator!=(const Optional<T>& other) const {
			// support case where sub-class returns a symbolic ref type
			using RetType = decltype(value() != other.value());
			if (same_as(other)) return RetType(false);
			if (*this != nullptr && other != nullptr) {
				return value() != other.value();
			}
			else {
				return RetType(true);
			}
		}

		/** 重载等于操作符 */
		auto operator==(const T& other) const {
			using RetType = decltype(value() == other);
			if (same_as(other)) return RetType(true);
			if (*this != nullptr) return value() == other;
			return RetType(false);
		}

		/** 重载不等操作符 */
		auto operator!=(const T& other) const { return !(*this == other); }

		/** 重载等于操作符 */
		template <typename U>
		auto operator==(const U& other) const {
			using RetType = decltype(value() == other);
			if (*this == nullptr) return RetType(false);
			return value() == other;
		}

		/** 重载不等操作符 */
		template <typename U>
		auto operator!=(const U& other) const {
			using RetType = decltype(value() != other);
			if (*this == nullptr) return RetType(true);
			return value() != other;
		}
	};


	/** 表示Optional为空的实例 */
	constexpr NullOptType NullOpt{};


	/** 检查实例是否是optional类型，包括Optional和std::optional */
	template <typename T>
	constexpr bool is_optional(T const&) { return false; }


	/** 检查实例是否是optional类型，包括Optional和std::optional */
	template <typename T>
	constexpr bool is_optional(std::optional<T> const&) { return true; }


	/** 检查实例是否是optional类型，包括Optional和std::optional */
	template <typename T>
	constexpr bool is_optional(Optional<T> const&) { return true; }
}
