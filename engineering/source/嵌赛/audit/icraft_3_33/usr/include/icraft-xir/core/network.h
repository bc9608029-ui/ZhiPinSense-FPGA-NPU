#pragma once
#include <icraft-xir/base/map.h>
#include <icraft-xir/base/string.h>
#include <icraft-xir/core/operation.h>
#include <icraft-xir/core/pattern.h>
#include <icraft-xir/utils/wise_enum.h>
#include <icraft-utils/dll.h>
#include <icraft-utils/midware/filestream.hpp>


namespace icraft::xir {

	 /**
	 * @enum	Framework
	 * @brief	表示IR中前端框架的枚举
	 */
	// enum class Framework {
	// 	PYTORCH,		///< Pytorch框架
	// 	CAFFE,			///< Caffe框架
	// 	TENSORFLOW,		///< Tensorflow框架
	// 	DARKNET,		///< Darknet框架
	// 	ONNX			///< ONNX框架
	// };

	// enum class Serialize {
	// 	JSON,			///< Json
	// 	RAW,			///< Raw
	// 	MESSAGEPACK,	///< MessagePack
	// 	FLATBUFFERS		///< FlatBuffers
	// };
	WISE_ENUM_CLASS(Framework, PYTORCH, CAFFE, TENSORFLOW, DARKNET, ONNX);
	WISE_ENUM_CLASS(Serialize, JSON, RAW, MESSAGEPACK, FLATBUFFERS);


	class NetworkRewriter;
	class NetworkView;


	class NetworkBaseNode : public NodeBase<NetworkBaseNode, Node> {
	public:
		Array<Operation> ops;											///< Op列表
		CompileTarget ai_target = BuyiTarget::Init();					///< 准备部署到的ICore后端

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(NetworkBaseNode* other, const ReduceVisitor& reduce) const;

	protected:
		std::map<int64_t, int64_t> op_index_map_;						///< Op快查表			：op_id, op_index
		std::map<int64_t, Value> value_map_;							///< Value快查表		：value_id, Value
		std::map<int64_t, std::map<int64_t, int64_t>> value_uses_map_;	///< Value被Op使用快查表：value_id, (op_id, times)

	private:
		XIR_DLL virtual const Array<Value>& inputs() const;
		XIR_DLL virtual const Array<Value>& outputs() const;

		friend class NetworkBase;
	};


	class NetworkBase : public HandleBase<NetworkBase, Handle, NetworkBaseNode> {
	public:
		/**
		 * @brief 获取网络中的输入
		 * @return 网络中输入算子的输出Value列表，即网络的输入
		 */
		XIR_DLL const Array<Value>& inputs() const;

		/**
		 * @brief 获取网络中的输出
		 * @return 网络中输出算子的输入Value列表，即网络的输出
		 */
		XIR_DLL const Array<Value>& outputs() const;

		/**
		 * @brief 获取网络的第index个算子
		 * @param index 索引（支持负数索引）
		 * @return 指定位置的算子
		 * @throw 如果索引越界则抛出异常
		 */
		XIR_DLL Operation operator[](int64_t index) const;

		/**
		 * @brief 根据指定ID获取网络中的Op
		 * @param op_id 指定的ID
		 * @return 对应的Op的const引用
		 * @throw 如果op_id指定的Op不存在则抛出异常
		 */
		XIR_DLL Operation getOpById(int64_t op_id) const;

		/**
		 * @brief 根据指定ID列表获取网络中的Op列表
		 * @param op_ids 指定的ID列表
		 * @return 对应的Op列表
		 * @throw 如果op_id指定的Op不存在则抛出异常
		 */
		XIR_DLL Array<Operation> getOpsById(const Array<int64_t>& op_ids) const;

		/**
		 * @brief 根据指定ID获取网络中的Value
		 * @param v_id 指定的ID
		 * @return 对应的Value的const引用
		 * @throw 如果v_id指定的Value不存在则抛出异常
		 */
		XIR_DLL const Value& getValueById(int64_t v_id) const;

		/**
		 * @brief 获取网络中所有算子的Params
		 * @return 网络中所有算子的Params
		 */
		XIR_DLL Array<Params> allParams() const;

		/**
		 * @brief 根据指定ID列表获取网络中的Value列表
		 * @param value_ids 指定的ID列表
		 * @return 对应的Value列表
		 * @throw 如果v_id指定的Value不存在则抛出异常
		 */
		XIR_DLL Array<Value> getValuesById(const Array<int64_t>& value_ids) const;

		/**
		 * @brief 获取网络中使用某Value(即以该Value做输入)的Op列表
		 * @param v_id 指定的ID
		 * @return 使用该Value的Op列表
		 */
		XIR_DLL Array<Operation> getUsesOpByValueId(int64_t v_id) const;

		/**
		 * @brief 获取网络中使用某Value(即以该Value做输入)的Op数量
		 * @param v_id 指定的ID
		 * @return 使用该Value的Op数量
		 */
		XIR_DLL size_t getUsesNumByValueId(int64_t v_id) const;

		/**
		 * @brief 获取指定Op在网络执行序中的index
		 * @param op_id 指定Op的ID
		 * @return 该Op在网络中的index
		 */
		XIR_DLL int64_t getOpIndexById(int64_t op_id) const;

		/**
		 * @brief 获取网络Op列表中(即执行序)某个Op的前一个Op
		 * @param op_id 指定的ID
		 * @return 该Op的前一个Op
		 * @throw 如果要查找的算子是第一个算子则抛出异常
		 */
		XIR_DLL Operation getPreOpById(int64_t op_id) const;

		/**
		 * @brief 获取网络Op列表中(即执行序)某个Op的后一个Op
		 * @param op_id 指定的ID
		 * @return 该Op的后一个Op
		 * @throw 如果要查找的算子是最后一个算子则抛出异常
		 */
		XIR_DLL Operation getNextOpById(int64_t op_id) const;

		/**
		 * @brief 获取网络中指定Op的生产者(生产者的输出是该Op的输入)
		 * @param op_id 指定的ID
		 * @return 该Op的生产者列表
		 */
		XIR_DLL Array<Operation> getProducersByOpId(int64_t op_id, bool sorted = false) const;

		/**
		 * @brief 获取网络中指定Op的消费者(消费者的输入是该Op的输出)
		 * @param op_id 指定的ID
		 * @param sorted 是否按执行序排序
		 * @return 该Op的消费者列表
		 */
		XIR_DLL Array<Operation> getConsumersByOpId(int64_t op_id, bool sorted = false) const;

		/**
		 * @brief 从该网络创建一个NetworkView
		 * @param ops	NetworkView包含的算子
		 * @return 创建的NetworkView
		 */
		XIR_DLL NetworkView view(Array<Operation> ops) const;

		/**
		 * @brief 从该网络创建一个NetworkView
		 * @param op_ids	NetworkView包含的算子的ID列表
		 * @return 创建的NetworkView
		 */
		XIR_DLL NetworkView view(const std::vector<int64_t>& op_ids) const;

		/**
		 * @brief 从该网络创建一个NetworkView
		 * @param op_ids	NetworkView不包含的算子的ID列表
		 * @return 创建的NetworkView
		 */
		XIR_DLL NetworkView viewExcept(const std::vector<int64_t>& op_ids) const;

		/**
		 * @brief 从该网络创建一个NetworkView
		 * @param start_index	NetworkView包含的算子在原网络中的开始索引(包含)，支持负数索引
		 * @param end_index		NetworkView包含的算子在原网络中的结束索引(不包含)，支持负数索引
		 * @return 创建的NetworkView
		 */
		XIR_DLL NetworkView view(int64_t start_index, int64_t end_index) const;

		/**
		 * @brief 从该网络创建一个NetworkView
		 * @param start_op_id	NetworkView包含的开始算子ID(包含)
		 * @param end_op_id		NetworkView包含的结束算子ID(包含)
		 * @return 创建的NetworkView
		 */
		XIR_DLL NetworkView viewByOpId(int64_t start_op_id, int64_t end_op_id) const;

		/**
		 * @brief 从该网络创建一个NetworkView
		 * @param start_index	NetworkView包含的算子在原网络中的开始索引(包含)，支持负数索引
		 * @return 创建的NetworkView
		 */
		XIR_DLL NetworkView view(int64_t start_index = 0) const;

		/**
		 * @brief 从该网络创建一个NetworkView
		 * @param judge	判断算子是否放入NetworkView的函数
		 * @return 创建的NetworkView
		 */
		XIR_DLL NetworkView view(std::function<bool(const Operation& op)> judge) const;

		/**
		 * @brief 设置网络准备部署到的ICore后端
		 * @param	ai_target	准备部署到的ICore后端
		 * @return 自身
		 */
		XIR_DLL NetworkBase& setAITarget(const CompileTarget& ai_target);

	protected:
		void removeValueUses(const Value& v, int64_t op_id);
		void removeValueUsesById(int64_t v_id, int64_t op_id);
		void addValueUses(const Value& v, int64_t op_id);
		void addValueUsesById(int64_t v_id, int64_t op_id);

		/**
		 * @brief 修改Network中算子的ID
		 * @param old_id	旧ID
		 * @param new_id	新ID
		 * @throw 如果新ID在网络中已经存在则抛出异常
		 */
		void changeOpIdById(int64_t old_id, int64_t new_id);
		void changeValueIdById(int64_t old_id, int64_t new_id);

		bool checkIsFirstOpById(int64_t op_id) const;
		bool checkIsLastOpById(int64_t op_id) const;
		void replaceValue(Value src, Value dest);

		/** 网络的执行序是否存在逆序 */
		bool isInOrder() const;

		void reorderExecutionSequence();
	};


	/** 表示IR中的网络的类型 */
	class NetworkNode : public NodeBase<NetworkNode, NetworkBaseNode> {
	public:
		std::string name;												///< 网络名称
		Framework framework_kind;										///< 前端框架
		std::string framework_version;									///< 框架版本
		std::string icraft_xir_version;									///< XIR版本
		std::string icraft_version;										///< Icraft版本
		uint64_t params_bytes = 0;										///< 参数大小
		std::string params_md5 = "d41d8cd98f00b204e9800998ecf8427e";	///< 参数的MD5
		Map<String, ObjectRef> tags;									///< 一些标记

	private:
		NetworkRewriter* rewriter_;

		int64_t values_id_ = 0;
		int64_t ops_id_ = 0;											///< 默认op_id，单调递增
		void* mapped_addr_ = nullptr;
		uint64_t mapped_byte_size_;
		friend Network;

		XIR_DLL virtual const Array<Value>& inputs() const override;
		XIR_DLL virtual const Array<Value>& outputs() const override;

	public:
		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(NetworkNode* other, const ReduceVisitor& reduce) const;

		/** 析构函数 */
		XIR_DLL ~NetworkNode();
	};


	/** IR中网络的引用类 */
	class Network : public HandleBase<Network, NetworkBase, NetworkNode> {
	public:
		/** 默认构造函数 */
		Network() = default;

		/**
		 * @brief 构造函数
		 * @param name 网络名称
		 * @param framework_kind 前端框架
		 * @param framework_version 框架版本
		 * @param ai_target 准备部署到的ICore后端
		 */
		XIR_DLL Network(const std::string& name, Framework framework_kind, const std::string& framework_version, CompileTarget ai_target = BuyiTarget::Init());

		/**
		 * @brief 设置网络的名称
		 * @param	name	网络的名称
		 * @return 自身
		 */
		XIR_DLL Network& setName(const std::string& name);

		/**
		 * @brief 设置网络的标签
		 * @param	key		标签的键
		 * @param	value	标签的值
		 * @return 自身
		 */
		XIR_DLL Network& setTag(const std::string& key, ObjectRef value);

		/**
		 * @brief 获取网络的标签
		 * @param	key		标签的建
		 * @return 标签的值（可选）
		 */
		XIR_DLL std::optional<ObjectRef> getTag(const std::string& key) const;

		/**
		 * @brief 删除算子的标签
		 * @param	key		标签的建
		 * @return 如果标签存在则返回true，否则返回false
		 */
		XIR_DLL bool removeTag(const std::string& key);

		/**
		 * @brief 向网络中插入算子
		 * @param it 插入位置
		 * @param op 被插入Op
		 * @return 自身
		 * @throw 如果遇到以下情况，则抛出异常
		 *   * 将Input插入非空网络
		 *   * 在空网络中插入非Input算子
		 *   * Op为空
		 *   * Op已经加入过别的网络
		 *   * Op在该网络中已经存在
		 *	 * Op指定的op_id在网络中已被分配
		 *	 * Op不是Input算子，但是却没有输入
		 *   * Op的输出指定的v_id在网络中已被分配
		 */
		XIR_DLL Network& insertOp(const Array<Operation>::const_iterator& it, Operation op);

		/**
		 * @brief 向网络中插入算子
		 * @param op_index 插入位置
		 * @param op 被插入Op
		 * @return 自身
		 */
		XIR_DLL Network& insertOp(int64_t op_index, Operation op);

		/**
		 * @brief 向网络中插入算子
		 * @param op_id 插入位置（即在op_id算子正前方插入算子）
		 * @param op 被插入Op
		 * @return 自身
		 */
		XIR_DLL Network& insertOpById(int64_t op_id, Operation op);

		/**
		 * @brief 向网络中添加算子
		 * @param op 被添加的算子
		 * @return 自身
		 * @throw @see Network::insertOp
		 */
		XIR_DLL Network& addOp(Operation op);

		/**
		 * @brief 移除网络中的算子
		 * @param op_id 被移除算子的ID
		 * @return 自身
		 * @throw 如果指定的Op在网络中不存在则抛出异常
		 */
		XIR_DLL Network& removeOpById(int64_t op_id);

		/**
		 * @brief 一次性移除网络中的若干算子，但保留它们之间的连接关系
		 * @param op_ids 被移除算子们的ID
		 * @return 自身
		 * @throw 如果指定的Op在网络中不存在则抛出异常
		 */
		XIR_DLL Network& removeOpsById(const std::vector<int64_t>& op_ids);

		/**
		 * @brief 移除网络中的算子
		 * @tparam	F	移除条件函数的类型，输入Operation返回bool
		 * @param	f	移除的条件函数
		 * @return 自身
		 */
		template <typename F, typename = std::enable_if_t<std::is_same_v<bool, std::invoke_result_t<F, Operation>>>>
		Network& removeOp(F f) {

			for (auto&& op : (*this)->ops) {
				if (f(op)) {
					removeOpById(op->op_id);
				}
			}

			return *this;
		}

		/**
		 * @brief 替换网络中的算子
		 * @param op_id 被替换的算子ID
		 * @param op 替换后的算子
		 * @return 自身
		 */
		XIR_DLL Network& replaceOpById(int64_t op_id, Operation op);

		/**
		 * @brief 替换网络中的算子，保持原来的连接关系
		 * @param op_id 被替换的算子ID
		 * @param op 替换后的算子
		 * @return 自身
		 * @throw 如果老Op和新Op的输出数量不同，则抛出异常
		 */
		XIR_DLL Network& replaceOpByIdKeepUses(int64_t op_id, Operation op);

		/**
		 * @brief 替换网络中的算子
		 * @param src 被替换的算子
		 * @param dest 替换后的算子
		 * @return 自身
		 */
		XIR_DLL Network& replaceOp(Operation src, Operation dest);

		/**
		 * @brief 替换网络中的算子，保持原来的连接关系
		 * @param src 被替换的算子
		 * @param dest 替换后的算子
		 * @return 自身
		 */
		XIR_DLL Network& replaceOpKeepUses(Operation src, Operation dest);

		/**
		 * @brief 将网络序列化为Json，并输出到指定的流
		 * @param stream 指定的输出流
		 * @param calc_md5 序列化时是否计算参数的MD5
		 */
		XIR_DLL void dumpJson(std::ostream& stream, bool calc_md5 = true) const;

		/**
		 * @brief 将网络序列化为MSG，并输出到指定的流
		 * @param stream 指定的输出流
		 * @param calc_md5 序列化时是否计算参数的MD5
		 */
		//XIR_DLL void dumpMSG(std::ostream& stream, bool calc_md5 = true) const;

		/**
		 * @brief 将网络序列化为FlatBuffers，并输出到指定的流
		 * @param stream 指定的输出流
		 * @param calc_md5 序列化时是否计算参数的MD5
		 */
		XIR_DLL void dumpFlat(std::ostream& stream, bool calc_md5 = true) const;

		/**
		 * @brief 输出网络参数到指定的流
		 * @param stream 指定的输出流
		 */
		XIR_DLL void dumpParams(std::ostream& stream) const;


		XIR_DLL void dumpToFile(const icraft::midware::path& file_path, Serialize mode, bool calc_md5 = true, bool validate = true) const;
		#if !defined(_BAREME)
		XIR_DLL void dumpToFile(const std::filesystem::path& file_path, Serialize mode, bool calc_md5 = true, bool validate = true) const;
		#endif
		/**
		 * @brief 将网络序列化为Json，并输出到指定的文件
		 * @param file_path 指定的文件路径
		 * @param calc_md5 序列化时是否计算参数的MD5
		 * @param validate 序列化时是否检查网络必须符合规范
		 */
		XIR_DLL void dumpJsonToFile(const icraft::midware::path& file_path, bool calc_md5 = true, bool validate = true) const;
		#if !defined(_BAREME)
		XIR_DLL void dumpJsonToFile(const std::filesystem::path& file_path, bool calc_md5 = true, bool validate = true) const;
		#endif
		/**
		 * @brief 输出网络参数到指定的文件
		 * @param file_path 指定的文件路径
		 */
		XIR_DLL void dumpParamsToFile(const icraft::midware::path& file_path) const;
		#if !defined(_BAREME)
		XIR_DLL void dumpParamsToFile(const std::filesystem::path& file_path) const;
		#endif

		/**
		 * @brief 将网络序列化为MSG，并输出到指定的文件
		 * @param file_path 指定的文件路径
		 * @param calc_md5 序列化时是否计算参数的MD5
		 * @param validate 序列化时是否检查网络必须符合规范
		 */
		//XIR_DLL void dumpMSGToFile(const icraft::midware::path& file_path, bool calc_md5 = true, bool validate = true) const;

		/**
		 * @brief 将网络序列化为FlatBuffers，并输出到指定的文件
		 * @param file_path 指定的文件路径
		 * @param calc_md5 序列化时是否计算参数的MD5
		 * @param validate 序列化时是否检查网络必须符合规范
		 */
		XIR_DLL void dumpFlatToFile(const icraft::midware::path& file_path, bool calc_md5 = true, bool validate = true) const;
		#if !defined(_BAREME)
		XIR_DLL void dumpFlatToFile(const std::filesystem::path& file_path, bool calc_md5 = true, bool validate = true) const;
		#endif

		/**
		 * @brief 从Json文件创建一个网络
		 * @param file_path Json文件路径
		 * @return 创建得到的网络对象
		 */
		XIR_DLL static Network CreateFromJsonFile(const icraft::midware::path& file_path);
		#if !defined(_BAREME)
		XIR_DLL static Network CreateFromJsonFile(const std::filesystem::path& file_path);
		#endif

		/**
		 * @brief 从MSG文件创建一个网络
		 * @param file_path MSG文件路径
		 * @return 创建得到的网络对象
		 */
		// XIR_DLL static Network CreateFromMSGFile(const icraft::midware::path& file_path);

		/**
		 * @brief 从Flat文件创建一个网络
		 * @param file_path Flat文件路径
		 * @return 创建得到的网络对象
		 */
		XIR_DLL static Network CreateFromFlatFile(const icraft::midware::path& file_path);		
		#if !defined(_BAREME)
		XIR_DLL static Network CreateFromFlatFile(const std::filesystem::path& file_path);
		#endif
		/**
		 * @brief 从输入流中加载网络的参数
		 * @param stream 指定的输入流
		 * @param calc_md5 反序列化时是否计算参数的MD5
		 * @throw 如果参数的MD5和网络不匹配的抛出异常
		 */
		XIR_DLL void loadParams(std::istream& stream, bool calc_md5 = true);

		
		/**
		 * @brief 从文件中加载网络的参数
		 * @param file_path 指定的文件路径
		 * @param calc_md5 反序列化时是否计算参数的MD5
		 * @throw 如果参数的MD5和网络不匹配的抛出异常
		 * @throw 如果文件不存在或者打开失败则抛出异常
		 */
		XIR_DLL void loadParamsFromFile(const icraft::midware::path& file_path, bool calc_md5 = true);
		#if !defined(_BAREME)
		XIR_DLL void loadParamsFromFile(const std::filesystem::path& file_path, bool calc_md5 = true);
		#endif

		/**
		 * @brief 从指针中惰性加载网络的参数
		 * @param mapped_ptr 参数文件mmaped后的指针
		 * @param byte_size 参数的字节大小
		 * @param calc_md5 反序列化时是否计算参数的MD5
		 */
		XIR_DLL void lazyLoadParams(char* mapped_ptr, uint64_t byte_size, bool calc_md5 = true);

		/**
		 * @brief 从文件中惰性加载网络的参数
		 * @param file_path 指定的文件路径
		 * @param calc_md5 反序列化时是否计算参数的MD5
		 */
		XIR_DLL void lazyLoadParamsFromFile(const icraft::midware::path& file_path, bool calc_md5 = true);
		XIR_DLL void lazyLoadParamsFromFile(const std::string& file_path, bool calc_md5 = true);
		#if !defined(_BAREME)
		XIR_DLL void lazyLoadParamsFromFile(const std::filesystem::path& file_path, bool calc_md5);
		#endif

		/**
		 * @brief 搜索网络中符合模式的结构
		 * @param pattern 指定的模式
		 * @return 搜索结果
		 */
		XIR_DLL std::vector<MatchGroup> search(const Pattern& pattern) const;

		/**
		 * @brief 搜索网络中符合模式的结构一次
		 * @param pattern 指定的模式
		 * @return 搜索结果
		 */
		XIR_DLL MatchGroup searchOnce(const Pattern& pattern) const;

		/** 表示rewrite的回调类型 */
		using PatternCallback = std::function<void(Network& network, const MatchGroup& result)>;

		/**
		 * @brief 根据指定的模式和回调重写网络
		 * @param pattern 指定的模式
		 * @param callback 回调函数，实现了改变网络的逻辑
		 * @param times 搜索的最大次数
		 */
		XIR_DLL void rewrite(const Pattern& pattern, PatternCallback callback, uint64_t times = 10000);

		/**
		 * @brief 将MatchGroup表达的子图替换为某个算子
		 * @param src MatchGroup表达的子图
		 * @param dest 替换后的算子
		 * @return 自身
		 */
		XIR_DLL Network& replaceGroup(const MatchGroup& src, Operation dest);

		/**
		 * @brief 表示某个Value被使用的信息：
		 *		  { 使用的Op, 在该Op输入中的index }
		 * @return 自身
		 */
		using ValueUsesInfo = std::vector<std::tuple<Operation, std::set<int64_t>>>;

		/**
		 * @brief 获取某个Value的使用信息
		 * @param v		目标Value
		 * @return ValueUsesInfo表示的使用信息
		 */
		XIR_DLL ValueUsesInfo getUsesInfo(const Value& v) const;

		/**
		 * @brief 获取某个Value的使用信息，排除匹配结果中的算子
		 * @param v		目标Value
		 * @param match	匹配结果
		 * @return ValueUsesInfo表示的使用信息
		 */
		XIR_DLL ValueUsesInfo getUsesInfoExceptMatch(const Value& v, const MatchGroup& match) const;

		/**
		 * @brief 将(算子输出)Value连接到算子to的第index个输入
		 * @param from	源Value
		 * @param to	目标算子
		 * @param index	算子的第index个输入
		 * @return 自身
		 */
		XIR_DLL Network& connect(const Value& from, Operation to, uint64_t index);

		/**
		 * @brief 将(算子输出)Value连接到算子to最后一个输入
		 * @param from	源Value
		 * @param to	目标算子
		 * @return 自身
		 */
		XIR_DLL Network& connect(const Value& from, Operation to);

		/**
		 * @brief 将(算子输出)Value连接到ValueUsesInfo表示的目标
		 * @param from	源Value
		 * @param to	目标
		 * @return 自身
		 */
		XIR_DLL Network& connect(const Value& from, const ValueUsesInfo& to);

		/** 获取网络的NetworkRewriter */
		XIR_DLL NetworkRewriter& rewriter() const;

		/** 将该网络转换为NetworkView */
		XIR_DLL operator NetworkView() const;

		/** 验证Network是否符合规范 */
		XIR_DLL void validate() const;

	private:
		int64_t genValueId();
		int64_t genOpId();
		void calcMd5(bool enable = true) const;

		friend class Operation;
		friend class Value;
	};

	/**
	 * @brief 网络的重写器，提供continue和break方法控制重写过程
	 * 默认的重写过程会重复从头匹配网络，而continue可以使其从上一个匹配位置继续，
	 * break会直接中断重写过程。
	 */
	class NetworkRewriter {
	public:
		/** 从上次匹配的位置继续匹配和重写 */
		void Continue() { is_continue = true; }

		/** 中断重写过程 */
		void Break() { is_break = true; }

	private:
		bool is_continue = false;
		bool is_break = false;
		uint64_t current = 0;

		XIR_DLL void rewrite(Network& network, const Pattern& pattern, Network::PatternCallback callback, uint64_t times);

		friend class Network;
	};

	/**
	 * @brief 表示网络视图的类
	 * 网络视图表示网络中部分算子及其连接关系组成的子图
	 */
	class NetworkViewNode : public NodeBase<NetworkViewNode, NetworkBaseNode> {
	public:
		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(NetworkViewNode* other, const ReduceVisitor& reduce) const;

	private:
		Array<Value> inputs_;
		Array<Value> outputs_;
		Network network_;
		friend class NetworkView;

		XIR_DLL virtual const Array<Value>& inputs() const override;
		XIR_DLL virtual const Array<Value>& outputs() const override;
	};

	/** 网络视图引用类 */
	class NetworkView : public HandleBase<NetworkView, NetworkBase, NetworkViewNode> {
	public:
		/** 默认构造函数 */
		NetworkView() = default;

	private:
		XIR_DLL NetworkView(const NetworkBase& network, Array<Operation> ops);

		friend class NetworkBase;

	public:
		/** 获取该网络视图对应的Network */
		XIR_DLL Network network() const;

		/** 将当前网络视图转为一个独立的网络，如果缺失输入输出会自动补全 */
		XIR_DLL Network toNetwork() const;

		/**
		 * @brief 修改NetworkView的输出Value的顺序
		 * @param value_ids	输出Value的vid
		 * @return 自身
		 * @throw 传入的vid必须与原来的vid仅有顺序上的差异，否则抛出异常
		 */
		XIR_DLL NetworkView& setOutputsOrderByValueIds(const std::vector<int64_t>& value_ids);
	};
}
