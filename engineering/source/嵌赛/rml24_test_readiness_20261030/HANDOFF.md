# 两项测试唯一交接入口

状态：**OFFLINE_TEST_PREP_COMPLETE_TARGET_PREFLIGHT_REQUIRED**。这是独立测试包，不是正式服务覆盖包。先参数测试，再 FPGA 候选板测；每阶段失败都停在该阶段。不得把离线模拟、XRT 语法检查或位流产出称为设备通过。

## 已完成与下一步

| 项目 | 电脑侧已完成 | 第一次设备步骤 |
|---|---|---|
| 增益/重复段数 | 240 源资产冻结；24/240 机会发射计划；独立 TX/RX；时钟界限；预先选帧；NPU 启停；固定分母判分；恢复读回 | 核验板上依赖与服务身份，先无发射、再24类 |
| FPGA 辅助 | 已生成候选/原位流回退文件；具体 XRT DDR/寄存器驱动；same-IQ 软件/fpga/auto 入口；8向量对照；错误分类/安全退出 | 板端原生构建，临时 JTAG 加载，身份检查，再 same-IQ |

操作分别见 `PARAMETER_BOARDTEST.md` 和 `FPGA_BOARDTEST.md`。不要直接执行旧手册的 RF 正式回归入口。

## 真实验证证据

- `evidence/OFFLINE_RECEIPT.json` 与日志：20 项 Python 反例/保护测试；旧增益工具自检；24 类 TX 干跑；8 组软件PSD；选帧/判分CLI合成全流程；包身份预检。
- `evidence/host_compile.log`：WSL g++ 协议模拟测试（8用例）及真实 XRT 头文件 `gnu++17` 语法核验。不是 aarch64 链接/设备验证。
- `evidence/BASELINE_EXCEPTION_GATE.json`、`FINAL_REPORT_REVIEW.json`：本次候选完整布线及历史 NPU 例外证据。全局 setup/hold 通过；两条继承的 NPU 最小周期违规保留，**不是完整 STA PASS，也没有厂商豁免**。
- `fpga/CANDIDATE_RECEIPT.json`：位流生成退出码0，自动/显式 Procise 转换一致。最终候选 SHA `47b9e1fd2154104bb1bf34e247af07db6908f70436e2ec68845d617e47514ccd`。

## 严格范围

1. 模型、two-DC、正式位流和正式自启不改；不训练。参数试验只改变指定的 RX 硬件增益/AGC；重复段数是同raw离线1/2/4/8消融，TX仍发送8段，不证明真正缩帧后的RF效果。
2. 真值、源IQ、发射计划和TX日志仅留PC。RX不接受类别、源IQ或实时起发通知；SSH仅采集前后观察时间、以及测试后的文件传输。RX的公共前导同步仍由RF自己完成。
3. 分数使用预冻结24/240机会分母；缺失/恢复失败/未推理不能删除。选帧按时间中点，先于推理；不能事后挑正确帧。
4. 本包参数分数是冻结two-DC恢复后的固定集合分类实验；不等同完整 UI/lock/sweep 生产运行的端到端验收。不能凭此自动晋级参数。
5. FPGA驱动是隔离板测诊断，不会自动接管正式接收器。same-IQ/回退通过后，才有依据单独合入真实扫频入口；实时RF接入与240+240回归不由本次离线通过冒充。
6. `auto` 对启动/空闲硬件故障回退软件；仍忙的DDR超时必须停测并复位，不得自动重启正式NPU。错误的成功PSD不伪装成“软件回退成功”。

## 收到包后的第一步

电脑解压后：

```powershell
$Root = 'F:\嵌赛\rml24_test_readiness_20261030'
& 'D:\Anaconda\python.exe' -I "$Root\preflight.py"
```

板端首次预检需要你当时的实际路径/URI/服务名，全部必须先只读核对。不要把旧会话的 `usb:1.3.5` 或任何已失效目录当成固定值。没有板端编译、设备测试、RF测试或正式替换的声明。
