# rrspike ISA Investigation Skill

目标：给定 `ELF + 目标指令 index`，自动抵达 Spike 执行该指令的入口，并输出附近 ISA 事件（CSR 读写 / trap）。

## 标准流程

1. 进入目标入口（交互式 rr/gdb）

```bash
rrspike goto \
  --elf-path <ELF_PATH> \
  --target-index <INDEX> \
  --instruction-budget <BUDGET> \
  --work-dir <WORK_DIR>
```

2. 生成 ISA 事件窗口

```bash
rrspike inspect-events \
  --trace-path <WORK_DIR>/spike_trace.json \
  --target-index <INDEX> \
  --before 24 \
  --after 24 \
  --out-path <WORK_DIR>/isa_events.json
```

3. 结果解读准则

- `event_type=csr-read`：CSR/FCSR/FRM/FFLAGS 读取
- `event_type=csr-write`：CSR 写入或位更新
- `event_type=trap`：`ecall/ebreak/mret/sret` 等控制流事件
- `is_target=true`：目标指令本身

## 面向子智能体的检查清单

当被问“某条指令涉及哪些 CSR 读写/trap 事件”时：

1. 先确认 `ELF`、`index`、`work_dir` 三个输入
2. 运行 `rrspike goto` 到入口（若只需要事件可跳过交互停留）
3. 运行 `rrspike inspect-events` 产出结构化事件
4. 以时间线格式输出：
   - `index`
   - `pc`
   - `text`
   - `event_type`
   - `is_target`
5. 若没有事件，明确给出“窗口内未捕获 CSR/trap 事件”并建议扩大窗口
