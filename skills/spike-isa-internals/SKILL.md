---
name: spike-isa-internals
description: |
  Investigate RISC-V instruction execution details by combining rr/Spike replay
  with interactive gdb in a tmux session. Use when the user needs to understand
  what a specific instruction does at the microarchitectural level — CSR reads/writes,
  trap behavior, permission checks, register/memory side effects.

  Key dependency: rr record/replay must work. If rr fails, stop immediately.
  Requires: tmux skill for interactive gdb session.

  Trigger phrases: "spike", "instruction execution", "csr debug", "rrspike",
  "goto instruction", "what happened at index", "instruction behavior",
  "spike internal", "execute.cc", "processor_t::step".
---

# Skill: rrspike-investigate

目标：在 tmux 会话中使用 `rrspike goto` 抵达目标指令，然后由 agent 主动在交互式 gdb 会话中探索指令执行细节，给出证据化结论。

**关键依赖**: `rr record` 和 `rr replay` **必须**正常工作。如果 rr 失败，立即停止并报告错误。

## 前置条件：tmux 会话

**必须先启动 tmux 会话，才能在其中运行 `rrspike goto` 的交互式 gdb**。

使用 tmux skill 创建一个 shell 会话：

```bash
./tools/create-session.sh -n rrspike-debug --shell
```

然后在该会话中执行所有后续命令。监控方式：

```bash
tmux -S <socket> capture-pane -p -J -t rrspike-debug:0.0 -S -200
```

## Part 0: 初始化与快速定位

### 步骤 1: 生成 Spike 执行日志（确定目标指令 PC）

在 tmux 会话中运行：

```bash
rrspike goto \
  --elf-path <ELF_PATH> \
  --target-index <INDEX> \
  --instruction-budget <BUDGET> \
  --work-dir <WORK_DIR>
```

**如果 rrspike goto 失败**（任何原因），输出会包含错误信息。**停止，报告完整错误输出，不继续**。

**关键点**：
- `--target-index` 是 Spike 执行日志中第 N 条指令的序号（0-indexed）
- `--instruction-budget` 应足够覆盖目标指令。默认公式 `max(4096, index + 256)`
- 成功时会输出 `READY_FOR_INTERACTIVE_DEBUG` 并在 `execute.cc:308` 处暂停在目标 PC

### 输出迹象

```
Breakpoint hit at execute.cc:308 (processor_t::step)
HIT_TARGET_PC=0x80000ca
READY_FOR_INTERACTIVE_DEBUG
```

此时 gdb 会话已启动，正在等待你的交互命令。

---

## Part 1: 通用 rr/gdb 调试技巧

在交互式 gdb 会话中使用这些命令。

### 基本导航

| 命令 | 效果 | 用途 |
|------|------|------|
| `continue` | 向前执行到下一个断点 | 大步向前 |
| `stepi` | 执行一条机器指令 | 单步向前（Spike 内部实现） |
| `reverse-continue` | 向后回放到上一个断点 | 大步向后 |
| `reverse-stepi` | 回放一条机器指令 | 单步向后 |
| `finish` | 执行直到当前函数返回 | 跳过函数调用 |

### 检查指令与上下文

| 命令 | 效果 |
|------|------|
| `x/i $pc` | 反汇编当前 PC 处的指令 |
| `print/x pc` | 打印当前 RISC-V PC（目标架构） |
| `info registers` | 显示 x86-64 宿主寄存器（调试工具的寄存器） |
| `backtrace` | 显示 C++ 调用栈（Spike 内部） |

### 编译优化带来的变量访问问题

**问题**：局部变量被优化掉，无法用 `print var` 访问。

**解决方案**：
1. **通过函数参数推导**：看 `info args` 输出
2. **通过寄存器推导**：x86-64 调用约定中，参数在 `rdi`, `rsi`, `rdx` 等寄存器中
3. **访问 Spike 数据结构**：
   - RISC-V 寄存器文件：`print $processor->state.XRF[5]`（寄存器 a5 的内容）
   - PC：`print/x pc` 直接得到（因为 `pc` 是 Spike 的执行状态）

### 断点与条件表达式

在特定条件下暂停：

```bash
break ../riscv/execute.cc:308 if pc == 0x80000ca
```

这会在 `execute.cc:308` 处设置断点，但仅当 RISC-V PC 等于 `0x80000ca` 时触发。

### 回放与二分查找

rr 的强大之处：可以无损回放执行。用途：

- **验证执行顺序**：`reverse-continue` 返回前一条指令，检查 PC 序列
- **二分定位问题**：在反向探索中找到状态变化点
  1. 在某处暂停
  2. 向前 10 步，观察状态
  3. 如果正常，继续向前；如果异常，回放 5 步找中点
  4. 重复直到找到第一条改变状态的指令

### 日志与输出控制

在 gdb 脚本中常见的设置：

```bash
set pagination off      # 禁用分页（自动 "more"）
set confirm off         # 禁用确认提示
set height 0            # 行高无限制
set width 0             # 列宽无限制
```

---

## Part 2: Spike 特定知识

### Spike 执行流程与 goto 原理

Spike 是单步解释器。每条 RISC-V 指令的执行流程：

```
processor_t::step()  [execute.cc:308]
  ├─ fetch fetch+pc
  ├─ decode → insn（指令对象）
  └─ execute_insn_fast(this, pc, fetch)  [execute.cc:162]
       └─ fetch.func(p, insn, pc)  [ISA 特定的处理函数]
           └─ 处理指令（读/写寄存器、CSR、内存等）
           └─ 返回新 PC（或异常编号）
```

**goto 的工作原理**：
1. 生成 Spike 执行日志（指令序列 + PC）
2. 从日志中提取目标指令的 PC
3. 用 `rr record` 记录 Spike 执行
4. 用 `rr replay` 回放
5. 在 `execute.cc:308`（每条指令同步点）设置条件断点 `if pc == <target_pc>`
6. gdb 连接到 rr 回放服务器，`continue` 直到命中断点

### 关键断点位置

| 位置 | 意义 |
|------|------|
| `execute.cc:308` | `processor_t::step()` 中每条指令的入口（ISA 无关同步点） |
| `execute.cc:162` | `execute_insn_fast()` 即将调用指令处理函数（ISA 特定处理前） |
| `insns/csrrs.h:2` | CSR 指令处理函数内部（访问 CSR 前） |
| Spike 源码中的 CSR 处理 | 依赖具体 CSR 编号 |

### 状态变量访问

#### RISC-V 寄存器（整数）

访问方式：

```bash
print $processor->state.XRF[5]     # 寄存器 a5（x5）的值
print $processor->state.XRF[10]    # 寄存器 a0（x10）的值
```

X86-64 宿主中看到的寄存器（`info registers`）是 Spike 解释器的临时状态，**不是** RISC-V 寄存器。

#### RISC-V 浮点寄存器

```bash
print $processor->state.FRF[5]     # 浮点寄存器 fa5（f5）
print $processor->state.FRF[5].d   # 作为 double 解读
```

#### CSR（控制状态寄存器）

读取 CSR 值：

```bash
print $processor->state.csrmap[0x001]    # fflags (CSR 0x001)
print $processor->state.csrmap[0x300]    # mstatus (CSR 0x300)
```

或通过 Spike 内部接口（取决于编译选项）：

```bash
print $processor->state.fflags->read()   # 如果有便捷方法
```

#### MMU 与内存

虚拟→物理地址翻译：

```bash
print $processor->mmu->translate(0x80000000, LOAD, 8)
```

设置虚拟地址断点：

```bash
break ../riscv/mmu.cc:200 if va == 0x80000000
```

### 常见指令类型的观测点

#### CSR 读取指令（csrr）

问题示例：`csrr a5, fflags` 读取浮点标志。

观测流程：

```bash
# Step 1: 在目标 PC 暂停（goto 已完成）
# Step 2: 检查当前上下文
x/i $pc                              # 应显示 csrr 指令
print/x pc                            # 显示 0x800000ca (例)
backtrace                             # 显示调用栈

# Step 3: 进入 CSR 处理逻辑
stepi                                 # 进入 execute_insn_fast
stepi                                 # 继续单步到 CSR 访问

# Step 4: 检查 CSR 数值与权限
print $processor->state.csrmap[0x001] # fflags 当前值
print $processor->state.mstatus       # 检查权限位（如 FS 字段）

# Step 5: 完成指令
continue                              # 或 finish 跳过细节
```

**预期输出**：
- CSR 数值被成功读取到 RISC-V 寄存器
- 无异常（no trap）
- PC 推进到下一条指令

#### CSR 写入指令（csrw）

类似，但需检查：

1. 写入值是否合法
2. 写入后 CSR 的新值
3. 是否触发副作用（如 MMU flush、中断使能变化）

#### 浮点指令

问题示例：`fadd.d` 可能改变 fflags。

观测点：

```bash
print $processor->state.FRF[10]       # 操作数 fa0
print $processor->state.FRF[11]       # 操作数 fa1
print $processor->state.csrmap[0x001] # 执行前的 fflags

stepi                                 # 执行指令

print $processor->state.FRF[12]       # 结果 fa2
print $processor->state.csrmap[0x001] # 执行后的 fflags（检查异常标志）
```

#### 陷入与异常（ecall, ebreak, mret）

`execute_insn_fast()` 返回值表示结果：

| 返回值 | 含义 |
|--------|------|
| 正数（如 3） | 正常执行，返回的是新 PC 或状态码 |
| 负数 | 异常号（e.g., -2 表示非法指令异常） |

观测方式：

```bash
stepi                                 # 执行指令
print/x $rax                          # x86-64 返回值寄存器
```

如果返回负数，则发生异常，应检查：

```bash
print $processor->state.scause        # 异常原因
print $processor->state.stval         # 异常信息
print $processor->state.pc            # 新 PC（可能指向异常处理程序）
```

---

## Part 3: 真实案例：complex example 中的 csrr fflags

### 背景

在 `examples/freestanding/complex/` 中，某处执行 `csrr a5, fflags` 指令。问题：这条指令做了什么？

指令信息：
- Index: 9254
- PC: 0x800000ca
- 编码：`0x001027f3`（csrr a5, fflags）
- 编译来自：`sink = (u64)acc ^ read_fflags();`

### 调试步骤

#### 第 1 步：定位与初始化

```bash
rrspike goto \
  --elf-path examples/freestanding/complex/main.elf \
  --target-index 9254 \
  --work-dir ./rrspike_debug_complex
```

输出（在 gdb 中）：

```
Breakpoint 1 at ...
HIT_TARGET_PC=0x800000ca
READY_FOR_INTERACTIVE_DEBUG
```

#### 第 2 步：观察当前上下文

```bash
(gdb) x/i $pc
=> 0x...: csrr a5, fflags

(gdb) backtrace
#0 execute_insn_fast (fetch=..., pc=2147483850, p=0x...) at ../riscv/execute.cc:162
#1 processor_t::step (... ) at ../riscv/execute.cc:308
#2 sim_t::step (...) at stl_vector.h:1043
#3 sim_t::idle (...) at sim.cc:465
```

**发现**：在 `execute_insn_fast()` 的第一行，即将执行指令处理器函数。

#### 第 3 步：单步进入 CSR 处理逻辑

```bash
(gdb) stepi
(gdb) x/i $pc
=> 0x...: mov %rdi,%rax     # 进入处理函数

(gdb) stepi
(gdb) stepi
...（继续单步，直到到达关键逻辑）

(gdb) info line *0x...    # 确定当前源位置
insns/csrrs.h, line 2
```

**发现**：进入了 `insns/csrrs.h` 的 CSR 读取处理。

#### 第 4 步：检查权限验证

```bash
(gdb) finish                # 完成 validate_csr() 调用
(gdb) print/x $rax          # 返回值
$1 = 0x3                    # 3 = CSR 有效
```

**发现**：`validate_csr()` 返回 3，表示 CSR 0x001（fflags）是有效的，权限检查通过。

#### 第 5 步：读取 fflags 当前值

```bash
(gdb) print $processor->state.csrmap[0x001]
$2 = 0x0                    # fflags = 0（无异常标志）
```

**发现**：fflags 当前为 0，无任何浮点异常标志。

#### 第 6 步：继续执行并观察结果

```bash
(gdb) continue              # 完成指令
(gdb) print $processor->state.XRF[5]
$3 = 0x0                    # 寄存器 a5 现在持有值 0x0
```

**发现**：FFLAGS 值（0）被成功读入寄存器 a5。

### 案例结论

| 方面 | 结论 |
|------|------|
| **执行状态** | 正常完成，无异常 |
| **权限** | 通过（validate_csr 返回 3） |
| **读取值** | fflags = 0x0 |
| **副作用** | 无（仅读取） |
| **后续操作** | 该值被用于计算校验和 |

---

## Part 4: 决策树与常见问题

### "我想知道这条指令是否读/写了某个 CSR"

1. 运行 `rrspike goto` 定位指令
2. 在 gdb 中：
   ```bash
   x/i $pc                           # 确认指令类型
   ```
3. 如果是 CSR 指令（csrr/csrw/csrrs/csrrc）：
   - 对于 **csrr**（读）：执行后检查 `print $processor->state.XRF[rd]`（目标寄存器）
   - 对于 **csrw**（写）：执行前后比较 `print $processor->state.csrmap[csr]`

### "这条指令是否触发异常？"

1. 在 execute.cc:162 处暂停
2. 执行 `stepi` 进入处理逻辑
3. 观察返回值：
   ```bash
   finish                 # 完成 execute_insn_fast()
   print/x $rax           # 返回值
   ```
   - 正数 = 正常，PC 推进
   - 负数 = 异常号

### "变量被优化掉了，如何访问？"

查看 RISC-V 状态结构：

```bash
print $processor->state.XRF[5]       # 寄存器（不会被优化掉）
print $processor->state.csrmap[0x001] # CSR 状态
print $processor->state.FRF[10].d     # 浮点寄存器，作为 double
```

如果仍无法访问，使用反向探索找到状态改变的位置：

```bash
reverse-continue           # 回到前一条指令
print $processor->state... # 比较状态
```

### "我看到的 x86-64 寄存器与预期不符"

**记住**：`info registers` 显示的是 **gdb 宿主机（x86-64）** 的寄存器，不是 RISC-V 寄存器。

RISC-V 状态存储在 Spike 数据结构中：

```bash
print $processor->state.XRF[5]       # RISC-V a5
print $processor->pc                 # RISC-V PC
print $processor->state.mstatus      # RISC-V mstatus CSR
```

---

## 输出要求（必须证据化）

回答任何关于指令执行的问题时，必须包含：

1. **指令确认**：`x/i $pc` 输出，确认目标指令
2. **执行时间线**：
   - 执行前的关键状态（CSR 值、寄存器）
   - 单步过程中的关键断点输出
   - 执行后的状态变化
3. **每条结论对应的证据**：gdb 输出片段或日志摘录
4. **不确定项的明确标记**（如"变量被优化掉，无法观测"）

**禁止**：
- 仅基于指令操作码推断行为（必须运行并观测）
- 忽略异常或权限检查
- 声称观测到未在 gdb 输出中出现的值

---

## 已知限制

**硬性依赖**：如果 `rr record` 失败，**此技能无法使用**。

**故障原因常见于**：
- Zen CPU 上的 SpecLockMap 限制（需运行 zen_workaround.py）
- rr 未安装或权限不足
- Linux 内核版本过旧

**处理方式**：
1. 停止使用此技能
2. 报告 rr 故障消息
3. 修复 rr 问题（运行 zen_workaround.py、安装 rr、更新系统）或在其他系统上运行

**不要**尝试用其他技能替代本技能。

### 编译优化的变量访问

当目标变量被编译器优化掉时，无法通过 `print var` 访问。替代方案：

1. **访问 Spike 内部状态**（推荐）
   ```bash
   print $processor->state.XRF[5]    # RISC-V 寄存器
   print $processor->state.csrmap[0x001]  # CSR
   ```

2. **回溯到寄存器分配点**
   - 使用 `reverse-continue` 回到变量存储点
   - 观察寄存器内容

3. **修改源代码并重编译**（开发场景）
   - 添加 `volatile` 防止优化
   - 或降低优化级别（-O0 或 -O1）
