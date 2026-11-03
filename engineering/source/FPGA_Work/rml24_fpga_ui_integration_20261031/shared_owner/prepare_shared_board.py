from pathlib import Path
import shutil,hashlib,json
root=Path('/root/rml24_fpga_shared_owner_20261031');root.mkdir(exist_ok=False);old=Path('/root/realrf_finetune_pilot1_test_1773373090')
for sub in ['board_package','sdr_adapter']:shutil.copytree(old/sub,root/sub)
p=root/'board_package/npu_classifier24.hpp';s=p.read_text();before=hashlib.sha256(p.read_bytes()).hexdigest();needle='private:';assert needle in s;s=s.replace(needle,'    icraft::xrt::Device auxiliary_device() const { return device_; }\n\nprivate:',1);p.write_text(s)
shutil.copyfile('/root/rml24_fpga_diag_1793380588/scan_protocol.hpp',root/'scan_protocol.hpp')
shutil.copyfile('/root/rml24_three_modes_execution_20261029/fpga_ui_integration_20261031/npu_stream_shared.cpp',root/'npu_stream_shared.cpp')
(root/'CMakeLists.txt').write_text("cmake_minimum_required(VERSION 3.10)\nproject(shared_owner LANGUAGES CXX)\nset(CMAKE_CXX_STANDARD 17)\nfind_package(icraft-zg330backend REQUIRED)\nfind_package(icraft-hostbackend REQUIRED)\nadd_executable(npu_stream_shared npu_stream_shared.cpp)\ntarget_include_directories(npu_stream_shared PRIVATE board_package sdr_adapter)\ntarget_link_libraries(npu_stream_shared PRIVATE Icraft::ZG330Backend Icraft::HostBackend pthread dl)\n")
(root/'SOURCE_CHANGE.json').write_text(json.dumps(dict(original_header_sha=before,scope='Expose shared existing Device handle; inference lifecycle and model unchanged; extra NaN-tagged PSD RPC',model_changed=False,formal_binary_unchanged=True),indent=2))
print('SHARED_OWNER_BUILD_PREPARED')
