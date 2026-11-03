#pragma once
#include <unordered_map>
#include <icraft-xir/base/optional.h>


namespace icraft::xir {

	/** 表达哈希映射的类 */
	class MapNode : public Object {
	public:

		/** 键类型 */
		using key_type = ObjectRef;

		/** 值类型 */
		using mapped_type = ObjectRef;

		/** 底层容器类型 */
		using ContainerType = std::unordered_map<ObjectRef, ObjectRef, ObjectHash, ObjectEqual>;

		/** 迭代器类型 */
		using iterator = ContainerType::iterator;

		/** const迭代器类型 */
		using const_iterator = ContainerType::const_iterator;

		using KVType = ContainerType::value_type;

		static_assert(std::is_standard_layout<KVType>::value, "KVType is not standard layout");
		static_assert(sizeof(KVType) == 32 || sizeof(KVType) == 16 || sizeof(KVType) == 8, "sizeof(KVType) incorrect");

		/** 获取Map的大小 */
		size_t size() const { return data_.size(); }

		/**
		 * @brief 获取Map中指定key的数量
		 * @param key 索引key
		 * @return 0或1
		 */
		size_t count(const key_type& key) const { return data_.count(key); }

		/**
		 * @brief 获取指定key对应的值
		 * @param key 索引key
		 * @return 值的const引用
		 * @throw 如果指定的key不存在则抛出异常
		 */
		const mapped_type& at(const key_type& key) const { return data_.at(key); }

		/**
		 * @brief 获取指定key对应的值
		 * @param key 索引key
		 * @return 值的引用
		 * @throw 如果指定的key不存在则抛出异常
		 */
		mapped_type& at(const key_type& key) { return data_.at(key); }

		/** 获取开始迭代器 */
		iterator begin() { return data_.begin(); }

		/** 获取开始const迭代器 */
		const_iterator begin() const { return data_.begin(); }

		/** 获取结束迭代器 */
		iterator end() { return data_.end(); }

		/** 获取结束const迭代器 */
		const_iterator end() const { return data_.end(); }

		/**
		 * @brief 查找指定key对应的迭代器
		 * @param key 索引key
		 * @return 和key对应的迭代器，如果key不存在则返回结束迭代器
		 */
		const_iterator find(const key_type& key) const { return data_.find(key); }

		/**
		 * @brief 查找指定key对应的迭代器
		 * @param key 索引key
		 * @return 和key对应的迭代器，如果key不存在则返回结束迭代器
		 */
		iterator find(const key_type& key) { return data_.find(key); }

		/**
		 * @brief 擦除迭代器指定位置的元素
		 * @param position 指定位置的迭代器
		 */
		void erase(const iterator& position) { data_.erase(position); }

		/**
		 * @brief 擦除key对应的元素
		 * @param key 索引key
		 */
		void erase(const key_type& key) { data_.erase(key); }

		/**
		 * @brief 创建一个空的容器
		 * @return 相应的智能指针
		 */
		static ObjectPtr<MapNode> Empty() { return make_object<MapNode>(); }

		/**
		 * @brief 创建一个Map，内容复制于别的Map
		 * @param from 复制源
		 * @return 所创建Map的智能指针
		 */
		static ObjectPtr<MapNode> CopyFrom(const MapNode* from) {
			ObjectPtr<MapNode> p = make_object<MapNode>();
			p->data_ = ContainerType(from->data_.begin(), from->data_.end());
			return p;
		}

	protected:
		/// @cond
		/**
		 * @brief 根据迭代器指定的内容创建Map
		 * @param first 开始迭代器
		 * @param last 结束迭代器
		 * @tparam IterType 迭代器的类型
		 * @return 所创建Map的智能指针
		 */
		template <typename IterType>
		static ObjectPtr<Object> CreateFromRange(IterType first, IterType last) {
			ObjectPtr<MapNode> p = make_object<MapNode>();
			p->data_ = ContainerType(first, last);
			return p;
		}

		ContainerType data_;
		template <typename, typename, typename, typename>
		friend class Map;
		/// @endcond
	};


	/**
	 * @brief Map容器，用于ObjectRef -> ObjectRef的键值映射
	 *		operator[]只提供const访问，请使用set方法来设置Map的值
	 * @tparam K 键类型，ObjectRef的子类
	 * @tparam V 值类型，ObjectRef的子类
	 */
	template <typename K, typename V,
		typename = typename std::enable_if_t<std::is_base_of_v<ObjectRef, K>>,
		typename = typename std::enable_if_t<std::is_base_of_v<ObjectRef, V>>>
	class Map : public ObjectRef {
	public:
		using key_type = K;
		using mapped_type = V;

		/// @cond
		class iterator;
		/// @endcond

		/** 默认构造函数(空Map) */
		Map() { data_ = MapNode::Empty(); }

		/** 移动构造函数 */
		Map(Map<K, V>&& other) { data_ = std::move(other.data_); }

		/** 复制构造函数 */
		Map(const Map<K, V>& other) : ObjectRef(other.data_) {}

		/** 移动赋值函数 */
		Map<K, V>& operator=(Map<K, V>&& other) {
			data_ = std::move(other.data_);
			return *this;
		}

		/** 复制赋值函数 */
		Map<K, V>& operator=(const Map<K, V>& other) {
			data_ = other.data_;
			return *this;
		}

		/** 构造函数，从ObjectPtr<Object>构造 */
		explicit Map(ObjectPtr<Object> n) : ObjectRef(n) {}

		/**
		 * @brief 构造函数，从迭代器构造
		 * @param begin 开始迭代器
		 * @param end 结束迭代器
		 * @tparam IterType 迭代器类型
		 */
		template <typename IterType>
		Map(IterType begin, IterType end) {
			data_ = MapNode::CreateFromRange(begin, end);
		}

		/**
		 * @brief 构造函数，从初始化列表构造
		 * @param init 用于构造的初始化列表
		 */
		Map(std::initializer_list<std::pair<K, V>> init) {
			data_ = MapNode::CreateFromRange(init.begin(), init.end());
		}

		/**
		 * @brief 构造函数，从unordered_map构造
		 * @param init 用于构造的unordered_map
		 */
		template <typename Hash, typename Equal>
		Map(const std::unordered_map<K, V, Hash, Equal>& init) {				// NOLINT(*)
			data_ = MapNode::CreateFromRange(init.begin(), init.end());
		}

		/**
		 * @brief 获取指定key对应的元素
		 * @param key 索引key
		 * @return key对应的元素
		 */
		V at(const K& key) const { return DowncastNoCheck<V>(getMapNode()->at(key)); }

		/**
		 * @brief 获取指定key对应的元素
		 * @param key 索引key
		 * @return key对应的元素
		 */
		V operator[](const K& key) const { return this->at(key); }

		/** 获取Map的大小 */
		size_t size() const {
			MapNode* n = getMapNode();
			return n == nullptr ? 0 : n->size();
		}

		/**
		 * @brief 获取Map中指定key的数量
		 * @param key 索引key
		 * @return 0或1
		 */
		size_t count(const K& key) const {
			MapNode* n = getMapNode();
			return n == nullptr ? 0 : getMapNode()->count(key);
		}

		/** 检查Map是否为空  */
		bool empty() const {
			return size() == 0;
		}

		/** 释放Map中所有元素  */
		void clear() {
			if (getMapNode() != nullptr) {
				data_ = MapNode::Empty();
			}
		}

		/**
		 * @brief 设置Map的元素
		 * @param key 元素key
		 * @param value 元素值
		 */
		void set(const K& key, const V& value) {
			getMapNode()->data_[key] = value;
		}

		/** 获取开始迭代器 */
		iterator begin() const { return iterator(getMapNode()->begin()); }

		/** 获取结束迭代器 */
		iterator end() const { return iterator(getMapNode()->end()); }

		/**
		 * @brief 查找指定key对应的迭代器
		 * @param key 索引key
		 * @return 和key对应的迭代器，如果key不存在则返回结束迭代器
		 */
		iterator find(const K& key) const { return iterator(getMapNode()->find(key)); }

		/** 获取key指定的元素，如果不存在则返回NullOpt */
		Optional<V> get(const K& key) const {
			MapNode::iterator iter = getMapNode()->find(key);
			if (iter == getMapNode()->end()) {
				return NullOptType{};
			}

			return DowncastNoCheck<V>(iter->second);
		}

		/**
		 * @brief 擦除key对应的元素
		 * @param key 索引key
		 */
		void erase(const K& key) {
			getMapNode()->erase(key);
		}

		/**
		 * @brief 合并另一个Map
		 * @param rhs 被合并的Map
		 */
		void merge(const Map<K, V>& rhs) {
			for (const auto& p : rhs) {
				this->set(p.first, p.second);
			}
		}

		/** 复制一个Map */
		Map<K, V> clone(int64_t depth = 1) const {
			return Downcast<Map<K, V>>(ObjectRef::clone(depth));
		}

		using NodeType = MapNode;

		/// @cond
		/** Map的迭代器 */
		class iterator {
		public:
			using iterator_category = std::bidirectional_iterator_tag;
			using difference_type = int64_t;
			using value_type = const std::pair<K, V>;
			using pointer = value_type*;
			using reference = value_type;

			iterator() : itr() {}

			bool operator==(const iterator& other) const { return itr == other.itr; }
			bool operator!=(const iterator& other) const { return itr != other.itr; }
			pointer operator->() const = delete;

			reference operator*() const {
				auto& kv = *itr;
				return std::make_pair(DowncastNoCheck<K>(kv.first), DowncastNoCheck<V>(kv.second));
			}

			iterator& operator++() {
				++itr;
				return *this;
			}

			iterator operator++(int) {
				iterator copy = *this;
				++(*this);
				return copy;
			}

		private:
			iterator(const MapNode::iterator& itr) : itr(itr) {}					// NOLINT(*)

			template <typename, typename, typename, typename>
			friend class Map;

			MapNode::iterator itr;
		};
		/// @endcond

		static Map Get(ObjectPtr<Object> node) { return Map(node);}

	private:
		MapNode* getMapNode() const { return static_cast<MapNode*>(data_.get()); }
	};
}
