#pragma once

#include <icraft-xir/core/data.h>

namespace icraft::xrt::utils {
	/**
	* @brief 验证的时间点，表示运行验证的时间点或者检查验证是否通过的时间点
	*/
	enum class ValidateTime {
		Apply, Serialize
	};
	/**
	* @brief 验证结果，若存在多个结果需要合并，合并优先级按定义顺序从低到高排序，即NotRun>Fail>Success
	*/
	struct ValidateResult {
		enum class ValidateResultEnum {
			/**
			* @brief 验证成功
			*/
			Success,
			/**
			* @brief 验证失败
			*/
			Fail,
			/**
			* @brief 尚未验证
			*/
			NotRun
		};
		ValidateResult(ValidateResultEnum result) :result(result) {}
		ValidateResult(ValidateResultEnum result, std::string_view message) : result(result), message(message) {}

		void throw_if_fail() const {
			if (result != ValidateResultEnum::Success) {
				ICRAFT_LOG_EXCEPT().append(message);
			}
		}

		static ValidateResult Default() {
			return ValidateResult(ValidateResultEnum::NotRun);
		}
		bool operator>(const ValidateResult& x) const {
			return static_cast<int>(result) > static_cast<int>(x.result);
		}

		ValidateResultEnum result;
		std::string message;
	};

	/**
	* @brief 验证器的数据容器，用于存储验证器所需的数据
	*/
	class ValidatorNode :public xir::NodeBase<ValidatorNode, Node> {
	public:
		/**
		* @brief 运行验证的时间点
		*/
		ValidateTime validate_at;
		/**
		* @brief 检查验证是否通过的时间点
		*/
		ValidateTime validate_for;
		/**
		* @brief 运行验证过程
		*/
		virtual void validate() = 0;
		/**
		* @brief 验证结果
		*/
		ValidateResult validate_result = ValidateResult::Default();

		virtual void accept(AttrVisitor& visitor) { ICRAFT_LOG_EXCEPT().append("not implemented"); }

		virtual bool reduceAccept(Node* other, const ReduceVisitor& reduce) const { ICRAFT_LOG_EXCEPT().append("not implemented"); return true; }
		virtual bool parentReduceAccept(Node* other, const ReduceVisitor& reduce) const { ICRAFT_LOG_EXCEPT().append("not implemented"); return true; }
	};
	/**
	* @brief 验证器引用，用于在Session的运行过程中检查是否存在非法状态
	*/
	class Validator:public xir::VirtualBase<Validator,Handle,ValidatorNode> {
	public:
		void validate() {
			get_mutable()->validate();
		}
		ValidateResult result() const {
			return (*this)->validate_result;
		}
	};
	class LambdaValidatorNode :public NodeBase<LambdaValidatorNode, ValidatorNode> {
	public:
		LambdaValidatorNode(const std::function<ValidateResult()>& func) :func(func) {
		}
		void validate() override {
			validate_result = func();
		}

	private:
		std::function<ValidateResult()> func;
	};
	class LambdaValidator :public VirtualBase<LambdaValidator, Validator, LambdaValidatorNode> {
	public:
		template<typename Func>
		LambdaValidator(Func&& func, ValidateTime validate_at, ValidateTime validate_for) {
			data_ = make_object<LambdaValidatorNode>(std::function<ValidateResult()>(std::forward<Func>(func)));
			get_mutable()->validate_at = validate_at;
			get_mutable()->validate_for = validate_for;
		}
	};
	class Validation {
	public:
		void add_validator(const Validator& validator) {
			validator_runners.emplace(std::make_pair(validator->validate_at,validator));
			validator_results.emplace(std::make_pair(validator->validate_for, validator));
		}
		ValidateResult validate(ValidateTime validate_time) {
			// do validate
			{
				auto range = validator_runners.equal_range(validate_time);
				for (auto i = range.first; i != range.second; i++) {
					auto&& validator = i->second;
					validator.validate();
				}
			}
			// retrieve result
			{
				ValidateResult result = ValidateResult(ValidateResult::ValidateResultEnum::Success);
				auto range = validator_results.equal_range(validate_time);
				for (auto i = range.first; i != range.second; i++) {
					auto&& validator = i->second;
					auto validator_result = validator.result();
					if (validator_result > result) {
						result = validator_result;
					}
				}
				return result;
			}
		}

	private:
		std::unordered_multimap<ValidateTime, Validator> validator_runners;
		std::unordered_multimap<ValidateTime, Validator> validator_results;
	};
}