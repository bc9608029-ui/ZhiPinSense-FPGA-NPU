#pragma once
#ifndef ICRAFT_XIR_CORE_PASS_H_
#define ICRAFT_XIR_CORE_PASS_H_
#include <icraft-xir/core/node.h>
#include <icraft-xir/core/reflection.h>
#include <icraft-xir/base/array.h>
#include <icraft-xir/base/map.h>
#include <icraft-xir/base/string.h>
#include <icraft-xir/base/with.h>
#include <icraft-utils/dll.h>
#include <type_traits>
#include <utility>

namespace icraft::xir {

	/** 表示Pass上下文的类型 */
	class PassContextNode : public NodeBase<PassContextNode, Node> {
	public:
		uint64_t top_level{ LLONG_MAX };	///< 该上下文支持Pass的最高等级
		Array<String> required_passes;		///< 该上下文需要的前置Pass
		Array<String> disabled_passes;		///< 该上下文禁用的Pass
		Map<String, ObjectRef> config;		///< 该上下文的配置

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;
	};


	class PassInfo;


	/** 表示Pass上下文的引用类 */
	class PassContext : public HandleBase<PassContext, Handle, PassContextNode> {
	public:
		/** 默认构造函数 */
		PassContext() = default;

		/**
		 * @brief 构造函数
		 * @param top_level			上下文支持Pass的最高等级
		 * @param required_passes	上下文需要的前置Pass, 默认为空
		 * @param disabled_passes	上下文禁用的Pass, 默认为空
		 * @param config			上下文的配置, 默认为空
		 */
		XIR_DLL explicit PassContext(uint64_t top_level, Array<String> required_passes = {},
			Array<String> disabled_passes = {}, Map<String, ObjectRef> config = {});

		/** 获取一个初始化的上下文*/
		XIR_DLL static PassContext Init();

		/** 获取当前作用域下的上下文 */
		XIR_DLL static PassContext& Current();

		/**
		 * @brief 为上下文添加前置Pass
		 * @param pass_name 被添加Pass的名字
		 * @return 自身
		 */
		XIR_DLL PassContext& requirePass(const std::string& pass_name);

		/**
		 * @brief 为上下文移除前置Pass
		 * @param pass_name 被移除Pass的名字
		 * @return 自身
		 */
		XIR_DLL PassContext& removeRequiredPass(const std::string& pass_name);

		/**
		 * @brief 为上下文添加禁用Pass
		 * @param pass_name 被禁用Pass的名字
		 * @return 自身
		 */
		XIR_DLL PassContext& disablePass(const std::string& pass_name);

		/**
		 * @brief 为上下文移除禁用Pass
		 * @param pass_name 被禁用Pass的名字
		 * @return 自身
		 */
		XIR_DLL PassContext& removeDisabledPass(const std::string& pass_name);

		/**
		 * @brief 为上下文添加配置
		 * @param key	配置的键
		 * @param value 配置的值
		 * @return 自身
		 */
		XIR_DLL PassContext& setConfig(const std::string& key, ObjectRef value);

		/**
		 * @brief 获取上下文的配置
		 * @tparam				配置的类型
		 * @param key			配置的键
		 * @param default_value 如果配置不存在则使用的默认值
		 */
		template <typename T, typename = typename std::enable_if_t<(std::is_base_of_v<ObjectRef, T>)>>
		Optional<T> getConfig(const std::string& key, Optional<T> default_value = NullOpt) const {

			if (!(*this)->config.defined()) {
				return default_value;
			}

			if ((*this)->config.count(key)) {
				return Downcast<Optional<T>>((*this)->config[key]);
			}

			return default_value;
		}

		/**
		 * @brief 获取上下文的配置(为实现自动类型转换的重载)
		 * @tparam				配置的类型
		 * @param key			配置的键
		 * @param default_value 如果配置不存在则使用的默认值
		 */
		template <typename T, typename = typename std::enable_if_t<(std::is_base_of_v<ObjectRef, T>)>>
		Optional<T> getConfig(const std::string& key, T default_value) const {
			return getConfig<T>(key, Optional<T>(default_value));
		}

		/**
		 * @brief 检查指定的PassInfo表示的Pass是否可以在该上下文中执行
		 *		  可以执行的条件如下：
		 *		  *	1. 该Pass没有被禁用
		 *		  *	2. 该Pass优化等级小于等于上下文允许的最大等级
		 * @param info	指定的PassInfo
		 * @return 如果可执行则返回true
		 */
		XIR_DLL bool isPassEnabled(const PassInfo& info) const;

		XIR_DLL void _enterWithScope();
		XIR_DLL void _exitWithScope();
	};


	/** 表示Pass信息的类型 */
	class PassInfoNode : public NodeBase<PassInfoNode, Node> {
	public:
		String name;					///< Pass的名称
		uint64_t opt_level;				///< Pass的优化等级
		Array<String> required_passes;	///< Pass需要的前置Pass

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;
	};


	/** 表示Pass信息的引用类型 */
	class PassInfo : public HandleBase<PassInfo, Handle, PassInfoNode> {
	public:
		/** 默认构造函数 */
		PassInfo() = default;

		/**
		 * @brief 构造函数
		 * @param name				Pass的名称
		 * @param opt_level			Pass的优化等级, 默认为0
		 * @param required_passes	Pass需要的前置Pass, 默认为空
		 */
		XIR_DLL PassInfo(String name, uint64_t opt_level = 0, Array<String> required_passes = {});
	};


	class Network;


	/** Pass抽象了对网络的增删查改等访问 */
	class PassNode : public NodeBase<PassNode, Node> {
	public:
		PassInfo pass_info;		///< Pass的信息

		virtual void accept(AttrVisitor& visitor) override {
			visitor.visit("pass_info", pass_info);
		};

		/**
		 * @brief 执行Pass的接口
		 * @param network	输入网络
		 * @param pass_ctx	Pass的上下文
		 * @return 输出网络
		 */
		virtual Network operator()(Network network, const PassContext& pass_ctx) const = 0;
	};


	/** Pass的引用类 */
	class Pass : public VirtualBase<Pass, Handle, PassNode> {
	public:
		/**
		 * @brief 执行Pass
		 * @param network	输入网络
		 * @param pass_ctx	Pass的上下文, 默认为当前作用域下的上下文
		 * @return 输出网络
		 */
		XIR_DLL Network operator()(Network network, const PassContext& pass_ctx = PassContext::Current()) const;

		/**
		 * @brief 根据名字创建一个Pass
		 * @param name		Pass的名字
		 * @param dll_path	Pass所在的DLL路径，如果指定，则从该路径加载DLL，不再搜索。默认为空
		 * @param env_var	环境变量，如果指定，则尝试从该环境变量指定的路径中搜索
		 *					当不指定dll_path时，会先尝试搜索env_var，然后搜索xir的动态链接库所在路径
		 */
		XIR_DLL static Pass Create(const std::string& name, const icraft::midware::path& dll_path = {}, const std::string& env_var = "");
		template <typename PathType,
			std::enable_if_t<
				!std::is_same_v<std::remove_cv_t<std::remove_reference_t<PathType>>, icraft::midware::path> &&
				std::is_constructible_v<icraft::midware::path, PathType>, int> = 0>
		static Pass Create(const std::string& name, PathType&& dll_path, const std::string& env_var = "") {
			return Create(name, icraft::midware::path(std::forward<PathType>(dll_path)), env_var);
		}
		/**
		 * @brief 设置Pass的名字
		 * @param name				Pass的名称
		 */
		XIR_DLL Pass& setName(String name);

		/**
		 * @brief 设置Pass的优化等级
		 * @param opt_level			Pass的优化等级
		 */
		XIR_DLL Pass& setOptLevel(uint64_t opt_level);

		/**
		 * @brief 设置Pass的前置Pass
		 * @param required_passes	Pass需要的前置Pass
		 */
		XIR_DLL Pass& setRequiredPasses(Array<String> required_passes);

		/**
		 * @brief 设置Pass的信息
		 * @param pass_info		Pass的信息
		 */
		XIR_DLL Pass& setPassInfo(PassInfo pass_info);
	};


	/**
	 * @brief 表示网络Pass的类型
	 *		  NetworkPass会对输入的Network调用执行函数进行处理，然后返回处理后的Network
	 */
	class NetworkPassNode : public NodeBase<NetworkPassNode, PassNode> {
	public:
		std::function<Network(Network, const PassContext&)> pass_func;	///< Pass的执行函数

		/**
		 * @brief 实现执行Pass接口
		 * @param network	输入网络
		 * @param pass_ctx	Pass的上下文, 默认为当前作用域下的上下文
		 * @return 输出网络
		 */
		XIR_DLL virtual Network operator()(Network network, const PassContext& pass_ctx) const override final;
	};


	/** 网络Pass的引用类 */
	class NetworkPass : public HandleBase<NetworkPass, Pass, NetworkPassNode> {
	public:
		/** 默认构造函数 */
		NetworkPass() = default;

		/**
		 * @brief 构造函数.
		 * @param pass_func			Pass的执行函数
		 * @param name				Pass的名称
		 * @param opt_level			Pass的优化等级，默认为0
		 * @param required_passes	Pass的前置Pass，默认为空
		 */
		NetworkPass(
			std::function<Network(Network, const PassContext&)> pass_func,
			String name,
			uint64_t opt_level = 0,
			Array<String> required_passes = {}
		) : NetworkPass(pass_func, PassInfo(std::move(name), opt_level, std::move(required_passes)))
		{}

		/**
		 * @brief 构造函数
		 * @param pass_func	Pass的执行函数
		 * @param pass_info	Pass的信息
		 */
		XIR_DLL NetworkPass(std::function<Network(Network, const PassContext&)> pass_func, PassInfo pass_info);
	};


	/**
	 * @brief 表示Pass序列的类型
	 *		  Pass序列即一系列Pass组成的一个Pass, 该Pass执行时会依次执行每一个Pass
	 */
	class SequentialPassNode : public NodeBase<SequentialPassNode, PassNode> {
	public:
		Array<Pass> passes;		///< Pass列表

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		/**
		 * @brief 实现执行Pass接口
		 * @param network	输入网络
		 * @param pass_ctx	Pass的上下文, 默认为当前作用域下的上下文
		 * @return 输出网络
		 */
		XIR_DLL virtual Network operator()(Network network, const PassContext& pass_ctx) const override final;
	};


	/** Pass序列的引用类 */
	class SequentialPass : public HandleBase<SequentialPass, Pass, SequentialPassNode> {
	public:
		/** 默认构造函数 */
		SequentialPass() = default;

		/**
		 * @brief 构造函数
		 * @param pass_names			Pass的列表
		 * @param name					Pass的名称
		 * @param opt_level				Pass的优化等级，默认为0
		 * @param required_passes		Pass的前置Pass，默认为空
		 * @param env_var				指定搜索Pass动态链接库的环境变量
		 */
		SequentialPass(
			const std::vector<std::string>& pass_names,
			String name,
			uint64_t opt_level = 0,
			Array<String> required_passes = {},
			const std::string& env_var = ""
		) : SequentialPass(pass_names, PassInfo(std::move(name), opt_level, std::move(required_passes)), env_var)
		{}

		/**
		 * @brief 构造函数.
		 * @param pass_func			Pass的执行函数
		 * @param name				Pass的名称
		 * @param opt_level			Pass的优化等级，默认为0
		 * @param required_passes	Pass的前置Pass，默认为空
		 */
		SequentialPass(
			Array<Pass> passes,
			String name,
			uint64_t opt_level = 0,
			Array<String> required_passes = {}
		) : SequentialPass(std::move(passes), PassInfo(std::move(name), opt_level, std::move(required_passes)))
		{}

		/**
		 * @brief 构造函数
		 * @param pass_names	Pass名称列表
		 * @param pass_info		Pass信息, 默认为Pass名为sequential
		 * @param env_var		指定搜索Pass动态链接库的环境变量
		 */
		XIR_DLL SequentialPass(
			const std::vector<std::string>& pass_names,
			PassInfo pass_info = PassInfo("sequential"),
			const std::string& env_var = ""
		);

		/**
		 * @brief 构造函数
		 * @param passes	Pass列表
		 * @param pass_info	Pass信息, 默认为Pass名为sequential
		 */
		XIR_DLL SequentialPass(Array<Pass> passes, PassInfo pass_info = PassInfo("sequential"));
	};
}

#endif // ICRAFT_XIR_CORE_PASS_H_
