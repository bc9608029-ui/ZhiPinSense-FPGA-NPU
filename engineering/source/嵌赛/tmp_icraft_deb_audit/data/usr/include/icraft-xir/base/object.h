#pragma once
#include <atomic>
#include <string>
#include <string_view>
#include <icraft-xir/base/dllexport.h>


namespace icraft::xir {

	/** 万物之基类 */
	class Object {
	public:
		/** 默认构造函数 */
		Object() = default;

		/** 复制构造函数 */
		Object(const Object& other) {}

		/** 复制赋值函数 */
		Object& operator=(const Object& other) noexcept { return *this; }

		/** 移动赋值函数 */
		Object& operator=(Object&& other) noexcept { return *this; }

		/**
		 * @brief 检查是否是TargetType的实例
		 * @tparam TargetType 目标类型
		 * @return 如果是则返回true
		 */
		template <typename TargetType>
		inline bool isInstance() const {
			if (std::is_same_v<TargetType, Object>) {
				return true;
			}
			else {
				return dynamic_cast<const TargetType*>(this);
			}
		}

		/**
		 * @brief 获取对象的type_key
		 * @return 对象的type_key
		 */
		virtual std::string_view typeKey() const { return type_key; }

		bool isArray() const { return this->typeKey() == "ArrayNode"; }

		/** 默认析构函数 */
		virtual ~Object() = default;

		static constexpr std::string_view type_key = "Object";

	protected:
		/// @cond
		inline void incref() {
			++count_;
		}

		inline void decref() {
			if ((--count_) == 0) {
				delete this;
			}
		}
		/// @endcond
	private:
		std::atomic<int> count_{0};

		template <class>
		friend class ObjectPtr;
	};


	/**
	 * @brief Object的(侵入式)智能指针类
	 * @tparam T 指向的数据类型
	 */
	template <class T>
	class ObjectPtr {
	public:
		/** 默认构造函数(空指针) */
		ObjectPtr() = default;

		/** 构造函数，从nullptr构造 */
		ObjectPtr(std::nullptr_t) {}

		/** 复制构造函数 */
		ObjectPtr(const ObjectPtr<T>& other) : ObjectPtr(other.data_,other.no_ref_count_) {}

		/** 移动构造函数 */
		ObjectPtr(ObjectPtr<T>&& other) : data_(other.data_),no_ref_count_(other.no_ref_count_) {
			other.data_ = nullptr;
		}

		/** 复制构造函数：从其他类型的指针复制构造 */
		template <typename U>
		ObjectPtr(const ObjectPtr<U>& other) : ObjectPtr(other.data_) {
			static_assert(std::is_base_of_v<T, U>,
				"can only assign of child class ObjectPtr to parent");
		}

		/** 移动构造函数：从其他类型的指针移动构造 */
		template <typename U>
		ObjectPtr(ObjectPtr<U>&& other) : data_(other.data_),no_ref_count_(other.no_ref_count_) {
			static_assert(std::is_base_of_v<T, U>,
				"can only assign of child class ObjectPtr to parent");
			other.data_ = nullptr;
		}

		/** 复制赋值函数 */
		ObjectPtr<T>& operator=(const ObjectPtr<T>& other) {
			ObjectPtr(other).swap(*this);
			return *this;
		}

		/** 移动赋值函数 */
		ObjectPtr<T>& operator=(ObjectPtr<T>&& other) {
			ObjectPtr(std::move(other)).swap(*this);
			return *this;
		}

		/** 清除指向实例为nullptr */
		void reset() {
			if (data_ && !no_ref_count_) { data_->decref(); }
			data_ = nullptr;
		}

		/**
		 * @brief 检查是否为nullptr
		 * @return 如果为nullptr则返回true
		 */
		explicit operator bool() const { return get() != nullptr; }

		/** 和其他指针交换指向的实例 */
		void swap(ObjectPtr<T>& other) { std::swap(data_, other.data_); }

		/** 获取指向实例的指针 */
		T* get() const { return static_cast<T*>(data_); }

		/** 重载指针运算符 */
		T* operator->() const { return get(); }

		/** 重载解引用运算符 */
		T& operator*() const { return *get(); }

		/** 获取引用计数 */
		int use_count() const { return data_ != nullptr ? (int)data_->count_ : 0; }

		/**
		 * @brief 检查引用是否唯一
		 * @return 如果唯一则返回true
		 */
		bool unique() const { return data_ != nullptr && data_->count_ == 1; }

		/** 重载等于运算符 */
		bool operator==(const ObjectPtr<T>& other) const { return data_ == other.data_; }

		/** 重载不等于运算符 */
		bool operator!=(const ObjectPtr<T>& other) const { return data_ != other.data_; }

		/** 重载等于运算符, 检查是否为nullptr */
		bool operator==(std::nullptr_t null) const { return data_ == nullptr; }

		/** 重载不等于运算符, 检查是否不为nullptr */
		bool operator!=(std::nullptr_t null) const { return data_ != nullptr; }

		/** 析构函数 */
		~ObjectPtr() { this->reset(); }

	private:
		Object* data_{ nullptr };
		bool no_ref_count_=false;

		explicit ObjectPtr(Object* data, bool noRefCnt=false) : data_(data),no_ref_count_(noRefCnt) {
			if (data_ && !no_ref_count_) {
				data_->incref();
			}
		}

		friend class Object;
		friend class ObjectRef;
		friend struct ObjectPtrHash;
		template <typename>
		friend class ObjectPtr;
		template <typename RelayRefType, typename ObjType>
		friend RelayRefType GetRef(const ObjType* ptr, bool noRefCnt);
		template <typename RelayRefType, typename ObjType>
		friend RelayRefType GetRef(const ObjType* ptr);
		template <typename BaseType, typename ObjType>
		friend ObjectPtr<BaseType> GetObjectPtr(ObjType* ptr);
		template <typename U, typename... Args>
		friend ObjectPtr<U> make_object(Args&&... args);
	};


	/** 表示Object的引用的基类 */
	class ObjectRef {
	public:
		/** 默认构造函数(空引用) */
		ObjectRef() = default;

		/**
		 * @brief 构造函数
		 * 从ObjectPtr<Object>构造
		 */
		explicit ObjectRef(ObjectPtr<Object> data) : data_(data) {}

		/** 重载等于运算符 */
		XIR_DLL bool operator==(const ObjectRef& other) const;

		/** 重载不等于运算符 */
		XIR_DLL bool operator!=(const ObjectRef& other) const;

		XIR_DLL ObjectRef clone(int64_t depth = 1) const;

		/**
		 * @brief 比较引用的实例是否相同
		 * @return 相同则返回true
		 */
		XIR_DLL bool same_as(const ObjectRef& other) const;

		/** 重载(地址)小于运算符 */
		XIR_DLL bool operator<(const ObjectRef& other) const;

		/**
		 * @brief 检查引用的实例是否存在
		 * @return 存在则返回true
		 */
		XIR_DLL bool defined() const;

		/** 获取内部对象的指针 */
		XIR_DLL const Object* get() const;

		/** 获取内部对象的指针 */
		XIR_DLL const Object* operator->() const;

		/**
		 * @brief 判断引用是否唯一
		 * @return 唯一则返回true
		 */
		XIR_DLL bool unique() const;

		/** 获取引用计数 */
		XIR_DLL int use_count() const;

		/** 获取对象的字符串表示 */
		XIR_DLL std::string toString() const;

		/**
		 * @brief 将内部对象向下转换为指定类型的裸指针
		 * @tparam ObjectType 目标类型
		 * @return 转换后的指针，转换失败则返回nullptr
		 */
		template <typename ObjectType>
		inline const ObjectType* as() const {
			if (data_ != nullptr && data_->isInstance<ObjectType>()) {
				return static_cast<const ObjectType*>(data_.get());
			}
			else {
				return nullptr;
			}
		}

		/// @cond
		template <typename ObjectType>
		inline ObjectType* as_mutable() const {
			if (data_ != nullptr && data_->isInstance<ObjectType>()) {
				return static_cast<ObjectType*>(data_.get());
			}
			else {
				return nullptr;
			}
		}
		/// @endcond

		using NodeType = Object;

		/**
		 * @brief 从给定的对象指针获取一个ObjectRef实例
		 * @param data 指定的对象指针
		 * @return 获得的ObjectRef实例
		 */
		static ObjectRef Get(ObjectPtr<Object> data) { return ObjectRef(data); }

	protected:
		/// @cond
		/**
		 * @brief 获取一个可更改的内部对象的裸指针
		 * 主要用于子类
		 */
		Object* get_mutable() const { return data_.get(); }

		/** 获取内部对象的智能指针 */
		template <typename ObjectType>
		static ObjectPtr<ObjectType> GetDataPtr(const ObjectRef& ref) {
			return ObjectPtr<ObjectType>(ref.data_.data_);
		}

		/**
		 * @brief 将一个ObjectRef不做类型检查地向下转换
		 * @tparam T 目标类型
		 * @return 目标类型的实例
		 */
		template <typename T>
		static T DowncastNoCheck(ObjectRef ref) {
			return T::Get(std::move(ref.data_));
		}

		ObjectPtr<Object> data_;

		friend struct ObjectPtrHash;
		template <typename SubRef, typename BaseRef>
		friend SubRef Downcast(BaseRef ref);
		friend class ReduceVisitor;
		/// @endcond
	};


	/**
	 * @brief 在堆上分配一个对象
	 * @tparam T 对象的目标类型
	 * @tparam Args 构造函数的参数类型
	 * @param args 构造函数的参数
	 * @return 分配所得对象的智能指针
	 */
	template <typename T, typename... Args>
	inline ObjectPtr<T> make_object(Args&&... args) {
		T* ptr = new T(std::forward<Args>(args)...);
		return ObjectPtr<T>(ptr);
	}


	/**
	 * @brief 获取裸指针的ObjectPtr
	 * @tparam BaseType 目标类型
	 * @tparam ObjType 裸指针类型
	 * @param ptr 裸指针
	 * @return 目标类型的ObjectPtr
	 */
	template <typename BaseType, typename ObjType>
	inline ObjectPtr<BaseType> GetObjectPtr(ObjType* ptr) {
		static_assert(std::is_base_of_v<BaseType, ObjType>,
			"Can only cast to the ref of same container type");
		return ObjectPtr<BaseType>(static_cast<Object*>(ptr));
	}


	/**
	 * @brief 获取裸指针的ObjectRef
	 * @tparam BaseType 目标类型
	 * @tparam ObjType 裸指针类型
	 * @param ptr 裸指针
	 * @param noRefCnt 是否不进行引用计数的增减
	 * @note 当noRefCnt为false时，调用GetRef会自动将引用计数+1，
	 * 返回的ObjectRef析构时则自动-1。若noRefCnt为true则不对引用计数增减。
	 * @return 目标类型的ObjectRef
	 */
	template <typename RefType, typename ObjType>
	inline RefType GetRef(const ObjType* ptr, bool noRefCnt) {
		static_assert(std::is_base_of_v<typename RefType::NodeType, ObjType>,
			"Can only cast to the ref of same container type");
		return RefType::Get(ObjectPtr<Object>(const_cast<Object*>(static_cast<const Object*>(ptr)),noRefCnt));
	}


	template <typename RefType, typename ObjType>
	inline RefType GetRef(const ObjType* ptr) {
		static_assert(std::is_base_of_v<typename RefType::NodeType, ObjType>,
			"Can only cast to the ref of same container type");
		return RefType::Get(ObjectPtr<Object>(const_cast<Object*>(static_cast<const Object*>(ptr)),false));
	}


	/// @cond
	/** ObjectRef hash 仿函数 */
	struct ObjectPtrHash {
		size_t operator()(const ObjectRef& a) const { return operator()(a.data_); }

		template <typename T>
		size_t operator()(const ObjectPtr<T>& a) const {
			return std::hash<Object*>()(a.get());
		}
	};


	/** ObjectRef equal 仿函数 */
	struct ObjectPtrEqual {
		bool operator()(const ObjectRef& a, const ObjectRef& b) const { return a.same_as(b); }

		template <typename T>
		size_t operator()(const ObjectPtr<T>& a, const ObjectPtr<T>& b) const {
			return a == b;
		}
	};


	/** 基于字符串的ObjectRef hash仿函数 */
	struct ObjectHash {
		size_t operator()(const ObjectRef& a) const;
	};


	/** 基于字符串的ObjectRef equal仿函数 */
	struct ObjectEqual {
		bool operator()(const ObjectRef& a, const ObjectRef& b) const;
	};
	/// @endcond


	/**
	 * @brief 将一个基类的引用向下转换为子类引用
	 * @tparam SubRef 目标子类引用类型
	 * @tparam BaseRef 基类的引用类型
	 * @param ref 被转换的基类引用
	 * @return 转换后的子类引用
	 */
	template <typename SubRef, typename BaseRef>
	inline SubRef Downcast(BaseRef ref) {
		if (ref.defined()) {
			if (ref->template isInstance<typename SubRef::NodeType>()) {
				return SubRef::Get(std::move(ref.data_));
			}
		}

		return SubRef::Get(nullptr);
	}
}


/// @cond
#if defined(__GNUC__) || defined(__IAR_SYSTEMS_ICC__)
#define ICRAFT_ATTRIBUTE_UNUSED __attribute__((unused))
#else
#define ICRAFT_ATTRIBUTE_UNUSED
#endif


#define ICRAFT_STR(x) #x
#define ICRAFT_STR_CONCAT_(__x, __y) __x##__y
#define ICRAFT_STR_CONCAT(__x, __y) ICRAFT_STR_CONCAT_(__x, __y)
/// @endcond
