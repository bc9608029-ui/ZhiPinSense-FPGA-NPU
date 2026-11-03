#!/bin/bash
set -e
W=/mnt/f/嵌赛/fix10class24_fix1v2_board_impl1_work
D=$(mktemp -d)
cd "$D"
# 单层检查：gzip.decompress 一次必须是合法 tar（用 tar -tf 直接读 .tar.gz 若报错=双层/损坏）
tar tzf "$W/dist/fix1v2_board_impl1_PATCH.tar.gz" >/dev/null 2>&1 || { echo "TAR_READ_FAIL(possibly double-gzip)"; exit 1; }
echo "single-layer tar read: OK"
tar xzf "$W/dist/fix1v2_board_impl1_PATCH.tar.gz"
echo "=== sha256sum -c 逐文件校验 ==="
sha256sum -c SHA256SUMS.txt 2>&1
echo "=== 成员数 ==="
tar tzf "$W/dist/fix1v2_board_impl1_PATCH.tar.gz" | wc -l
# 二次确认无内层 gzip 成员
echo "=== 检查是否有 .gz 成员（应无）==="
tar tzf "$W/dist/fix1v2_board_impl1_PATCH.tar.gz" | grep -E '\.gz$' || echo "(none .gz member)"
cd /; rm -rf "$D"
