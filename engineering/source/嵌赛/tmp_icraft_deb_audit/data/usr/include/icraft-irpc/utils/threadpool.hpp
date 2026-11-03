/**
 * @file threadpool.hpp
 * @author Weifan Gao (gaoweifan@fmsh.com.cn)
 * @brief 简易线程池实现
 * @details https://github.com/mtrebi/thread-pool
 * @date 2023-09-12
 * 
 * @copyright Copyright (c) 2023 Shanghai Fudan Microelectronics Group Co., Ltd. All rights reserved.
 * 
 */
#ifndef _THREADPOOL_H
#define _THREADPOOL_H

#include <functional>
#include <future>
#include <mutex>
#include <condition_variable>
#include <queue>
#include <thread>
#include <utility>
#include <vector>
#include <iostream>
namespace irpc::utils{
    /**
     * @brief Thread safe implementation of a Queue using an std::queue
     * 
     * @tparam T type of queue element
     */
    template <typename T>
    class SafeQueue {
    private:
    std::queue<T> m_queue;
    std::mutex m_mutex;
    public:
    SafeQueue() {}
    SafeQueue(SafeQueue& other) {}//TODO:
    ~SafeQueue() {}

    bool empty() {
        const std::lock_guard<std::mutex> lock(m_mutex);
        return m_queue.empty();
    }
    
    int size() {
        const std::lock_guard<std::mutex> lock(m_mutex);
        return m_queue.size();
    }

    void enqueue(T& t) {
        const std::lock_guard<std::mutex> lock(m_mutex);
        m_queue.push(t);
    }
    
    bool dequeue(T& t) {
        const std::lock_guard<std::mutex> lock(m_mutex);

        if (m_queue.empty()) {
        return false;
        }
        t = std::move(m_queue.front());
        
        m_queue.pop();
        return true;
    }
    };

    /**
     * @brief thread pool
     * @details A thread pool is a technique that allows developers to exploit the concurrency of modern processors in an easy and efficient manner. 
     * It's easy because you send "work" to the pool and somehow this work gets done without blocking the main thread. 
     * It's efficient because threads are not initialized each time we want the work to be done. 
     * Threads are initialized once and remain inactive until some work has to be done. This way we minimize the overhead.
     * 
     */
    /*
    class ThreadPool {
    private:
    class ThreadWorker {
    private:
        int m_id;
        ThreadPool * m_pool;
    public:
        ThreadWorker(ThreadPool * pool, const int id)
        : m_pool(pool), m_id(id) {
        }

        void operator()() {
        std::function<void()> func;
        bool dequeued;
        while (!m_pool->m_shutdown) {
            {
            std::unique_lock<std::mutex> lock(m_pool->m_conditional_mutex);
            if (m_pool->m_queue.empty()) {
                m_pool->m_conditional_lock.wait(lock);
            }
            dequeued = m_pool->m_queue.dequeue(func);
            }
            if (dequeued) {
            func();
            }
        }
        }
    };

    volatile bool m_shutdown;
    SafeQueue<std::function<void()>> m_queue;
    std::vector<std::thread> m_threads;
    std::mutex m_conditional_mutex;
    std::condition_variable m_conditional_lock;
    public:
    int n_threads;
    ThreadPool(const int n_threads)
        : m_threads(std::vector<std::thread>(n_threads)), m_shutdown(false), n_threads(n_threads) {
    }

    ThreadPool(const ThreadPool &) = delete;
    ThreadPool(ThreadPool &&) = delete;

    ThreadPool & operator=(const ThreadPool &) = delete;
    ThreadPool & operator=(ThreadPool &&) = delete;

    // Inits thread pool
    void init() {
        for (int i = 0; i < m_threads.size(); ++i) {
        m_threads[i] = std::thread(ThreadWorker(this, i));
        }
    }

    // Waits until threads finish their current task and shutdowns the pool
    void shutdown() {
        m_shutdown = true;
        m_conditional_lock.notify_all();
        
        for (int i = 0; i < m_threads.size(); ++i) {
        if(m_threads[i].joinable()) {
            m_threads[i].join();
        }
        }
    }

    // Submit a function to be executed asynchronously by the pool
    template<typename F, typename...Args>
    auto submit(F&& f, Args&&... args) -> std::future<decltype(f(args...))> {
        // Create a function with bounded parameters ready to execute
        std::function<decltype(f(args...))()> func = std::bind(std::forward<F>(f), std::forward<Args>(args)...);
        // Encapsulate it into a shared ptr in order to be able to copy construct / assign 
        auto task_ptr = std::make_shared<std::packaged_task<decltype(f(args...))()>>(func);

        // Wrap packaged task into void function
        std::function<void()> wrapper_func = [task_ptr]() {
        (*task_ptr)(); 
        };

        // Enqueue generic wrapper function
        m_queue.enqueue(wrapper_func);

        // Wake up one thread if its waiting
        m_conditional_lock.notify_one();

        // Return future from promise
        return task_ptr->get_future();
    }
    };
    */

    namespace detail {

        template<typename Iterator>
        struct future_info {
            typedef typename std::iterator_traits<Iterator>::value_type future_type;
            typedef decltype(std::declval<future_type>().get()) value_type;
            static constexpr bool is_void = std::is_void<value_type>::value;
        };

    } // detail


    // Waits until all futures contain results
    template<typename Iterator>
    inline
    void wait(Iterator first, Iterator last) {
        for (; first != last; ++first)
            first->wait();
    }


    // Waits until all futures contain results with a given timeout duration and
    // returns a container of std::future::status
    template<typename Result, typename Iterator, typename Rep, typename Period>
    inline
    Result wait_for(Iterator first, Iterator last,
                    const std::chrono::duration<Rep, Period>& timeout_duration,
                    Result result) {
        for (; first != last; ++first)
            result.push_back(first->wait_for(timeout_duration));
        return result;
    }


    // Waits until all futures contain results with a given timeout duration and
    // returns a vector of std::future::status
    template<typename Iterator, typename Rep, typename Period>
    inline
    std::vector<std::future_status> wait_for(Iterator first, Iterator last,
                                            const std::chrono::duration<Rep, Period>& timeout_duration) {
        return wait_for(first, last, timeout_duration, std::vector<std::future_status>{});
    }


    // Waits until all futures contain results with a given timeout time and
    // returns a container of std::future::status
    template<typename Result, typename Iterator, typename Clock, typename Duration>
    inline
    Result wait_until(Iterator first, Iterator last,
                    const std::chrono::time_point<Clock, Duration>& timeout_time,
                    Result result) {
        for (; first != last; ++first)
            result.push_back(first->wait_until(timeout_time));
        return result;
    }


    // Waits until all futures contain results with a given timeout time and
    // returns a vector of std::future::status
    template<typename Iterator, typename Clock, typename Duration>
    inline
    std::vector<std::future_status> wait_until(Iterator first, Iterator last,
                                                const std::chrono::time_point<Clock, Duration>& timeout_time) {
        return wait_until(first, last, timeout_time, std::vector<std::future_status>{});
    }


    // Calls get() on all futures
    template<typename Iterator,
            typename = typename std::enable_if<detail::future_info<Iterator>::is_void>::type>
    inline
    void get(Iterator first, Iterator last) {
        for (; first != last; ++first)
            first->get();
    }


    // Calls get() on all futures and stores the results in the returned container
    template<typename Result, typename Iterator,
            typename = typename std::enable_if<!detail::future_info<Iterator>::is_void>::type>
    inline
    Result get(Iterator first, Iterator last, Result result) {
        for (; first != last; ++first)
            result.push_back(first->get());
        return result;
    }


    // Calls get() on all futures and stores the results in the returned vector
    template<typename Iterator,
            typename = typename std::enable_if<!detail::future_info<Iterator>::is_void>::type>
    inline
    std::vector<typename detail::future_info<Iterator>::value_type>
    get(Iterator first, Iterator last) {
        return get(first, last, std::vector<typename detail::future_info<Iterator>::value_type>{});
    }


    namespace detail {


    template<typename Index, Index max = std::numeric_limits<Index>::max()>
    class infinite_counter {
    public:

        infinite_counter()
        : count_{0}
        {}

        infinite_counter& operator++() {
            if (count_.back() == max)
                count_.push_back(0);
            else
                ++count_.back();
            return *this;
        }

        bool operator>(const infinite_counter& other) const {
            if (count_.size() == other.count_.size()) {
                return count_.back() > other.count_.back();
            } else {
                return count_.size() > other.count_.size();
            }
        }

    private:
        std::vector<Index> count_;
    };


    class priority_task {
    public:
        typedef std::size_t counter_elem_t;

        priority_task()
        : callback_{}, priority_{}, order_{}
        {}

        // cppcheck-suppress passedByValue
        priority_task(std::function<void()> callback, std::size_t priority, detail::infinite_counter<counter_elem_t> order)
        : callback_{std::move(callback)}, priority_(priority), order_{std::move(order)}
        {}

        bool operator<(const priority_task& other) const {
            if (priority_ == other.priority_) {
                return order_ > other.order_;
            } else {
                return priority_ < other.priority_;
            }
        }

        void operator()() const {
            return callback_();
        }

    private:
        std::function<void()> callback_;
        std::size_t priority_;
        detail::infinite_counter<counter_elem_t> order_;
    };


    } // detail


    // Exception thrown by the thread_pool class
    class thread_pool_error : public std::runtime_error {
    public:
        explicit thread_pool_error(const std::string& message)
        : std::runtime_error{message}
        {}
    };


    // A thread pool for C++
    //
    // Constructing the thread pool launches the worker threads while
    // destructing it joins them. The threads will be alive for as long as the
    // thread pool is not destructed. One may call add_threads() to add more
    // threads to the thread pool.
    //
    // Tasks can be pushed into the pool with and w/o providing a priority >= 0.
    // Not providing a priority is equivalent to providing a priority of 0.
    // Those tasks are processed first that have the highest priority.
    // If priorities are equal those tasks are processed first that were pushed
    // first into the pool (FIFO).
    class ThreadPool {
    public:

        // Constructor. No threads are launched
        ThreadPool()
        : done_{false}, paused_{false}, threads_{}, tasks_{}, task_counter_{},
        task_cond_var_{}, task_mutex_{}, thread_mutex_{}
        {}

        // Constructor. Launches the desired number of threads. Passing 0 is
        // equivalent to calling the no-argument constructor
        explicit ThreadPool(std::size_t n_threads)
        : ThreadPool{}
        {
            if (n_threads > 0) {
                std::lock_guard<std::mutex> thread_lock(thread_mutex_);
                const auto n_target = threads_.size() + n_threads;
                while (threads_.size() < n_target) {
                    std::thread thread;
                    try {
                        thread = std::thread{&ThreadPool::worker, this};
                    } catch (...) {
                        shutdown();
                        throw;
                    }
                    try {
                        threads_.push_back(std::move(thread));
                    } catch (...) {
                        shutdown();
                        thread.join();
                        throw;
                    }
                }
            }
        }

        // Destructor. Joins all threads launched. Waits for all running tasks
        // to complete
        ~ThreadPool() {
            shutdown();
        }

        // deleting copy/move semantics
        ThreadPool(const ThreadPool&) = delete;
        ThreadPool& operator=(const ThreadPool&) = delete;
        ThreadPool(ThreadPool&&) = delete;
        ThreadPool& operator=(ThreadPool&&) = delete;

        // Adds new threads to the pool and launches them
        void add_threads(std::size_t n_threads) {
            if (n_threads > 0) {
                {
                    std::lock_guard<std::mutex> task_lock(task_mutex_);
                    if (done_)
                        throw thread_pool_error{"add_threads called while pool is shutting down"};
                }
                std::lock_guard<std::mutex> thread_lock(thread_mutex_);
                const auto n_target = threads_.size() + n_threads;
                while (threads_.size() < n_target) {
                    std::thread thread(&ThreadPool::worker, this);
                    try {
                        threads_.push_back(std::move(thread));
                    } catch (...) {
                        shutdown();
                        thread.join();
                        throw;
                    }
                }
            }
        }

        // Returns the number of threads launched
        std::size_t n_threads() const {
            {
                std::lock_guard<std::mutex> task_lock(task_mutex_);
                if (done_)
                    throw thread_pool_error{"n_threads called while pool is shutting down"};
            }
            std::lock_guard<std::mutex> thread_lock(thread_mutex_);
            return threads_.size();
        }

        // Pushes a new task into the thread pool and returns the associated future.
        // The task will have a priority of 0
        template<typename Functor, typename... Args>
        auto submit(Functor&& functor, Args&&... args) -> std::future<decltype(functor(args...))> {
            return submit(0, std::forward<Functor>(functor), std::forward<Args>(args)...);
        }

        // Pushes a new task into the thread pool while providing a priority and
        // returns the associated future. Higher priorities are processed first
        template<typename Functor, typename... Args>
        auto submit(std::size_t priority, Functor&& functor, Args&&... args) -> std::future<decltype(functor(args...))> {
            typedef decltype(functor(args...)) result_type;
            auto pack_task = std::make_shared<std::packaged_task<result_type()>>(
                    std::bind(std::forward<Functor>(functor), std::forward<Args>(args)...));
            auto future = pack_task->get_future();
            {
                std::lock_guard<std::mutex> task_lock(task_mutex_);
                if (done_)
                    throw thread_pool_error{"push called while pool is shutting down"};
                tasks_.emplace([pack_task]{ (*pack_task)(); }, priority, ++task_counter_);
            }
            task_cond_var_.notify_one();
            return future;
        }

        // Returns the current number of queued tasks
        std::size_t n_tasks() const {
            std::lock_guard<std::mutex> task_lock(task_mutex_);
            return tasks_.size();
        }

        // Clears all queued tasks, not affecting currently running tasks
        void clear() {
            std::lock_guard<std::mutex> task_lock(task_mutex_);
            decltype(tasks_) empty;
            tasks_.swap(empty);
        }

        // If enabled then pauses the processing of tasks, not affecting currently
        // running tasks. Disabling it will resume the processing of tasks
        void set_pause(bool enabled) {
            {
                std::lock_guard<std::mutex> task_lock(task_mutex_);
                paused_ = enabled;
            }
            if (!paused_)
                task_cond_var_.notify_all();
        }

        void shutdown() {
            if(done_)
                return;
            {
                std::lock_guard<std::mutex> task_lock(task_mutex_);
                done_ = true;
                paused_ = false;
            }
            task_cond_var_.notify_all();
            std::lock_guard<std::mutex> thread_lock(thread_mutex_);
            for (auto& thread : threads_)
                thread.join();
        }

    private:

        void worker() {
            for (;;) {
                detail::priority_task task;
                {
                    std::unique_lock<std::mutex> task_lock(task_mutex_);
                    task_cond_var_.wait(task_lock, [this]{
                        return !paused_ && (done_ || !tasks_.empty());
                    });
                    if (done_ && tasks_.empty())
                        break;
                    task = tasks_.top();
                    tasks_.pop();
                }
                task();
            }
        }

        bool done_;
        bool paused_;
        std::vector<std::thread> threads_;
        std::priority_queue<detail::priority_task> tasks_;
        detail::infinite_counter<
        typename detail::priority_task::counter_elem_t> task_counter_;
        std::condition_variable task_cond_var_;
        mutable std::mutex task_mutex_;
        mutable std::mutex thread_mutex_;
    };
}
#endif