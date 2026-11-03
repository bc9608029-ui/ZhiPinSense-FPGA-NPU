#pragma once
#ifndef XRT_ZG330_DEVICE_PCH_GUARD
#define XRT_ZG330_DEVICE_PCH_GUARD
#include <icraft-xrt/core/device.h>
#include <cstdint>
#include <map>

namespace icraft::xrt {

	/**
	 * @brief mmu地址映射表
	 */
	class MMUMapTableNode : public NodeBase<MMUMapTableNode, Node>
	{
	public:
		std::map<uint16_t, uint64_t> map_table;
		uint64_t chunk_addr = 0;
		uint64_t max_id = 0;
		uint64_t bytesize = 0;
		std::shared_ptr<uint32_t[]> buffer = nullptr;

		virtual void accept(AttrVisitor& visitor) override {};
	};

	/**
	 * @brief mmu地址映射表引用类
	 */
	class MMUMapTable :public HandleBase<MMUMapTable, Handle, MMUMapTableNode> {
	public:
		MMUMapTable() = default;
		XRT_DLL MMUMapTable(std::shared_ptr<uint32_t[]> buffer_, uint64_t max_id_);
		XRT_DLL MMUMapTable(const std::map<uint16_t, uint64_t>& map_table_);
		XRT_DLL void setMemChunkAddr(uint64_t addr);
		XRT_DLL void updateBuffer(uint16_t chunkid, uint64_t addr) const;
	};

	/**
	 * @brief 表示ZG330架构的设备.
	 */
	class ZG330DeviceNode : public NodeBase<ZG330DeviceNode, DeviceNode> {
	public:
		uint64_t timer_addr = 0;
		uint64_t timer_bytes = 0;

		uint64_t profiler_addr = 0;
		uint64_t profiler_bytes = 0;
		
		MMUMapTable mmu_table;

		int master_cid = 1;
		int sub_cols = 2;

		uint64_t icore_clk_freq = 1000E6;
		uint64_t ddr_clk_freq = 333E6;

	private:
		static constexpr uint64_t FPGA_REG_BASE = 0x00000000;
		static constexpr uint64_t ICORE_REG_BASE = 0x00040000;

		//HOST_CTRL
		static constexpr uint64_t FPGA_STATE_CLEAR_REG = 0x04 + FPGA_REG_BASE;
		static constexpr uint64_t FPGA_STATE_REG = 0x08 + FPGA_REG_BASE;
		static constexpr uint64_t FPGA_LAYER_CNT_REG = 0x0C + FPGA_REG_BASE;
		static constexpr uint64_t FPGA_WTILE_CNT_REG = 0x10 + FPGA_REG_BASE;
		static constexpr uint64_t FPGA_RTILE_CNT_REG = 0x14 + FPGA_REG_BASE;

		static constexpr uint64_t FPGA_TIMER_CNT_REG = 0x18 + FPGA_REG_BASE;
		static constexpr uint64_t FPGA_VERSION_REG = 0x1C + FPGA_REG_BASE;
		static constexpr uint64_t FPGA_EXHS_VLD_REG = 0x20 + FPGA_REG_BASE;
		static constexpr uint64_t FPGA_EXHS_ACK_REG = 0x28 + FPGA_REG_BASE;
		static constexpr uint64_t FPGA_STID_INFO_REG = 0x4C + FPGA_REG_BASE;// not found
		static constexpr uint64_t FPGA_AVR_STATE_REG = 0x50 + FPGA_REG_BASE;
		static constexpr uint64_t FPGA_RESET_REG = 0x34 + FPGA_REG_BASE;

		//ICORE_REG
		static constexpr uint64_t ICORE_RUN_BASE_REG = 0x18 + ICORE_REG_BASE;
		static constexpr uint64_t ICORE_RUN_SIZE_REG = 0x20 + ICORE_REG_BASE;
		static constexpr uint64_t ICORE_RUN_START_REG = 0x24 + ICORE_REG_BASE;

		uint64_t last_run_addr_ = 0;
		uint64_t last_run_size_ = 0;

		friend class ZG330Device;


	protected:
		XRT_DLL virtual void initAfterRegions() override;

		XRT_DLL virtual void reset(int level) override;

		XRT_DLL virtual bool check(int level) const override;

		XRT_DLL virtual void showStatus(int level) const override;

		XRT_DLL virtual std::unordered_map<std::string, std::string> version() const override;

		XRT_DLL uint32_t readReg(uint32_t cid, uint32_t rid, uint32_t offset) const;

		XRT_DLL void writeReg(uint32_t cid, uint32_t rid, uint32_t offset, uint32_t data) const;

		XRT_DLL std::pair<int, int> getRowsCols() const;

		XRT_DLL double calcTime() const;

		/** PL间数据拷贝，地址和数据长度需64字节对齐 */
		XRT_DLL void dmaMemcpy(uint64_t dest, uint64_t src, uint64_t byte_size, int timeout) const;

		/**
		 * @brief 获取ocm上所有的数据.
		 * @return	ocm上的数据，数据长度2MB
		 */
		XRT_DLL std::shared_ptr<char[]> readOcmData() const;

		/**
		 * @brief 写ocm上的数据.
		 * @param	data			写ocm的数据
		 * @param	byte_size		数据长度，需小于2MB
		 */
		XRT_DLL void writeOcmData(const std::shared_ptr<char[]> data, uint64_t byte_size) const;

		xir::Array<xir::CompileTarget> compileTargets() const override {
			return { xir::ZhugeTarget::Init(),xir::FPGATarget::Init() };
		}

	private:
		XRT_DLL bool dmaCheck() const;

		XRT_DLL bool regCheck() const;

		XRT_DLL void configVPE(uint64_t addr, uint64_t size);

		XRT_DLL uint32_t layerCount() const;

		XRT_DLL uint32_t wTileCount(int cid) const;

		XRT_DLL uint32_t rTileCount(int cid) const;

		XRT_DLL void showReg(uint32_t base, std::string info) const;

		XRT_DLL void showReg(uint32_t cid, uint32_t rid, uint32_t offset, std::string info) const;

		XRT_DLL void showIcoreTimer(int c) const;

		XRT_DLL void showLayerTime(int from_idx, int op_cnt) const;

		XRT_DLL void showComState(int cid) const;

		XRT_DLL void showVpeState(int c) const;

		XRT_DLL void showVpeState() const;

		XRT_DLL void showError() const;

		XRT_DLL int showOcmError() const;

		XRT_DLL int showVpeError() const;

		XRT_DLL void showInstStatus() const;

		XRT_DLL void showAvrStatus() const;

		XRT_DLL int showMpeAvr() const;

		XRT_DLL int showVpeAvr() const;

		XRT_DLL void showTileCnt() const;

		XRT_DLL void showVersion() const;

	};

	/**
	 * @brief ZG330架构设备的引用类.
	 */
	class ZG330Device : public HandleBase<ZG330Device, Device, ZG330DeviceNode> {
	public:
		/**
		 * @brief 获取设备使能的MPE的行数和列数.
		 * @return	std::pair表示的行数和列数
		 */
		XRT_DLL std::pair<int, int> getRowsCols() const;

		/**
		 * @brief 读指定行列位置的寄存器.
		 * @param	cid		列ID
		 * @param	rid		行ID
		 * @param	offset	偏移地址
		 * @return	读取的寄存器值
		 */
		XRT_DLL uint32_t readReg(uint32_t cid, uint32_t rid, uint32_t offset) const;

		/**
		 * @brief 写指定行列位置的寄存器.
		 * @param	cid		列ID
		 * @param	rid		行ID
		 * @param	offset	偏移地址
		 * @param	data	写入的数据
		 */
		XRT_DLL void writeReg(uint32_t cid, uint32_t rid, uint32_t offset, uint32_t data) const;

		/**
		 * @brief 启动Icore计算.
		 * @param	addr	指令地址
		 * @param	size	指令长度
		 */
		XRT_DLL void icoreCalc(uint64_t addr, uint64_t size);

		/** 获取当前的执行计数 */
		XRT_DLL uint32_t layerCount() const;

		/** 获取当前的写Tile计数 */
		XRT_DLL uint32_t wTileCount(int cid) const;

		/** 获取当前的读Tile计数 */
		XRT_DLL uint32_t rTileCount(int cid) const;

		/** 获取执行时间（ms） */
		XRT_DLL float calcTime() const;

		/** 配置计时器的空间 */
		XRT_DLL void configTimer(const MemChunk& chunk);

		/** 配置Profiler的空间 */
		XRT_DLL void configProfiler(const MemChunk& chunk);

		/** 设置master_cid */
		XRT_DLL void setMasterCID(int master_cid);

		/** 设置Icore的时钟频率(Hz) */
		XRT_DLL void setIcoreClkFreq(uint64_t freq_hz);

		/** 设置DDR的时钟频率(Hz) */
		XRT_DLL void setDDRClkFreq(uint64_t freq_hz);

		/** 设置握手状态 */
		XRT_DLL void setOpWait(int reg_idx, uint32_t data);

		/** 获得握手状态 */
		XRT_DLL uint32_t getOpWait(int reg_idx);

		/** 设置mmu使能状态 */
		XRT_DLL void setMMUMode(bool enable);

		/** 获取mmu使能状态 */
		XRT_DLL bool getMMUMode();

		/** 更新mmu映射表基址 */
		XRT_DLL void updateMMU(const MMUMapTable& mmu_map_table);

		/** 清除mmu缓存表 */
		XRT_DLL void clearMMUCache();

		/** 输出显示计时结果 */
		XRT_DLL void showLayerTime(int from_idx, int op_cnt) const;

		/** 获取计时结果，单位毫秒 */
		XRT_DLL std::vector<double> getLayerTime(int layer_cnt);
	};
}
#endif //XRT_ZG330_DEVICE_PCH_GUARD