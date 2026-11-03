#pragma once
#ifndef XRT_TENSOR_PCH_GUARD
#define XRT_TENSOR_PCH_GUARD
#include "icraft-xir/core/data_type.h"
#include "icraft-xrt/base/dllexport.h"
#include "icraft-utils/midware/thread.hpp"
#include "icraft-utils/midware/clock.hpp"
#include <icraft-xrt/core/device.h>
#include <icraft-xir/core/data.h>

namespace icraft::xrt {
	using icraft::xir::TensorType;

	/**
	 * @brief 表示张量的类型.
	 */
	class TensorNode : public NodeBase<TensorNode, Node> {
	private:
		TensorType dtype_;
		MemChunk chunk_;
		uint64_t offset_;
		bool ready_ = true;
		std::function<bool(const Device& device)> check_func_;

	friend class Tensor;

	public:
		virtual void accept(AttrVisitor& visitor) override {
			visitor.visit("dtype", dtype_);
			visitor.visit("chunk", chunk_);
		};

		bool reduceAccept(TensorNode* other, const ReduceVisitor& reduce) const {
			return reduce(dtype_, other->dtype_)
				&& reduce(chunk_, other->chunk_);
		}
	};

	/**
	 * @brief 张量的引用类.
	 */
	class Tensor : public HandleBase<Tensor, Handle, TensorNode> {
	public:
		/** Tensor的检查函数，用于检查是否ready */
		using CheckFunc = std::function<bool(const Device& device)>;

		/** 默认构造函数 */
		Tensor() = default;

		/**
		 * @brief 构造函数.
		 * @param	dtype		数据类型
		 * @param	chunk		数据所在的内存块
		 * @param	offset		数据在内存块中的偏移
		 * @param	check_func	状态检查函数
		 */
		XRT_DLL Tensor(TensorType dtype, MemChunk chunk, uint64_t offset = 0, CheckFunc check_func = nullptr);

		/**
		 * @brief 构造函数，构造一个没有数据的Tensor.
		 * @param	dtype		数据类型
		 * @param	check_func	状态检查函数
		 */
		XRT_DLL Tensor(TensorType dtype, CheckFunc func = nullptr);

		/**
		 * @brief 构造函数，从xir::Value构造.
		 */
		XRT_DLL Tensor(const icraft::xir::Value &value);

		/**
		 * @brief 构造函数，从xir::Params构造.
		 */
		XRT_DLL Tensor(const icraft::xir::Params& params);

		/**
		 * @brief 设置张量的数据类型.
		 * @param dtype	被设置的数据类型
		 */
		XRT_DLL Tensor& setDType(TensorType dtype);

		/**
		 * @brief 设置张量数据所在的内存块.
		 * @param chunk		数据所在内存块
		 * @param offset	数据在内存块中的偏移
		 */
		XRT_DLL Tensor& setData(MemChunk chunk, uint64_t offset = 0);

		/**
		 * @brief 设置张量的数据检查函数.
		 * @param check_func	状态检查函数
		 */
		XRT_DLL Tensor& setCheckFunc(CheckFunc check_func);

		/**
		 * @brief 设置张量的的状态.
		 * @param ready	状态是否ready
		 */
		XRT_DLL Tensor& setReady(bool ready);

		/**
		 * @brief	在指定的MemRegion上分配Tensor所需要的内存.
		 * @param	mregion		指定的MemRegion
		 * 
		 * @note 如果Tensor已经分配了内存块，该方法会覆盖原有的内存块
		 */
		XRT_DLL Tensor& mallocOn(const MemRegion& mregion);

		/**
		 * @brief 从指定的Tensor复制数据.
		 * @param dest_offset	目标偏移位置
		 * @param src_tensor	源Tensor
		 * @param src_offset	源偏移位置
		 * @param byte_size		字节大小
		 */
		XRT_DLL void copyFrom(
			uint64_t dest_offset, 
			const Tensor& src_tensor,
			uint64_t src_offset,
			uint64_t byte_size
		);

		/** 获取该Tensor数据的起始位置指针 */
		XRT_DLL MemPtr data() const;

		/** 获取该Tensor数据所在的内存块 */
		XRT_DLL const MemChunk& chunk() const;

		/** 获取该Tensor数据在内存块中的偏移 */
		XRT_DLL uint64_t offset() const;

		/** 获取该Tensor的数据类型 */
		XRT_DLL const TensorType& dtype() const;

		/** 检查该Tensor是否ready */
		XRT_DLL bool isReady() const;

		/** 检查该Tensor是否具有数据 */
		XRT_DLL bool hasData() const;

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
		 * @biref 将Tensor复制到指定的MemRegion的上.
		 * @param mregion	指定的MemRegion
		 * @return 在指定MemRegion复制得到的Tensor
		 * 
		 * @note 如果该Tensor已经在指定的MemRegion上，则复制不会发生，而是直接返回原Tensor
		 */
		XRT_DLL Tensor to(const MemRegion& mregion) const;

		/**
		 * @brief 检查该Tensor是否在指定的MemRegion上.
		 * @tparam	mregion	指定的MemRegion
		 */
		XRT_DLL bool isOn(const MemRegion& mregion) const;

		/** 获取该Tensor所在的MemRegion */
		XRT_DLL const MemRegion& memRegion() const;

		/**
		 * @brief 将Tensor的数据按指定格式导出到指定的输出流中.
		 * @param	os		指定的输出流
		 * @param	format	指定的输出格式
		 * 
		 * @note 支持的格式由三个字母表示：
		 * * 第一个字母表示排布，H表示硬件，S表示软件
		 * * 第二个字母表示数值，F表示浮点，Q表示定点
		 * * 第三个字母表示序列化形式，B表示二进制，T表示文本
		 * 
		 * 若一个Tensor原本的排布时H，那么可以转为S；若原本的数值为Q，那么可以转为F；反之不可
		 */
		XRT_DLL void dump(std::ostream& os, const std::string& format = "") const;
		
		/**
		 * @brief 等待Tensor的状态ready.
		 * @param	timeout	等待的超时时间，超时则返回false
		 * @param	sleep	两次查询之间的休眠时间，默认为0
		 * @return	若timeout时间内查询到状态ready则返回true，否则返回false
		 */
		template<typename Rep, typename Period>
		bool waitForReady(
			std::chrono::duration<Rep, Period> timeout,
			std::chrono::duration<Rep, Period> sleep = std::chrono::duration<Rep, Period>::zero()
		) const {
			ICRAFT_CHECK(this->hasData(), 11012).append("The tensor has no chunk allocated!");
			auto mptr = get_mutable();
			if (mptr->ready_) return true;
			auto device = mptr->chunk_->region.device();
			auto milli_timeout = std::chrono::duration_cast<std::chrono::milliseconds>(timeout);
			const auto min_wait_ms = static_cast<std::chrono::milliseconds::rep>(device->wait_time);
			if (milli_timeout.count() < min_wait_ms)
			{
				milli_timeout = std::chrono::milliseconds(min_wait_ms);
			}
			auto start = icraft::midware::steady_clock::now();
			while (!mptr->check_func_(device)) {
				if (icraft::midware::steady_clock::now() - start > milli_timeout) { return false; }
				if (sleep != std::chrono::seconds::zero()) {
					icraft::midware::sleep_for(sleep);
				}
			}
			mptr->ready_ = true;
			return true;
		}

		/**
		 * @brief		填充数据
		 * @tparam	T	被填充数据的类型，必须是POD
		 * @param	f	数据的生成函数，以index作为参数返回对应的T
		 */
		template <typename T, typename = typename std::enable_if_t<std::is_pod_v<T>>>
		Tensor& fill(std::function<T(uint64_t)> f) {
			ICRAFT_CHECK(this->hasData(), 11012).append("The tensor has no chunk allocated!");
			auto dtype = this->dtype();
			auto etype = dtype->element_dtype;
			auto tbits = sizeof(T) * 8;
			auto sbits = etype.bits();
			ICRAFT_CHECK(tbits == sbits, 11010)
				.append("sizeof(T) not match element_dtype, {} vs. {}", tbits, sbits);
			auto num_elements = dtype.numElements();
			auto filled_data = std::make_unique<T[]>(num_elements);
			for (uint64_t i = 0; i < num_elements; i++) {
				filled_data[i] = f(i);
			}
			(*this)->chunk_.write(0, (char*)filled_data.get(), dtype.bytes());
			return *this;
		}
	};
}
#endif //XRT_TENSOR_PCH_GUARD