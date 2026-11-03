#pragma once
#include "icraft-utils/logging.h"
#include "icraft-utils/dllexport.h"


namespace icraft {

	/**
	 * @brief 表示进度条的类	 * @details 使用ProgressBar可以在显示一个进度条并控制进度
	 */
	class ProgressBar {
	public:
		/** 构造函数 */
		UTILS_DLL ProgressBar();

		/**
		 * @brief 构造函数，从颜色构造		 * @param color	颜色名称
		 */
		UTILS_DLL explicit ProgressBar(ColorName color);

		/**
		 * @brief 设置进度条颜色		 * @param color	颜色名称
		 */
		UTILS_DLL void setColor(ColorName color);

		/**
		 * @brief 设置进度条进度		 * @param progress	进度条进度
		 */
		UTILS_DLL void setProgress(float progress);

		/**
		 * @brief 获取进度条进度		 * @return 进度条进度
		 */
		UTILS_DLL float progress() const;

		/**
		 * @brief 进度前进1		 */
		UTILS_DLL void tick();

		/**
		 * @brief 进度前进 @a progress		 * @param progress 前进的进度
		 */
		UTILS_DLL void tick(int progress);

		/**
		 * @brief 设置前置文本		 * @param text 前置文本		 */
		UTILS_DLL void setPrefixText(const std::string& text);

		/**
		 * @brief 设置后置文本		 * @param text 后置文本		 */
		UTILS_DLL void setPostfixText(const std::string& text);

		/**
		 * @brief 是否显示消耗时间		 * @param show 为true时显示消耗时间		 */
		UTILS_DLL void showElapsedTime(bool show);

		/**
		 * @brief 是否显示剩余时间		 * @param show 为true时显示剩余时间		 */
		UTILS_DLL void showRemainingTime(bool show);

		/**
		 * @brief 获取当前进度		 * @return 当前进度		 */
		UTILS_DLL float current();

		/**
		 * @brief 进度条是否完成		 * @return 完成时返回true
		 */
		UTILS_DLL bool isCompleted();

		/**
		 * @brief 标记进度条已完成		 */
		UTILS_DLL void markAsCompleted();
		
		/// @cond
		UTILS_DLL ~ProgressBar();
		/// @endcond

	private:
		struct Impl_BPB;
		std::shared_ptr<Impl_BPB> impl_bpb;

		friend class DynamicProgressBars;
	};

	/**
	 * @brief 表示动态进度条的类	 * @details DynamicProgressBars可以动态的添加和减少进度条	 */
	class DynamicProgressBars {
	public:
		/**
		 * @brief 构造函数，从ProgressBar的初始化列表构造		 * @param bars	ProgressBar的初始化列表
		 */
		UTILS_DLL DynamicProgressBars(std::vector<ProgressBar> bars);

		/**
		 * @brief 获取第 @a index 个进度条		 * @param index 进度条的索引
		 * @return @a index 处的进度条
		 */
		UTILS_DLL ProgressBar& operator[](size_t index);

		/**
		 * @brief 添加进度条		 * @param bar 被添加的进度条
		 * @return 添加后总进度条的个数
		 */
		UTILS_DLL size_t append(ProgressBar& bar);

		/**
		 * @brief 是否隐藏完成的进度条		 * @param hide 为true时隐藏
		 */
		UTILS_DLL void hideBarWhenComplete(bool hide);

	private:
		struct Impl_DP;
		std::shared_ptr<Impl_DP> impl_dp;
	};
}
