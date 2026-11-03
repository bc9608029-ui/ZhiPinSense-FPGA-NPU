# 最终电脑侧复验

## 通过

- 固定向量生成：4/4；
- Python 固定点/协议自检：6/6；
- PREP2 反例与跨帧自检：8/8；
- XSim 2018.3：边界测试通过；双帧 2048/2048 bin 在背压下通过；
- Vivado 2018.3 + FMSH patch：XFFT 9.1 生成和 OOC 综合通过；
- 真实接口冻结：16-bit 输入、27-bit 输出、54-bit 功率、自然序、XK_INDEX；
- Procise 2025.1.1 后级 OOC：JFMQL30TAI676H、100 MHz、slack +0.1784 ns；
- OOC 引脚为 69/250，不再出现把全数据总线外引造成的 258/250 假超限。

## 尚未通过/尚未执行

- 官方 XFFT DCP→Procise 迁移在 FMSH `runEco0` 报 `Unrecognized character`，无 PASS；
- 未形成包含 XFFT、窗口、功率和双缓冲的同一 Procise 完整工程；
- 未实现正式 PS→PL 输入、PS 回读和 `auto` 软件回退；
- 未生成或加载候选位流；未做板端 same-IQ A/B、24+24 smoke、240+240 RF 回归。

## 结论

电脑侧可独立验证的算法、位宽、RTL、真实 XFFT 配置和后级目标器件实现证据已完成。
当前不能进入正式上板测试；必须先解决 XFFT 迁移并补齐完整 PS/PL 链。主链候选、原位流、
two-DC、模型和正式服务均未改动。
