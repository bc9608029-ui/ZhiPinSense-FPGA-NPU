#pragma once

#include <chrono>

namespace icraft::xrt::utils {
    /**
     * @brief 计时器，为计时提供方便.
     */
    class Timer {
    public:
        /** 开始计时 */
        void tik() {
            start = std::chrono::high_resolution_clock::now();
        }

        /** 停止计时 */
        void tok() {
            end = std::chrono::high_resolution_clock::now();
        }

        /**
         * @brief   获取计时的时间.
         * @tparam  T   时间单位类型，支持std::chrono::seconds等单位类型
         * @return  指定单位下的时间
         */
        template <typename T>
        double elapsed() const {
            return std::chrono::duration<double, typename T::period>(end - start).count();
        }

        /** 获取纳秒表示的计时时间 */
        std::chrono::nanoseconds duration() const {
            return end - start;
        }

    private:
        std::chrono::time_point<std::chrono::high_resolution_clock> start, end;
    };
}
