#pragma once
#ifndef HOSTBKND_BACKEND_PCH_GUARD
#define HOSTBKND_BACKEND_PCH_GUARD
#include <icraft-xrt/core/backend.h>
#include <icraft-xrt/core/device.h>
#include "icraft-backends/hostbackend/dllexport.h"

namespace icraft {
	namespace xrt {
		/**
		 * @brief 表示Host类型后端, 后端表示一种计算资源，包含了所有其所支持的算子在该计算资源的前向实现
		 */
		class HostBackendNode : public NodeBase<HostBackendNode, BackendNode> {
		public:

			HOSTBKND_DLL HostBackendNode();

			HOSTBKND_DLL virtual void init(const NetworkView& networkview, const Device& device) override;

			HOSTBKND_DLL virtual void deinit() override;

			HOSTBKND_DLL virtual void apply() override {};

			HOSTBKND_DLL virtual void view(uint64_t start_index, uint64_t end_index) override {};

			HOSTBKND_DLL virtual Backend fork() override;

			HOSTBKND_DLL virtual MergedOps autoMerge() override;

			HOSTBKND_DLL virtual Operation serialize(int64_t op_id) override;

			~HostBackendNode();

			friend class HostBackend;

		private:
			struct HostBkndParams;
			std::unique_ptr<HostBkndParams> params_;
			class HostBkndUtilFuncs;
			std::unique_ptr<HostBkndUtilFuncs> ufs_;
		};

		/** @brief Host类型后端引用类 */
		class HostBackend : public HandleBase<HostBackend, Backend, HostBackendNode> {
		public:
			/**
			 * @brief   设置HostBackend是否以fakeQf模式运行，fakeQf模式下定点前向不做截位和饱和，
			 *			主要用来对比adapted和generated算子前向结果
			 * @param	fakeQf	是否开启fakeQf模式
			 */
			HOSTBKND_DLL void setFakeQf(bool fakeQf);

			/**
			 * @brief   查询是否已开启fakeQf模式
			 * @return	是否已开启fakeQf模式
			 */
			HOSTBKND_DLL bool getFakeQf() const;

			/**
			 * @brief   设置HostBackend指令仿真时是否使用fireby仿真器;
			 * @param	enable_fireby	是否使用fireby仿真
			 */
			HOSTBKND_DLL void setCodeSimFireby(bool enable_fireby);

			/**
			 * @brief   查询是否使用fireby仿真
			 * @return	是否使用fireby仿真
			 */
			HOSTBKND_DLL bool getCodeSimFireby() const;

			/**
			 * @brief   设置CPU前向推理时算子库自动启用的线程数, 在某些情况下占用过多资源会导致问题，需要手动降低线程数
			 *			该变量是全局变量, 即不同的HostBackend对象共享该设置
			 * @param	num_threads  期望用于CPU推理加速的线程数
			 */
			HOSTBKND_DLL static void setThreadsNum(int num_threads);

			/**
			 * @brief   查询CPU前向推理时算子库自动启用的线程数, 该变量是全局变量, 即不同的HostBackend对象共享该设置
			 * @return	线程数
			 */
			HOSTBKND_DLL static int getThreadsNum();

			/**
			 * @brief   仅在BY指令仿真时有效，如果存在的话以指定的格式dump合并算子之后HardOp的中间Ftmps中指定id的Ftmps
			 * @param	ids	 希望dump的ftmp
			 * @param	path dump文件夹路径
			 * @param	format	dump的format
			 */
			HOSTBKND_DLL void dumpHiddenFtmp(const std::vector<int64_t>& ids, const std::string& path, const std::string& format = "");


			/**
			 * @brief   (开发接口)获取HostBackendUtilFuncs
			 * @return	HostBackendUtilFuncs
			 */
			HOSTBKND_DLL HostBackendNode::HostBkndUtilFuncs* getUFs() const;
		};



		using HostFInitOp = std::function<void(const xir::Operation&, HostBackend)>;
		using HostFForwardOp = std::function<std::vector<Tensor>(
			const xir::Operation&, 
			const std::vector<Tensor>&, 
			const std::vector<Tensor>&, 
			HostBackend)>;

		/**
		 * @brief HostBackend算子注册辅助类，用来管理HostBackend各Target上的Op初始化和前向函数
		 */
		class HostBkndOpFuncManager {
		public:
			//HostBkndOpFuncManager();
			~HostBkndOpFuncManager();
			HostBkndOpFuncManager(std::string_view op_type);

			void add_init(std::string_view target_type, HostFInitOp init_func);

			void add_forward(std::string_view target_type, HostFForwardOp forward_func);

			void run_op_init_func(const xir::Operation& op, HostBackend backend);

			std::vector<xrt::Tensor> run_op_forward_func(
				const xir::Operation& op, 
				const std::vector<Tensor>& inputs, 
				const std::vector<Tensor>& outputs,
				HostBackend backend
			);

		private:
			HostBkndOpFuncManager& operator=(const HostBkndOpFuncManager&) = delete;
			struct ManagerParams;
			std::unique_ptr<ManagerParams> params_;
		};

		/**
		 * @brief HostBackend算子注册辅助类，用来提供HostBackend各Target上的Op初始化和前向函数绑定到Backend的注册接口
		 */
		class HostBkndOpFuncRegister {
		public:
			template <
				typename OpType,
				typename TargetType,
				typename = typename std::enable_if_t<
				std::is_base_of_v<Operation, OpType>>,
				typename = typename std::enable_if_t<
				std::is_base_of_v<xir::CompileTarget, TargetType>>
				>
				static HostBkndOpFuncRegister* RegOpTargetFuncs(
					std::function<void(const OpType&, HostBackend)> initFuncParam,
					std::function<std::vector<Tensor>(
						const OpType&, 
						const std::vector<Tensor>& ,
						const std::vector<Tensor>&, 
						HostBackend)> forwardFuncParam
				)
			{
				auto instance = getInstance();
				auto& func_map = instance->hostbknd_op_func_manager_map;
				if (func_map.find(OpType::NodeType::type_key) == func_map.end()) {
					std::string_view op_type = OpType::NodeType::type_key;
					func_map.emplace(op_type, std::make_unique<HostBkndOpFuncManager>(op_type));
					auto& new_op_func_manager = func_map[OpType::NodeType::type_key];
					auto op_init_func =
						[&new_op_func_manager](const xir::Operation& op, HostBackend backend) {
						new_op_func_manager->run_op_init_func(op, backend);
						};
					auto op_forward_func =
						[&new_op_func_manager](const xir::Operation& op, const std::vector<Tensor>& inputs, const std::vector<Tensor>& outputs, HostBackend backend) {
						return new_op_func_manager->run_op_forward_func(op, inputs, outputs, backend);
						};
					ICRAFT_ADD_OP_TO_BACKEND(OpType, HostBackend)
						.set_init(op_init_func)
						.set_forward(op_forward_func);
				}
				auto& op_func_manager = func_map[OpType::NodeType::type_key];
				auto f_init = [=](const xir::Operation& op, Backend backend) {
					initFuncParam(op.cast<OpType>(), backend.cast<HostBackend>());
					};
				op_func_manager->add_init(TargetType::NodeType::type_key, f_init);
				auto f_forward = [=](const xir::Operation& op, const std::vector<Tensor>& inputs, const std::vector<Tensor>& outputs, Backend backend) {
					return forwardFuncParam(op.cast<OpType>(), inputs, outputs, backend.cast<HostBackend>());
					};
				op_func_manager->add_forward(TargetType::NodeType::type_key, f_forward);
				return instance;
			};
		private:
			static HostBkndOpFuncRegister* getInstance();
			HostBkndOpFuncRegister() {};
			~HostBkndOpFuncRegister();
			HostBkndOpFuncRegister(const HostBkndOpFuncRegister&) = delete;
			HostBkndOpFuncRegister& operator=(const HostBkndOpFuncRegister&) = delete;
			//内部维护的ManagerMap
			std::unordered_map<std::string_view, std::unique_ptr<HostBkndOpFuncManager>>  hostbknd_op_func_manager_map = {};
		};
	}
}

#define ICRAFT_HOSTBKND_REG_OP_FUNC_VAR_DEF 			\
  static ICRAFT_ATTRIBUTE_UNUSED auto __reg_op_hostbknd_func_var_def

#define ICRAFT_ADD_HOSTBKND_OP(OpType, TargetType, initFunc, forwardFunc) 	\
ICRAFT_STR_CONCAT(ICRAFT_HOSTBKND_REG_OP_FUNC_VAR_DEF, __COUNTER__) = \
icraft::xrt::HostBkndOpFuncRegister::RegOpTargetFuncs<OpType, TargetType>(initFunc, forwardFunc)

#endif //HOSTBKND_BACKEND_PCH_GUARD
