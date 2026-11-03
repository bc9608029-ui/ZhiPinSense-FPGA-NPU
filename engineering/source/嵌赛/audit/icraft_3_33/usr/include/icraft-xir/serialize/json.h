#pragma once
#include <icraft-xir/core/reflection.h>
#include <icraft-xir/utils/json.hpp>


namespace icraft::xir {


	using Json = nlohmann::json;


	/** ObjectRef Json序列化类，将任意ObjectRef序列化到Json */
	class JsonPrinter : public AttrVisitor {
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

		XIR_DLL Json dumpArray(const ObjectRef& ref, std::string_view tinfo);

	public:
		/**
		 * @brief 将指定的ObjectRef序列化到Json
		 * @param ref 指定的ObjectRef
		 * @param options 自定义选项
		 * @return 序列化所得Json对象
		 */
		XIR_DLL Json dump(const ObjectRef& ref, std::string_view tinfo = TypeName<ObjectRef>());

		Json _json;
	};


	class Network;


	/** ObjectRef Json解析类，将Json反序列化到ObjectRef */
	class JsonParser : public AttrVisitor {
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

		XIR_DLL ObjectRef parseArray(Json& json, std::string_view tinfo);

		XIR_DLL Operation parseOperation(Json& j_op);

	public:
		/**
		 * @brief 解析Json，反序列化得到ObjectRef
		 * @param json 指定的Json对象
		 * @param options 自定义选项
		 * @return 反序列化得到的ObjectRef对象
		 */
		XIR_DLL ObjectRef parse(Json& json, std::string_view tinfo = TypeName<ObjectRef>());

		Json _json;
	};


	/** Params序列化类，将所包含的Params序列化到输出流 */
	class ParamsDumper : public AttrVisitor {
	private:
		/// @cond
		virtual void _visit(std::string_view key, float& value) {}
		virtual void _visit(std::string_view key, int64_t& value) {}
		virtual void _visit(std::string_view key, uint64_t& value) {}
		virtual void _visit(std::string_view key, int& value) {}
		virtual void _visit(std::string_view key, bool& value) {}
		virtual void _visit(std::string_view key, std::string& value, std::string_view tinfo = "") {}

		virtual void _visit(std::string_view key, ObjectRef& value, std::string_view tinfo) {
			genParamsTable(value);
		}
		/// @endcond

		XIR_DLL void genParamsTable(const ObjectRef& ref);

		std::unordered_map<int, std::tuple<uint64_t, const char*>> params_table_;
		std::ostream& stream_;

	public:
		/**
		 * @brief 构造函数
		 * @param stream 指定的输出流
		 */
		ParamsDumper(std::ostream& stream) : stream_(stream) {}

		/**
		 * @brief 将ObjectRef中所包含的Params序列化到输出流
		 * @param ref 指定的ObjectRef
		 * @return 被序列化参数的字节大小
		 */
		XIR_DLL uint64_t dump(const ObjectRef& ref);

		/**
		 * @brief 计算ObjectRef中所包含的Params的MD5，并写到输出流
		 * @param ref 指定的ObjectRef
		 * @return 被序列化参数的字节大小
		 */
		XIR_DLL uint64_t calcMd5(const ObjectRef& ref);
	};

	/** Params反序列化类，加载输入流中的Params数据 */
	class ParamsLoader : public AttrVisitor {
	private:
		/// @cond
		virtual void _visit(std::string_view key, float& value) {}
		virtual void _visit(std::string_view key, int64_t& value) {}
		virtual void _visit(std::string_view key, uint64_t& value) {}
		virtual void _visit(std::string_view key, int& value) {}
		virtual void _visit(std::string_view key, bool& value) {}
		virtual void _visit(std::string_view key, std::string& value, std::string_view tinfo = "") {}

		virtual void _visit(std::string_view key, ObjectRef& value, std::string_view tinfo) {
			loadParams(value);
		}
		/// @endcond

		XIR_DLL void loadParams(ObjectRef& ref);

		std::unordered_map<int, uint64_t> offset_map_;
		std::istream& stream_;

	public:
		/**
		 * @brief 构造函数
		 * @param stream 指定的输入流
		 */
		ParamsLoader(std::istream& stream) : stream_(stream) {}

		/**
		 * @brief 加载输入流中的Params数据到ObjectRef
		 * @param ref 指定的ObjectRef
		 */
		XIR_DLL void load(ObjectRef& ref);
	};


	/** Params惰性加载器，惰性加载指定的数据 */
	class ParamsLazyLoader : public AttrVisitor {
	private:
		/// @cond
		virtual void _visit(std::string_view key, float& value) {}
		virtual void _visit(std::string_view key, int64_t& value) {}
		virtual void _visit(std::string_view key, uint64_t& value) {}
		virtual void _visit(std::string_view key, int& value) {}
		virtual void _visit(std::string_view key, bool& value) {}
		virtual void _visit(std::string_view key, std::string& value, std::string_view tinfo = "") {}

		virtual void _visit(std::string_view key, ObjectRef& value, std::string_view tinfo) {
			loadParams(value);
		}
		/// @endcond

		XIR_DLL void loadParams(ObjectRef& ref);

		static void null_deleter(const char*) {}

		std::unordered_map<int, uint64_t> offset_map_;
		char* mapped_ptr_;

	public:
		/**
		 * @brief 构造函数
		 * @param mapped_ptr 指定的数据指针
		 */
		ParamsLazyLoader(char* mapped_ptr) : mapped_ptr_(mapped_ptr) {}

		/**
		 * @brief 惰性加载指定数据到ObjectRef
		 * @param ref 指定的ObjectRef
		 */
		XIR_DLL void load(ObjectRef& ref);
	};

	/** 计算文件输入流的MD5 */
	XIR_DLL std::string CalcMD5(std::istream& stream);

	/** 计算指定数据的MD5 */
	XIR_DLL std::string CalcMD5(char* ptr, uint64_t byte_size);

	/** 重载输出流操作符 */
	XIR_DLL std::ostream& operator<<(std::ostream& os, const ObjectRef& ref);

	/** 重载输出流操作符 */
	XIR_DLL std::ostream& operator<<(std::ostream& os, const Object* obj);
}
