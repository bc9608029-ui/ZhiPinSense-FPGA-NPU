#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""train_finetune_pilot.py — 并行线 C 职责C：E0-E3 微调框架（含真实训练循环）。

从原始可训练 checkpoint 初始化 ADAMRV11Net（24 类），按 E0-E3 冻结策略微调：
  E0 冻结原模型不训练（基线）
  E1 冻结特征提取器（denoiser+features），只训分类头 classifier
  E2 解冻最后一个特征块 features[-1] + 分类头，冻结 denoiser + features[:-1]
  E3 全模型小学习率微调

数据：每 batch 混合真实 RF（S1/S2 板端恢复 IQ，[2,1024] f32）与原始 RadioML 数字样本
（S1/S2 源 IQ）1:1；交叉熵 + AdamW + weight_decay + 早停（S3 上无增益）；超参数只据 S3，
禁看 S4；≥3 随机种子；保存配置/checkpoint/训练曲线/SHA。

默认 --selftest 只构建 + 冻结掩码 + 合成前反向自测（不训练）；--train 才进入真实训练。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))
from gt_join import load_ground_truth, BOARD_EMPTY_TRUTH_COLS  # noqa: E402

MODEL_SRC = r"F:\FPGA_Work\sdr_amr_12class_ood_u_v1"
CKPT = (r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\_frozen\runs\rml24_base"
        r"\formal\t002_losscross_entropy_optadamw\seed2027\checkpoints\best.pt")
CKPT_SHA = "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d"
MODEL_KWARGS = {
    "denoiser_channels": 24,
    "denoiser_blocks": 3,
    "feature_channels": (32, 48, 64, 96),
    "classifier_hidden": 128,
    "dropout": 0.15,
}
N_CLASSES = 24
EXPERIMENTS = ["E0", "E1", "E2", "E3"]

LINE_A = Path(r"F:\嵌赛\fix10class24_realrf_finetune_pilot1_work\line_a")
LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
    "FM", "GMSK", "OQPSK",
)

# Do not rely on the embedded non-ASCII absolute path above: it is already
# mojibake-corrupted in this checkout and would silently omit all digital
# RadioML companions.  Resolve line_a relative to this script instead.
WORK_ROOT = _SCRIPTS.parents[1]
LINE_A = WORK_ROOT / "line_a"


def _load_torch_and_model():
    import torch
    from torch import nn
    sys.path.insert(0, MODEL_SRC)
    from models.ad_amr_v1_1_net import ADAMRV11Net  # noqa: E402
    return torch, nn, ADAMRV11Net


def load_frozen_model():
    torch, nn, ADAMRV11Net = _load_torch_and_model()
    sha = hashlib.sha256(Path(CKPT).read_bytes()).hexdigest()
    if sha != CKPT_SHA:
        raise SystemExit("checkpoint SHA mismatch: %s" % sha)
    ck = torch.load(CKPT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=N_CLASSES, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    return torch, nn, ADAMRV11Net, model, ck


def freeze_for_experiment(model, exp: str):
    """按实验设置 requires_grad，返回可训练参数数。"""
    for p in model.parameters():
        p.requires_grad = False
    trainable_mods = []
    if exp == "E0":
        pass
    elif exp == "E1":
        trainable_mods = [model.classifier]
    elif exp == "E2":
        trainable_mods = [model.classifier, model.features[-1]]
    elif exp == "E3":
        for p in model.parameters():
            p.requires_grad = True
        trainable_mods = [model]
    else:
        raise ValueError("unknown experiment %s" % exp)
    for m in trainable_mods:
        for p in m.parameters():
            p.requires_grad = True
    n_train = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return n_train


def param_groups(model, exp: str, head_lr: float = 3e-4, bone_lr: float = 1e-5):
    groups = []
    if exp in ("E1", "E2"):
        head_params = [p for p in model.classifier.parameters() if p.requires_grad]
        if head_params:
            groups.append({"params": head_params, "lr": head_lr, "name": "head"})
        if exp == "E2":
            bone = [p for p in model.features[-1].parameters() if p.requires_grad]
            if bone:
                groups.append({"params": bone, "lr": bone_lr, "name": "last_block"})
    else:
        all_params = [p for p in model.parameters() if p.requires_grad]
        if all_params:
            groups.append({"params": all_params, "lr": bone_lr, "name": "all"})
    return groups


# ---------------------------------------------------------------------------
# 数据加载（真实 RF + 原始数字 1:1 混合）
# ---------------------------------------------------------------------------
def _read_capture_records(capture_tsv: Path, gt=None) -> dict[str, dict]:
    """读 32 字段采集 TSV，返回 source_id -> {label, gate_pass, hard_invalid,
    model_input_sha256, ...真值列}。

    有限 tensor 的权威信号是 `model_input_sha256`（板端只在 tensor 落盘且有限时回填，
    无 tensor / hard-invalid / no_sync / non-finite 一律留空）。

    gt 提供时（真实采集）：断言板端真值列全空并按 source_id 离线回填 label（评审 39e5
    Blocker 2，接收端不得持有类别真值）；gt=None（合成夹具自测）直接读 label。
    """
    lines = [ln.rstrip("\r\n") for ln in capture_tsv.read_text(encoding="utf-8").splitlines()]
    header = lines[0].split("\t")
    ci = {h: i for i, h in enumerate(header)}
    for k in ("source_id", "gate_pass", "hard_invalid", "model_input_sha256") \
            + BOARD_EMPTY_TRUTH_COLS:
        if k not in ci:
            raise SystemExit("capture TSV missing col %s" % k)
    recs = {}
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        rec = {
            "gate_pass": f[ci["gate_pass"]],
            "hard_invalid": f[ci["hard_invalid"]],
            "model_input_sha256": f[ci["model_input_sha256"]],
        }
        for c in BOARD_EMPTY_TRUTH_COLS:
            rec[c] = f[ci[c]]
        recs[f[ci["source_id"]]] = rec
    if gt is not None:
        for sid, rec in recs.items():
            for c in BOARD_EMPTY_TRUTH_COLS:
                if rec.get(c, "") not in ("", None):
                    raise SystemExit("board capture leaked ground-truth col %s (%s)"
                                     % (c, sid))
            if sid not in gt:
                raise SystemExit("source_id %r not in ground-truth manifest" % sid)
            rec["label"] = gt[sid]["class_index"]
    else:
        for rec in recs.values():
            rec["label"] = int(rec["label"])
    return recs


def _is_sha64(v: str) -> bool:
    if len(v) != 64:
        return False
    try:
        int(v, 16)
    except ValueError:
        return False
    return True


def _load_tensor_2x1024(path: Path) -> np.ndarray:
    b = path.read_bytes()
    if len(b) != 8192:
        raise SystemExit("%s is %d bytes (want 8192)" % (path.name, len(b)))
    x = np.frombuffer(b, dtype="<f4").reshape(2, 1024).astype(np.float32)
    if not np.all(np.isfinite(x)):
        raise SystemExit("%s has non-finite values" % path.name)
    return x


# RF 训练样本选择臂（评审 39e5 Blocker 3）：
#   RF_ALL_FINITE    默认：任何有有限 tensor 的 RF 样本都进主训练集——gate_pass、
#                    诊断旁路（门拒但恢复出有限 tensor 的 post-sync 失败）一律纳入；
#                    只排除 hard_invalid/no_sync/non-finite（无 tensor，model_input_sha256
#                    留空）。门拒样本标诊断旁路 ≠ 伪装生产，但**微调**目标是学 RF 域，
#                    故有限 tensor 一律可训。
#   RF_GATE_PASS_ONLY 保守对照：只训 gate_pass=1 且非 hard_invalid 的 RF 样本。
RF_ARMS = ("RF_ALL_FINITE", "RF_GATE_PASS_ONLY")


def build_finetune_dataset(capture_tsv: Path, tensor_dir: Path, session: str,
                           selection: str = "RF_ALL_FINITE", gt=None):
    """返回 [(tensor_path, label, is_rf)] 用于训练/验证。

    - RF 样本：tensor_dir/<source_id>.model_input.bin（板端恢复 model_input）。按 `selection` 决定
      纳入口径（默认 RF_ALL_FINITE：所有有限 tensor）。
    - 数字样本：line_a/inputs/S{sn}/{source_id}.bin（原始 RadioML 源 IQ）。
    - gt：主机真值清单（评审 39e5 Blocker 2，label 离线回填；None=合成夹具直接读 label）。
    """
    if selection not in RF_ARMS:
        raise ValueError("unknown RF train arm %r (want %s)" % (selection, RF_ARMS))
    recs = _read_capture_records(capture_tsv, gt=gt)
    out = []
    tdir = Path(tensor_dir)
    for sid, r in recs.items():
        if not sid.startswith("s%d_" % int(session[1])):
            continue
        if selection == "RF_GATE_PASS_ONLY":
            rf_ok = r["gate_pass"] == "1" and r["hard_invalid"] != "1"
        else:  # RF_ALL_FINITE
            # 有有限 tensor（model_input_sha256 为 64-hex 即 tensor 已落盘且有限）；
            # hard_invalid / no_sync / non_finite 无 tensor，留空故被排除。
            rf_ok = _is_sha64(r["model_input_sha256"]) and r["hard_invalid"] != "1"
        if rf_ok:
            # Board capture contract: recovered tensors are persisted as
            # <source_id>.model_input.bin (not <source_id>.bin).
            p = tdir / f"{sid}.model_input.bin"
            if p.is_file():
                out.append((p, r["label"], True))
        # 数字：原始源 IQ（同一 source_id 的干净版本）
        dp = LINE_A / "inputs" / session / f"{sid}.bin"
        if dp.is_file():
            out.append((dp, r["label"], False))
    return out


def _mixed_batches(records, batch_size: int, rng: np.random.Generator):
    """把记录按 1:1（RF:数字）混合打散成 batches（返回下标列表）。"""
    rf = [i for i, r in enumerate(records) if r[2]]
    dig = [i for i, r in enumerate(records) if not r[2]]
    if not rf or not dig:
        # 单边缺数据：退化为纯单一来源（仍可跑，但记录 warning）
        allidx = list(range(len(records)))
        rng.shuffle(allidx)
        return [allidx[i:i + batch_size] for i in range(0, len(allidx), batch_size)]
    half = max(1, batch_size // 2)
    batches = []
    rng.shuffle(rf)
    rng.shuffle(dig)
    n = max(len(rf), len(dig))
    for i in range(0, n, half):
        # `i` is already the element offset for this batch.  Using i//half
        # repeatedly sampled a small sliding prefix and skipped most records.
        b = [rf[(i + j) % len(rf)] for j in range(half)]
        b += [dig[(i + j) % len(dig)] for j in range(half)]
        batches.append(b)
    return batches


def _load_batch(torch, records, idxs):
    xs = np.stack([_load_tensor_2x1024(records[i][0]) for i in idxs], axis=0)
    ys = np.array([records[i][1] for i in idxs], dtype=np.int64)
    return torch.from_numpy(xs), torch.from_numpy(ys)


# ---------------------------------------------------------------------------
# 真实训练循环
# ---------------------------------------------------------------------------
def run_training(exp: str, seed: int, train_recs, val_recs, out_dir: Path,
                 epochs: int = 20, batch_size: int = 64, head_lr: float = 3e-4,
                 bone_lr: float = 1e-5, weight_decay: float = 1e-4,
                 label_smoothing: float = 0.1, patience: int = 4,
                 torch=None, nn=None):
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    model = load_frozen_model()[3]
    n_train = freeze_for_experiment(model, exp)
    groups = param_groups(model, exp, head_lr, bone_lr)
    opt = torch.optim.AdamW(groups, weight_decay=weight_decay)
    loss_fn = nn.CrossEntropyLoss(label_smoothing=label_smoothing)
    model.train()

    best_val = -1.0
    best_state = None
    bad_epochs = 0
    curve = []
    for ep in range(epochs):
        # train
        model.train()
        total = 0
        correct = 0
        nbatch = 0
        for idxs in _mixed_batches(train_recs, batch_size, rng):
            x, y = _load_batch(torch, train_recs, idxs)
            opt.zero_grad()
            logits, _ = model(x)
            loss = loss_fn(logits, y)
            loss.backward()
            opt.step()
            pred = logits.argmax(dim=1)
            total += y.numel()
            correct += int((pred == y).sum())
            nbatch += 1
        train_acc = correct / total if total else 0.0

        # validate (S3 only, never S4)
        val_acc, val_n = _evaluate_recs(model, torch, val_recs)
        curve.append({"epoch": ep, "train_acc": train_acc, "val_acc": val_acc})
        if val_acc > best_val:
            best_val = val_acc
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            bad_epochs = 0
        else:
            bad_epochs += 1
        print("  [%s seed%d] epoch=%d train_acc=%.4f val_acc=%.4f (n=%d) best=%.4f" %
              (exp, seed, ep, train_acc, val_acc, val_n, best_val))
        if bad_epochs >= patience:
            break

    if best_state is not None:
        model.load_state_dict(best_state)
    ckpt_path = out_dir / f"{exp}_seed{seed}_best.pt"
    torch.save({"model_state": model.state_dict(),
                "class_names": list(LABEL_ORDER_24),
                "experiment": exp, "seed": seed, "best_val_acc": best_val},
               ckpt_path)
    meta = {"experiment": exp, "seed": seed, "best_val_acc": best_val,
            "trainable_params": n_train, "curve": curve,
            "checkpoint": str(ckpt_path),
            "checkpoint_sha256": hashlib.sha256(ckpt_path.read_bytes()).hexdigest()}
    (out_dir / f"{exp}_seed{seed}.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def _evaluate_recs(model, torch, recs):
    if not recs:
        return 0.0, 0
    model.eval()
    correct = 0
    total = 0
    with torch.no_grad():
        for i in range(0, len(recs), 64):
            idxs = list(range(i, min(i + 64, len(recs))))
            x, y = _load_batch(torch, recs, idxs)
            logits, _ = model(x)
            pred = logits.argmax(dim=1)
            correct += int((pred == y).sum())
            total += y.numel()
    model.train()
    return (correct / total) if total else 0.0, total


# ---------------------------------------------------------------------------
# 自测 + 入口
# ---------------------------------------------------------------------------
def selftest() -> int:
    torch, nn, ADAMRV11Net, model, ck = load_frozen_model()

    assert list(ck.get("class_names", [])) == list(LABEL_ORDER_24), \
        "class_names != frozen 24-class order"

    n_total = sum(p.numel() for p in model.parameters())
    masks = {}
    for exp in EXPERIMENTS:
        for p in model.parameters():
            p.requires_grad = True
        masks[exp] = freeze_for_experiment(model, exp)
        assert masks[exp] <= n_total
    assert masks["E0"] == 0
    assert masks["E1"] == sum(p.numel() for p in model.classifier.parameters())
    assert masks["E2"] == (sum(p.numel() for p in model.classifier.parameters())
                           + sum(p.numel() for p in model.features[-1].parameters()))
    assert masks["E3"] == n_total

    freeze_for_experiment(model, "E1")
    model.train()
    x = torch.randn(4, 2, 1024)
    y = torch.randint(0, N_CLASSES, (4,))
    logits, _ = model(x)
    assert logits.shape == (4, N_CLASSES)
    torch.nn.functional.cross_entropy(logits, y).backward()
    assert model.classifier[0].weight.grad is not None
    assert model.denoiser.stem[0].weight.grad is None

    # 训练循环可达性（合成夹具，1 epoch + 极小数据）
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # 合成 8 RF + 8 数字样本
        rf_dir = td / "rf"
        rf_dir.mkdir()
        recs = []
        for i in range(8):
            p = rf_dir / f"s1_c{i:02d}_i00.bin"
            p.write_bytes(np.zeros((2, 1024), dtype="<f4").tobytes())
            recs.append((p, i % N_CLASSES, True))
        for i in range(8):
            p = rf_dir / f"s1_c{i:02d}_i01.bin"
            p.write_bytes(np.zeros((2, 1024), dtype="<f4").tobytes())
            recs.append((p, i % N_CLASSES, False))
        meta = run_training("E1", 0, recs, recs[:4], td, epochs=1, batch_size=4,
                            torch=torch, nn=nn)
        assert (td / "E1_seed0_best.pt").exists()
        assert "checkpoint_sha256" in meta

    # RF 训练样本选择臂（评审 39e5 Blocker 3 反例）：门拒但有有限 tensor 进 RF_ALL_FINITE
    # 而不进 RF_GATE_PASS_ONLY；hard-invalid 无 tensor 两臂都排除。
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        hdr = "\t".join([
            "session_id", "source_id", "class_index", "class_name", "dataset_index",
            "split", "source_iq_sha256", "tx_payload_sha256", "raw_rx_sha256",
            "model_input_sha256", "logits_sha256", "digital_pred", "digital_label_correct",
            "board_pred1", "board_pred2", "label", "capture_ok", "no_sync", "rx_clipped",
            "hard_invalid", "gate_pass", "failure_token", "coarse_cfo_hz",
            "fractional_timing", "timing_offset", "corr", "training_residual",
            "training_residual_rel", "a_real", "a_imag", "b_real", "b_imag",
        ])

        def mk_row(sid, ci, model_sha, gate_pass, hard_invalid):
            f = [""] * 32
            f[0], f[1], f[2], f[3], f[4], f[5] = "S1", sid, str(ci), "class%d" % ci, str(ci), "train"
            f[9] = model_sha
            f[15] = str(ci)          # label
            f[19] = hard_invalid
            f[20] = gate_pass
            return "\t".join(f)

        sha_a, sha_b = "a" * 64, "b" * 64
        rows = [
            mk_row("s1_c00_i00", 0, sha_a, "1", "0"),   # gate-pass
            mk_row("s1_c01_i00", 1, sha_b, "0", "0"),   # gate-reject but finite
            mk_row("s1_c02_i00", 2, "",    "0", "1"),   # hard-invalid, no tensor
        ]
        tsv = td / "capture.tsv"
        tsv.write_text(hdr + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
        tdir = td / "tensors"
        tdir.mkdir()
        for sid in ("s1_c00_i00", "s1_c01_i00"):        # hard-invalid 不落 tensor
            (tdir / f"{sid}.model_input.bin").write_bytes(
                np.zeros((2, 1024), dtype="<f4").tobytes())

        def rf_sids(recs):
            return sorted(p.name.removesuffix(".model_input.bin")
                          for p, _, is_rf in recs if is_rf)

        all_finite = build_finetune_dataset(tsv, tdir, "S1", "RF_ALL_FINITE")
        gate_only = build_finetune_dataset(tsv, tdir, "S1", "RF_GATE_PASS_ONLY")
        assert rf_sids(all_finite) == ["s1_c00_i00", "s1_c01_i00"], rf_sids(all_finite)
        assert rf_sids(gate_only) == ["s1_c00_i00"], rf_sids(gate_only)

    print("train_finetune_pilot SELFTEST OK: ckpt SHA verified; E0=%d E1=%d E2=%d E3=%d "
          "(total %d); real training loop reachable; RF_ALL_FINITE vs RF_GATE_PASS_ONLY "
          "arms split correctly" %
          (masks["E0"], masks["E1"], masks["E2"], masks["E3"], n_total))
    return 0


def cmd_train(args) -> int:
    torch, nn, _, _, _ = _load_torch_and_model()
    cap = Path(args.capture_tsv)
    if not cap.is_file():
        raise SystemExit("--capture-tsv not found: %s" % cap)
    gt = load_ground_truth(Path(args.ground_truth) if args.ground_truth else None)
    train = build_finetune_dataset(cap, Path(args.tensor_dir), "S1", args.train_rf_arm, gt=gt) + \
            build_finetune_dataset(cap, Path(args.tensor_dir), "S2", args.train_rf_arm, gt=gt)
    val = build_finetune_dataset(cap, Path(args.tensor_dir), "S3", args.train_rf_arm, gt=gt)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    seeds = [int(s) for s in args.seeds.split(",")]
    for exp in (args.experiments.split(",") if args.experiments else EXPERIMENTS):
        for sd in seeds:
            run_training(exp, sd, train, val, out, epochs=args.epochs,
                         batch_size=args.batch_size, head_lr=args.head_lr,
                         bone_lr=args.bone_lr, patience=args.patience,
                         torch=torch, nn=nn)
    print("FINETUNE_TRAIN_DONE")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true",
                    help="构建 + 冻结掩码 + 合成前反向 + 训练循环可达性自测")
    ap.add_argument("--train", action="store_true", help="真实微调（采集后）")
    ap.add_argument("--capture-tsv", default="", help="32 字段采集 TSV")
    ap.add_argument("--tensor-dir", default="", help="板端恢复 model_input 张量目录")
    ap.add_argument("--ground-truth", default="",
                    help="主机真值清单（9 列，source_manifest_960.tsv；默认自动定位）")
    ap.add_argument("--train-rf-arm", default="RF_ALL_FINITE",
                    choices=RF_ARMS,
                    help="RF 训练样本纳入口径：RF_ALL_FINITE(默认，所有有限 tensor) / "
                         "RF_GATE_PASS_ONLY(仅过门)")
    ap.add_argument("--experiments", default="", help="逗号分隔 E0..E3，默认全部")
    ap.add_argument("--seeds", default="2027,2028,2029")
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--head-lr", type=float, default=3e-4)
    ap.add_argument("--bone-lr", type=float, default=1e-5)
    ap.add_argument("--patience", type=int, default=4)
    ap.add_argument("--out-dir", default="")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.train:
        if not (args.capture_tsv and args.tensor_dir and args.out_dir):
            ap.error("--train needs --capture-tsv --tensor-dir --out-dir")
        return cmd_train(args)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
