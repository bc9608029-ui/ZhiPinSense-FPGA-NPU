#pragma once
#include <string>
#include <ostream>
#include <icraft-utils/logging.h>
#include <icraft-xir/base/object.h>


namespace icraft::xir {

	/** 表示字符串的Object */
	class StringNode : public Object {
	public:
		const char* data;		///< 字符数据
		uint64_t size;			///< 数据大小

	private:
		class FromStd;
		friend class String;
	};


	/** 字符串类 */
	class String : public ObjectRef {
	public:

		/** 默认构造函数(空字符串) */
		String() : String(std::string()) {}

		/**
		 * @brief 构造函数，从std::string构造
		 * @param other 被移动/复制的std::string实例
		 * @note 如果other是const引用，则会发生复制，如果是右值则会被移动
		 */
		String(std::string other);									// NOLINT(*)

		/**
		 * @brief 构造函数，从const char*构造
		 * @param other const char*表示的字符串
		 */
		String(const char* other) : String(std::string(other)) {}	// NOLINT(*)

		/** 构造函数，从nullptr构造 */
		String(std::nullptr_t) : ObjectRef(nullptr) {}				// NOLINT(*)

		/** 赋值函数，赋值std::string表示的字符串 */
		inline String& operator=(std::string other);

		/** 赋值函数，赋值const char*表示的字符串 */
		inline String& operator=(const char* other);

		/**
		 * @brief 和其他String对象做比较
		 * @param other 被比较的其他String对象
		 * @return 0，-1，1分别表示相等，小于和大于
		 */
		int compare(const String& other) const {
			return memncmp(data(), other.data(), size(), other.size());
		}

		/**
		 * @brief 和其他std::string对象做比较
		 * @param other 被比较的其他std::string对象
		 * @return 0，-1，1分别表示相等，小于和大于
		 */
		int compare(const std::string& other) const {
			return memncmp(data(), other.data(), size(), other.size());
		}

		/**
		 * @brief 和其他const char*字符串做比较
		 * @param other 被比较的其他const char*字符串
		 * @return 0，-1，1分别表示相等，小于和大于
		 */
		int compare(const char* other) const {
			return memncmp(data(), other, size(), std::strlen(other));
		}

		/** 获取字符串的const char*指针 */
		const char* c_str() const { return get()->data; }

		/** 获取字符串的大小 */
		size_t size() const {
			const auto* ptr = get();
			return ptr->size;
		}

		/** 获取字符串的大小 */
		size_t length() const { return size(); }

		/** 检查字符串是否为空 */
		bool empty() const { return size() == 0; }

		/**
		 * @brief 获取指定位置的字符
		 * @param index 索引（支持负数索引）
		 * @return 该位置的字符
		 * @throw 如果位置越界则抛出异常
		 */
		char at(int64_t index) const {

			// 检查：下标越界
			ICRAFT_CHECK(-(int64_t)size() <= index && index < (int64_t)size()).append("Index {} out of bounds {}",
				index, size());

			return data()[index];
		}

		/** 获取字符串的const char*指针 */
		const char* data() const { return get()->data; }

		/** 转换 String 到 std::string */
		operator std::string() const { return std::string{ get()->data, size() }; }

		/** 转换 String 到 std::string_view */
		operator std::string_view() const { return std::string_view{get()->data, size() }; }

		/**
		 * @brief 对字符串做哈希
		 * @param data 字符串的const char*指针
		 * @param size 字符串的大小
		 * @return 哈希结果
		 */
		static size_t HashBytes(const char* data, size_t size) {
			return std::hash<std::string_view>()(std::string_view(data, size));
		}

		const StringNode* operator->() const { return static_cast<const StringNode*>(ObjectRef::get()); }
		const StringNode* get() const { return operator->(); }

		using NodeType = StringNode;
		explicit String(ObjectPtr<Object> n) : ObjectRef(n) {}
		static String Get(ObjectPtr<Object> node) { return String(node); }

	private:
		/**
		 * @brief 比较两个字符序列
		 * @param lhs 被比较字符串之一的指针
		 * @param rhs 被比较字符串之二的指针
		 * @param lhs_count 被比较字符串之一的长度
		 * @param rhs_count 被比较字符串之二的长度
		 * @return 0，-1，1分别表示相等，小于和大于
		 */
		static int memncmp(const char* lhs, const char* rhs, size_t lhs_count, size_t rhs_count);

		/**
		 * @brief 拼接两个字符序列
		 * @param lhs 被拼接字符串之一的指针
		 * @param lhs_size 被拼接字符串之一的大小
		 * @param rhs 被拼接字符串之二的指针
		 * @param rhs_size 被拼接字符串之二的大小
		 * @return 拼接后的字符串序列
		 */
		static String Concat(const char* lhs, size_t lhs_size, const char* rhs, size_t rhs_size) {
			std::string ret(lhs, lhs_size);
			ret.append(rhs, rhs_size);
			return String(ret);
		}

		// 重载operator+
		friend String operator+(const String& lhs, const String& rhs);
		friend String operator+(const String& lhs, const std::string& rhs);
		friend String operator+(const std::string& lhs, const String& rhs);
		friend String operator+(const String& lhs, const char* rhs);
		friend String operator+(const char* lhs, const String& rhs);

		friend struct ObjectEqual;
	};


	/** 表示来自std::string的对象 */
	class StringNode::FromStd : public StringNode {
	public:
		/** 构造函数，从std::string构造 */
		explicit FromStd(std::string other) : data_container{ other } {}

	private:
		std::string data_container;

		friend class String;
	};


	inline String::String(std::string other) {
		auto ptr = make_object<StringNode::FromStd>(std::move(other));
		ptr->size = ptr->data_container.size();
		ptr->data = ptr->data_container.data();
		data_ = std::move(ptr);
	}


	inline String& String::operator=(std::string other) {
		String replace{ std::move(other) };
		data_.swap(replace.data_);
		return *this;
	}


	inline String& String::operator=(const char* other) { return operator=(std::string(other)); }


	/** 重载加号操作符 */
	inline String operator+(const String& lhs, const String& rhs) {
		size_t lhs_size = lhs.size();
		size_t rhs_size = rhs.size();
		return String::Concat(lhs.data(), lhs_size, rhs.data(), rhs_size);
	}

	/** 重载加号操作符 */
	inline String operator+(const String& lhs, const std::string& rhs) {
		size_t lhs_size = lhs.size();
		size_t rhs_size = rhs.size();
		return String::Concat(lhs.data(), lhs_size, rhs.data(), rhs_size);
	}

	/** 重载加号操作符 */
	inline String operator+(const std::string& lhs, const String& rhs) {
		size_t lhs_size = lhs.size();
		size_t rhs_size = rhs.size();
		return String::Concat(lhs.data(), lhs_size, rhs.data(), rhs_size);
	}

	/** 重载加号操作符 */
	inline String operator+(const char* lhs, const String& rhs) {
		size_t lhs_size = std::strlen(lhs);
		size_t rhs_size = rhs.size();
		return String::Concat(lhs, lhs_size, rhs.data(), rhs_size);
	}

	/** 重载加号操作符 */
	inline String operator+(const String& lhs, const char* rhs) {
		size_t lhs_size = lhs.size();
		size_t rhs_size = std::strlen(rhs);
		return String::Concat(lhs.data(), lhs_size, rhs, rhs_size);
	}

	/** 重载小于操作符 */
	inline bool operator<(const String& lhs, const std::string& rhs) { return lhs.compare(rhs) < 0; }
	/** 重载小于操作符 */
	inline bool operator<(const std::string& lhs, const String& rhs) { return rhs.compare(lhs) > 0; }
	/** 重载小于操作符 */
	inline bool operator<(const String& lhs, const String& rhs) { return lhs.compare(rhs) < 0; }
	/** 重载小于操作符 */
	inline bool operator<(const String& lhs, const char* rhs) { return lhs.compare(rhs) < 0; }
	/** 重载小于操作符 */
	inline bool operator<(const char* lhs, const String& rhs) { return rhs.compare(lhs) > 0; }

	/** 重载大于操作符 */
	inline bool operator>(const String& lhs, const std::string& rhs) { return lhs.compare(rhs) > 0; }
	/** 重载大于操作符 */
	inline bool operator>(const std::string& lhs, const String& rhs) { return rhs.compare(lhs) < 0; }
	/** 重载大于操作符 */
	inline bool operator>(const String& lhs, const String& rhs) { return lhs.compare(rhs) > 0; }
	/** 重载大于操作符 */
	inline bool operator>(const String& lhs, const char* rhs) { return lhs.compare(rhs) > 0; }
	/** 重载大于操作符 */
	inline bool operator>(const char* lhs, const String& rhs) { return rhs.compare(lhs) < 0; }

	/** 重载小于等于操作符 */
	inline bool operator<=(const String& lhs, const std::string& rhs) { return lhs.compare(rhs) <= 0; }
	/** 重载小于等于操作符 */
	inline bool operator<=(const std::string& lhs, const String& rhs) { return rhs.compare(lhs) >= 0; }
	/** 重载小于等于操作符 */
	inline bool operator<=(const String& lhs, const String& rhs) { return lhs.compare(rhs) <= 0; }
	/** 重载小于等于操作符 */
	inline bool operator<=(const String& lhs, const char* rhs) { return lhs.compare(rhs) <= 0; }
	/** 重载小于等于操作符 */
	inline bool operator<=(const char* lhs, const String& rhs) { return rhs.compare(lhs) >= 0; }

	/** 重载大于等于操作符 */
	inline bool operator>=(const String& lhs, const std::string& rhs) { return lhs.compare(rhs) >= 0; }
	/** 重载大于等于操作符 */
	inline bool operator>=(const std::string& lhs, const String& rhs) { return rhs.compare(lhs) <= 0; }
	/** 重载大于等于操作符 */
	inline bool operator>=(const String& lhs, const String& rhs) { return lhs.compare(rhs) >= 0; }
	/** 重载大于等于操作符 */
	inline bool operator>=(const String& lhs, const char* rhs) { return lhs.compare(rhs) >= 0; }
	/** 重载大于等于操作符 */
	inline bool operator>=(const char* lhs, const String& rhs) { return rhs.compare(rhs) <= 0; }

	/** 重载等于操作符 */
	inline bool operator==(const String& lhs, const std::string& rhs) { return lhs.compare(rhs) == 0; }
	/** 重载等于操作符 */
	inline bool operator==(const std::string& lhs, const String& rhs) { return rhs.compare(lhs) == 0; }
	/** 重载等于操作符 */
	inline bool operator==(const String& lhs, const String& rhs) { return lhs.compare(rhs) == 0; }
	/** 重载等于操作符 */
	inline bool operator==(const String& lhs, const char* rhs) { return lhs.compare(rhs) == 0; }
	/** 重载等于操作符 */
	inline bool operator==(const char* lhs, const String& rhs) { return rhs.compare(lhs) == 0; }

	/** 重载不等于操作符 */
	inline bool operator!=(const String& lhs, const std::string& rhs) { return lhs.compare(rhs) != 0; }
	/** 重载不等于操作符 */
	inline bool operator!=(const std::string& lhs, const String& rhs) { return rhs.compare(lhs) != 0; }
	/** 重载不等于操作符 */
	inline bool operator!=(const String& lhs, const String& rhs) { return lhs.compare(rhs) != 0; }
	/** 重载不等于操作符 */
	inline bool operator!=(const String& lhs, const char* rhs) { return lhs.compare(rhs) != 0; }
	/** 重载不等于操作符 */
	inline bool operator!=(const char* lhs, const String& rhs) { return rhs.compare(lhs) != 0; }


	/** 重载输出流操作符 */
	inline std::ostream& operator<<(std::ostream& out, const String& input) {
		out.write(input.data(), input.size());
		return out;
	}


	inline int String::memncmp(const char* lhs, const char* rhs, size_t lhs_count, size_t rhs_count) {

		if (lhs == rhs && lhs_count == rhs_count) {
			return 0;
		}

		for (size_t i = 0; i < lhs_count && i < rhs_count; ++i) {
			if (lhs[i] < rhs[i]) return -1;
			if (lhs[i] > rhs[i]) return 1;
		}

		if (lhs_count < rhs_count) {
			return -1;
		}
		else if (lhs_count > rhs_count) {
			return 1;
		}
		else {
			return 0;
		}
	}


	inline size_t ObjectHash::operator()(const ObjectRef& a) const {
		if (const auto* str = a.as<StringNode>()) {
			return String::HashBytes(str->data, str->size);
		}

		return ObjectPtrHash()(a);
	}


	inline bool ObjectEqual::operator()(const ObjectRef& a, const ObjectRef& b) const {
		if (a.same_as(b)) {
			return true;
		}

		if (const auto* str_a = a.as<StringNode>()) {
			if (const auto* str_b = b.as<StringNode>()) {
				return String::memncmp(str_a->data, str_b->data, str_a->size, str_b->size) == 0;
			}
		}

		return false;
	}
}
