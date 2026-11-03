#pragma once
#include <icraft-xir/core/data.h>
#include <icraft-xir/ops/hard_op.h>
#include "icraft-xrt/core/device.h"
#include "icraft-xrt/core/backend.h"
#include <icraft-xrt/dev/buyi_device.h>
//#include "buyibackend_apply.h"


#include <iostream>
#include <vector>
#include <map>
#include <set>
#include <list>

typedef unsigned long long ULL;

using namespace icraft::xir;

namespace icraft::xrt {

	using icraft::xir::Value;
	using icraft::xir::Node;
	using icraft::xir::NodeBase;
	using icraft::xir::HandleBase;
	using icraft::xir::HardOp;

	WISE_ENUM_CLASS(Segment, WEIGHT, INSTR, INPUT, OUTPUT, FTMP );

	using ITER_TYPE = icraft::xir::Array<icraft::xir::Operation>::const_iterator;
	/**
	 * @enum		Segment
	 * @brief	网络分段属性的枚举类 
	 */
	// enum class Segment {
	// 	WEIGHT,				//< 权重分段，etm上存放hardop对应的的权重数据
	// 	INSTR,				//< 指令分段，etm上存放hardop对应需要执行的指令数据
	// 	INPUT,				//< 输入分段，etm上存放的Value作为网络输入
	// 	OUTPUT,				//< 输出分段，etm上存放的Value作为网络输出
	// 	FTMP				//< 中间层分段，etm上存放的Value作为可以优化的中间层
	// };


	class ValueInfoNode : public NodeBase<ValueInfoNode, Node> {
	
	public:

		Value value;						//< icraft::xir::Value的引用类，获得对应的Value指针

		bool real = true;					//< 若为true，表示对应的value在etm上真实分配了地址；若为false表示，其地址与fake_from的value地址共用
		bool is_ocm = false;				//< 若为true，表示对应的value数据存放在ocm上
		bool is_host = false;				//< 若为true，表示对应的value数据存放在host端
		std::vector<Value> real_to;			//< real若为true, 可能包含与其共用etm为false的value
		Value fake_from;					//< real若为false，必定存在预期共用etm地址且为true的value
		uint64_t logic_addr = 0;			//< value 在etm分配的逻辑字节地址

		
		bool user_used = false;				//< 若为true，表示存放value的memchunk为用户申请
		uint64_t phy_addr = 0;				//< value 在etm分配的真实物理字节地址
		uint64_t byte_size = 0;				//< value 在etm上占据的字节大小
		Segment segment = Segment::FTMP;	//< value 在etm上地址对应的分段类型


		virtual void accept(AttrVisitor& visitor) override;

		virtual bool reduceAccept(Node* other, const ReduceVisitor& reduce) const override;
	};

	/** 
	 * @brief ValueInfo引用类
	 */
	class ValueInfo : public HandleBase<ValueInfo, Handle, ValueInfoNode> {
	public:
		ValueInfo() = default;
		ValueInfo(const Value& value)  {
			auto node = make_object<ValueInfoNode>();
			if (value->mtype.is<icraft::xir::OnChipMem>()) {
				node->is_ocm = true;
			}
			if (value->mtype.is<icraft::xir::HostMem>()) {
				node->is_host = true;
			}

			node->byte_size = value.storageBytes();
			node->value = value;
			//node->consumer = value.getUsesOp();
			data_ = std::move(node);
		}

		void setReal(bool real);
		void setPhyAddr(uint64_t phy_addr);
		void setLogicAddr(uint64_t logic_addr);
		void setFakeFrom(const Value& value);
		void setRealTo(const std::vector<Value>& value);
		void addRealTo(const Value& value);
		void setValue(const Value& value);
		void setSegment(Segment segment);

	};

	/**
	 * @brief 与icraft::xir::HardOp类的对应，包含BuyiBackend中一些补充信息
	 */
	class HardOpInfoNode : public NodeBase<HardOpInfoNode, Node> {
	public:

		uint64_t weights_logic_addr = 0;		//< 对应HardOp的权重在etm上分配的逻辑字节地址
		uint64_t weights_size = 0;				//< 对应HardOp的权重在etm上的字节大小
		uint64_t instr_logic_addr = 0;			//< 对应HardOp的指令在etm上分配的逻辑字节地址
		uint64_t instr_size = 0;			//< 对应HardOp的指令在etm上分配的逻辑字节大小

		bool user_used = false;					//< 若为true，表示对应HardOp在etm对应的memchunk为用户申请
		uint64_t weight_phy_addr;				//< 对应HardOp的权重在etm上的真实物理字节地址
		uint64_t instr_phy_addr;				//< 对应HardOp的指令在etm上的真实物理字节地址

		HardOp net_hardop;						//< 对应icraft::xir::HardOp类的指针

		std::vector<ULL> instr_data;			//< 对应HardOp执行的指令
		std::vector<int64_t> merge_from;			//< 如果在speedMode下，表示合并前的hardop op_id集合
		std::pair<int,int> sync_idx;			//< 对应HardOp的同步信息

		virtual void accept(AttrVisitor& visitor) override;

		virtual bool reduceAccept(Node* other, const ReduceVisitor& reduce) const override;
	};

	/** 
	 * @brief HardOpInfo引用类
	 */
	class HardOpInfo : public HandleBase<HardOpInfo, Handle, HardOpInfoNode> {
	public:
		HardOpInfo() = default;
		HardOpInfo(const HardOp& hardop) {
			auto node = make_object<HardOpInfoNode>();
			node->net_hardop = hardop;
			data_ = std::move(node);
		}

		void setWLogicAddr(uint64_t w_logic_addr);
		void setWSize(uint64_t w_byte_size);
		void setWPhyAddr(uint64_t w_phy_addr);
		void setILogicAddr(uint64_t i_logic_addr);
		void setISize(uint64_t i_byte_size);
		void setIPhyAddr(uint64_t i_phy_addr);
		void setSyncIdx(std::pair<int,int> sync_idx);
		std::vector<ULL>& getInstrData();
		std::vector<int64_t>& getMergeFrom();
	
	};

	/**
	 * @brief 逻辑分段类，在BuyiBackend 初始化时生成，表示对应network_view的各分段的逻辑地址相关数据
	 */
	class LogicSegmentNode : public NodeBase<LogicSegmentNode, Node> {
	public:
		std::unordered_map<int64_t, ValueInfo> info_map;				//< 逻辑分段包含的valueInfo信息  <v_id, valueInfo>
		std::unordered_map<int64_t, HardOpInfo> hardop_map;			//< 逻辑分段包含的hardOp信息     <op_id, hardopInfo>

		uint64_t logic_addr = 0;						//< 逻辑分段在etm的逻辑字节地址
		uint64_t byte_size = 0;							//< 逻辑分段在etm的字节大小
		Segment segment_type;							//< 逻辑分段的分段类型

		virtual void accept(AttrVisitor& visitor) override;

		virtual bool reduceAccept(Node* other, const ReduceVisitor& reduce) const override;
	};

	/** 
	 * @brief LogicSegment引用类
	 */
	class LogicSegment : public  HandleBase<LogicSegment, Handle, LogicSegmentNode> {
	public:
		LogicSegment() = default;

		LogicSegment(Segment segment_type) {
			auto node = make_object<LogicSegmentNode>();
			node->segment_type = segment_type;
			data_ = std::move(node);
		}
		std::unordered_map<int64_t, ValueInfo>& getValueMap();
		std::unordered_map<int64_t, HardOpInfo>& getOpMap();

		void setLogicAddr(uint64_t logic_addr);
		void setByteSize(uint64_t byte_size);

	};

	/**
	 * @brief 物理分段类，在BuyiBackend在apply部署后生成，表示对应network_view的各分段的真实物理地址相关数据
	 */
	class PhySegmentNode : public NodeBase<PhySegmentNode, Node> {
	public:
		Segment segment_type;						//< 物理分段的分段类型
		uint64_t byte_size;							//< 物理分段在etm上的字节大小
		uint64_t phy_addr;							//< 物理分段在etm上的真实物理字节地址

		MemChunk memchunk;							//< 物理分段在etm上申请的memchunk

		std::unordered_map<int64_t, ValueInfo> info_map;			//< 物理分段包含的valueInfo信息  <v_id, valueInfo>
		std::unordered_map<int64_t, HardOpInfo> hardop_map;		//< 物理分段包含的hardOp信息     <op_id, hardopInfo>
		bool user_used = false;						//< 若为true，表示物理分段的memchunk是用户申请的

		virtual void accept(AttrVisitor& visitor) override;

		virtual bool reduceAccept(Node* other, const ReduceVisitor& reduce) const override;
	};

	/** 
	 * @brief PhySegment引用类
	 */
	class PhySegment : public HandleBase<PhySegment, Handle, PhySegmentNode> {
	public:
		PhySegment() = default;
		PhySegment(LogicSegment logic_segment) {
			auto node = make_object<PhySegmentNode>();
			node->segment_type = logic_segment->segment_type;
			node->byte_size = logic_segment->byte_size;
			node->phy_addr = logic_segment->logic_addr;
			node->info_map = logic_segment->info_map;
			node->hardop_map = logic_segment->hardop_map;
			data_ = std::move(node);
		}

		PhySegment(Segment segment_type) {
			auto node = make_object<PhySegmentNode>();
			node->segment_type = segment_type;

			data_ = std::move(node);
		}

		std::unordered_map<int64_t, ValueInfo>& getValueMap();
		std::unordered_map<int64_t, HardOpInfo>& getOpMap();

		void setPhyAddr(uint64_t logic_addr);
		void setByteSize(uint64_t byte_size);
		void setUserUsed(bool user_used);

		void setMemChunk(MemChunk mem_chunk);
	};



	/**
	 * @brief 在非speedMode下包含前向所需要的信息
	 */
	class ForwardInfoNode : public NodeBase<ForwardInfoNode, Node> {
	public:

		std::unordered_map<int64_t, ValueInfo> value_map;				//< network_view包含的所有valueInfo的集合  <v_id, ValueInfo>
		std::unordered_map<int64_t, HardOpInfo> hardop_map;				//< network_view包含的所有hardopInfo的集合 <op_id, HardOpInfo>
		std::map<int, std::pair<int,int>> idx_map;						//< network_view中所有op的同步信息集合     <op_id, <sync_idx,diff_idx>>


		XRT_DLL virtual void accept(AttrVisitor& visitor) override;                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       

		XRT_DLL virtual bool reduceAccept(Node* other, const ReduceVisitor& reduce) const override;
	};

	/** 
	 * @brief ForwardInfo引用类
	 */
	class ForwardInfo : public HandleBase<ForwardInfo, Handle, ForwardInfoNode> {
	public:
		ForwardInfo() = default;

		std::unordered_map<int64_t, ValueInfo>& getValueMap();
		std::unordered_map<int64_t, HardOpInfo>& getHardopMap();
		std::map<int, std::pair<int, int>>& getIdxMap();
		

	};

	class BuyiBackend;
	class ApplyHelper;

	/**
	 * @brief BuyiBackend 表示执行在BUYI架构7100芯片的后端
	 * 必须配置对应的device才能正确执行
	 */
	class BuyiBackendNode: public NodeBase<BuyiBackendNode, BackendNode> {
	public:
		XRT_DLL virtual void accept(AttrVisitor& visitor) override;

		/**
		 * @brief BuyiBackend初始化.初始化的过程中会将网络在etm的存储区域进行分段，生成network_view对应的逻辑地址信息
		 * @param network_view	NetworkView中包含所有需要部署在BuyiBackend的算子
		 * @param device		执行的硬件设备，需要传入对应的7100device
		 */
		XRT_DLL virtual void init(const NetworkView& network, const Device& device) override;

		/**
		 * @brief BuyiBackend 部署，session部署的过程中会调用.
		 * 部署的过程中会根据用户的配置执行响应的操作，修改指令，上传修改后的指令，执行每个算子的init函数
		 */
		XRT_DLL virtual void apply() override;

		XRT_DLL virtual void view(uint64_t start_index, uint64_t end_index) override;

		XRT_DLL virtual Backend fork() override;

		XRT_DLL virtual MergedOps autoMerge() override;

		XRT_DLL virtual void deinit() override;

		/**
		* @brief 序列化当前算子相关信息
		* @param builder flatbuffer构建器对象
		* @param op_id 当前算子的id
		* @return 当前算子以及其输入输出的序列化对象
		*/
		//XRT_DLL virtual std::tuple < SerializeOp,
			//std::vector< SerializeFtmp>> serialize(FlatbufferBuilder& builder, int64_t op_id) override;

		XRT_DLL virtual Operation serialize(int64_t op_id) override;

		std::map<int64_t, ValueInfo> value_info;			//< 包含network_view所有valueInfo的信息, <v_id, ValueInfo>

		ForwardInfo forward_info = ForwardInfo::Init();		//< 包含buyibackend所有前向所需要的信息
			
		SegTable seg_table_;   //< 记录段表中的逻辑地址和物理地址等相关数据
		/*
		const Device& getDevice() const;
		const NetworkView& getNetworkView() const;
		*/
		std::unordered_map<Segment, LogicSegment> logic_segment_map;	//< 包含buyibackend的所有逻辑分段信息，<segment_type, logicSegment>
		std::unordered_map<Segment, PhySegment> phy_segment_map;		//< 包含buyibackend的所有物理分段信息, <segment_type, phySegment>
		std::list<Value> value_list;						//< 所有在etm上真实分配空间的value的信息
		
		std::vector<HardOpInfo> speed_ops_;       //< 合并后的算子列表

		void FtmpRealloc(const Value& input_ftmp);
		void overlapFtmp(ValueInfo& big, ValueInfo& small);
		void setSegmentValueMap();
		void calcLogic();
		void userSetSegment(MemChunk& memchunk, Segment segment_type, uint64_t offset = 0);
		void updateSegTable();
		void compressFtmp();


		bool is_speedmode_ = false;							//< 若为true，buyibackend开启speedmode
		bool is_compressftmp_ = false;						//< 若为true, buyibackend开启compressFtmp功能
		bool is_applied_ = false;							//< 若为true, buyibackend已完成部署
		bool is_mmu = true;									//< 若为true, buyibackend开启mmu
		bool is_pure_ = false;								//< 若为true，则为纯净版（仅内部测试用），运行将不再依赖mmu和改指令，但需要注意网络必须按照mmu场景要求进行编译

		static int buyibackend_sid;							//< buyibackend的静态技术，计算当前程序下buyibackend的个数
		int buyibackend_id = 0;								//< 当前buyibackend的id

		friend BuyiBackend;
		friend ApplyHelper;
	};

	class BuyiBackend : public HandleBase<BuyiBackend, Backend, BuyiBackendNode> {
	public:
		/**
		 * @brief 开启speedMode模式，该模式下连续且可以合并的硬算子会自动合并，减少硬算子过多导致频繁同步带来的软件开销
		 * mmu模式下不支持buyibackend开启speedmode
		 */
		XRT_DLL void speedMode();

		/**
		 * @brief 压缩中间层，将ftmp段的网络中间层进行地址复用，从而减少网络对etm的使用量
		 * 中间层压缩开启后会对网络逻辑ftmp分段进行修改，apply部署以后才会真正生效
		 * mmu模式下不支持buyibackend开启内存优化
		 */
		XRT_DLL void compressFtmp();


		/**
		 * @brief 生成BuyiBackend对应的log
		 * log保存在 ${工作目录}/logs/runtime/ 路径下
		 */
		XRT_DLL void log();

		/**
		 * @brief 获得该网络在etm上的部署字节大小
		 * @return 该网络在bybakned部署的字节大小
		 */
		XRT_DLL uint64_t getDeploySize();

		/**
		 * @brief 对改buyibackend进行预检，会检查内存中的指令以及权重数据是否正确上传至etm指定地址
		 * @return 若为True则预检通过
		 */
		XRT_DLL bool precheck();

		/**
		 * @brief 用户配置指定网络数据段的memchunk
		 * @param memchunk 用户自行申请的memchunk
		 * @param segment_type buyibackend 物理数据段phySegment的类型 
		 * @param uint64_t memchunk的偏移，数据会放到memchunk的首地址+偏移的位置 
		 */
		XRT_DLL void userSetSegment(MemChunk& memchunk, Segment segment_type, uint64_t offset =0);
	};

}