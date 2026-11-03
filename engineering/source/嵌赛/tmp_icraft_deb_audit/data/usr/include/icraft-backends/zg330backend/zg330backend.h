#pragma once
#include "icraft-xir/core/data.h"
#include "icraft-xir/ops/hard_op.h"
#include "icraft-xrt/core/device.h"
#include "icraft-xrt/core/backend.h"
#include "icraft-xrt/dev/zg330_device.h"

#include <iostream>
#include <vector>
#include <map>
#include <set>
#include <list>

typedef unsigned long long ULL;

using namespace icraft::xir;

namespace icraft::xrt {
	namespace zg330 {

		/**
		 * @enum	SegmentType
		 * @brief	网络分段属性的枚举类
		 */
		enum class SegmentType {
			WEIGHT,				//< 权重分段，etm上存放hardop对应的的权重数据
			INSTR,				//< 指令分段，etm上存放hardop对应需要执行的指令数据
			FTMP,				//< 中间层分段，etm/ocm上存放的Value作为可以优化的中间层
			INPUT,				//< 输入分段，etm上存放的Value作为网络输入
			OUTPUT				//< 输出分段，etm上存放的Value作为网络输出
		};

		/**
		 * @enum	AllocMode
		 * @brief	内存管理模式，用于区分不同模式下使用不同的内存管理机制
		 */
		enum class AllocMode {
			MMU,				//< MMU模式
			BYPASS,				//< BYPASS模式
			RECODE				//< 改指令模式
		};

		/**
		 * @enum	OcmOpt
		 * @brief	OCM优化方案
		 */
		enum class OcmOpt {
			None,				//< 无
			OPTION1,			//< 方案一,全局评分法
			OPTION2,			//< 方案二,局部最优动态规划法
			OPTION3,			//< 方案三,顺序按评分踢出法
			BEST_SCORE	= -1		//< 选取三个方案中评分最优的一个
		};

		class ValueInfoNode : public NodeBase<ValueInfoNode, Node> {

		public:
			Value value;								//< icraft::xir::Value的引用类，获得对应的Value指针
			bool real = true;							//< 若为true，表示对应的value在etm/ocm上真实分配了地址；若为false表示，其地址与fake_from的value地址共用
			bool is_ocm = false;						//< 若为true，表示对应的value数据存放在ocm上
			bool is_host = false;						//< 若为true，表示对应的value数据存放在host端
			std::vector<Value> real_to;					//< real若为true, 可能包含与其共用etm为false的value
			Value fake_from;							//< real若为false，必定存在预期共用etm地址且为true的value
			uint64_t logic_addr = 0;					//< value 在etm/ocm分配的逻辑字节地址
			uint64_t phy_addr = 0;						//< value 在etm/ocm分配的真实物理字节地址
			uint64_t byte_size = 0;						//< value 占据的字节大小
			SegmentType segment = SegmentType::FTMP;	//< value 对应的分段类型

			virtual void accept(AttrVisitor& visitor) override {};
		};

		/**
		 * @brief ValueInfo引用类
		 */
		class ValueInfo : public HandleBase<ValueInfo, Handle, ValueInfoNode> {
		public:
			ValueInfo() = default;
			ValueInfo(const Value& value) {
				auto node = make_object<ValueInfoNode>();
				if (value->mtype.is<OnChipMem>()) {
					node->is_ocm = true;
					node->logic_addr = value->mtype.cast<OnChipMem>()->addr;
				}
				if (value->mtype.is<HostMem>()) {
					node->is_host = true;
				}
				if (value->mtype.is<ExternalMem>())
				{
					node->logic_addr = value->mtype.cast<ExternalMem>()->addr;
				}
				node->byte_size = value.storageBytes();
				node->value = value;
				data_ = std::move(node);
			}

			void setReal(bool real);
			void setOcm(bool is_ocm);
			void setPhyAddr(uint64_t phy_addr);
			void setLogicAddr(uint64_t logic_addr);
			void setFakeFrom(const Value& value);
			void setRealTo(const std::vector<Value>& value);
			void addRealTo(const Value& value);
			void setValue(const Value& value);
			void setSegmentType(SegmentType segment);
		};

		/**
		 * @brief 与icraft::xir::HardOp类的对应，包含ZG330Backend中一些补充信息
		 */
		class HardOpInfoNode : public NodeBase<HardOpInfoNode, Node> {
		public:

			uint64_t weights_logic_addr = 0;				//< 对应HardOp的权重在etm上分配的逻辑字节地址
			uint64_t weights_size = 0;						//< 对应HardOp的权重在etm上的字节大小
			uint64_t instr_logic_addr = 0;					//< 对应HardOp的指令在etm上分配的逻辑字节地址
			uint64_t instr_size = 0;						//< 对应HardOp的指令在etm上分配的逻辑字节大小

			uint64_t weight_phy_addr;						//< 对应HardOp的权重在etm上的真实物理字节地址
			uint64_t instr_phy_addr;						//< 对应HardOp的指令在etm上的真实物理字节地址

			HardOp net_hardop;								//< 对应icraft::xir::HardOp类的指针
			std::pair<int, int> sync_idx;					//< 对应HardOp的同步信息  <network_view_idx，layer_count>
			std::vector<int64_t> merge_from;				//< 如果在算子连贯执行模式下，表示合并前的hardop op_id集合

			virtual void accept(AttrVisitor& visitor) override {};
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
				if (!hardop->instr.empty() && hardop->instr[0].defined()) {
					if (hardop->instr[0]->mtype.is<ExternalMem>())
					{
						node->instr_logic_addr = hardop->instr[0]->mtype.cast<ExternalMem>()->addr;
					}
					node->instr_size = hardop->instr[0].storageBytes();
				}
				auto total_weights_size = 0;
				if (!hardop->params.empty() && hardop->params[0].defined()) {
					if (hardop->params[0]->mtype.is<ExternalMem>())
					{
						node->weights_logic_addr = hardop->params[0]->mtype.cast<ExternalMem>()->addr;
					}
					for (int i = 0; i < hardop->params.size(); i++) {
						total_weights_size += hardop->params[i].storageBytes();
					}
					
				}
				node->weights_size = total_weights_size;
				data_ = std::move(node);
			}

			void setWLogicAddr(uint64_t w_logic_addr);
			void setWSize(uint64_t w_byte_size);
			void setWPhyAddr(uint64_t w_phy_addr);
			void setILogicAddr(uint64_t i_logic_addr);
			void setISize(uint64_t i_byte_size);
			void setIPhyAddr(uint64_t i_phy_addr);
			void setSyncIdx(std::pair<int, int> sync_idx);
			std::vector<int64_t>& getMergeFrom();
		};

		/**
		 * @brief 逻辑分段类，在ZG330Backend 初始化时生成，表示对应network_view的各分段的逻辑地址相关数据
		 */
		class LogicSegmentNode : public NodeBase<LogicSegmentNode, Node> {
		public:
			std::unordered_map<int64_t, ValueInfo> info_map;			//< 逻辑分段包含的valueInfo信息  <v_id, valueInfo>
			std::unordered_map<int64_t, HardOpInfo> hardop_map;			//< 逻辑分段包含的hardOp信息     <op_id, hardopInfo>

			uint64_t logic_addr = 0;						//< 逻辑分段在etm的逻辑字节地址
			uint64_t byte_size = 0;							//< 逻辑分段在etm的字节大小
			SegmentType segment_type;						//< 逻辑分段的分段类型

			virtual void accept(AttrVisitor& visitor) override {};
		};

		/**
		 * @brief LogicSegment引用类
		 */
		class LogicSegment : public  HandleBase<LogicSegment, Handle, LogicSegmentNode> {
		public:
			LogicSegment() = default;
			LogicSegment(SegmentType segment_type) {
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
		* @brief 物理内存类，表示真实分配的物理内存相关数据
		*/
		class MemChunkInfoNode : public NodeBase<MemChunkInfoNode, Node> {
		public:
			MemChunk memChunk;									//< 在etm/ocm上申请的memchunk
			bool user_used = false;								//< 若为true，表示对应的memchunk是用户申请的	
			std::unordered_map<int64_t, MemChunk> staged_chunk;	//< 用于输入/输出内存复用时无法直接复用同一块memchunk的情况

			virtual void accept(AttrVisitor& visitor) override {};
		};

		/**
		* @brief MemChunkInfo引用类
		*/
		class MemChunkInfo : public HandleBase<MemChunkInfo, Handle, MemChunkInfoNode> {
		public:
			MemChunkInfo() = default;
			MemChunkInfo(MemChunk memchunk, bool user_used = false) {
				auto node = make_object<MemChunkInfoNode>();
				node->memChunk = memchunk;
				node->user_used = user_used;
				data_ = std::move(node);
			}

			void setMemChunk(MemChunk mem_chunk);
			void setUserUsed(bool user_used);
			void setStagedChunk(int64_t v_id, MemChunk staged_chunk);
		};

		/**
		 * @brief 物理分段类，在ZG330Backend在apply部署后生成，表示对应network_view的各分段的真实物理地址相关数据
		 */
		class PhySegmentNode : public NodeBase<PhySegmentNode, Node> {
		public:
			SegmentType segment_type;							//< 物理分段的分段类型
			uint64_t byte_size;									//< 物理分段在etm上的字节大小
			uint64_t phy_addr;									//< 物理分段在etm上的真实物理字节地址
			std::unordered_map<int64_t, ValueInfo> info_map;	//< 物理分段包含的valueInfo信息  <v_id, valueInfo>
			std::unordered_map<int64_t, HardOpInfo> hardop_map;	//< 物理分段包含的hardOp信息     <op_id, hardopInfo>

			virtual void accept(AttrVisitor& visitor) override {};

			std::unordered_map<int64_t, MemChunkInfo> multi_chunk;	//< 输入、输出分段根据value在etm上申请的多段memchunk	<v_id, MemChunkInfo>
			MemChunkInfo single_chunk;								//< 权重、指令、中间层段在etm/ocm上申请的一段memchunk

			friend class PhySegment;
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

			PhySegment(SegmentType segment_type) {
				auto node = make_object<PhySegmentNode>();
				node->segment_type = segment_type;

				data_ = std::move(node);
			}

			std::unordered_map<int64_t, ValueInfo>& getValueMap();
			std::unordered_map<int64_t, HardOpInfo>& getOpMap();
			void setPhyAddr(uint64_t logic_addr);
			void setByteSize(uint64_t byte_size);
			MemChunkInfo& getSingleMemChunk();
			std::unordered_map<int64_t, MemChunkInfo>& getMutiMemChunk();
		};

		/**
		 * @brief ZG330Backend前向所需要的信息
		 */
		class ForwardInfoNode : public NodeBase<ForwardInfoNode, Node> {
		public:

			std::unordered_map<int64_t, ValueInfo> value_map;				//< network_view包含的所有valueInfo的集合  <v_id, ValueInfo>
			std::unordered_map<int64_t, HardOpInfo> hardop_map;				//< network_view包含的所有hardopInfo的集合 <op_id, HardOpInfo>
			std::unordered_map<int, std::pair<int, int>> idx_map;			//< network_view中所有op的同步信息集合     <op_id, <sync_idx,layer_count>>
			std::unordered_map<int64_t, MemChunkInfo> memchunk_map;			//< network_view中所有value对应的物理内存集合  <v_id, MemChunkInfo>

			virtual void accept(AttrVisitor& visitor) override {};
		};

		/**
		 * @brief ForwardInfo引用类
		 */
		class ForwardInfo : public HandleBase<ForwardInfo, Handle, ForwardInfoNode> {
		public:
			ForwardInfo() = default;

			std::unordered_map<int64_t, ValueInfo>& getValueMap();
			std::unordered_map<int64_t, HardOpInfo>& getHardopMap();
			std::unordered_map<int, std::pair<int, int>>& getIdxMap();
			std::unordered_map<int64_t, MemChunkInfo>& getMemChunkMap();
		};

		class ZG330Backend;
		class ApplyHelper;

		/**
		 * @brief ZG330Backend 表示执行在ZG330芯片的后端
		 * 必须配置对应的device才能正确执行
		 */
		class ZG330BackendNode : public NodeBase<ZG330BackendNode, BackendNode> {
		public:
			XRT_DLL ZG330BackendNode();

			/**
			 * @brief ZG330Backend初始化.初始化的过程中会将网络在etm的存储区域进行分段，生成network_view对应的逻辑地址信息
			 * @param network_view	NetworkView中包含所有需要部署在ZG330Backend的算子
			 * @param device		执行的硬件设备
			 */
			XRT_DLL virtual void init(const NetworkView& network, const Device& device) override;

			/**
			 * @brief ZG330Backend部署，session部署的过程中会调用.
			 */
			XRT_DLL virtual void apply() override;

			XRT_DLL virtual void view(uint64_t start_index, uint64_t end_index) override;

			XRT_DLL virtual Backend fork() override;

			XRT_DLL virtual MergedOps autoMerge() override;

			XRT_DLL virtual void deinit() override;

			XRT_DLL virtual Operation serialize(int64_t op_id) override;

			//XRT_DLL virtual std::tuple < SerializeOp,
			//	std::vector< SerializeFtmp>> serialize(FlatbufferBuilder& builder, int64_t op_id); //override;

			ForwardInfo forward_info = ForwardInfo::Init();						//< 包含zg330backend的所有前向所需要信息
			std::unordered_map<SegmentType, LogicSegment> logic_segment_map;	//< 包含zg330backend的所有逻辑分段信息，<segment_type, logicSegment>
			std::unordered_map<SegmentType, PhySegment> phy_segment_map;		//< 包含zg330backend的所有物理分段信息, <segment_type, phySegment>
			std::unordered_map<int64_t, ValueInfo> value_info;					//< 包含network_view所有valueInfo的信息, <v_id, ValueInfo>
			//< 包含network_view所有value的chunkid相关的信息, <chunk_id, <std::vector<v_id>, chunk_addr, chunk_bytesize, chunk_info>>
			std::unordered_map<uint16_t, std::tuple<std::vector<ValueInfo>, uint64_t, uint64_t, MemChunkInfo>> value_chunk_ids;
			std::unordered_map<uint16_t, HardOpInfo> params_chunk_ids;			//< 包含network_view所有params的chunkid的信息, <chunk_id, HardOpInfo>
			std::vector<HardOpInfo> speed_ops;									//< 合并后的Hardop算子列表
			HardOp first_instr_hardop;											//< zg330backend绑定的网络中的第一个有指令的HardOp引用（包括合并算子）
			MMUMapTable map_table;												//< MMU地址映射表
			MemChunk map_table_chunk;											//< 保存MMU地址映射表的memchunk
			MemChunk time_info;													//< 保存计时结果的chunk，默认分配

			static int zg330backend_sid;						//< 计算当前程序下zg330backend的个数
			int zg330backend_id = 0;							//< 当前zg330backend的id
			bool is_applied = false;							//< 若为true, zg330backend已完成部署
			bool is_mergeHardop = true;							//< 若为true，zg330backend开启算子连贯执行模式
			bool is_etmOptimize = true;							//< 若为true, zg330backend开启中间层内存回收
			AllocMode alloc_mode = AllocMode::BYPASS;			//< 不同模式下使用不同的内存管理机制
			OcmOpt ocmopt = OcmOpt::BEST_SCORE;					//< 使用的ocm优化方案，如果是使用BEST_SCORE，apply后更新为最后选择的方案

		private:
			void FtmpRealloc(const Value& input_ftmp);
			void overlapFtmp(ValueInfo& big, ValueInfo& small);
			void setSegmentValueMap();
			void calcLogic();

			std::unique_ptr<ApplyHelper> apply_helper;
			std::unordered_map<int64_t, int64_t> op_index_map;

			friend ZG330Backend;
			friend ApplyHelper;
		};

		class ZG330Backend : public HandleBase<ZG330Backend, Backend, ZG330BackendNode> {
		public:
			/**
			 * @brief 生成ZG330Backend对应的log，log保存在 ${工作目录}/.icraft/logs/ 路径下
			 * @note 在apply后调用
			 */
			XRT_DLL void log();

			/**
			 * @brief 对ZG330Backend进行预检，会检查内存中的指令以及权重数据是否正确上传至etm指定地址
			 * @return 若为True则预检通过
			 * @note 在apply后调用
			 */
			XRT_DLL bool precheck();

			/**
			 * @brief 用户配置网络权重/指令/中间层数据段的memchunk，用于复用数据或内存空间，减少多网络部署对etm的使用量
			 * @param memchunk 用户自行申请的 memchunk
			 * @param segment_type 物理数据段phySegment的类型
			 * @note 在apply前调用
			 */
			XRT_DLL void userReuseSegment(MemChunk& memchunk, SegmentType segment_type);

			/**
			 * @brief 用户配置网络输入/输出数据段的memchunk，用于连接多网络在etm上的输入和输出
			 * @param memchunk	用户自行申请的 memchunk
			 * @param v_id		网络中指定的value id
			 * @note 在apply前调用
			 */
			XRT_DLL void userConnectNetwork(MemChunk& memchunk, int64_t v_id);

			/**
			 * @brief 关闭算子连贯执行模式，ZG330Backend默认是使用算子连贯执行模式，该模式下连续在icore上运行的算子连贯执行，从而减少频繁同步带来的软件开销
			 * @note  在apply前调用
			 */
			XRT_DLL void disableMergeHardOp();

			/**
			 * @brief 关闭etm内存回收，ZG330Backend默认开启etm内存回收，网络中间层特征图的内存可以复用，从而减少对etm的使用量
			 * @note 在apply前调用
			 */
			XRT_DLL void disableEtmOptimize();

			/**
			 * @brief 选择ocm优化方案，ZG330Backend默认使用OcmOpt::BEST_SCORE，即开启ocm优化并选取方案一、方案二、方案三中评分最高的作为最后使用的方案，
			 *		  开启ocm优化可以将满足条件的特征图存放在片上存储中，从而减小读写etm的带宽压力，提高模型在硬件上的运行效率
			 *		  关闭ocm优化选择OcmOpt::None
			 * @note 在apply前调用
			 */
			XRT_DLL void ocmOptimize(OcmOpt option);

		};
	}

}