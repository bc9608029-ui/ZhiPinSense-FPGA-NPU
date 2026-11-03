# secure boot 审计（PREP2 离线）

状态令牌：`FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP2-BOARD-EVIDENCE-COLLECTION-READY`。
本审计只记录**本地可证**的加密/认证标志；区分「镜像未加密」与「板端 secure boot 未启用」——两者**不可互换**。

## 1. BOOT.bin 头部加密/认证标志（本审计解析，仅限本地镜像）

解析对象：vendor 示例 BOOT.bin（`vendor_lite_boot/BOOT.bin`，SHA `ff350477…`）。

| 字段 | 偏移 | 值 | 含义 |
|---|---|---|---|
| 魔数 | `0x20` | `66 55 99 aa`（= 0xAA995566） | FMSH 启动镜像魔数 |
| 标识 | `0x24` | `HSMF`（小端 `FMSH`） | vendor 标识 |
| 加密字 | `0x28` | `0x00000000` | **未加密**（encrypted=False） |
| 其余头部字（`0x2C`、`0x30`…） | — | 本地无权威文档定义 | **不解读、不猜测**（认证/长度等字段语义 UNCONFIRMED） |

- 结论（仅针对该镜像）：**candidate/示例 BOOT.bin 未加密**。这只说明「这个镜像文件是明文」，
  **不说明**「板端 secure boot 已禁用」。

## 2. U-Boot / FSBL 的 secure-boot 状态输出

- 板端 U-Boot `printenv`、FSBL 启动日志中是否出现 secure-boot/签名校验相关输出：**尚未采集**（`UNCONFIRMED`）。
- 采集方式（只读）：
  - U-Boot：`printenv`（`docs/COM12_UBOOT_READONLY.md`）；
  - Linux dmesg 全文（`scripts/collect_fmql_boot_state_v2.sh` 已含 dmesg 抓取）。
- 若未来板端出现 `secure boot enabled`/`auth`/`RSA`/`sha` 等字样，据实补记；**本文件不凭空假设其含义**。

## 3. 芯片只读状态寄存器 / eFuse / key 使能迹象

- **本地没有任何 FMSH 权威文档给出** secure-boot 状态寄存器地址、eFuse 布局或 key 使能位地址。
  因此：**不读取、不猜测任何寄存器/eFuse 地址**（`UNCONFIRMED`）。
- eFuse 为一次性熔丝，误读/误判风险高，必须等待权威芯片手册明确地址与语义后才可涉及。

## 4. 关键区分（红线）

1. 「candidate BOOT.bin 未加密」（§1，本地已证）= 镜像层面，可离线断言。
2. 「板端 secure boot 是否启用」= 板级熔丝/配置层面，**`UNCONFIRMED`**，只能由板端权威输出或权威手册确认。

> 结论：在板端 secure boot 状态确认前，**不写入任何自生成 BOOT.bin**（PREP1 红线沿用）。
> 若板端确认 secure boot 启用，则方案 A/B/C 全部需要先解决签名/认证，否则禁止写入。

## 5. 待补证据

1. 板 U-Boot `printenv`（是否含 secure-boot 相关变量）。
2. 板 FSBL/启动日志（是否有签名校验输出）。
3. 用户若能提供 FMSH 芯片手册中 secure-boot/eFuse 章节（页号），据实补记。
