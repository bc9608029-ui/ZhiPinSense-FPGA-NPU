# 离线构建证据

- 编译环境：WSL Ubuntu，g++ 15.2.0，x86-64。
- 命令：`ui_fivepage_candidate/board_package/build_ui_live_rml24_final.sh`。
- 原脚本参数保持：GNU++17、`-O2 -Wall -Wextra -Werror`。
- 结果：`UI_BUILD_RESULT result=PASS`。
- 触控导航单元测试：`FIVEPAGE_NAV_TEST result=PASS tabs=5`。
- 静态结构审计：`FIVEPAGE_STATIC_AUDIT result=PASS checks=9`。

该编译证明源码依赖闭合且通过严格警告，不是板端 aarch64 编译。生成的 x86-64 ELF 已移到：

`host_tests/bin/board_ui_live_rml24_final.host_x86_64`

候选树的 `bin/` 不放置该文件，防止误部署。上板后必须原生运行构建脚本，看到新的 `UI_BUILD_RESULT result=PASS` 才能运行。
