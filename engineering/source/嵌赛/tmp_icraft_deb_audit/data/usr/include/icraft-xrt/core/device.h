#pragma once
#ifndef XRT_DEVICE_PCH_GUARD
#define XRT_DEVICE_PCH_GUARD
#include <cstdint>
#include <functional>
#include <chrono>
#include <icraft-xrt/base/dllexport.h>
#include <icraft-utils/midware/clock.hpp>
#include <icraft-utils/midware/mutex.hpp>

#include <icraft-xir/base/string.h>
#include <icraft-xir/base/map.h>
#include <icraft-xir/core/data.h>
#include <icraft-xir/core/reflection.h>
#include <icraft-xir/core/compile_target.h>
#include <vector>
#include <list>
#include <map>

namespace icraft::xrt {
	using icraft::xir::Node;
	using icraft::xir::Handle;
	using icraft::xir::NodeBase;
	using icraft::xir::VirtualBase;
	using icraft::xir::HandleBase;
	using icraft::xir::make_object;
	using icraft::xir::AttrVisitor;
	using icraft::xir::ReduceVisitor;
	using icraft::xir::GetRef;
	using icraft::xir::ObjectRef;
	using icraft::xir::IntImm;
	using icraft::xir::CompileTarget;

	/**
	* @enum		PtrType
	* @brief	表示XRT中指针类型的枚举
	*/
	/*enum class PtrType {
		CPTR,			///< C指针
		ADDR,			///< 物理地址
		BOTH			///< 既包含C指针，又包含物理地址
	};*/
	WISE_ENUM_CLASS(PtrType, CPTR, ADDR, BOTH)


	/**
	 * @brief 表示XRT中的内存指针
	 */
	class MemPtrNode : public NodeBase<MemPtrNode, Node> {
	private:
		uint64_t addr_;
		char* cptr_ = nullptr;
		PtrType ptype_ = PtrType::CPTR;

		friend class MemPtr;

	public:
		XRT_DLL virtual void accept(AttrVisitor& visitor) override;

		XRT_DLL bool reduceAccept(MemPtrNode* other, const ReduceVisitor& reduce) const;
	};

	/**
	 * @brief 表示XRT中内存指针的引用类型
	 */
	class MemPtr : public icraft::xir::HandleBase<MemPtr, Handle, MemPtrNode> {
	public:
		/** 默认构造函数 */
		MemPtr() = default;

		/**
		 * @brief 构造函数，构造一个PtrType::BOTH类型的MemPtr.
		 * @param cptr	C指针的值
		 * @param addr	物理地址的值
		 */
		XRT_DLL MemPtr(void* cptr, uint64_t addr);

		/**
		 * @brief 构造函数，构造一个PtrType::CPTR类型的MemPtr.
		 * @param cptr	C指针的值
		 */
		XRT_DLL explicit MemPtr(void* cptr);

		/**
		 * @brief 构造函数，构造一个PtrType::ADDR类型的MemPtr.
		 * @param addr	物理地址的值
		 */
		XRT_DLL explicit MemPtr(uint64_t addr);

		/**
		 * @brief 创建一个空指针.
		 * @note  在XRT中，当且仅当MemPtr为PtrType::CPTR且cptr的值为nullptr时，认为这个MemPtr为空指针
		 */
		XRT_DLL static MemPtr NullPtr();

		/** 检查该MemPtr是否是空指针 */
		XRT_DLL bool isNull() const;

		/**
		 * @brief 获取该MemPtr的C指针.
		 * @throw 如果MemPtr为PtrType::ADDR类型时，抛出异常
		 */
		XRT_DLL char* cptr() const;

		/**
		 * @brief 获取该MemPtr的物理地址.
		 * @throw 如果MemPtr为PtrType::CPTR类型时，抛出异常
		 */
		XRT_DLL uint64_t addr() const;

		/** 获取该MemPtr的类型 */
		XRT_DLL PtrType ptype() const;
	};

	/** 为MemPtr重载加号运算符 */
	XRT_DLL MemPtr operator+(const MemPtr& lhs, uint64_t rhs);
	/** 为MemPtr重载加号运算符 */
	XRT_DLL MemPtr operator+(uint64_t lhs, const MemPtr& rhs);
	/** 为MemPtr重载减号运算符 */
	XRT_DLL MemPtr operator-(const MemPtr& lhs, uint64_t rhs);
	/** 为MemPtr重载减号运算符 */
	XRT_DLL int64_t operator-(const MemPtr& lhs, const MemPtr& rhs);

	/** 为MemPtr重载小于号运算符 */
	XRT_DLL bool operator<(const MemPtr& lhs, const MemPtr& rhs);
	/** 为MemPtr重载小于等于号运算符 */
	XRT_DLL bool operator<=(const MemPtr& lhs, const MemPtr& rhs);
	/** 为MemPtr重载大于号运算符 */
	XRT_DLL bool operator>(const MemPtr& lhs, const MemPtr& rhs);
	/** 为MemPtr重载大于等于号运算符 */
	XRT_DLL bool operator>=(const MemPtr& lhs, const MemPtr& rhs);
	
	class MemChunk;
	class MemChunkNode;
	class MemRegion;
	class MemRegionNode;
	class DeviceNode;
	class Device;

	/** MemChunk自定义删除函数的原型 */
	using FChunkDeleter = std::function<void(const MemPtr&)>;

	/**
	 * @brief 表示内存管理器的抽象类
	 */
	class MemManagerNode : public NodeBase<MemManagerNode, Node> {
	protected:
		const MemRegionNode* region = nullptr;
		XRT_DLL MemChunk CreateMemChunk(
			MemPtr begin,
			uint64_t byte_size,
			FChunkDeleter deleter = nullptr,
			bool auto_free = true) const;

	private:
		virtual void accept(AttrVisitor& visitor) override {};

		virtual MemChunk malloc(uint64_t byte_size, bool auto_free, uint64_t alignment) = 0;

		virtual MemChunk malloc(MemPtr begin, uint64_t byte_size, FChunkDeleter deleter, bool auto_free) = 0;

		virtual void free(const MemPtr& ptr) = 0;

		virtual std::vector<MemChunk> getAllMemChunk() const = 0;
	
		virtual std::map<std::string, ObjectRef>& getMemRegionInfo() const = 0;
		
		friend class MemManager;
	};

	/**
	 * @brief 内存管理器的引用类
	 */
	class MemManager : public VirtualBase<MemManager, Handle, MemManagerNode> {
	public:	
		/** 绑定所属的Memregion */
		XRT_DLL void _bindMemRegion(const MemRegionNode* region);
		
		XRT_DLL MemChunk malloc(uint64_t byte_size, bool auto_free, uint64_t alignment);

		XRT_DLL MemChunk malloc(MemPtr begin, uint64_t byte_size, FChunkDeleter deleter, bool auto_free);

		XRT_DLL void free(const MemPtr& ptr);

		/** 获得当前已分配的所有MemChunk */
		XRT_DLL std::vector<MemChunk> getAllMemChunk() const;
	
		/**
		 * @brief 获取指定的已分配内存.
		 * @param	ptr			内存起始位置
		 * @param	byte_size	内存大小
		 * @return 	若指定起始位置和大小的内存存在，返回对应的MemChunk，否则返回nullopt
		 */
		XRT_DLL std::optional<MemChunk> getMemChunk(const MemPtr& ptr, uint64_t byte_size) const;

		/** 获得设备信息，不同设备保存的信息不同，详见具体设备的内存管理器使用说明 */
		XRT_DLL std::map<std::string, ObjectRef>& getMemRegionInfo() const;
	};

	/**
	 * @brief 表示内存区域的类.
	 * 内存区域表示一块受管理的内存空间，比如NPU的PLDDR或者PS上的UDMABuf区域
	 */
	class MemRegionNode : public NodeBase<MemRegionNode, Node> {
	public:
	 	virtual void accept(AttrVisitor& visitor) override {}
		
	protected:
		const DeviceNode* dev_ = nullptr;
		mutable MemManager mm_;

		XRT_DLL static MemChunk CreateMemChunk(
			MemPtr begin,
			uint64_t byte_size,
			MemRegion region,
			FChunkDeleter deleter = nullptr,
			bool auto_free = true
		);

	private:
		/** MemRegion的初始化接口，在该接口的实现中初始化资源 */
		virtual void init() = 0;

		/** MemRegion的关闭接口，在该接口的实现中关闭初始化的资源 */
		virtual void deinit() = 0;
		
		/**
		 * @brief MemRegion的读接口，将指定位置的数据读到数据缓存.
		 * @param	dest		数据被读取到char*表示的缓存
		 * @param	src			从该位置开始读取数据
		 * @param	byte_size	读取数据的字节大小
		 */
		virtual void read(char* dest, const MemPtr& src, uint64_t byte_size) const = 0;

		/**
		 * @brief MemRegion的写接口，将数据缓存中数据写到指定位置.
		 * @param	dest		数据被写入的位置
		 * @param	src			char*表示的数据缓存
		 * @param	byte_size	写入数据的字节大小
		 */
		virtual void write(const MemPtr& dest, char* src, uint64_t byte_size) const = 0;

		/**
		 * @brief MemRegion的内存分配接口，分配指定大小的内存.
		 * @param	byte_size	分配内存的大小
		 * @param	auto_free	指定分配的内存是否会被自动释放
		 * @param	alignment	指定分配的内存地址字节对齐
		 */
		virtual MemChunk malloc(uint64_t byte_size, bool auto_free, uint64_t alignment = 1) const = 0;

		/**
		 * @brief MemRegion的内存分配接口，尝试分配指定位置开始的内存
		 * @param	begin		指定的内存位置
		 * @param	byte_size	分配内存的大小
		 * @param	deleter		内存释放的自定义函数，若指定了FChunkDeleter，则调用该函数来释放内存
		 * @param	auto_free	指定分配的内存是否会被自动释放
		 */
		virtual MemChunk malloc(
			MemPtr begin, 
			uint64_t byte_size, 
			FChunkDeleter deleter,
			bool auto_free
		) const = 0;

		/**
		 * @brief MemRegion的内存释放接口，释放指定位置的内存
		 * @param	src		指定的内存位置
		 */
		virtual void free(const MemPtr& src) const = 0;

		/**
		 * @brief MemRegion的内存复制接口，在指定的内存位置间复制数据
		 * @param	dest		内存复制的目的位置
		 * @param	src			内存复制的源位置
		 * @param	byte_size	内存复制的字节大小
		 */
		virtual void memcpy(const MemPtr& dest, const MemPtr& src, uint64_t byte_size) const = 0;

		/**
		 * @brief MemRegion的跨MemRegion内存复制接口
		 * @param	dest_ptr	内存复制的目的位置
		 * @param	src_region	内存复制的源MemRegion
		 * @param	src_ptr		内存复制的源位置
		 * @param	byte_size	内存复制的字节大小
		 * 
		 * @note 该接口有默认实现，即将源MemRegion的数据复制到Host，然后写的目的MemRegion. 
		 * 若硬件对两个MemRegion之间的复制有特殊优化，可以覆盖实现
		 */
		XRT_DLL virtual void memcpy(
			const MemPtr& dest_ptr,
			const MemRegion& src_region,
			const MemPtr& src_ptr,
			uint64_t byte_size
		) const;

		friend class MemRegion;
		friend class MemManagerNode;
	};

	/** @brief 内存区域引用类 */
	class MemRegion : public VirtualBase<MemRegion, Handle, MemRegionNode> {
	private:
		XRT_DLL void init();

		XRT_DLL void deinit();

		friend class MemChunkNode;
		friend class MemChunk;
		friend class DeviceNode;
		friend class Device;

	public:
		/**
		 * @brief 释放指定位置的内存
		 * @param	src	指定的内存位置
		 * 
		 * @note 除了Device开发，否则不应直接调用该方法，而应该使用MemChunk的free方法
		 */
		XRT_DLL void free(const MemPtr& src) const;

		/**
		 * @brief 读取指定位置的数据.
		 * @param	dest		数据被读取到char*表示的缓存
		 * @param	src			从该位置开始读取数据
		 * @param	byte_size	读取数据的字节大小
		 * 
		 * @note 除了Device开发，否则不应直接调用该方法，而应该使用MemChunk的read方法
		 */
		XRT_DLL void read(char* dest, const MemPtr& src, uint64_t byte_size) const;

		/**
		 * @brief 将数据写到指定位置.
		 * @param	dest		数据被写入的位置
		 * @param	src			char*表示的数据缓存
		 * @param	byte_size	写入数据的字节大小
		 * 
		 * @note 除了Device开发，否则不应直接调用该方法，而应该使用MemChunk的write方法
		 */
		XRT_DLL void write(const MemPtr& dest, char* src, uint64_t byte_size) const;

		/**
		 * @brief 在指定的内存位置间复制数据
		 * @param	dest		内存复制的目的位置
		 * @param	src			内存复制的源位置
		 * @param	byte_size	内存复制的字节大小
		 * 
		 * @note 除了Device开发，否则不应直接调用该方法，而应该使用MemChunk的memcpy方法
		 */
		XRT_DLL void memcpy(const MemPtr& dest, const MemPtr& src, uint64_t byte_size) const;

		/**
		 * @brief 跨MemRegion复制数据
		 * @param	dest_ptr	内存复制的目的位置
		 * @param	src_region	内存复制的源MemRegion
		 * @param	src_ptr		内存复制的源位置
		 * @param	byte_size	内存复制的字节大小
		 *
		 * @note 除了Device开发，否则不应直接调用该方法，而应该使用MemChunk的memcpy方法
		 */
		XRT_DLL void memcpy(
			const MemPtr& dest_ptr, 
			const MemRegion& src_region, 
			const MemPtr& src_ptr, 
			uint64_t byte_size
		) const;

	public:
		MemRegion() = default;

		/**
		 * @brief 申请分配指定大小的内存.
		 * @param	byte_size	分配内存的大小
		 * @param	auto_free	指定分配的内存是否会被自动释放
		 * @param	alignment	指定分配的内存地址字节对齐
		 */
		XRT_DLL MemChunk malloc(uint64_t byte_size, bool auto_free = true, uint64_t alignment = 1) const;

		/**
		 * @brief 申请分配指定位置开始的内存.
		 * @param	byte_size	分配内存的大小
		 * @param	deleter		内存释放的自定义函数，若指定了FChunkDeleter，则调用该函数来释放内存
		 * @param	auto_free	指定分配的内存是否会被自动释放
		 */
		XRT_DLL MemChunk malloc(
			MemPtr begin,
			uint64_t byte_size,
			FChunkDeleter deleter = nullptr,
			bool auto_free = true
		) const;

		/** 绑定所在的设备 */
		XRT_DLL MemRegion& _bindDevice(const DeviceNode* dev);
		
		/** 绑定内存分配器 */
		XRT_DLL void _bindMemmanager(const MemManagerNode* manager);

		/** 获取所在的Device */
		XRT_DLL Device device() const;

		/** 获取所属的MemManager */
		XRT_DLL const MemManager memManager() const;
	};

	/** @brief 表示一块连续的内存块 */
	class MemChunkNode : public NodeBase<MemChunkNode, Node> {
	public:
		MemPtr begin;			///< 内存块开始的位置
		uint64_t byte_size;		///< 内存块的字节大小
		MemRegion region;		///< 内存块所在的内存区域

	private:
		FChunkDeleter deleter_;
		bool auto_free_;
		
		void free();

		friend class MemChunk;
	public:
		XRT_DLL virtual void accept(AttrVisitor& visitor) override;

		bool reduceAccept(MemChunkNode* other, const ReduceVisitor& reduce) const {
			return reduce(begin, other->begin)
				&& reduce(byte_size, other->byte_size)
				&& reduce(region, other->region);
		}

		/** 析构函数 */
		XRT_DLL ~MemChunkNode() noexcept;
	};

	/** @brief 内存块引用类 */
	class MemChunk : public HandleBase<MemChunk, Handle, MemChunkNode> {
	private:
		XRT_DLL MemChunk(
			MemPtr begin, 
			uint64_t byte_size, 
			MemRegion region, 
			FChunkDeleter deleter = nullptr,
			bool auto_free = true
		);

		friend class MemRegionNode;

	public:
		/** 默认构造函数 */
		MemChunk() = default;

		/**
		 * @brief 读取指定偏移的数据.
		 * @param	dest		数据被读取到char*表示的缓存
		 * @param	src_offset	从该偏移开始读取数据
		 * @param	byte_size	读取数据的字节大小
		 */
		XRT_DLL void read(char* dest, uint64_t src_offset, uint64_t byte_size) const;

		/**
		 * @brief 将数据写到指定偏移位置.
		 * @param	dest_offset		数据被写入的偏移位置
		 * @param	src				char*表示的数据缓存
		 * @param	byte_size		写入数据的字节大小
		 */
		XRT_DLL void write(uint64_t dest_offset, char* src, uint64_t byte_size) const;

		/**
		 * @brief 从其它MemChunk复制数据.
		 * @param	dest_offset		目的偏移位置
		 * @param	src_chunk		源MemChunk
		 * @param	src_offset		源偏移位置
		 * @param	byte_size		复制的字节大小
		 */
		XRT_DLL void copyFrom(uint64_t dest_offset,
			const MemChunk& src_chunk,
			uint64_t src_offset,
			uint64_t byte_size
		) const;

		/** 释放该MemChunk所占用的内存 */
		XRT_DLL void free();

		/** 检查该MemChunk是否位于某个MemRegion上 */
		XRT_DLL bool isOn(const MemRegion& region) const;

		/** 设置自定义删除函数 */
		XRT_DLL void setDeleter(FChunkDeleter deleter_) const;

		/** 设置是否autofree */
		XRT_DLL void setAutoFree(bool auto_free) const;
	};

	/** @brief 表示寄存器区域的类 */
	class RegRegionNode : public NodeBase<RegRegionNode, Node> {
	public:
		virtual void accept(AttrVisitor& visitor) override {}

	protected:
		const DeviceNode* dev_ = nullptr;

	private:
		/** RegRegion的初始化接口，在该接口的实现中初始化资源 */
		virtual void init() = 0;

		/** RegRegion的关闭接口，在该接口的实现中关闭初始化的资源 */
		virtual void deinit() = 0;

		/**
		 * @brief RegRegion的读数据接口.
		 * @param addr		读取的地址
		 * @param relative	是否以相对地址读取数据
		 * @return 读取到的寄存器数据
		 */
		virtual uint64_t read(uint64_t addr, bool relative = false) const = 0;

		/**
		 * @brief RegRegion的写数据接口.
		 * @param addr		写入的地址
		 * @param data		写入的数据
		 * @param relative	是否以相对地址写入数据
		 */
		virtual void write(uint64_t addr, uint64_t data, bool relative = false) const = 0;

		friend class RegRegion;
	};

	class RegRegion : public HandleBase<RegRegion, Handle, RegRegionNode> {
	private:
		XRT_DLL void init();

		XRT_DLL void deinit();

		friend class DeviceNode;
		friend class Device;
	public:
		/**
		 * @brief 读取指定地址的数据.
		 * @param addr		读取的地址
		 * @param relative	是否以相对地址读取数据
		 * @return 读取到的寄存器数据
		 */
		XRT_DLL uint64_t read(uint64_t addr, bool relative = false) const;

		/**
		 * @brief 将数据写入指定地址.
		 * @param addr		写入的地址
		 * @param data		写入的数据
		 * @param relative	是否以相对地址写入数据
		 */
		XRT_DLL void write(uint64_t addr, uint64_t data, bool relative = false) const;

		/** 获取该RegRegion所在的Device */
		XRT_DLL Device device() const;

		/** 绑定到所在的Device */
		XRT_DLL RegRegion& _bindDevice(const DeviceNode* dev);
	};

	namespace utils {
		/** @brief 解析URL的工具类 */
		class UrlParser {
		private:
			std::string url_;
			std::string protocol_;
			std::string device_;
			std::string site_;
			std::unordered_map<std::string, std::string> params_;

		public:
			/**
			 * @brief 构造函数.
			 * @param	url	被解析的UTL字符串
			 */
			XRT_DLL UrlParser(const std::string& url);

			/** 获取URL */
			XRT_DLL const std::string& url() const;

			/** 获取解析后的协议名 */
			XRT_DLL const std::string& protocol() const;

			/** 获取解析后的设备名 */
			XRT_DLL const std::string& device() const;

			/** 获取解析后的位置名 */
			XRT_DLL const std::string& site() const;

			/** 获取解析后的所有参数 */
			XRT_DLL const std::unordered_map<std::string, std::string>& params() const;

			/**
			 * @brief 根据键值获取参数值.
			 * @param	key		键值
			 * @return 参数值
			 */
			XRT_DLL const std::string& getParam(const std::string& key) const;
		};
	}

	/** @brief 表示设备的类型 */
	class DeviceNode : public NodeBase<DeviceNode, Node> {
	private:
		virtual void initBeforeRegions() = 0;

		virtual void initAfterRegions() = 0;

		virtual void deinitBeforeRegions() = 0;

		virtual void deinitAfterRegions() = 0;

		virtual void reset(int level) = 0;

		virtual bool check(int level) const = 0;

		virtual void showStatus(int level) const = 0;

		virtual std::unordered_map<std::string, std::string> version() const = 0;

		virtual xir::Array<xir::CompileTarget> compileTargets() const = 0;

	protected:
		std::unordered_map<std::string_view, MemRegion> mem_regions;
		std::unordered_map<std::string_view, RegRegion> reg_regions;
		MemRegion default_mem_region;
		RegRegion default_reg_region;
		std::vector<std::string_view> mregion_names;
		std::vector<std::string_view> rregion_names;

		friend class Device;
	public:
		std::string url;										///< 设备的URL
		std::string protocol;									///< 设备的协议名
		std::string device;										///< 设备的设备名
		std::string site;										///< 设备的位置名
		std::unordered_map<std::string, std::string> params;	///< 设备的参数
		uint64_t wait_time = 10000;

		virtual void accept(AttrVisitor& visitor) override {
			visitor.visit("url", url);
		}
	};

	/** @brief 设备的引用类 */
	class Device : public VirtualBase<Device, Handle, DeviceNode> {
	public:
		/**
		 * @brief 打开设备.
		 * @param url	设备的URL
		 * @return	打开的设备对象
		 */
		XRT_DLL static Device Open(const std::string& url);

		/**
		 * @brief 关闭设备.
		 * @param 被关闭的设备对象
		 */
		XRT_DLL static void Close(Device& device);

		/** 获取设备默认的MemRegion */
		XRT_DLL const MemRegion& defaultMemRegion() const;

		/**
		 * @brief 将指定的MemRegion设置为默认MemRegion.
		 * @param region_name	指定的MemRegion名字
		 */
		XRT_DLL Device& setDefaultMemRegion(const std::string& region_name);

		/**
		 * @brief 根据名字获取设备的MemRegion.
		 * @param name	MemRegion的名字
		 * @return	相对应的MemRegion对象
		 */
		XRT_DLL const MemRegion& getMemRegion(const std::string& name) const;

		/**
		 * @brief 在默认的MemRegion上申请分配内存.
		 * @param byte_size	申请的内存大小
		 * @return	申请得到的MemChunk对象
		 */
		XRT_DLL MemChunk malloc(uint64_t byte_size) const;

		/**
		 * @brief 在指定的MemRegion上申请分配内存.
		 * @param mem_region	指定的MemRegion的名字
		 * @param byte_size		申请的内存大小
		 * @return	申请得到的MemChunk对象
		 */
		XRT_DLL MemChunk malloc(const std::string& mem_region, uint64_t byte_size) const;

		/** 获取设备默认的RegRegion */
		XRT_DLL const RegRegion& defaultRegRegion() const;

		/**
		 * @brief 将指定的RegRegion设置为默认RegRegion.
		 * @param region_name	指定的RegRegion名字
		 */
		XRT_DLL Device& setDefaultRegRegion(const std::string& region_name);

		/**
		 * @brief 根据名字获取设备的RegRegion.
		 * @param name	RegRegion的名字
		 * @return	相对应的RegRegion对象
		 */
		XRT_DLL const RegRegion& getRegRegion(const std::string& name) const;

		/**
		 * @brief 在默认的RegRegion上读取寄存器.
		 * @param addr		读取的地址
		 * @param relative	是否以相对地址读取寄存器
		 * @return	读取得到的寄存器数据
		 */
		XRT_DLL uint64_t readReg(uint64_t addr, bool relative = false) const;

		/**
		 * @brief 在指定的的RegRegion上读取寄存器.
		 * @param region_name	指定的RegRegion的名字
		 * @param addr		读取的地址
		 * @param relative	是否以相对地址读取寄存器
		 * @return	读取得到的寄存器数据
		 */
		XRT_DLL uint64_t readReg(const std::string& region_name, uint64_t addr, bool relative = false) const;

		/**
		 * @brief 将数据写入默认的RegRegion上的寄存器.
		 * @param addr		写入的地址
		 * @param relative	是否以相对地址写入寄存器
		 */
		XRT_DLL void writeReg(uint64_t addr, uint64_t data, bool relative = false) const;

		/**
		 * @brief 将数据写入指定的RegRegion上的寄存器.
		 * @param region_name	指定的RegRegion的名字
		 * @param addr		写入的地址
		 * @param data		写入的数据
		 * @param relative	是否以相对地址写入寄存器
		 */
		XRT_DLL void writeReg(const std::string& region_name, uint64_t addr, uint64_t data, bool relative = false) const;

		/**
		 * @brief　复位设备.
		 * @param level		复位等级
		 * 
		 * @note 复位等级，不同的设备具有不同的定义和实现，详见具体设备的使用说明
		 */
		XRT_DLL void reset(int level);

		/**
		 * @brief　检查设备.
		 * @param level		检查等级
		 * 
		 * @note 检查等级，不同的设备具有不同的定义和实现，详见具体设备的使用说明
		 */
		XRT_DLL bool check(int level) const;

		/**
		 * @brief　显示设备状态.
		 * @param level		状态等级
		 *
		 * @note 状态等级，不同的设备具有不同的定义和实现，详见具体设备的使用说明
		 */
		XRT_DLL void showStatus(int level) const;

		/**
		 * @brief 获取设备的版本.
		 * @return 表示设备各个版本信息的Map
		 */
		XRT_DLL std::unordered_map<std::string, std::string> version() const;

		/**
		 * @brief	设置同步tensor的最长等待时间
		 * @param	wait_time	等待时间，单位ms
		 */
		XRT_DLL void setWaitTime(uint64_t wait_time);

		xir::Array<xir::CompileTarget> compileTargets() const {
			return (*this)->compileTargets();
		}

	private:
		void initParams(const utils::UrlParser& parser);
		void init();
		void deinit();
	};

	/** Device的注册辅助类型 */
	class DeviceRegistry {
	public:
		class Manager;

		/** Device创建函数的原型 */
		using FCreator = std::function<Device()>;

		/** 设置Device创建函数 */
		XRT_DLL DeviceRegistry& set_creator(FCreator f);

		/**
		 * @brief 注册Device.
		 * @param name			Device的名字
		 * @param can_override	是否允许覆盖, 默认为否
		 */
		XRT_DLL static DeviceRegistry& Register(std::string_view name, bool can_override = false);


		/**
		 * @brief 移除注册的Device.
		 * @param name	Device的名字
		 * @return 如果Device不存在返回false, 否则返回true
		 */
		XRT_DLL static bool Remove(const std::string& name);


		/**
		 * @brief 获取注册的Device.
		 * @param name	Device的名字
		 * @return Device创建函数的Optional
		 */
		XRT_DLL static std::optional<FCreator> Get(const std::string& name);

		/** 获取所有注册Device的名称列表 */
		XRT_DLL static std::vector<std::string_view> ListNames();

	private:
		FCreator fcreator_;
	};

	/**
	 * @brief 默认的内存管理器
	 */
	class DefaultMemManagerNode : public NodeBase<DefaultMemManagerNode, MemManagerNode> {
	public:
		MemPtr start_;
		uint64_t byte_size_;
		std::list<std::pair<MemPtr, uint64_t>> chunk_list_;
		std::vector<const MemChunkNode*> chunk_node_; //保存const MemChunkNode*避免增加引用计数
		mutable std::map<std::string, ObjectRef> info_;
		mutable midware::Mutex mem_mutex_;
		
		DefaultMemManagerNode(MemPtr start, uint64_t byte_size) : start_(start), byte_size_(byte_size) {
			info_.insert({"start", start});
			info_.insert({"byte_size", IntImm(byte_size) });
		};

		XRT_DLL virtual MemChunk malloc(uint64_t byte_size, bool auto_free, uint64_t alignment) override;

		XRT_DLL virtual MemChunk malloc(MemPtr begin, uint64_t byte_size, FChunkDeleter deleter, bool auto_free) override;

		XRT_DLL virtual void free(const MemPtr& ptr) override;

		XRT_DLL virtual std::vector<MemChunk> getAllMemChunk() const override;

		XRT_DLL virtual std::map<std::string, ObjectRef>& getMemRegionInfo() const override;

	};

	class  DefaultMemManager : public HandleBase<DefaultMemManager, MemManager, DefaultMemManagerNode> {};

	namespace utils {
		/**
		 * @brief 不断查询某个条件是否满足，若满足则返回true，若一段时间不满足则停止查询且返回false.
		 * @param check			被查询的条件函数，该函数返回true时认为条件满足
		 * @param timeout		超过timeout时间仍不满足则返回false
		 */
		template<typename predicate, typename Rep, typename Period>
		static bool WaitUntil(predicate check, std::chrono::duration<Rep, Period> timeout){
		auto start = icraft::midware::steady_now();
		while (!check()){
			if(icraft::midware::steady_now() - start > timeout){return false;}
		}
		return true;

		}
	}
}

/// @cond
#define ICRAFT_DECLARE_DEVICE_NODE(DeviceNode)	DeviceNode()
#define ICRAFT_MEM_REGION_FIELD(RegionName, MemRegionType)				\
	mregion_names.push_back(ICRAFT_STR(RegionName));					\
	mem_regions[ICRAFT_STR(RegionName)] = MemRegionType::Init()._bindDevice(this)
#define ICRAFT_REG_REGION_FIELD(RegionName, RegRegionType)				\
	rregion_names.push_back(ICRAFT_STR(RegionName));					\
	reg_regions[ICRAFT_STR(RegionName)] = RegRegionType::Init()._bindDevice(this)

#define ICRAFT_DEFAULT_MEM_REGION_FIELD(RegionName, MemRegionType)		\
	ICRAFT_MEM_REGION_FIELD(RegionName, MemRegionType);					\
	default_mem_region = mem_regions.at(ICRAFT_STR(RegionName))
#define ICRAFT_DEFAULT_REG_REGION_FIELD(RegionName, RegRegionType)		\
	ICRAFT_REG_REGION_FIELD(RegionName, RegRegionType);					\
	default_reg_region = reg_regions.at(ICRAFT_STR(RegionName))
#define ICRAFT_REGION_MEM_MANAGER_FIELD(RegionName, MemManagerNode, ...)		\
	mem_regions[ICRAFT_STR(RegionName)]._bindMemmanager(make_object<MemManagerNode>(__VA_ARGS__).get())

/** Device注册生成宏 */
#define ICRAFT_DEVICE_REG_VAR_DEF															\
static ICRAFT_ATTRIBUTE_UNUSED ::icraft::xrt::DeviceRegistry __make_device

/** Device注册辅助宏 */
#define ICRAFT_REGISTER_DEVICE(DeviceHeadURL, DeviceType)									\
 ICRAFT_STR_CONCAT(ICRAFT_DEVICE_REG_VAR_DEF, __COUNTER__) =								\
      ::icraft::xrt::DeviceRegistry::Register(DeviceHeadURL)								\
.set_creator([](){ return DeviceType::Init(); })
/// @endcond

#endif //XRT_DEVICE_PCH_GUARD
