#pragma once
#include "icraft-xrt/core/device.h"
#include "icraft-backends/hostbackend/cuda/memory.h"
#include "icraft-backends/hostbackend/cuda/dllexport.h"


namespace icraft {
	namespace xrt {
		/**
		 * @brief 表示Cuda设备的类型.
		 */
		class CudaDeviceNode : public NodeBase<CudaDeviceNode, DeviceNode> {
		public:
			ICRAFT_DECLARE_DEVICE_NODE(CudaDeviceNode) {
				ICRAFT_DEFAULT_MEM_REGION_FIELD(cuda, CudaMemRegion);
			}

			/** 实现initBeforeRegions接口 */
			virtual void initBeforeRegions() override {};

			/** 实现initAfterRegions接口 */
			virtual void initAfterRegions() override {};

			/** 实现deinitBeforeRegions接口 */
			virtual void deinitBeforeRegions() override {};

			/** 实现deinitAfterRegions接口 */
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

			virtual xir::Array<xir::CompileTarget> compileTargets() const override {
				return { xir::HostTarget::Init() };
			}
		};

		class CudaDevice : public HandleBase<CudaDevice, Device, CudaDeviceNode> {
		public:
			/**
			 * @brief 获取全局默认的CudaDevice对象.
			 */
			CUDADEV_DLL static CudaDevice& Default();

			/**
			 * @brief 获取全局默认的CudaDevice的内存区域对象.
			 */
			CUDADEV_DLL static CudaMemRegion& MemRegion();
		};
	}
}