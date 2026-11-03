#pragma once
#include <iostream>
#include <icraft-utils/midware/path.hpp>
#include <icraft-xir/core/network.h>
#include <icraft-xrt/base/dllexport.h>

namespace icraft::xrt {
	using namespace icraft::xir;
	
	class SerializeOp
	{
	public:
		XRT_DLL SerializeOp();
		XRT_DLL SerializeOp(uint32_t offset);
		XRT_DLL bool isNull();

		struct Impl;
		std::shared_ptr<Impl> impl;
	};

	class SerializeFtmp
	{
	public:
		XRT_DLL SerializeFtmp();
		XRT_DLL SerializeFtmp(uint32_t offset);
		XRT_DLL bool isNull();

		struct Impl;
		std::shared_ptr<Impl> impl;
	};

	class SerializeNetwork
	{
	public:
		XRT_DLL SerializeNetwork();
		XRT_DLL SerializeNetwork(uint32_t offset);
		XRT_DLL bool isNull();

		struct Impl;
		std::shared_ptr<Impl> impl;
	};

	class FlatbufferBuilder {
	public:
		XRT_DLL FlatbufferBuilder();
		XRT_DLL void finish(SerializeNetwork& network, const icraft::midware::path& filepath);
		XRT_DLL SerializeFtmp createFtmp(
			uint32_t& addr,
			const Value& ftmp);

		XRT_DLL SerializeNetwork createNetwork(
			const Network& network,
			std::vector<SerializeOp>& ops,
			std::vector<SerializeFtmp>& ftmps);

		XRT_DLL SerializeOp createInput(std::vector<uint32_t>& ofms);
		XRT_DLL SerializeOp createOutput(std::vector<uint32_t>& ifms);
		XRT_DLL SerializeOp createHardop(
			uint8_t& compile_target,
			uint32_t& op_id,
			std::vector<uint32_t>& ifms,
			std::vector<uint32_t>& ofms,
			uint32_t& sync_idx,
			uint32_t& layer_count,
			std::vector<uint8_t>& hdop_instr_data,
			std::vector<uint8_t>& hdop_param_data,
			uint32_t& hdop_instr_logic_addr,
			uint32_t& hdop_instr_physic_addr,
			uint32_t& hdop_param_addr);
		
		XRT_DLL SerializeOp createCast(
			uint8_t& compile_target,
			uint32_t& op_id,
			std::vector<uint32_t>& ifms,
			std::vector<uint32_t>& ofms);

		XRT_DLL SerializeOp createImageMake(
			uint8_t& compile_target,
			uint32_t& op_id,
			std::vector<uint32_t>& ifms,
			std::vector<uint32_t>& ofms,
			const std::map<std::string_view, Any>& attrs_map);

		XRT_DLL SerializeOp createDetpost(
			uint8_t& compile_target,
			uint32_t& op_id,
			std::vector<uint32_t>& ifms,
			std::vector<uint32_t>& ofms,
			const std::map<std::string_view, Any>& attrs_map);

		XRT_DLL SerializeOp createSwapOrder(
			uint8_t& compile_target,
			uint32_t& op_id,
			std::vector<uint32_t>& ifms,
			std::vector<uint32_t>& ofms,
			const std::map<std::string_view, Any>& attrs_map);

		XRT_DLL SerializeOp createResize(
			uint8_t& compile_target,
			uint32_t& op_id,
			std::vector<uint32_t>& ifms,
			std::vector<uint32_t>& ofms,
			const std::map<std::string_view, Any>& attrs_map);

		XRT_DLL SerializeOp createAlignAxis(
			uint8_t& compile_target,
			uint32_t& op_id,
			std::vector<uint32_t>& ifms,
			std::vector<uint32_t>& ofms,
			const Operation& xir_op);

		XRT_DLL SerializeOp createPruneAxis(
			uint8_t& compile_target,
			uint32_t& op_id,
			std::vector<uint32_t>& ifms,
			std::vector<uint32_t>& ofms,
			const Operation& xir_op);

		XRT_DLL SerializeOp createReorg(
			uint8_t& compile_target,
			uint32_t& op_id,
			std::vector<uint32_t>& ifms,
			std::vector<uint32_t>& ofms,
			const std::map<std::string_view, Any>& attrs_map);

		XRT_DLL SerializeOp createAdd(
			uint8_t& compile_target,
			uint32_t& op_id,
			std::vector<uint32_t>& ifms,
			std::vector<uint32_t>& ofms,
			const std::map<std::string_view, Any>& attrs_map);

		XRT_DLL SerializeOp createMultiply(
			uint8_t& compile_target,
			uint32_t& op_id,
			std::vector<uint32_t>& ifms,
			std::vector<uint32_t>& ofms);

		XRT_DLL SerializeOp createYolo(
			uint8_t& compile_target,
			uint32_t& op_id,
			std::vector<uint32_t>& ifms,
			std::vector<uint32_t>& ofms,
			const std::map<std::string_view, Any>& attrs_map);
		
		XRT_DLL SerializeOp createSegpost(
			uint8_t& compile_target,
			uint32_t& op_id,
			std::vector<uint32_t>& ifms,
			std::vector<uint32_t>& ofms,
			const std::map<std::string_view, Any>& attrs_map);

		XRT_DLL SerializeOp createWarpAffine(
			uint8_t& compile_target,
			uint32_t& op_id,
			std::vector<uint32_t>& ifms,
			std::vector<uint32_t>& ofms,
			const std::map<std::string_view, Any>& attrs_map);

		struct Impl;
		std::shared_ptr<Impl> impl;
	};

	class FlatbufferParser {
	public:
		XRT_DLL FlatbufferParser(char* map_ptr, uint64_t byte_size) : _map_ptr(map_ptr), _byte_size(byte_size) {}
		XRT_DLL Network Deserialize(const icraft::midware::path& filepath);
		
	private:
		static void null_deleter(const uint8_t*) {}
		char* _map_ptr = nullptr;
		uint64_t _byte_size;
	};
}
