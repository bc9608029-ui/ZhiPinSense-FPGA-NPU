#pragma once
#include <icraft-xrt/core/backend.h>
#include <icraft-xrt/utils/timer.h>

namespace icraft::xrt {
	class HostBackendNode : public NodeBase<HostBackendNode, BackendNode> {
	public:
		bool fake_qf;
		bool deinited = false;

	private:
		XRT_DLL virtual void init(const NetworkView& network_view, const Device& device) override;

		XRT_DLL virtual void deinit() override;

		virtual void apply() override {};

		virtual void view(uint64_t start_index, uint64_t end_index) override {};

		XRT_DLL virtual Backend fork() override;

		XRT_DLL virtual MergedOps autoMerge() override;

		XRT_DLL virtual Operation serialize(int64_t op_id) override;

		friend class HostBackend;
	};

	class HostBackend : public HandleBase<HostBackend, Backend, HostBackendNode> {
	public:
		XRT_DLL void setFakeQf(bool fake_qf);

	};
}
