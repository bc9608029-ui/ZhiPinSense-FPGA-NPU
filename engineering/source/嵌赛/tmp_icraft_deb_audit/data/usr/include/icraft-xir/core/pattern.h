#pragma once
#include <icraft-xir/base/any.h>
#include <icraft-xir/base/string.h>
#include <icraft-xir/core/compile_target.h>
#include <icraft-xir/core/data.h>


namespace icraft::xir {

	/** 表示XIR中模式匹配的基类 */
	class PatternNode : public NodeBase<PatternNode, Node> {
	public:
		virtual void accept(AttrVisitor& visitor) override {};
	};


	/** 模式匹配的引用类 */
	class Pattern : public VirtualBase<Pattern, Handle, PatternNode> {};


	/** 表示匹配算子属性的模式 */
	class AttrPatternNode : public NodeBase<AttrPatternNode, PatternNode> {
	public:
		std::string key;		///< 属性的键
		Any value;				///< 属性的值

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;
	};


	/** 算子属性模式的引用类 */
	class AttrPattern : public HandleBase<AttrPattern, Pattern, AttrPatternNode> {
	public:
		/** 默认构造函数 */
		AttrPattern() = default;

		/**
		 * @brief 构造函数
		 * @param key	属性的键
		 * @param value	属性的值
		 */
		XIR_DLL AttrPattern(std::string key, Any value);
	};


	/** 表示XIR中模式匹配的通配符 */
	class AnycardsPatternNode : public NodeBase<AnycardsPatternNode, PatternNode> {};


	/** 通配符的引用类 */
	class AnycardsPattern : public HandleBase<AnycardsPattern, Pattern, AnycardsPatternNode> {};


	class OpPatternNode;
	class OptionalOpPatternNode;
	class ValuePattern;


	/** 算子模式的引用类 */
	class OpPattern : public HandleBase<OpPattern, Pattern, OpPatternNode> {
	public:
		/** 默认构造函数 */
		OpPattern() = default;

		/**
		 * @brief 构造函数
		 * @param op_types	算子可能的类型字符串列表
		 */
		XIR_DLL explicit OpPattern(std::vector<std::string_view> op_types);

		/**
		 * @brief 设置算子的输入模式
		 * @param inputs	输入模式列表
		 * @return 自身
		 */
		XIR_DLL OpPattern& operator()(Array<ValuePattern> inputs);

		/**
		 * @brief 设置算子的输入模式
		 * @param args	输入模式列表
		 * @return 自身
		 */
		template <typename... Args>
		OpPattern& operator()(Args... args) {
			return operator()({std::forward<Args>(args)...});
		}

		/**
		 * @brief 获取算子的输出模式
		 * @param index	索引
		 * @return 对应的输出模式
		 */
		XIR_DLL ValuePattern operator[](uint64_t index) const;

		/**
		 * @brief 为算子添加属性模式
		 * @param key	属性的键
		 * @param value	属性的值, 默认为Any()
		 * @return 自身
		 */
		XIR_DLL OpPattern& hasAttr(std::string key, Any value = Any());

		/**
		 * @brief 描述算子的编译目标
		 * @tparam T 编译目标的类型
		 * @return 自身
		 */
		template <typename T, typename = typename std::enable_if_t<std::is_base_of_v<CompileTarget, T>>>
		OpPattern& onTarget();

		/**
		 * @brief 描述算子的编译目标
		 * @param type_key 编译目标的类型字符串
		 * @return 自身
		 */
		XIR_DLL OpPattern& onTarget(std::string type_key);

		/**
		 * @brief 描述算子的约束函数
		 * @tparam cfunc 算子的约束函数
		 * @return 自身
		 */
		XIR_DLL OpPattern& setConstraint(std::function<bool(const Operation& op)> cfunc);
	};


	/** 可选算子模式的引用类 */
	class OptionalOpPattern : public HandleBase<OptionalOpPattern, OpPattern, OptionalOpPatternNode> {
	public:
		/** 默认构造函数 */
		OptionalOpPattern() = default;

		/**
		 * @brief 构造函数
		 * @param op_types	算子可能的类型字符串列表
		 */
		XIR_DLL explicit OptionalOpPattern(std::vector<std::string_view> op_types);

		/**
		 * @brief 设置算子的输入模式
		 * @param inputs	输入模式列表
		 * @return 自身
		 */
		XIR_DLL OptionalOpPattern& operator()(Array<ValuePattern> inputs);
	};


	/** 表示匹配算子输入的模式 */
	class ValuePatternNode : public NodeBase<ValuePatternNode, PatternNode> {
	public:
		OpPattern op_pattern;		///< 产生Value的算子
		int64_t index = -1;			///< 该Value在算子输出中的索引位置
		int64_t uses = -1;			///< 使用该Value的Op数量，默认为-1，表示任意数量
		TensorType dtype;			///< 该Value的数据类型

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;
	};


	/** 算子输入模式的引用类 */
	class ValuePattern : public HandleBase<ValuePattern, Pattern, ValuePatternNode> {
	public:
		/** 默认构造函数 */
		ValuePattern() = default;

		/**
		 * @brief 构造函数
		 * @param op_pattern	产生该Value的算子
		 * @param index			该Value在算子输出中的索引位置，默认为-1，表示任意位置
		 * @param uses			使用该Value的Op数量，默认为-1，表示任意数量
		 * @param dtype			该Value的数据类型
		 */
		XIR_DLL ValuePattern(OpPattern op_pattern, int64_t index = -1, int64_t uses = -1, TensorType dtype = TensorType());

		/** 构造函数，从通配符构造 */
		ValuePattern(AnycardsPattern) {}

		/**
		 * @brief 描述Value的使用次数
		 * @param uses	使用次数
		 * @return 返回一个新的模式
		 */
		XIR_DLL ValuePattern hasUses(uint32_t uses);

		/**
		 * @brief 描述Value的数据类型
		 * @param dtype	该Value的数据类型
		 * @return 返回一个新的模式
		 */
		XIR_DLL ValuePattern hasDtype(TensorType dtype);

		/** 检查该模式是否是Wildcard */
		XIR_DLL bool isWildcard() const;

		/** 检查该模式是否是Anycards */
		XIR_DLL bool isAnycards() const;
	};


	/** 表示匹配算子的模式 */
	class OpPatternNode : public NodeBase<OpPatternNode, PatternNode> {
	public:
		Array<String> op_type;							///< 算子可能的类型
		Array<AttrPattern> attrs;						///< 算子的属性
		Array<ValuePattern> inputs;						///< 算子的输入
		std::string target_type;						///< 算子的编译目标类型
		std::function<bool(const Operation& op)> cfunc;	///< 算子的约束函数

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;
	};


	/** 表示匹配可选算子的模式 */
	class OptionalOpPatternNode : public NodeBase<OptionalOpPatternNode, OpPatternNode> {
	public:
		XIR_DLL virtual void accept(AttrVisitor& visitor) override;
	};


	template <typename T, typename>
	OpPattern& OpPattern::onTarget() {
		get_mutable()->target_type = T::NodeType::type_key;
		return *this;
	}


	/** 表示模式匹配中的或逻辑 */
	class OrPatternNode : public NodeBase<OrPatternNode, PatternNode> {
	public:
		Pattern left;		///< 左操作数
		Pattern right;		///< 右操作数

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;
	};


	/** 模式匹配或逻辑的引用类 */
	class OrPattern : public HandleBase<OrPattern, Pattern, OrPatternNode> {
	public:
		/** 默认构造函数 */
		OrPattern() = default;

		/**
		 * @brief 构造函数
		 * @param left	左操作数
		 * @param right	右操作数
		 */
		XIR_DLL OrPattern(Pattern left, Pattern right);
	};


	/// @cond
	template<typename T>
	struct IsOneOf {
		template<typename... Args>
		static constexpr bool value = std::disjunction_v<std::is_same<T, Args>...>;
	};
	/// @endcond


	/**
	 * @brief 或逻辑的操作符重载
	 *		  只支持OpPattern和OrPattern之间取或
	 */
	template <typename P, typename = typename std::enable_if_t<
		IsOneOf<P>::template value<OpPattern, OrPattern>>,
		typename Q, typename = typename std::enable_if_t<
		IsOneOf<Q>::template value<OpPattern, OrPattern>>>
	OrPattern operator||(P left, Q right) { return OrPattern(left, right); }


	/** 构造一个通配符模式，匹配任意一个输入 */
	inline ValuePattern Wildcard() { return ValuePattern::Init(); }


	/** 构造一个通配符模式，匹配任意数量输入 */
	inline AnycardsPattern Anycards() { return AnycardsPattern::Init(); }

	template <typename... Ts>
	struct are_all_operations : std::conjunction<std::is_base_of<Operation, Ts>...> {};

	/**
	 * @brief 构造一个匹配算子的模式, 如果不指定类型，则匹配任意算子类型
	 * @tparam T	算子的类型
	 * @tparam Args 算子的输入类型
	 * @param  args 算子的输入
	 * @return 构造所得的算子匹配模式
	 */
	template <typename... T,
		typename = typename std::enable_if_t<are_all_operations<T...>::value>, typename... Args>
	OpPattern IsOp(Args... args) {
		auto op_types = std::vector<std::string_view>{ T::NodeType::type_key... };
		return OpPattern(op_types)({std::forward<Args>(args)...});
	}


	/**
	 * @brief 构造一个匹配可选算子的模式, 如果不指定类型，则匹配任意算子类型
	 * @tparam T	算子的类型
	 * @tparam Args 算子的输入类型
	 * @param  args 算子的输入
	 * @return 构造所得的算子匹配模式
	 */
	template <typename... T,
		typename = typename std::enable_if_t<are_all_operations<T...>::value>, typename... Args>
	OptionalOpPattern IsOptionalOp(Args... args) {
		auto op_types = std::vector<std::string_view>{ T::NodeType::type_key... };
		return OptionalOpPattern(op_types)({ std::forward<Args>(args)... });
	}

	/**
	 * @brief 表示一组匹配结果
	 *		  是一个以OpPattern为键，以Opeation为值的Map.可以根据OpPattern获取对应的算子
	 */
	using MatchGroup = std::unordered_map<OpPattern, Operation, ObjectPtrHash, ObjectPtrEqual>;
}


/** 用于添加算子约束的辅助宏 */
#define PATTERN_REQUIRE(x) if (!(x)) return false
