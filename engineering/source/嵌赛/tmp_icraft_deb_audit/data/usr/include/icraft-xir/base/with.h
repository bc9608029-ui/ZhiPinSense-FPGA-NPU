#pragma once


namespace icraft::xir {

	/*!
	 * \brief RAII 上下文管理器，模仿python的with
	 *
	 * \code
	 * {
	 *   With<PassContext> scope(arguments);
	 *   // effect take place.
	 * }
	 * \endcode
	 *
	 * \tparam 上下文对象的类型
	 */
	template <typename ContextType>
	class With {
	public:

		template <typename... Args>
		explicit With(Args&&... args) : ctx_(std::forward<Args>(args)...) {
			ctx_._enterWithScope();
		}

		~With() { ctx_._exitWithScope(); }

		// 删除复制和移动构造函数
		With(const With& other) = delete;
		With& operator=(const With& other) = delete;
		With(With&& other) = delete;
		With& operator=(With&& other) = delete;

		ContextType* get() { return &ctx_; }
		const ContextType* get() const { return &ctx_; }

		ContextType* operator->() { return get(); }
		const ContextType* operator->() const { return get(); }
		ContextType& operator*() { return *get(); }
		const ContextType* operator*() const { return *get(); }

		ContextType operator()() { return ctx_; }

	private:
		ContextType ctx_;
	};
}
