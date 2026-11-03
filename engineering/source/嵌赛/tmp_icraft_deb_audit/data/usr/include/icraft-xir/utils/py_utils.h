#pragma once
#include <pybind11/pybind11.h>

#include <icraft-xir/core/node.h>


#define ICRAFT_BIND_OP_PROPERTY(OpType, PropType, prop, docs)					\
	.def_property(#prop,														\
		[](OpType& x) { return x->prop; },										\
		[](OpType& x, const PropType& prop) { x.get_mutable()->prop = prop;},	\
		docs																	\
	)


namespace icraft::xir {

	namespace py = pybind11;
	using namespace py::literals;

	template <typename type_, typename base_, typename... options>
	void add_virtual_handle_methods(py::class_<type_, base_, options...>& cls) {
		cls.def_readonly_static("type_key", &type_::NodeType::type_key)
			.def("clone", &type_::clone, "depth"_a = 1,
				R"(
				克隆一份该对象
				:param depth:	克隆的深度，默认为1，即浅克隆
				:return:		克隆得到的新对象
				)")
			.def(py::init([](const ObjectRef& base) {
				return Downcast<type_>(base);
				}),
				"将父类强制转换为子类（该类型）"
				);
	}

	template <typename type_, typename base_, typename... options>
	void add_handle_methods(py::class_<type_, base_, options...>& cls) {
		add_virtual_handle_methods(cls);

		cls.def_static("Init", &type_::Init, "创建一个初始化(非空)对象");
	}
}