#pragma once
#include <cerrno>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

namespace shutdown_ctl {
// Root UI submits the fixed systemd operation. No shell and no receiver command.
class Action {
public:
    enum class Result { Waiting, Queued, DryRun, Failed };
    explicit Action(bool dry_run=false) : dry_run_(dry_run) {
        command_=dry_run?std::vector<std::string>{"/bin/true"}:
            std::vector<std::string>{"/bin/systemctl","--no-block","poweroff"};
    }
    ~Action() { if(pid_>0) { int status=0; ::waitpid(pid_,&status,WNOHANG); } }
    Action(const Action&)=delete;
    Action& operator=(const Action&)=delete;
    bool start(std::int64_t now_ms) {
        if(pid_>0 || uncertain_ || queued_) { error_="PREVIOUS REQUEST NOT CONFIRMED";return false; }
        if(!dry_run_ && ::geteuid()!=0) return fail("ROOT SERVICE REQUIRED - NOT SHUT DOWN");
        const long fd_limit=::sysconf(_SC_OPEN_MAX);
        if(fd_limit<0) return fail("CANNOT PREPARE SHUTDOWN PROCESS");
        std::vector<char*> argv;
        for(auto& s:command_) argv.push_back(const_cast<char*>(s.c_str()));
        argv.push_back(nullptr);
        error_.clear(); deadline_=now_ms+10000;
        pid_=::fork();
        if(pid_<0) return fail("CANNOT START SHUTDOWN PROCESS");
        if(pid_==0) {
            bool closed=false;
#if defined(SYS_close_range) && !defined(SHUTDOWN_TEST_NO_CLOSE_RANGE)
            closed=(::syscall(SYS_close_range,3U,~0U,0U)==0);
#endif
            if(!closed) for(long fd=3;fd<fd_limit;++fd) ::close(static_cast<int>(fd));
            ::execv(argv[0],argv.data());
            ::_exit(127);
        }
        result_=Result::Waiting;
        return true;
    }
    Result poll(std::int64_t now_ms) {
        if(result_!=Result::Waiting) return result_;
        int status=0;
        const pid_t reaped=::waitpid(pid_,&status,WNOHANG);
        if(reaped==pid_){
            pid_=-1;
            if(WIFEXITED(status) && WEXITSTATUS(status)==0) {
                result_=dry_run_?Result::DryRun:Result::Queued;
                queued_=!dry_run_;
            }
            else fail("SHUTDOWN COMMAND FAILED - NOT CONFIRMED");
        }else if(reaped<0 && errno!=EINTR){
            uncertain_=true;fail("SHUTDOWN STATUS UNCONFIRMED");
        }else if(now_ms>=deadline_){
            // Do not kill/retry: the OS may already have accepted the request.
            uncertain_=true;fail("SHUTDOWN STATUS UNCONFIRMED");
        }
        return result_;
    }
    const std::string& error() const { return error_; }
#ifdef SHUTDOWN_TESTING
    void test_command(std::vector<std::string> args) { command_=std::move(args); dry_run_=true; }
#endif
private:
    bool fail(const std::string& text) { error_=text;result_=Result::Failed;return false; }
    std::vector<std::string> command_;
    bool dry_run_=false,uncertain_=false,queued_=false;
    pid_t pid_=-1;
    std::int64_t deadline_=0;
    Result result_=Result::Failed;
    std::string error_;
};
} // namespace shutdown_ctl
