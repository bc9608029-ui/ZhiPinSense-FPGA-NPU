#!/usr/bin/env bash
# install_boot_display.sh -- 安装 RML23 UI 自启服务（**用户本人执行 = 明确批准修改启动服务**）。
#
# 只写根文件系统用户空间：复制 UI 二进制到 /opt/sdr/bin/ + 部署 boot_display.service，systemctl enable。
# **不写 Flash、不替换 BOOT.bin、不加载位流、不重配 FPGA、不改冻结模型/NPU 配置。**
#
# 语义（诚实）：本服务**不修重启黑屏**。它是「JTAG 重载合并位流后免手动 start_live_rml23.sh」的便利；
# 重启后位流丢失，服务会版本门失败（fail-closed）。是否 enable 由用户决定。
#
# 用法：
#   bash install_boot_display.sh --ui-bin=/abs/path/board_ui_live_rml23 [--start]
#   --ui-bin : 已构建的 UI 二进制绝对路径（board_package/build_ui_live_rml23.sh 产出，通常在
#              包根 bin/board_ui_live_rml23）；本脚本复制到 /opt/sdr/bin/ 并据其写 service 绝对路径。
#   --start  : enable 后立即 systemctl start（默认只 enable，下次开机生效，不擅自立即启动）
set -euo pipefail

UI_BIN_SRC=""
START=0
DEST_BIN="/opt/sdr/bin/board_ui_live_rml23"
DEST_DIR="/opt/sdr/bin"
SERVICE_NAME="boot-display-ui"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

for a in "$@"; do
    case "$a" in
        --ui-bin=*) UI_BIN_SRC="${a#--ui-bin=}" ;;
        --start) START=1 ;;
        *) echo "usage: $0 --ui-bin=/abs/path/board_ui_live_rml23 [--start]"; exit 2 ;;
    esac
done

if [ -z "$UI_BIN_SRC" ]; then
    echo "FAIL missing --ui-bin=/abs/path/board_ui_live_rml23"; exit 2
fi
if [ ! -f "$UI_BIN_SRC" ]; then
    echo "FAIL ui_binary_not_found $UI_BIN_SRC"; exit 2
fi
if [ ! -x "$UI_BIN_SRC" ]; then
    echo "FAIL ui_binary_not_executable $UI_BIN_SRC"; exit 2
fi

# 要求 root（写 /etc/systemd/system 与 /opt/sdr）
if [ "$(id -u)" -ne 0 ]; then
    echo "FAIL must_run_as_root"; exit 2
fi

mkdir -p "$DEST_DIR"
cp -f "$UI_BIN_SRC" "$DEST_BIN"
chmod 0755 "$DEST_BIN"
echo "OK ui_binary_installed $DEST_BIN"

# 生成 service（绝对路径已内嵌；此处用 sed 保证与 DEST_BIN 一致，防手动改动）
sed -e "s|/opt/sdr/bin/board_ui_live_rml23|$DEST_BIN|g" \
    "$SCRIPT_DIR/boot_display.service" > "/etc/systemd/system/$SERVICE_NAME.service"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME.service"

if [ "$START" -eq 1 ]; then
    echo "NOTE --start 指定：立即启动（需合并位流已在位，否则版本门失败退出）"
    systemctl start "$SERVICE_NAME.service"
fi

echo "INSTALL_OK service=$SERVICE_NAME enabled=1 start=$START"
echo "语义：本服务不修重启黑屏；重启后需先 JTAG 重载合并位流再 systemctl restart $SERVICE_NAME。"
echo "ROLLBACK: bash $(dirname "$0")/uninstall_boot_display.sh"
