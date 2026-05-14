# rr-spike-rv-replay 项目说明（中文版）

## 1. 项目定位

`rr-spike-rv-replay` 是一个面向 RISC-V 指令行为分析的自动化工具链，核心目标是：

- 用 `rr` 录制 `spike` 进程执行测例的全过程
- 用外部 RISC-V 指令 trace（独立于 rr）定位目标指令
- 自动生成并执行 `rr replay` 的 `gdb` 脚本
- 输出可复盘的分析工件（命中信息、脚本、摘要、审计数据）

一句话：把“录制 -> 定位 -> 回放 -> 观察 -> 报告”串成可重复执行的流水线。

---

## 2. 目录结构

### 2.1 代码目录

- `src/rr_spike_rv_replay/cli.py`：CLI 入口与参数校验，构造 `PipelineConfig`
- `src/rr_spike_rv_replay/pipeline.py`：主流程编排（preflight、record、trace 解析、脚本生成、replay、报告）
- `src/rr_spike_rv_replay/preflight.py`：工具可用性检查（`rr/gdb/spike`）与 Spike 符号检查入口
- `src/rr_spike_rv_replay/recorder.py`：`rr record` 命令构建与执行
- `src/rr_spike_rv_replay/replayer.py`：`rr replay -x` 命令构建与执行
- `src/rr_spike_rv_replay/trace_bridge.py`：外部 trace 解析与目标指令选择
- `src/rr_spike_rv_replay/gdb_script_builder.py`：`replay.gdb` 脚本模板与动态段生成
- `src/rr_spike_rv_replay/reporter.py`：`event_summary.md` 与 JSON 工件输出
- `src/rr_spike_rv_replay/llm_assist.py`：LLM 建议过滤（仅建议，不直接控制执行）
- `src/rr_spike_rv_replay/__init__.py`：对外导出 API

### 2.2 测试目录

- `tests/test_cli_args.py`
- `tests/test_pipeline.py`
- `tests/test_trace_bridge.py`
- `tests/test_gdb_script_builder.py`
- `tests/test_preflight.py`
- `tests/test_recorder.py`
- `tests/test_replayer.py`
- `tests/test_reporter.py`
- `tests/test_locator.py`

### 2.3 文档目录

- `docs/superpowers/specs/2026-03-26-rr-spike-rv-replay-design.md`：设计说明
- `docs/superpowers/plans/2026-03-26-rr-spike-rv-replay.md`：实现计划
- `docs/PROJECT_GUIDE_CN.md`：本说明文档

---

## 3. 架构设计总览

### 3.1 关键角色关系（谁运行谁）

- **被测对象**：RISC-V 测例（ELF/汇编）
- **执行者**：`spike`（在宿主 CPU 上模拟执行 RISC-V 指令）
- **录制者**：`rr`（录制的是 `spike` 进程）
- **调试观察点**：Spike 内部 step 入口（默认 `processor_t::step`），通过条件断点逼近目标指令
- **定位依据**：外部指令 trace（独立输入）

### 3.2 流水线阶段

1. **参数校验（CLI）**
2. **预检（preflight）**
3. **录制（rr record spike ...）**
4. **trace 桥接定位（index/pc/pattern 等）**
5. **生成 per-case `replay.gdb`**
6. **回放（rr replay -x replay.gdb）**
7. **输出工件与分析摘要**

### 3.3 设计原则

- **确定性核心**：record/replay 与目标选择逻辑可重复
- **LLM 仅建议层**：建议会被记录，但不直接决定执行动作
- **降级可用**：符号不可用时可切换地址/模式断点策略
- **可审计**：关键决策与工件落盘

---

## 4. 关键实现方式

### 4.1 配置模型与输入约束

`PipelineConfig`（`cli.py`）核心字段：

- 必填：`test_case`, `run_cmd`
- trace 相关：`trace_path`, `target_insn_index`, `target_pc`, `rv_instr_pattern`, `rv_instr`, `hart_id`
- step 断点相关：`spike_step_symbol`, `spike_step_address`, `spike_step_pattern`, `spike_counter_expr`
- 策略相关：`stop_policy(first-hit|nth-hit)`, `nth`, `window_before`, `window_after`
- LLM 相关：`llm_mode(off|assist)`

校验重点：

- `run_cmd` 首 token 必须是 `spike` 可执行名（支持绝对路径）
- 至少要有一个目标选择器
- `nth >= 1`，窗口值非负

### 4.2 外部 trace 桥接

`trace_bridge.py` 支持两种输入 JSON：

- `{"instructions": [...]}`
- `[...]`

每条记录至少包含 `index`，可选 `pc/binary/text/hart_id`。

目标选择优先级：

1. `target_insn_index`
2. `target_pc`
3. `rv_instr_pattern`（正则）
4. `rv_instr`（子串）

命中策略：`first-hit` / `nth-hit`，可叠加 `hart_id` 过滤。

无命中时：返回 `no-trace-match` 与 rerun hints（最近可观察点建议）。

### 4.3 Spike 符号策略与兜底

`pipeline.py` 中 `_resolve_symbol_strategy`：

- 符号可用：`symbol`（`break processor_t::step`）
- 符号不可用且有地址：`address`（`break *0x...`）
- 符号不可用且有模式：`pattern`（`rbreak ...`）
- 符号不可用且无兜底：直接 `RuntimeError`

符号检查来源是 **Spike 二进制符号**，不是 RISC-V 测例符号。

### 4.4 replay 脚本生成（per-case）

`gdb_script_builder.py` 使用“公共前导 + 动态注入”模式：

- 公共：`set pagination off`, `set confirm off`
- 动态：
  - case 标识
  - 目标 index/pc
  - 断点策略与断点值
  - 条件表达式：`{spike_counter_expr} == target_index`（可加 `&& $hartid == N`）
  - reverse/forward 步进窗口
  - 寄存器/内存观察语句

结论：`replay.gdb` 是 per-case 动态文件，不是固定通用脚本。

### 4.5 工件输出

默认输出以下工件：

- `capture_meta.json`：运行命令、symbol 策略、目标信息、preflight 结果、rerun hints
- `replay.gdb`：本次回放脚本
- `event_summary.md`：人类可读摘要
- `analysis_trace.json`：LLM 建议采纳情况
- `index_snapshot.json`：候选/trace 快照

---

## 5. 当前能力边界

### 已覆盖

- `rr` 录制 `spike` 进程
- 外部 trace 桥接定位
- `first-hit/nth-hit` 与 `hart` 过滤
- 符号不可用时的地址/模式兜底
- per-case replay 脚本生成与自动回放
- 全流程工件落盘与测试覆盖

### 尚可增强

- `trace_id` 目前依赖 rr 输出文本解析，个别环境可能为空
- `event_summary.md` 目前偏轻量，可扩展更丰富寄存器/内存变化叙述
- 默认 `spike_counter_expr` 需要结合具体 Spike 版本或 instrumentation 调整

---

## 6. 使用方法

### 6.1 环境准备

至少确保命令可用：

- `rr`
- `gdb`
- `spike`
- （可选）`pk` 与 RISC-V 工具链

快速自检：

```bash
cat /proc/sys/kernel/perf_event_paranoid
rr record /bin/true
which spike
```

### 6.2 准备输入

1. 准备测例 ELF
2. 生成外部 trace（例如 Spike `-l --log=...`）
3. 将 trace 转换为 JSON（包含 `index`，推荐带 `pc/text/hart_id`）

### 6.3 通过 Python API 运行

```python
from rr_spike_rv_replay.cli import build_config
from rr_spike_rv_replay.pipeline import run_pipeline

cfg = build_config(
    test_case="demo-case",
    run_cmd="/opt/riscv/bin/spike /opt/riscv/riscv64-unknown-elf/bin/pk /path/to/demo.elf",
    trace_path="/path/to/spike_trace.json",
    target_insn_index=1234,
    hart_id=0,
    stop_policy="first-hit",
    spike_step_symbol="processor_t::step",
    spike_counter_expr="spike_insn_count",
)

result = run_pipeline(cfg, "/tmp/rr_spike_out")
print(result)
```

### 6.4 通过 CLI 运行

项目已提供 `console_scripts` 入口：`rrspike`。

安装（建议 editable 模式）：

```bash
pip install -e .
```

执行示例：

```bash
rrspike run \
  --test-case demo-case \
  --run-cmd "/opt/riscv/bin/spike /opt/riscv/riscv64-unknown-elf/bin/pk /path/to/demo.elf" \
  --out-dir /tmp/rr_spike_out \
  --trace-path /path/to/spike_trace.json \
  --target-insn-index 1234 \
  --hart-id 0 \
  --stop-policy first-hit
```

补充两个高频命令：

```bash
# Spike commit log -> trace JSON
rrspike convert-log --log-path /tmp/spike.log --out-path /tmp/trace.json

# 给定 ELF + 第 x 条指令，进入交互式 rr/gdb 目标入口
rrspike goto --elf-path /path/to/demo.elf --target-index 1234 --work-dir /tmp/goto_demo

# 场景2：到入口后前/后向探测并输出证据日志
rrspike investigate \
  --elf-path /path/to/demo.elf \
  --target-index 1234 \
  --question "这条指令涉及哪些CSR读写/trap事件？" \
  --work-dir /tmp/investigate_demo \
  --steps-before 6 \
  --steps-after 6 \
  --out-path /tmp/investigate_demo/result.json

# 从 trace 中抽取目标指令前后的 CSR/trap ISA 事件
rrspike inspect-events \
  --trace-path /path/to/spike_trace.json \
  --target-index 1234 \
  --before 24 \
  --after 24 \
  --hart-id 0 \
  --out-path /tmp/isa_events.json
```

场景 2 的子智能体协作说明请参考：`skills/rrspike-isa-investigation.md`。
新版 agent 驱动探测 skill 请参考：`skills/rrspike-investigate.md`。

---

## 7. 注意事项与排障建议

### 7.1 rr 常见限制

- 若 `rr record` 报 `perf_event_open` 权限错误，需检查容器/宿主机是否允许 perf 计数器
- 容器场景常见需要：`SYS_PTRACE`、放宽 seccomp、设置 `perf_event_paranoid`

### 7.2 Spike 符号可见性

- 推荐使用带调试符号的 Spike（如 `-g -O0`）
- 若符号不可见，请提供 `spike_step_address` 或 `spike_step_pattern`

### 7.3 trace 质量

- `index` 必须存在
- 若要稳定命中，建议 trace 同时包含 `pc` 与 `text`
- 多 hart 场景建议明确 `hart_id`

### 7.4 断点条件表达式

- `spike_counter_expr` 必须是 gdb 上下文可求值表达式
- 若表达式不可用，会导致断点条件无法按预期命中

---

## 8. 测试与质量状态

本项目使用 `pytest`，测试覆盖配置校验、trace 选择、脚本生成、preflight、record/replay 命令构建、pipeline 主流程与失败路径。

执行方式：

```bash
python3 -m pytest -q
```

当前状态（最近验证）：全量测试通过。

---

## 9. 快速上手建议

如果你是第一次使用，建议按以下顺序：

1. 先跑一个最小 ELF（确认 Spike + pk 可执行）
2. 用 `rr record /bin/true` 验证 rr 环境
3. 用 Spike 生成一份短 trace，先用 `target_insn_index` 命中
4. 再逐步切换到 `target_pc`/`rv_instr_pattern` 与 `nth-hit`
5. 最后启用更多观察点与报告增强

这样能最快区分“环境问题”和“分析逻辑问题”。
