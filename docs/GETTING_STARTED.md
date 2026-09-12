# 从这里开始

![Research Code Stewardship Lab：Paper → Code → Evidence → Governance](images/research-code-stewardship-banner.svg)

**Research Code Stewardship Lab** 帮你判断一套“能运行”的研究代码、实验和 Agent 流程，是否仍然忠实于论文、实验协议与可追溯证据。它不是代码速写教程；它训练的是在 Coding Agent 时代做出有证据的研究判断。

[English](GETTING_STARTED_EN.md) · [仓库地图](../REPOSITORY_MAP.md) · [能力模型](COMPETENCY_MODEL.md) · [Mode Train](TRAIN_MODE.md) · [Mode Audit](AUDIT_MODE.md) · [双模式路线图](DUAL_MODE_ROADMAP.md)

命令行明确分为两条路径：`rcsl.py train ...` 用于人类能力训练（不是训练模型），`rcsl.py audit ...` 用于真实 Git 项目的证据与决策记录。旧顶层命令仅作兼容别名保留。

## 先选你的目标

| 你是谁 | 先做什么 | 你会得到什么 |
| --- | --- | --- |
| **Learner（学习者）** | 读 [Mode Train 指南](TRAIN_MODE.md)，再用 `python scripts/rcsl.py train progress init ...` 建立外部工作区 | 可暂停恢复的 Evidence Passport、不可变尝试、人工反馈与跨层 Capstone |
| **Project owner / Auditor（项目负责人或审计员）** | 读 [Mode Audit 指南](AUDIT_MODE.md)，再用 `python scripts/rcsl.py audit init ...` 绑定 clean Git `HEAD` | G0、结构化 finding/evidence、本地事件链和人工复审报告 |
| **Reviewer / Maintainer（审阅者或维护者）** | 运行公开检查，审查训练包的文档、接口与验证入口 | 一份可复现的公开检查结果，以及需要复审的风险清单 |
| **Research owner（研究负责人）** | 先冻结论文—代码—实验协议，再用 Skill 设计新的训练包 | 一份经人工批准的四级设计规格，而不是未经批准的候选代码 |

---

## 路径 A：我是学习者

### 1. 用公开检查确认环境可用

在仓库根目录运行：

```bash
python -m pip install -r requirements.txt
python scripts/rcsl.py train overview
python scripts/rcsl.py train doctor
python scripts/rcsl.py train validate
```

预期结果是连续出现 `LEVEL 1: PASS` 到 `LEVEL 4: PASS`。这说明你拿到的是一个可运行、公开结构完整的训练包；它**不**替你判断哪个候选忠实于论文，也不代表实验结论已成立。

若要保存学习进度，在仓库外建立自己的本地工作区：

```bash
python scripts/rcsl.py train progress init \
  --output /absolute/path/to/my-rcsl-progress \
  --learner "your declared label"
```

之后编辑 `worksheets/L1.md`，用 `train progress check` 检查结构、`submit` 冻结尝试、`review` 记录具名人工复核，并在 L1–L4 后完成 `capstone`。完整命令见 [Mode Train 指南](TRAIN_MODE.md)。

### 2. 按层级学习，不要跳关

从 [课程主页](../LLM4SBR_research_audit_training_v2/README.md) 和 [Progression](../LLM4SBR_research_audit_training_v2/PROGRESSION.md) 开始，然后依次进入每一关：

| Level | 审计问题 | 先读 | 公开检查 |
| --- | --- | --- | --- |
| 1 | 公式、张量、mask、loss 和梯度语义对吗？ | [`level_1_algorithm_semantics/README.md`](../LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/README.md) | `python LLM4SBR_research_audit_training_v2/level_1_algorithm_semantics/run_smoke.py` |
| 2 | 数据身份、切分、指标和 checkpoint 的链路完整吗？ | [`level_2_pipeline_integrity/README.md`](../LLM4SBR_research_audit_training_v2/level_2_pipeline_integrity/README.md) | `python LLM4SBR_research_audit_training_v2/level_2_pipeline_integrity/run_smoke.py` |
| 3 | 比较是否公平，证据是否支持科学主张？ | [`level_3_scientific_validity/README.md`](../LLM4SBR_research_audit_training_v2/level_3_scientific_validity/README.md) | `python LLM4SBR_research_audit_training_v2/level_3_scientific_validity/validate_evidence_schema.py` |
| 4 | Agent 的审批、预算、记录和受保护证据是否合规？ | [`level_4_agent_experiment_governance/README.md`](../LLM4SBR_research_audit_training_v2/level_4_agent_experiment_governance/README.md) | `python LLM4SBR_research_audit_training_v2/level_4_agent_experiment_governance/validate_ledger_schema.py` |

四级之后的 [跨层 Capstone](../LLM4SBR_research_audit_training_v2/CAPSTONE_BRIEF.md) 不是 L5。它把 G0、分诊、委派、影响面、claim 边界和沟通合并为一次事故响应，并且只能由具名人工复核通过。

### 3. 提交的是证据链，不是一个字母

每一关都有公开的 `ANSWER_SHEET.md`。在完成它之前，应能回答：

1. 结论对应哪一个具体位置或记录？
2. 它违反了哪条论文、流水线、实验或治理 contract？
3. 什么最小反例能够把问题暴露出来？
4. 为什么它仍能运行或给出看似合理的结果？
5. 最小的安全修复是什么？

### 可选前置：先只读论文，再看代码

如果你希望先建立独立判断基准，使用 [Source-Blind Paper Learning Protocol](PAPER_ONLY_REPRODUCTION_PROTOCOL.md)。该路线只依据论文及其公开补充材料建立 `PAPER_STUDY_GUIDE.md`，避免把“现有代码怎么做”误当作“论文必然要求什么”。

---

## 路径 B：我是审阅者或维护者

先运行完整公开检查：

```bash
python LLM4SBR_research_audit_training_v2/run_all_public_checks.py
```

然后按照下面的顺序审阅：

1. 读取 [四级课程主页](../LLM4SBR_research_audit_training_v2/README.md) 和 [框架概览](../LLM4SBR_research_audit_training_v2/FRAMEWORK_OVERVIEW.md)，确认题目对应的能力边界。
2. 阅读各 Level 的公开题目说明与公共验证脚本，检查入口、文档和 contract 是否一致。
3. 将 `PASS` 视为“这四个公开验证器在当前版本通过”，而不是“研究结论正确”或“题目没有任何科学偏差”。
4. 若修改训练包，重新运行同一组公开检查，并记录更改、理由、风险和未覆盖的假设。

预期产物是一份可追踪的维护说明：修改了什么、哪些公开约束被重新验证、哪些判断仍需要人工复审。

---

## 路径 C：我正在审计一个真实项目

先选择当前要检查的“首个失效契约”层级。目标必须是 clean Git 工作树，新工作区必须位于项目之外。例如，怀疑数据身份或 checkpoint 流程时从 L2 开始：

```bash
rcsl() { python scripts/rcsl.py "$@"; }
PROJECT="/absolute/path/to/clean-git-project"
WORKSPACE="/absolute/path/outside-project/my-project-audit"

rcsl audit init --project "$PROJECT" --output "$WORKSPACE" \
  --level 2 --actor "researcher"
rcsl audit status "$WORKSPACE"
```

初始化会固定当前 `HEAD` 与 branch，创建四份公开模板、`findings/`、工作区元数据和 hash-chained 事件日志；G0 初始状态是 `draft`。接着编辑新目录中的：

| 文件 | 由你填写的决定或证据 |
| --- | --- |
| `research-contract-template.md` | G0 的问题、允许主张、来源/许可、保护边界、预算和最终人类负责人 |
| `triage-card-template.md` | 异常、影响面、竞争假设、最小排查与停止/升级条件 |
| `delegation-contract-template.md` | Agent 能做什么、不能做什么、验收证据和人工审批点 |
| `evidence-passport-template.md` | 一项发现的准确位置、首个失效契约、反例、因果影响、修复和签字决定 |

将 G0 研究契约的每个双花括号占位项替换为真实声明；未知时写明 `Unknown — 原因与负责人`，不要猜测。然后检查 G0 并记录人类决定：

```bash
rcsl audit gate check "$WORKSPACE"
rcsl audit gate record "$WORKSPACE" --decision approved \
  --reviewer "research-owner" --rationale "Scope and evidence plan reviewed."
rcsl audit preflight "$WORKSPACE"
```

通过 preflight 后，才把一个可评审的 claim 记为 finding，追加证据，再显式转换状态：

```bash
rcsl audit finding add "$WORKSPACE" --id F-001 \
  --title "Possible split-lineage mismatch" --layer L2 --competency C2 \
  --severity high --claim "Generated IDs may cross the declared split boundary." \
  --first-contract "Sample identity remains split-isolated." --actor "researcher"

rcsl audit evidence add "$WORKSPACE" --finding F-001 --id E-001 \
  --kind observed --reference "config/split.yaml" \
  --summary "The recorded split rule needs independent recomputation." --actor "researcher"

rcsl audit finding transition "$WORKSPACE" --finding F-001 --to triaged \
  --actor "researcher" --rationale "Location and next decisive check are recorded."
rcsl audit finding list "$WORKSPACE"

# 人类完成其余三份模板后，再做整个工作区的结构检查与交接。
rcsl audit lint "$WORKSPACE"
rcsl audit verify "$WORKSPACE"
rcsl audit report build "$WORKSPACE" --output "$WORKSPACE/review.md" --format markdown
```

如果目标 `HEAD` 发生改变，preflight 会拒绝继续。人类先审阅变更，再显式换基线；该操作会把 G0 重置为 `draft`，旧 finding 仍绑定旧 commit：

```bash
rcsl audit rebaseline "$WORKSPACE" --actor "research-owner" \
  --reason "Reviewed the new commit; prior evidence remains on the old baseline."
```

`lint`、`gate check`、`preflight`、`verify` 和 `report build` 只说明它们声明的结构或本地一致性范围，**不表示研究问题正当、finding 成立、修复正确或科学结论获批**。`--actor` / `--reviewer` 是未认证的记录标签；hash chain 只能检出仍被保留的本地历史中的不一致，不能防删除、整体重写或认证身份。任何 scoped 状态都不是 scientific PASS。

Mode Audit 默认只读取目标项目和 Git 元数据，**不执行项目代码、不联网、不修改项目**。需要这些动作时，应在本工具之外另行取得明确授权。命令状态、finding 转换规则与 hash-chain 限制见 [Mode Audit 完整指南](AUDIT_MODE.md)。

七项负责人能力、四档成熟度和 capstone 见 [现代研究程序员能力模型](COMPETENCY_MODEL.md)。

---

## 路径 D：我是研究负责人，想为另一篇论文建立训练

这个仓库提供可复用的 [`research-code-audit-training` Skill](../skills/research-code-audit-training/SKILL.md)，将“论文 + 源码 + 实验协议”转为四级审计训练，而不是直接代写一个实验项目。

### 推荐流程

```text
冻结问题、论文证据、源码范围与实验协议
→ 生成论文到代码的映射和四级设计规格
→ 人工审核并批准设计规格
→ 生成候选、公开检查与隔离的教学材料
→ 用公开检查和独立审阅验证发布包
```

在 Codex 中安装该 Skill（可选）后，可在新任务中调用它：

```bash
mkdir -p ~/.codex/skills
cp -R skills/research-code-audit-training ~/.codex/skills/
```

```text
$research-code-audit-training
```

先使用 [`design-spec-template.md`](../skills/research-code-audit-training/assets/design-spec-template.md) 明确目标、保护输入、四级 fault family 与验收矩阵。**必须在设计规格获得人工批准后，才进入候选实现阶段。**

预期结果是一份可评审的设计规格：它把“论文主张—代码位置—可执行不变量—验证方式”连起来，并明确哪些选择仍是假设。

---

## 两条始终有效的边界

### 1. 答案隔离保护训练价值

课程将教师材料与学习者可见材料分开。完成某一关的公开题目、运行公开检查并写完证据链之前，不要搜索、读取或引用标明为教师专用或完成后解锁的材料。公开验证器也不应依赖这些材料。由于它们位于同一公开仓库，这只是 honor isolation，不是访问控制；真正盲测应按 [案例发布模型](CASE_RELEASE_MODEL.md) 分包。

### 2. `public PASS` 只是开始

公开 `PASS` 可以证明脚本、格式或部分可执行不变量没有立即失效；它不能证明：

- 某个实现忠实于论文；
- 数据与评估比较公平；
- 结果足以支持科学主张；
- Agent 的每个动作都已获授权；
- 任何论文结论已经被复现。

因此每一次审计仍要回到原始证据、冻结的协议和清楚记录的因果论证。

## 接下来去哪里

- 想理解所有目录：看 [仓库地图](../REPOSITORY_MAP.md)。
- 想直接开始 LLM4SBR 案例：看 [四级训练课程](../LLM4SBR_research_audit_training_v2/README.md)。
- 想审计自己的项目：按 [Mode Audit 指南](AUDIT_MODE.md) 用 `audit init` 建立绑定 commit 的证据工作区。
- 想知道哪些已实现、下一步做什么：看 [双模式路线图](DUAL_MODE_ROADMAP.md)。
- 想先建立不看源码的论文理解：看 [Source-Blind Protocol](PAPER_ONLY_REPRODUCTION_PROTOCOL.md)。
- 想把流程用于自己的论文：看 [Skill 主文件](../skills/research-code-audit-training/SKILL.md)。
