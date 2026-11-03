#pragma once
#include <icraft-xir/core/node.h>
#include <icraft-xir/utils/wise_enum.h>


namespace icraft::xir {

	/** 表示算子的编译目标的类型 */
	class CompileTargetNode : public NodeBase<CompileTargetNode, Node> {
	public:
		virtual void accept(AttrVisitor& visitor) override {}
	};


	/** 编译目标的引用类型 */
	class CompileTarget : public VirtualBase<CompileTarget, Handle, CompileTargetNode> {};


	/** 表示Host编译目标的类型 */
	class HostTargetNode : public NodeBase<HostTargetNode, CompileTargetNode> {};


	/** Host编译目标的引用类型 */
	class HostTarget : public HandleBase<HostTarget, CompileTarget, HostTargetNode> {};


	/** 表示FPGA编译目标的类型 */
	class FPGATargetNode : public NodeBase<FPGATargetNode, CompileTargetNode> {};


	/** FPGA编译目标的引用类型 */
	class FPGATarget : public HandleBase<FPGATarget, CompileTarget, FPGATargetNode> {};


	/** 表示Custom编译目标的类型 */
	class CustomTargetNode : public NodeBase<CustomTargetNode, CompileTargetNode> {};


	/** Custom编译目标的引用类型 */
	class CustomTarget : public HandleBase<CustomTarget, CompileTarget, CustomTargetNode> {};


	/** 表示Buyi编译目标的类型 */
	class BuyiTargetNode : public NodeBase<BuyiTargetNode, CompileTargetNode> {};


	/** Buyi编译目标的引用类型 */
	class BuyiTarget : public HandleBase<BuyiTarget, CompileTarget, BuyiTargetNode> {};


	/** 表示Zhuge编译目标的类型 */
	class ZhugeTargetNode : public NodeBase<ZhugeTargetNode, CompileTargetNode> {
	public:
		/**
		* @enum	Core
		* @brief	表示细分的的Zhuge后端芯片
		*/
		WISE_ENUM_CLASS_MEMBER(Core, ZG330, ZG340, ZG30S);

		Core core = Core::ZG330;		///< 表示细分的的Zhuge后端芯片

		XIR_DLL void accept(AttrVisitor& visitor);

		XIR_DLL bool reduceAccept(ZhugeTargetNode* other, const ReduceVisitor& reduce) const;
	};

	/** Zhuge编译目标的引用类型 */
	class ZhugeTarget : public HandleBase<ZhugeTarget, CompileTarget, ZhugeTargetNode> {
	public:
		using Core = ZhugeTargetNode::Core;

		/** 默认构造函数 */
		ZhugeTarget() = default;

		XIR_DLL ZhugeTarget(Core core);
	};


	/** 表示Wolong编译目标的类型 */
	class WolongTargetNode : public NodeBase<WolongTargetNode, CompileTargetNode> {
	public:
		/**
		* @enum	Core
		* @brief	表示细分的的Wolong(Zhuge)后端芯片
		*/
		WISE_ENUM_CLASS_MEMBER(Core, WL340, WL30S);

		Core core = Core::WL340;		///< 表示细分的的Wolong(Zhuge)后端芯片

		XIR_DLL void accept(AttrVisitor& visitor);

		XIR_DLL bool reduceAccept(WolongTargetNode* other, const ReduceVisitor& reduce) const;
	};


	/** Wolong编译目标的引用类型 */
	class WolongTarget : public HandleBase<WolongTarget, CompileTarget, WolongTargetNode> {
	public:
		using Core = WolongTargetNode::Core;

		/** 默认构造函数 */
		WolongTarget() = default;

		XIR_DLL WolongTarget(Core core);
	};
}
