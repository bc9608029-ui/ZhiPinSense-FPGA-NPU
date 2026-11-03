#include <icraft-xir/base/dllexport.h>
#include <icraft-xir/core/network.h>
#include <icraft-xir/ops/ops.h>

struct BufferData {
	uint8_t* buffer = NULL;
	int size = 0;
	void* impl;
};

extern "C" {
	XIR_DLL BufferData toFlatBuffers(const icraft::xir::Network& object);

	//XIR_DLL void freeBuffer(uint8_t* buffer);
	XIR_DLL void freeBuffer(BufferData* buffer);

	XIR_DLL icraft::xir::Network fromFlatBuffers(char* map_addr, uint64_t byte_size);
}
