#pragma once
#ifndef XRT_BACKEND_PCH_GUARD
#define XRT_BACKEND_PCH_GUARD
#include <icraft-xrt/base/dllexport.h>
#include <icraft-xir/core/data.h>
#include <icraft-xir/core/network.h>
#include <icraft-xrt/core/tensor.h>
#include <icraft-xir/core/operation.h>
#include <string_view>
#include <unordered_map>
//#include <icraft-xrt/utils/serialize.h>

namespace icraft::xrt {
	using icraft::xir::Operation;
	using icraft::xir::NetworkView;

	class Backend;
	using FInitOp = std::function<void(const xir::Operation&, Backend)>;
	using FForwardOp = std::function<std::vector<Tensor>(const xir::Operation&, const std::vector<Tensor>&, const std::vector<Tensor>&, Backend)>;

	using FForwardBackend = std::function<std::vector<Tensor>(const NetworkView, const std::vector<Tensor>&, const std::map<int64_t, Tensor>&, Backend, const Device& device, uint8_t priority, uint64_t currIdx)>;//后端前向函数

	using MergedOp = std::pair<Operation, std::vector<Operation>>;
	using MergedOps = std::vector<MergedOp>;

	class BackendNode;

	/** @brief 后端引用类 */
	class Backend : public VirtualBase<Backend, Handle, BackendNode> {
	public:
		/**
		 * @brief 获取指定算子的初始化函数.
		 * @param	op	指定的算子
		 * @return	初始化函数的可选项
		 */
		XRT_DLL std::optional<FInitOp> getInitFunc(const Operation& op) const;

		/**
		 * @brief 获取指定算子的前向函数.
		 * @param	op	指定的算子
		 * @return	前向函数的可选项
		 */
		XRT_DLL std::optional<FForwardOp> getForwardFunc(const Operation& op) const;

		/**
		 * @brief 获取后端的前向函数.
		 * @return	前向函数的可选项
		 */
		XRT_DLL std::optional<FForwardBackend> getForwardFunc() const;


		/**
		 * @brief 检查指定算子是否被支持.
		 * @param	op	指定的算子
		 */
		XRT_DLL bool isOpSupported(const Operation& op) const;

		/**
		 * @brief 初始化指定的算子.
		 * @param	op	指定的算子
		 */
		XRT_DLL void initOp(const Operation& op);

		/**
		 * @brief 前向指定的算子.
		 * @param	op		指定的算子
		 * @param	inputs	输入的Tensors
		 * @param	outputs	输出的Tensors，默认为空
		 * @return 前向的结果
		 */
		XRT_DLL std::vector<Tensor> forwardOp(const Operation& op, const std::vector<Tensor>& inputs, const std::vector<Tensor>& outputs = {});

		/**
		 * @brief	初始化Backend
		 * @param	network_view	网络
		 * @param	device			设备
		 */
		XRT_DLL void init(const NetworkView& network_view, const Device& device);

		/**
		 * @brief	释放Backend
		 */
		XRT_DLL void deinit();

		/** 应用Backend的一些选型 */
		XRT_DLL void apply();

		/**
		 * @brief 使能时间分析.
		 * @param	enable	是否使能
		 */
		XRT_DLL void enableTimeProfile(bool enable);

		/**
		 * @brief 记录指定算子的前向时间.
		 * @param	op_id		指定的Op ID
		 * @param	memcpy_time	数据复制时间
		 * @param	hard_time	硬件计算时间
		 */
		XRT_DLL void setTimeElapses(int64_t op_id, double memcpy_time, double hard_time);


		/**
		* @brief 获取指定算子的前向时间
		* @param	op_id		指定的Op ID
		* @return	指定算子的前向时间
		*/
		XRT_DLL std::optional<const std::tuple<double, double>> getTimeElapses(int64_t op_id) const;

		XRT_DLL void view(uint64_t start_index, uint64_t end_index);

		XRT_DLL MergedOps autoMerge();

		/** 复制一个Backend用于多线程 */
		XRT_DLL Backend fork();

		/**
		* @brief	获得序列化当前算子所需的信息
		* @param	op_id 当前算子的id
		* @return	新的算子，与原算子区别在于更新了运行时相关信息
		*/
		XRT_DLL Operation serialize(int64_t op_id);

		/**
		* @brief 序列化当前算子相关信息
		* @param builder flatbuffer构建器对象
		* @param op_id 当前算子的id
		* @return 当前算子以及其输入输出的序列化对象
		*/
		//XRT_DLL std::tuple < SerializeOp,
			//std::vector< SerializeFtmp>> serialize(FlatbufferBuilder& builder, int64_t op_id);

		/**
		 * @brief 为Backend绑定Device.
		 * @param	device	被绑定的Device
		 * @return 自身
		 */
		XRT_DLL Backend& setDevice(Device device);

		/**
		 * @brief 创建指定类型的Backend.
		 * @tparam	BackendType	后端的类型
		 * @param	network_view	网络
		 * @param	device			设备
		 */
		template <typename BackendType>
		static BackendType Create(const NetworkView& network_view, const Device& device) {
			auto backend = BackendType::Init();
			backend.init(network_view, device);
			return backend;
		}

		XRT_DLL void enableSnapshot(bool enable);

	};

	/**
	 * @brief 表示后端的类型.
	 * 后端表示一种计算资源，包含了所有其所支持的算子在该计算资源的前向实现
	 */
	class BackendNode : public NodeBase<BackendNode, Node> {
	public:
		NetworkView network_view;		///< 绑定到该后端的网络试图
		Device device;					///< 绑定到该后端的设备
		bool time_profile = false;		///< 是否开启时间分析
		bool snapshot = false;			///< 是否是快照模式

	private:
		std::unordered_map<int64_t, std::tuple<double, double>> time_elapses_;

		virtual void accept(AttrVisitor& visitor) override {}

		virtual void init(const NetworkView& network_view, const Device& device) = 0;

		virtual void deinit() = 0;

		virtual void apply() = 0;

		virtual void view(uint64_t start_index, uint64_t end_index) = 0;

		virtual MergedOps autoMerge() = 0;

		virtual Backend fork() = 0;

		virtual Operation serialize(int64_t op_id){
			return Operation();
		}

		//virtual std::tuple < SerializeOp,
			//std::vector< SerializeFtmp>> serialize(FlatbufferBuilder& builder, int64_t op_id) = 0;

		friend class Backend;
		friend class Session;
	};

	using FOpConstraint = std::function<bool(const xir::Operation&, Backend)>;
	/** Op注册到Backend的辅助类型 */
	class BackendOpRegistry {
	public:
		class Manager;

		/** 设置Op初始化函数 */
		XRT_DLL BackendOpRegistry& set_init(FInitOp f);

		/** 设置Op前向函数 */
		XRT_DLL BackendOpRegistry& set_forward(FForwardOp f);

		/** 设置Backend前向函数 */
		XRT_DLL BackendOpRegistry& set_forward(FForwardBackend f);

		/** 设置Op约束 */
		XRT_DLL BackendOpRegistry& set_constraint(FOpConstraint f);

		/**
		 * @brief 注册算子函数到后端
		 * @param backend		后端的名字
		 * @param op			算子的名字
		 * @param can_override	是否允许覆盖, 默认为否
		 */
		XRT_DLL static BackendOpRegistry& Register(std::string_view backend, std::string_view op, bool can_override = false);

		/**
		 * @brief 注册前向函数到后端
		 * @param backend		后端的名字
		 * @param can_override	是否允许覆盖, 默认为否
		 */
		XRT_DLL static BackendOpRegistry& Register(std::string_view backend, bool can_override = false);

		/**
		 * @brief 移除注册的算子函数.
		 * @param backend	后端的名字
		 * @param op		算子的名字
		 * @return 如果算子函数不存在返回false, 否则返回true
		 */
		XRT_DLL static bool Remove(std::string_view backend, std::string_view op);

		/**
		 * @brief 获取注册的算子初始化函数
		 * @param backend	后端的名字
		 * @param op		算子的名字
		 * @return 算子初始化函数的Optional
		 */
		XRT_DLL static std::optional<FInitOp> GetInitFunc(std::string_view backend, std::string_view op);

		/**
		 * @brief 获取注册的算子前向函数
		 * @param backend	后端的名字
		 * @param op		算子的名字
		 * @return 算子初始化函数的Optional
		 */
		XRT_DLL static std::optional<FForwardOp> GetForwardFunc(std::string_view backend, std::string_view op);


		/**
		 * @brief 获取注册的后端前向函数
		 * @param backend	后端的名字
		 * @return 后端初始化函数的Optional
		 */
		XRT_DLL static std::optional<FForwardBackend> GetForwardFunc(std::string_view backend);


		/**
		 * @brief 获取注册的算子约束函数
		 * @param backend	后端的名字
		 * @param op		算子的名字
		 * @return 算子约束函数的Optional
		 */
		XRT_DLL static std::optional<FOpConstraint> GetConstraintFunc(std::string_view backend, std::string_view op);

		/** 获取所有注册后端和算子的名称列表 */
		XRT_DLL std::vector<std::vector<std::string_view>> ListNames();

	private:
		FInitOp finit_;
		FForwardOp fforward_;
		FForwardBackend fforward_backend_;
		FOpConstraint fconstraint_;
	};

/// @cond
	template <
		typename OpType, 
		typename BackendType,
		typename = typename std::enable_if_t<
		std::is_base_of_v<Operation, OpType>>,
		typename = typename std::enable_if_t<
		std::is_base_of_v<Backend, BackendType>>
	>
	class BackendOpRegisterHelper {
	public:
		BackendOpRegisterHelper() 
			: registry_(BackendOpRegistry::Register(BackendType::NodeType::type_key, OpType::NodeType::type_key))
			{}

		BackendOpRegisterHelper& set_init(std::function<void(const OpType&, BackendType)> func) {
			auto f = [=](const xir::Operation& op, Backend backend) {
				func(op.cast<OpType>(), backend.cast<BackendType>());
			};
			registry_.set_init(f);
			return *this;
		}

		BackendOpRegisterHelper& set_forward(
			std::function<std::vector<Tensor>(const OpType&, const std::vector<Tensor>&, const std::vector<Tensor>&, BackendType)> func
		) {
			auto f = [=](const xir::Operation& op, const std::vector<Tensor>& inputs, const std::vector<Tensor>& outputs, Backend backend) {
				return func(op.cast<OpType>(), inputs, outputs, backend.cast<BackendType>());
			};
			registry_.set_forward(f);
			return *this;
		}

		BackendOpRegisterHelper& set_constraint(
			std::function<bool(const OpType&, BackendType)> func
		) {
			auto f = [=](const xir::Operation& op, Backend backend) {
				return func(op.cast<OpType>(), backend.cast<BackendType>());
			};
			registry_.set_constraint(f);
			return *this;
		}
	private:
		BackendOpRegistry& registry_;
	};
}

#define ICRAFT_ADD_OP_TO_BACKEND_IMPL_VAR_DEF 			\
  static ICRAFT_ATTRIBUTE_UNUSED auto __add_op_to_backend_impl

#define ICRAFT_ADD_OP_TO_BACKEND(OpType, BackendType) 	\
ICRAFT_STR_CONCAT(ICRAFT_ADD_OP_TO_BACKEND_IMPL_VAR_DEF, __COUNTER__) = \
icraft::xrt::BackendOpRegisterHelper<OpType, BackendType>()

#define ICRAFT_REGISTER_FFUNC_TO_BACKEND(BackendType) 	\
auto ICRAFT_STR_CONCAT(ICRAFT_REGISTER_FFUNC_TO_BACKEND_IMPL_VAR_DEF, __COUNTER__) = \
icraft::xrt::BackendOpRegistry::Register(BackendType::type_key)


/// @endcond

#endif //XRT_BACKEND_PCH_GUARD