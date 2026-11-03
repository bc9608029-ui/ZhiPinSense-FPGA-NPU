#pragma once
#include <icraft-xir/core/node.h>
#include <icraft-xir/core/reflection.h>
#include <icraft-xir/base/dllexport.h>


namespace icraft::xir {

	/** 表示IR中存储类型的类型 */
	class MemTypeNode : public NodeBase<MemTypeNode, Node> {
	public:
		/**
		 * @brief 根据给定的位数获取在该存储类型上需要的存储位数
		 * @param bits 给定的位数
		 * @return 需要的存储位数
		 */
		virtual uint64_t getStorageBits(uint64_t bits) const { return 0; };

		virtual void accept(AttrVisitor& visitor) override {}
	};


	class HostMemNode;
	class OnChipMemNode;
	class ExternalMemNode;


	/** 存储类型的引用类 */
	class MemType : public VirtualBase<MemType, Handle, MemTypeNode> {};


	/** IR中表示Host存储的类型 */
	class HostMemNode : public NodeBase<HostMemNode, MemTypeNode> {
	public:
		virtual void accept(AttrVisitor& visitor) override {};

		/**
		 * @see MemTypeNode::getStorageBits
		 */
		XIR_DLL virtual uint64_t getStorageBits(uint64_t bits) const override;
	};


	/** Host存储的引用类 */
	class HostMem : public HandleBase<HostMem, MemType, HostMemNode> {};


	/** IR中表示OCM存储的类型 */
	class OnChipMemNode : public NodeBase<OnChipMemNode, MemTypeNode> {
	public:
		uint64_t addr;		///< OCM上的地址

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(OnChipMemNode* other, const ReduceVisitor& reduce) const;

		/**
		 * @see MemTypeNode::getStorageBits
		 */
		XIR_DLL virtual uint64_t getStorageBits(uint64_t bits) const override;
	};


	/** OCM存储的引用类 */
	class OnChipMem : public HandleBase<OnChipMem, MemType, OnChipMemNode> {
	public:
		/** 默认构造函数 */
		OnChipMem() = default;

		/**
		 * @brief 构造函数，从地址构造
		 * @param addr OCM上的地址
		 */
		XIR_DLL explicit OnChipMem(uint64_t addr);

		/**
		 * @brief 设置地址
		 * @param addr OCM上的地址
		 * @return 自身
		 */
		XIR_DLL OnChipMem& setAddr(uint64_t addr);
	};


	/** IR中表示ETM存储的类型 */
	class ExternalMemNode : public NodeBase<ExternalMemNode, MemTypeNode> {
	public:
		uint64_t addr;		///< ETM上的地址

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(ExternalMemNode* other, const ReduceVisitor& reduce) const;

		/**
		 * @see MemTypeNode::getStorageBits
		 */
		XIR_DLL virtual uint64_t getStorageBits(uint64_t bits) const override;
	};


	/** ETM存储的引用类 */
	class ExternalMem : public HandleBase<ExternalMem, MemType, ExternalMemNode> {
	public:
		/** 默认构造函数 */
		ExternalMem() = default;

		/**
		 * @brief 构造函数，从地址构造
		 * @param addr ETM上的地址
		 */
		XIR_DLL explicit ExternalMem(uint64_t addr);

		/**
		 * @brief 设置地址
		 * @param addr ETM上的地址
		 * @return 自身
		 */
		XIR_DLL ExternalMem& setAddr(uint64_t addr);
	};


	/** IR中表示Chunk存储的类型 */
	class ChunkMemNode : public NodeBase<ChunkMemNode, MemTypeNode> {
	public:
		uint64_t chunk_id;	///< Chunk ID
		uint64_t offset;	///< Chunk上的偏移

		XIR_DLL virtual void accept(AttrVisitor& visitor) override;

		XIR_DLL bool reduceAccept(ChunkMemNode* other, const ReduceVisitor& reduce) const;

		/**
		 * @see MemTypeNode::getStorageBits
		 */
		XIR_DLL virtual uint64_t getStorageBits(uint64_t bits) const override;
	};


	/** Chunk存储的引用类 */
	class ChunkMem: public HandleBase<ChunkMem, MemType, ChunkMemNode> {
	public:
		/** 默认构造函数 */
		ChunkMem() = default;

		/**
		 * @brief 构造函数，从地址构造
		 * @param chunk_id	Chunk ID
		 * @param offset	Chunk上的偏移
		 */
		XIR_DLL explicit ChunkMem(uint64_t chunk_id, uint64_t offset);

		/**
		 * @brief 设置地址
		 * @param chunk_id	Chunk ID
		 * @param offset	Chunk上的偏移
		 * @return 自身
		 */
		XIR_DLL ChunkMem& setAddr(uint64_t chunk_id, uint64_t offset);
	};
}
