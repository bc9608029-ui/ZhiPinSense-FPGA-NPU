#pragma once
#include <icraft-xir/core/network.h>
#include <icraft-xir/core/reflection.h>


namespace icraft::xir {

	/** ObjectRef 属性个数计数器类 */
	class GetAttrNums : public AttrVisitor {
	private:
		/// @cond
		virtual void _visit(std::string_view key, float& value) { attrCount++; }
		virtual void _visit(std::string_view key, int64_t& value) { attrCount++; }
		virtual void _visit(std::string_view key, uint64_t& value) { attrCount++; }
		virtual void _visit(std::string_view key, int& value) { attrCount++; }
		virtual void _visit(std::string_view key, bool& value) { attrCount++; }
		virtual void _visit(std::string_view key, std::string& value, std::string_view tinfo = "") { attrCount++; }
		virtual void _visit(std::string_view key, ObjectRef& value, std::string_view tinfo) { attrCount++; }
		/// @endcond

		int attrCount = 0;

	public:
		int getAttrNums(const ObjectRef& ref) {
			auto node = ref.as_mutable<Node>();
			node->accept(*this);
			return this->attrCount;
		}
	};


	/** ObjectRef MSG序列化类，将ObjectRef序列化到MSG */
	class MSGDumper : public AttrVisitor {
	private:
		/// @cond
		XIR_DLL virtual void _visit(std::string_view key, float& value);
		XIR_DLL virtual void _visit(std::string_view key, int64_t& value);
		XIR_DLL virtual void _visit(std::string_view key, uint64_t& value);
		XIR_DLL virtual void _visit(std::string_view key, int& value);
		XIR_DLL virtual void _visit(std::string_view key, bool& value);
		XIR_DLL virtual void _visit(std::string_view key, std::string& value, std::string_view tinfo = "");

		XIR_DLL virtual void _visit(std::string_view key, ObjectRef& value, std::string_view tinfo);
		/// @endcond

		XIR_DLL void dumpArray(const ObjectRef& ref, std::string_view tinfo);

	public:
		XIR_DLL MSGDumper();

		/**
		 * @brief 将指定的ObjectRef序列化到MSG
		 * @param ref 指定的ObjectRef
		 */
		XIR_DLL void dump(const ObjectRef& ref, std::string_view tinfo = TypeName<ObjectRef>());

		XIR_DLL void write(std::ostream& stream);

		struct Impl_MSGD;
		std::shared_ptr<Impl_MSGD> impl_msgd;
	};


	/** ObjectRef MSG解析类，将MSG反序列化到ObjectRef */
	class MSGParser : public AttrVisitor {
	private:
		/// @cond
		XIR_DLL virtual void _visit(std::string_view key, float& value);
		XIR_DLL virtual void _visit(std::string_view key, int64_t& value);
		XIR_DLL virtual void _visit(std::string_view key, uint64_t& value);
		XIR_DLL virtual void _visit(std::string_view key, int& value);
		XIR_DLL virtual void _visit(std::string_view key, bool& value);
		XIR_DLL virtual void _visit(std::string_view key, std::string& value, std::string_view tinfo = "");

		XIR_DLL virtual void _visit(std::string_view key, ObjectRef& value, std::string_view tinfo);
		/// @endcond

	public:
		XIR_DLL MSGParser();

		/**
		 * @brief 读取MSG
		 * @param buffer MSG所在buffer
		 */
		XIR_DLL void read(const std::string& buffer);

		/** 将读取的MSG反序列化到指定RefType的ObjectRef */
		template<typename RefType> RefType parse() {
			auto node = make_object<typename RefType::NodeType>();
			node->accept(*this);
			return RefType::Get(node);
		}

		struct Impl_MSGP;
		std::shared_ptr<Impl_MSGP> impl_msgp;
	};


	/**
	* @brief 解析MSG文件，反序列化得到Network
	* @param buffer 指定的MSG对象文件
	* @return 反序列化得到的Network对象
	*/
	Network CreateNetworkFromMSG(const std::string& buffer);
}
