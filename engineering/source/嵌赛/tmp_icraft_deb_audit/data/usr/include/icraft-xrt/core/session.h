#pragma once
#ifndef XRT_SESSION_PCH_GUARD
#define XRT_SESSION_PCH_GUARD
//#include "filesystem/filesystem.h"
#include <icraft-xrt/core/backend.h>
#include <icraft-xir/core/network.h>
#include <icraft-xrt/utils/validator.h>

namespace icraft::xrt {
	using xir::Network;
	using xir::Array;

	/**
	 * @brief 表示会话的类型.
	 */
	class SessionNode : public NodeBase<SessionNode, Node> {
	public:
		XRT_DLL SessionNode();
		std::vector<Backend> backends;	///< 会话中的后端
		NetworkView network_view;		///< 会话中的网络视图

		virtual void accept(AttrVisitor& visitor) override {};
	
		XRT_DLL ~SessionNode();

	private:
		std::vector<std::tuple<Operation, Backend, FForwardOp, std::vector<int64_t>, std::vector<int64_t>>> forwards_;
		std::unordered_map<int64_t, Tensor> tmap_;
		std::unordered_map<int64_t, uint64_t> tuses_;
		std::unordered_map<int64_t, uint64_t> index_map_;
		std::vector<int64_t> network_input_ids_;
		std::vector<int64_t> network_output_ids_;

		uint64_t current_index_ = 0;

		bool time_profile_ = false;
		bool applied = false;
		std::unordered_map<int64_t, double> wall_times_;
		std::chrono::nanoseconds total_time_;

		bool backends_need_deinit = false;

		bool log_time_ = false;
		bool log_io_ = false;

		char* map_ptr = nullptr;
		uint64_t map_byte_size;
		
		bool dump_output_ = false;
		std::string dump_path_;
		std::string dump_format_;

		utils::Validation validation;

		friend class Session;
	};

	/**
	 * @brief 表示时间分析结果的类型.
	 * 该类型是一个Map，其键表示Op ID，值表示不同的时间类型，依次如下：
	 * * 总时间，即墙上时间
	 * * 数据复制时间
	 * * 硬件计算时间
	 * * 其他时间
	 */
	using TimeProfileResults = std::unordered_map<int64_t, std::tuple<double, double, double, double>>;

	/** @brief 会话的引用类 */
	class Session : public HandleBase<Session, Handle, SessionNode> {
	public:
		/** 默认构造函数 */
		Session() = default;

		/**
		 * @brief 创建一个会话，按优先级绑定到指定的后端.
		 * @tparam	BackendType	会话绑定的后端类型列表
		 * @param	network		网络视图
		 * @param	devices		设备列表
		 * 
		 * @note 设备列表中的Device和后端类型列表中的后端是一一对应的
		 */
		template <typename... BackendType>
		static Session Create(const NetworkView& network, const std::vector<Device>& devices) {
			auto backends = std::vector<Backend>{ BackendType::Init()... };
			auto sess = Session::Init();
			sess.bindToBackendsByOrder(network, std::move(backends), devices, true);
			return sess;
		}

		/**
		 * @brief 创建一个会话，按优先级绑定到指定的后端.
		 * @param	network		网络视图
		 * @param	backends	后端列表
		 * @param	devices		设备列表
		 *
		 * @note 设备列表中的Device和后端类型列表中的后端是一一对应的
		 */
		XRT_DLL static Session CreateByOrder(
			const NetworkView& network,
			std::vector<Backend> backends,
			const std::vector<Device>& devices
		);

		/**
		 * @brief 创建一个会话，使用绑定好网络和设备的后端.
		 * @param	network		网络视图
		 * @param	backends	后端列表
		 *
		 * @note 后端列表中的Backend已经完成了网络视图和设备的绑定
		 */
		XRT_DLL static Session CreateWithBackends(const NetworkView& network, const std::vector<Backend>& backends);

		/**
		 * @brief 从该session创建一个新的session, 共享相同的backends, 但是network_view不同.
		 * @param start_index	NetworkView包含的算子在原网络中的开始索引(包含)，支持负数索引
		 * @param end_index		NetworkView包含的算子在原网络中的结束索引(不包含)，支持负数索引
		 * @return 创建的session
		 */
		XRT_DLL Session sub(int64_t start_index, int64_t end_index) const;

		/**
		 * @brief 从该session创建一个新的session, 共享相同的backends, 但是network_view不同.
		 * @param start_index	NetworkView包含的算子在原网络视图中的开始索引(包含)，支持负数索引
		 * @return 创建的Session
		 */
		XRT_DLL Session sub(int64_t start_index) const;

		/** 应用Session的一些选项 */
		XRT_DLL void apply();

		/**
		 * @brief 使能时间分析功能.
		 * @param	enable	是否使能
		 */
		XRT_DLL void enableTimeProfile(bool enable);

		/**
		 * @brief 前向到指定的算子.
		 * @param	op_id	指定算子的Op ID
		 * @param	inputs	输入的Tensor列表
		 * @return	指定算子的前向结果
		 * 
		 * @note	只有在算子的输入来自外部时，才会取输入Tensor列表中的，否则使用生产者算子产生的Tensor
		 */
		XRT_DLL std::vector<Tensor> stepTo(int64_t op_id, const std::vector<Tensor>& inputs = {});

		/**
		 * @brief 前向会话中绑定的整个网络视图
		 * @param	inputs	输入的Tensor列表
		 * @return	整个网络视图的前向结果
		 */
		XRT_DLL std::vector<Tensor> forward(const std::vector<Tensor>& inputs);

		/**
		 * @brief 前向会话中绑定的整个网络视图
		 * @param	inputs	输入的Tensor列表
		 * @param	outputs	输出的Tensor列表
		 */
		XRT_DLL void forward(const std::vector<Tensor>& inputs, const std::vector<Tensor>& outputs);

		/**
		 * @brief 获取会话中所有算子的后端绑定关系.
		 * @return	Map表示的算子后端绑定关系，其键为Op ID, 值为该算子绑定的后端
		 */
		XRT_DLL std::unordered_map<int64_t, Backend> backendBindings() const;

		/**
		 * @brief	获取时间分析的结果.
		 * 
		 * @sa TimeProfileResults
		 */
		XRT_DLL TimeProfileResults timeProfileResults() const;

		/**
		 * @brief 获取会话总时间.
		 * @tparam T	时间单位类型，支持std::chrono::seconds等单位
		 * @return	指定单位下的总时间
		 */
		template <typename T>
		double totalTime() const {
			return std::chrono::duration<double, typename T::period>((*this)->total_time_).count();
		}

		/**
		* @brief 回调函数类型
		*/
		using CallBackFunc = std::function<void(const Session& sess, const Operation& op, const Backend& backend, std::vector<Tensor>& output_tensors)>;

		/**
		* @brief 向会话添加回调函数，通过该接口配置的回调函数将在每个算子执行前向之前被调用
		* @param 回调函数
		*/
		XRT_DLL void setPreCallBack(CallBackFunc func);

		/**
		* @brief 向会话添加回调函数，通过该接口配置的回调函数将在每个算子执行前向之前被调用
		* @param 回调函数
		*/
		XRT_DLL void setPostCallBack(CallBackFunc func);

		/**
		* @brief 前向算子类型
		*/
		using ForwardOps = std::vector<std::tuple<Operation, Backend, FForwardOp, std::vector<int64_t>, std::vector<int64_t>>>;

		/**
		* @brief 获取会话的前向算子列表
		* @return 前向算子列表
		*/
		XRT_DLL const ForwardOps& getForwards();

		/**
		* @brief 设置每层前向结束后是否打印IO信息，默认关闭
		* @param 开启标志
		*/
		XRT_DLL void setLogIO(bool flag);

		/**
		* @brief 设置每层前向结束后是否打印耗时信息，默认关闭
		* @param 开启标志
		*/
		XRT_DLL void setLogTime(bool flag);

		/**
		* @brief 设置每层前向结束后是否保存输出结果至指定路径下，默认关闭
		* @param flag 开启标志
		* @param path 保存输出结果路径
		* @param format 指定的输出格式
		* 
		* @note 支持的格式由三个字母表示：
		* 第一个字母表示排布，H表示硬件，S表示软件
		* 第二个字母表示数值，F表示浮点，Q表示定点
		* 第三个字母表示序列化形式，B表示二进制，T表示文本
		* 若一个Tensor原本的排布时H，那么可以转为S；若原本的数值为Q，那么可以转为F；反之不可
		*/
		XRT_DLL void setDumpOutputs(bool flag, const std::string& file_path, const std::string& format);

		/**
		* @brief 对当前session进行序列化得到二进制文件
		* @param filePath 二进制文件保存路径
		*/
		XRT_DLL void dumpSnapshot(const std::string& filePath);

		/**
		* @brief 根据二进制文件反序列化得到session
		* @param filePath 二进制文件保存路径
		* @param backends 后端列表
		* @param devices 设备列表
		*/
		XRT_DLL static Session CreateWithSnapshot(
			const std::string& filePath,
			std::vector<Backend> backends,
			const std::vector<Device>& devices);
        

	private:
		XRT_DLL void bindToBackendsByOrder(
			const NetworkView& network,
			std::vector<Backend> backends,
			const std::vector<Device>& devices,
			bool backends_need_deinit
		);
		CallBackFunc pre_callback_;
		CallBackFunc post_callback_;

		void logIO(const Operation& op, Backend& backend);
		void logTime(const Operation& op, Backend& backend);
		void dumpOutput(const std::vector<Tensor>& output_tensors, const std::vector<xir::Value>& outputs);
	};
}
#endif //XRT_SESSION_PCH_GUARD