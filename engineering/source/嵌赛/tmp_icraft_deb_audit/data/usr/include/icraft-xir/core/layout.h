#pragma once
#include <icraft-xir/base/dllexport.h>
#include <icraft-xir/base/optional.h>
#include <icraft-xir/core/node.h>


namespace icraft::xir {

	/** 表示Layout中的一个大写坐标轴 */
	class AxisNameNode : public NodeBase<AxisNameNode, Node> {
	public:
		std::string name;		///< 坐标轴的名字

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(AxisNameNode* other, const ReduceVisitor& reduce) const;
	};


	/** 大写坐标轴的引用类 */
	class AxisName : public HandleBase<AxisName, Handle, AxisNameNode> {
	public:
		/** 默认构造函数 */
		AxisName() = default;

		/**
		 * @brief 构造函数
		 * @param name 坐标轴的名字
		 */
		XIR_DLL explicit AxisName(char name);

		/** 检查该坐标轴和另一个是否相同 */
		XIR_DLL bool operator==(const AxisName& other) const;
	};


	/** 表示Layout中的一个小写坐标轴 */
	class AxisUnitNode : public NodeBase<AxisUnitNode, AxisNameNode> {
	public:
		uint64_t unit;		///< 坐标轴的单位长度

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(AxisUnitNode* other, const ReduceVisitor& reduce) const;
	};


	/** 小写坐标轴的引用类 */
	class AxisUnit : public HandleBase<AxisUnit, AxisName, AxisUnitNode> {
	public:
		/** 默认构造函数 */
		AxisUnit() = default;

		/**
		 * @brief 构造函数
		 * @param name 坐标轴名字
		 * @param unit 坐标轴的单位长度
		 */
		XIR_DLL AxisUnit(char name, uint64_t unit);

		/**
		 * @brief 构造函数(默认单位长度为0)
		 * @param name 坐标轴的名字
		 */
		explicit AxisUnit(char name) : AxisUnit(name, 0) {}

		/**
		 * @brief 设置坐标轴的单位长度
		 * @param unit 单位长度
		 * @return 自身
		 */
		XIR_DLL AxisUnit& setUnit(uint64_t unit);

		/** 检查该坐标轴和另一个是否相同 */
		XIR_DLL bool operator==(const AxisUnit& other) const;
	};


	/** IR中表示排布的类型 */
	class LayoutNode : public NodeBase<LayoutNode, Node> {
	public:
		Array<AxisName> axis_names;		///< 坐标轴的序列

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(LayoutNode* other, const ReduceVisitor& reduce) const;
	};


	/**
	 * @brief 排布的引用类
	 *		  Layout使用单个字符表示的坐标轴来解释Tensor的每一维是什么意义，目前有效的坐标轴为"NHWDCIO*nhwdcio"
	 *		  其中大写字母表示没被划分或划分后的Tile数量的坐标轴，小写字母表示做了划分后的单位坐标轴，
	 *		  后面跟数字表示单位长度，*表示不关心的坐标轴
	 *		  例如NCHWc32,，OIHWi32o32，N**HW**Cn2h3c4等都是有效的表达
	 */
	class Layout : public HandleBase<Layout, Handle, LayoutNode> {
	public:
		/** 默认构造函数 */
		Layout() = default;

		/**
		 * @brief 构造函数
		 * @param axis 表示坐标轴的列表
		 */
		XIR_DLL Layout(Array<AxisName> axis);

		/**
		 * @brief 构造函数，从字符串构造
		 * @param layout 表示Layout的字符串
		 */
		XIR_DLL explicit Layout(const std::string& layout);

		/**
		 * @brief 创建一个默认Layout
		 * @param size 表示Layout的长度，如果小于等于0则表示不含坐标轴
		 * @return 创建 "***C" 形式的默认Layout
		 */
		XIR_DLL static Layout Default(int64_t size = 0);

		/** 创建一个layout(NHWC) */
		XIR_DLL static Layout NHWC();

		/** 创建一个layout(NCHW) */
		XIR_DLL static Layout NCHW();

		/** 创建一个layout(HWIO) */
		XIR_DLL static Layout HWIO();

		/** 创建一个layout(OIHW) */
		XIR_DLL static Layout OIHW();

		/**
		 * @brief 检查Layout中是否包含某一坐标轴
		 * @param c 字符表示的坐标轴
		 */
		XIR_DLL bool has(char c) const;

		/**
		 * @brief 获取Layout中的某一坐标轴
		 * @param c 字符表示的坐标轴
		 * @return Optional<AxisName>，若坐标轴不存在则返回NullOpt
		 */
		XIR_DLL Optional<AxisName> get(char c) const;

		/**
		 * @brief 向Layout中添加坐标轴N
		 * @return 自身
		 */
		XIR_DLL Layout& N();

		/**
		 * @brief 向Layout中添加坐标轴L
		 * @return 自身
		 */
		XIR_DLL Layout& L();

		/**
		 * @brief 向Layout中添加坐标轴H
		 * @return 自身
		 */
		XIR_DLL Layout& H();

		/**
		 * @brief 向Layout中添加坐标轴W
		 * @return 自身
		 */
		XIR_DLL Layout& W();

		/**
		 * @brief 向Layout中添加坐标轴D
		 * @return 自身
		 */
		XIR_DLL Layout& D();

		/**
		 * @brief 向Layout中添加坐标轴C
		 * @return 自身
		 */
		XIR_DLL Layout& C();

		/**
		 * @brief 向Layout中添加坐标轴I
		 * @return 自身
		 */
		XIR_DLL Layout& I();

		/**
		 * @brief 向Layout中添加坐标轴O
		 * @return 自身
		 */
		XIR_DLL Layout& O();

		/**
		 * @brief 向Layout中添加坐标轴X
		 * @return 自身
		 */
		XIR_DLL Layout& X(uint32_t num = 1);

		/**
		 * @brief 向Layout中添加坐标轴n
		 * @param unit 坐标轴的单位长度
		 * @return 自身
		 */
		XIR_DLL Layout& n(int64_t unit);

		/**
		 * @brief 获取坐标轴n的单位长度
		 * @return n的单位长度，如果n不存在则返回0
		 */
		XIR_DLL uint64_t n() const;

		/**
		 * @brief 向Layout中添加坐标轴l
		 * @param unit 坐标轴的单位长度
		 * @return 自身
		 */
		XIR_DLL Layout& l(int64_t unit);

		/**
		 * @brief 获取坐标轴l的单位长度
		 * @return l的单位长度，如果l不存在则返回0
		 */
		XIR_DLL uint64_t l() const;

		/**
		 * @brief 向Layout中添加坐标轴h
		 * @param unit 坐标轴的单位长度
		 * @return 自身
		 */
		XIR_DLL Layout& h(int64_t unit);

		/**
		 * @brief 获取坐标轴h的单位长度
		 * @return h的单位长度，如果h不存在则返回0
		 */
		XIR_DLL uint64_t h() const;

		/**
		 * @brief 向Layout中添加坐标轴w
		 * @param unit 坐标轴的单位长度
		 * @return 自身
		 */
		XIR_DLL Layout& w(int64_t unit);

		/**
		 * @brief 获取坐标轴h的单位长度
		 * @return w的单位长度，如果w不存在则返回0
		 */
		XIR_DLL uint64_t w() const;

		/**
		 * @brief 向Layout中添加坐标轴d
		 * @param unit 坐标轴的单位长度
		 * @return 自身
		 */
		XIR_DLL Layout& d(int64_t unit);

		/**
		 * @brief 获取坐标轴d的单位长度
		 * @return d的单位长度，如果d不存在则返回0
		 */
		XIR_DLL uint64_t d() const;

		/**
		 * @brief 向Layout中添加坐标轴c
		 * @param unit 坐标轴的单位长度
		 * @return 自身
		 */
		XIR_DLL Layout& c(int64_t unit);

		/**
		 * @brief 获取坐标轴c的单位长度
		 * @return c的单位长度，如果c不存在则返回0
		 */
		XIR_DLL uint64_t c() const;

		/**
		 * @brief 向Layout中添加坐标轴i
		 * @param unit 坐标轴的单位长度
		 * @return 自身
		 */
		XIR_DLL Layout& i(int64_t unit);

		/**
		 * @brief 获取坐标轴i的单位长度
		 * @return i的单位长度，如果i不存在则返回0
		 */
		XIR_DLL uint64_t i() const;

		/**
		 * @brief 向Layout中添加坐标轴o
		 * @param unit 坐标轴的单位长度
		 * @return 自身
		 */
		XIR_DLL Layout& o(int64_t unit);

		/**
		 * @brief 获取坐标轴o的单位长度
		 * @return o的单位长度，如果o不存在则返回0
		 */
		XIR_DLL uint64_t o() const;

		/** 检查该Layout是否是layout(default) */
		XIR_DLL bool isDefault() const;

		/** 获取Layout中的坐标轴数量 */
		XIR_DLL uint64_t numAxis() const;

		/**
		 * @brief 获取指定坐标轴在Layout中的位置索引
		 * @param c 字符表示的坐标轴
		 * @return 该坐标轴的位置索引
		 */
		XIR_DLL uint64_t getIndexOf(char c) const;

		/**
		 * @brief 获取指定索引位置的坐标轴字符名称
		 * @param index 索引（支持负数索引）
		 * @return 该位置的坐标轴字符名称
		 */
		XIR_DLL char getAxisCharName(int64_t index) const;

		/**
		 * @brief 获取指定索引位置的坐标轴
		 * @param index 索引（支持负数索引）
		 * @return 该位置的坐标轴
		 */
		XIR_DLL AxisName operator[](int64_t index) const;

		/**
		 * @brief 交换两个坐标轴
		 * @param left_index	被交换的索引之一
		 * @param right_index	被交换的索引之二
		 * @return 自身
		 */
		XIR_DLL Layout& swapAxis(int64_t left_index, int64_t right_index);

		/**
		 * @brief 插入坐标轴
		 * @param index		被插入的位置索引（支持负数索引）
		 * @param axis_name	被插入的坐标轴
		 * @return 自身
		 */
		XIR_DLL Layout& insertAxis(int64_t index, AxisName axis_name);

		/**
		 * @brief 删除坐标轴
		 * @param index		被删除的位置索引（支持负数索引）
		 * @return 自身
		 */
		XIR_DLL Layout& eraseAxis(int64_t index);

		/**
		 * @brief 检查坐标轴的字符名是否是大写
		 * @param c 坐标轴的字符名
		 * @return 如果是大写则返回true
		 * @throw 如果字符名不被Layout支持则抛出异常
		 */
		XIR_DLL static bool CheckAxisNameUpper(char c);

		/** 验证Layout是否符合规范 */
		XIR_DLL void validate() const;

		/**
		 * @brief 获取字符串形式的Layout
		 * @return 字符串形式的Layout
		 */
		XIR_DLL std::string toString() const;

	private:
		inline static std::string_view valid_names = "NLHWDCIO*";
	};
}
