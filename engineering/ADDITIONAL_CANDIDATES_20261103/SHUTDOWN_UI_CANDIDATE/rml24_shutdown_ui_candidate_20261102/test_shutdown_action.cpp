#define SHUTDOWN_TESTING
#include "release/candidate/board_package/shutdown_action.hpp"
#include <cassert>
#include <chrono>
#include <fcntl.h>
#include <iostream>
#include <thread>
using shutdown_ctl::Action;
std::int64_t now_ms() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}
Action::Result finish(Action& action) {
    auto result=Action::Result::Waiting;
    const auto end=now_ms()+3000;
    while(result==Action::Result::Waiting && now_ms()<end){
        result=action.poll(now_ms()); std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    return result;
}
int main(int argc,char** argv) {
    if(argc==3 && std::string(argv[1])=="--fd-probe")
        return ::fcntl(std::stoi(argv[2]),F_GETFD)==-1 && errno==EBADF?0:1;
    int checks=0;
    Action dry(true);assert(dry.start(now_ms()));assert(finish(dry)==Action::Result::DryRun);++checks;
    Action failure(true);failure.test_command({"/bin/false"});assert(failure.start(now_ms()));
    assert(finish(failure)==Action::Result::Failed);++checks;
    Action missing(true);missing.test_command({"/not/a/command"});assert(missing.start(now_ms()));
    assert(finish(missing)==Action::Result::Failed);++checks;
    Action duplicate(true);duplicate.test_command({"/bin/sleep","0.1"});assert(duplicate.start(now_ms()));
    assert(!duplicate.start(now_ms()));assert(finish(duplicate)==Action::Result::DryRun);++checks;
    const int fd=::open("/dev/null",O_RDONLY);assert(fd>=3);
    Action descriptors(true);descriptors.test_command({argv[0],"--fd-probe",std::to_string(fd)});
    assert(descriptors.start(now_ms()));assert(finish(descriptors)==Action::Result::DryRun);::close(fd);++checks;
    Action timeout(true);timeout.test_command({"/bin/sleep","0.2"});const auto begin=now_ms();
    assert(timeout.start(begin));assert(timeout.poll(begin+10001)==Action::Result::Failed);
    assert(!timeout.start(now_ms()));std::this_thread::sleep_for(std::chrono::milliseconds(250));++checks;
    std::cout<<"SHUTDOWN_ACTION_TEST_PASS checks="<<checks<<" real_poweroff=NO\n";
}
