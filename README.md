# riscv-isa-skills

OpenCode skills 合集，面向 RISC-V ISA 分析、调试与逆向工程。

## Skills

| 目录 | 描述 |
|------|------|
| `skills/spike-isa-internals/` | Spike 模拟器内部机制调试：使用 rr+Spike 回放定位指令执行细节 |
| `skills/rrspike-isa-event-extractor/` | 从 Spike trace 中提取 ISA 事件（CSR 读写 / trap） |
| `skills/riscv-inst-decoder/` | 解码 RISC-V 指令二进制编码（基于 gem5 decode tree） |
| `skills/csr-parser/` | CSR 编码解析与字段分析 |

## 使用

将需要的 skill 目录复制或链接到 OpenCode 的 skills 目录，或直接通过 `skill` 工具加载。

```bash
# 例如加载 spike-isa-internals
cp -r skills/spike-isa-internals ~/.config/opencode/skills/
```

或使用软链接保持更新：

```bash
ln -sfn $(pwd)/skills/spike-isa-internals ~/.config/opencode/skills/
```

## 结构

```
riscv-isa-skills/
├── README.md
├── skills/
│   ├── spike-isa-internals/        # rr/Spike 交互调试 (SKILL.md + Python 工具链)
│   ├── rrspike-isa-event-extractor/ # ISA 事件提取
│   ├── riscv-inst-decoder/          # 指令解码
│   └── csr-parser/                  # CSR 解析
```
