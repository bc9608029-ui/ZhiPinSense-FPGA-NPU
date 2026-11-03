#pragma once
#ifndef XRT_HOST_DEVICE_PCH_GUARD
#define XRT_HOST_DEVICE_PCH_GUARD
#include <icraft-xrt/core/device.h>

namespace icraft::xrt {
	/** @brief 表示Host上内存区域的类型 */
	class HostMemRegionNode : public NodeBase<HostMemRegionNode, MemRegionNode> {
	private:
		virtual void init() override {};

		virtual void deinit() override {};

		XRT_DLL virtual void read(char* dest, const MemPtr& src, uint64_t byte_size) const override;

		XRT_DLL virtual void write(const MemPtr& dest, char* src, uint64_t byte_size) const override;

		XRT_DLL virtual MemChunk malloc(uint64_t byte_size, bool auto_free, uint64_t alignment) const override;

		XRT_DLL virtual MemChunk malloc(MemPtr begin, uint64_t byte_size, FChunkDeleter deleter, bool auto_free) const override;

		XRT_DLL virtual void free(const MemPtr& src) const override;

		XRT_DLL virtual void memcpy(const MemPtr& dest, const MemPtr& src, uint64_t byte_size) const override;
	};

	/**
	 * @breif Host内存区域的引用类型.
	 */
	class HostMemRegion : public HandleBase<HostMemRegion, MemRegion, HostMemRegionNode> {};

	/** @brief 跟踪 host-backed 分配块的内存管理器类型. */
	class HostBackedMemManagerNode : public NodeBase<HostBackedMemManagerNode, MemManagerNode> {
	public:
		XRT_DLL virtual MemChunk malloc(uint64_t byte_size, bool auto_free, uint64_t alignment) override;

		XRT_DLL virtual MemChunk malloc(MemPtr begin, uint64_t byte_size, FChunkDeleter deleter, bool auto_free) override;

		XRT_DLL virtual void free(const MemPtr& ptr) override;

		XRT_DLL virtual std::vector<MemChunk> getAllMemChunk() const override;

		XRT_DLL virtual std::map<std::string, ObjectRef>& getMemRegionInfo() const override;

		XRT_DLL void track(const MemChunk& chunk) const;

		XRT_DLL void untrack(const MemPtr& ptr) const;

	private:
		struct TrackedChunk {
			MemPtr begin;
			uint64_t byte_size = 0;
		};

		mutable std::vector<TrackedChunk> chunks_;
		mutable std::map<std::string, ObjectRef> info_;
		mutable midware::Mutex mem_mutex_;
	};

	class HostBackedMemManager : public HandleBase<HostBackedMemManager, MemManager, HostBackedMemManagerNode> {};

	/** @brief 表示带cache同步语义的Host内存区域类型. */
	class CacheSyncHostMemRegionNode : public NodeBase<CacheSyncHostMemRegionNode, MemRegionNode> {
	private:
		virtual void init() override {};

		virtual void deinit() override {};

		XRT_DLL virtual void read(char* dest, const MemPtr& src, uint64_t byte_size) const override;

		XRT_DLL virtual void write(const MemPtr& dest, char* src, uint64_t byte_size) const override;

		XRT_DLL virtual MemChunk malloc(uint64_t byte_size, bool auto_free, uint64_t alignment) const override;

		XRT_DLL virtual MemChunk malloc(MemPtr begin, uint64_t byte_size, FChunkDeleter deleter, bool auto_free) const override;

		XRT_DLL virtual void free(const MemPtr& src) const override;

		XRT_DLL virtual void memcpy(const MemPtr& dest, const MemPtr& src, uint64_t byte_size) const override;
	};

	/**
	 * @brief 带cache同步语义的Host内存区域引用类型.
	 */
	class CacheSyncHostMemRegion : public HandleBase<CacheSyncHostMemRegion, MemRegion, CacheSyncHostMemRegionNode> {};

	/**
	 * @brief 表示Host设备的类型.
	 */
	class HostDeviceNode : public NodeBase<HostDeviceNode, DeviceNode> {
	public:
		ICRAFT_DECLARE_DEVICE_NODE(HostDeviceNode) {
			ICRAFT_DEFAULT_MEM_REGION_FIELD(host, HostMemRegion);
			ICRAFT_REGION_MEM_MANAGER_FIELD(host, HostBackedMemManagerNode);
		}

		/** 实现init接口 */
		virtual void initBeforeRegions() override {};

		virtual void initAfterRegions() override {};

		/** 实现deinit接口 */
		virtual void deinitBeforeRegions() override {};

		virtual void deinitAfterRegions() override {};

		/** 实现reset接口 */
		virtual void reset(int level) override {};

		/** 实现check接口 */
		virtual bool check(int level) const override { return true; };

		/** 实现showStatus接口 */
		virtual void showStatus(int level) const override {};

		/** 实现version接口 */
		virtual std::unordered_map<std::string, std::string> version() const override { 
			return {};
		};

		xir::Array<xir::CompileTarget> compileTargets() const override {
			return { xir::HostTarget::Init() };
		}
	};

	class HostDevice : public HandleBase<HostDevice, Device, HostDeviceNode> {
	public:
		/**
		 * @brief 获取全局默认的HostDevice对象.
		 */
		XRT_DLL static HostDevice& Default();

		/**
		 * @brief 获取全局默认的HostDevice的内存区域对象.
		 */
		XRT_DLL static HostMemRegion& MemRegion();
	};
}
#endif //XRT_HOST_DEVICE_PCH_GUARD
