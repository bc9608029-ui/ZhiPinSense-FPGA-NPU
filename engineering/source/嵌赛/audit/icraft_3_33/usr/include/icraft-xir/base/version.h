#pragma once
#include <string_view>
#include <icraft-xir/base/dllexport.h>


namespace icraft::xir {

	/**
	* @brief 获取版本号
	* @return 表示版本号的字符串"<major>.<minor>.<patch>"
	*/
	XIR_DLL std::string_view MainVersion();

	/**
	* @brief 获取全版本号
	* @return 表示版本号的字符串"<major>.<minor>.<patch>.<CommitSinceTag>-<CommitID>+m?(<BuildTime>)"
	*/
	XIR_DLL std::string_view FullVersion();

	/** 获取主版本号 */
	XIR_DLL uint64_t MajorVersionNum();

	/** 获取次版本号 */
	XIR_DLL uint64_t MinorVersionNum();

	/** 获取补丁版本号 */
	XIR_DLL uint64_t PatchVersionNum();

	/** 获取Icraft版本号 */
	XIR_DLL std::string_view IcraftVersion();

	/** 获取自上个Tag提交了所少次 */
	XIR_DLL uint64_t CommitSinceTag();

	/** 获取CommitID */
	XIR_DLL std::string_view CommitID();

	/** 检查是否有修改 */
	XIR_DLL bool IsModified();

	/** 获取编译时间 */
	XIR_DLL std::string_view BuildTime();
}
