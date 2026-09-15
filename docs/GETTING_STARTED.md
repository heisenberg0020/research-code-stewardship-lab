# 从这里开始

![Research Code Stewardship Lab：Paper → Code → Evidence → Governance](images/research-code-stewardship-banner.svg)

**Research Code Stewardship Lab** 帮你判断一套“能运行”的研究代码、实验和 Agent 流程，是否仍然忠实于论文、实验协议与可追溯证据。它不是代码速写教程；它训练的是在 Coding Agent 时代做出有证据的研究判断。

[English](GETTING_STARTED_EN.md) · [仓库地图](../REPOSITORY_MAP.md) · [能力模型](COMPETENCY_MODEL.md) · [Mode Train](TRAIN_MODE.md) · [Mode Audit](AUDIT_MODE.md) · [案例发布](CASE_RELEASE_MODEL.md) · [双模式路线图](DUAL_MODE_ROADMAP.md)

命令行明确分为两条工作路径：`rcsl.py train ...` 用于人类能力训练（不是训练模型），`rcsl.py audit ...` 用于真实 Git 项目的证据与决策记录。案例维护者另用 `rcsl.py export ...` / `package ...` 生成发布产物。所有入口都使用这些明确命名空间，不会自动批准发布或科学结论。

## 先选你的目标

| 你是谁 | 先做什么 | 你会得到什么 |
| --- | --- | --- |
| **Learner（学习者）** | 读 [Mode Train 指南](TRAIN_MODE.md)，再用 `python scripts/rcsl.py train progress init ...` 建立外部工作区 | 可暂停恢复的 Evidence Passport、不可变尝试、人工反馈与跨层 Capstone |
| **Project owner / Auditor（项目负责人或审计员）** | 读 [Mode Audit 指南](AUDIT_MODE.md)，再用 `python scripts/rcsl.py audit init ...` 绑定 clean Git `HEAD` | G0、结构化 finding/evidence、本地事件链和人工复审报告 |
| **Reviewer / Maintainer（审阅者或维护者）** | 运行公开检查，审查训练包的文档、接口与验证入口 | 一份可复现的公开检查结果，以及需要复审的风险清单 |
| **Research owner（研究负责人）** | 先冻结论文—代码—实验协议，再用 Skill 设计新的训练包 | 一份经人工批准的四级设计规格，而不是未经批准的候选代码 |
| **Case publisher（案例发布者）** | 先判断案例是已公开 Open Demo，还是从第一天就分离保存的 never-public 候选 | 一个可验证的 Open Demo bundle，或等待受控部署的三包本地 staging |

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

先选择当前要检查的“首个失效契约”层级。目标必须是 clean Git 工作树，新工作区必须位于项目之外；`--output` 必须尚不存在，但它的直接父目录要预先创建并可访问。例如，怀疑数据身份或 checkpoint 流程时从 L2 开始：

```bash
rcsl() { python scripts/rcsl.py "$@"; }
PROJECT="/absolute/path/to/clean-git-project"
WORKSPACE="/absolute/path/outside-project/my-project-audit"

rcsl audit init --project "$PROJECT" --output "$WORKSPACE" \
  --level 2 --actor "researcher"
rcsl audit status "$WORKSPACE"
```

初始化会固定当前 `HEAD` 与 branch，创建四份公开模板、`findings/`、工作区元数据和 hash-chained 事件日志；G0 初始状态是 `draft`。获批 G0 还会保存当时的研究契约字节和 content-bound case。文件通过固定的父目录/新工作区句柄独占创建，结束前复核目录身份；创建期间若路径被替换或重定向会 fail closed。接着编辑新目录中的：

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

通过 preflight 后，才把一个可评审的 claim 记为 finding，导入一个你获准审阅的显式文件，再显式转换状态（把示例文件路径换成目标项目中真实存在的文件）：

```bash
rcsl audit finding add "$WORKSPACE" --id F-001 \
  --title "Possible split-lineage mismatch" --layer L2 --competency C2 \
  --severity high --claim "Generated IDs may cross the declared split boundary." \
  --first-contract "Sample identity remains split-isolated." --actor "researcher"

rcsl audit evidence import "$WORKSPACE" --finding F-001 --id E-001 \
  --type artifact --artifact-role split-config --kind observed \
  --source-kind project-relative --source-path config/split.yaml \
  --summary "保存当前配置字节；切分结果仍需人工重算。" --actor "researcher"

rcsl audit finding transition "$WORKSPACE" --finding F-001 --to triaged \
  --actor "researcher" --rationale "Location and next decisive check are recorded."
rcsl audit finding list "$WORKSPACE"
rcsl audit status "$WORKSPACE" --json

# 人类完成其余三份模板后，再做整个工作区的结构检查与交接。
rcsl audit lint "$WORKSPACE"
rcsl audit verify "$WORKSPACE"
rcsl audit report build "$WORKSPACE" --output "$WORKSPACE/review.md" --format markdown
```

报告必须是 workspace 根目录下尚不存在且非保留的直接子文件；命令固定并复核 workspace 目录身份，以 no-follow、exclusive-create 写入，在 POSIX 上权限为 `0600`。这些是本地防覆盖措施，不是签名或访问控制。

如果目标 `HEAD` 发生改变，preflight 会拒绝继续。人类先审阅变更，再显式换基线；该操作会把 G0 重置为 `draft`，旧 finding 仍绑定旧 commit：

```bash
rcsl audit rebaseline "$WORKSPACE" --actor "research-owner" \
  --reason "Reviewed the new commit; prior evidence remains on the old baseline."
```

`lint`、`gate check`、`preflight`、`verify` 和 `report build` 只说明它们声明的结构或本地一致性范围，**不表示研究问题正当、finding 成立、修复正确或科学结论获批**。`--actor` / `--reviewer` 是未认证的记录标签；hash chain 只能检出仍被保留的本地历史中的不一致，不能防删除、整体重写或认证身份。任何 scoped 状态都不是 scientific PASS；finding 的 `verified` / `closed` 只是声明式生命周期状态，不是独立验证或科学认证。

Mode Audit 默认只读取目标项目和 Git 元数据；导入时还读取你明确指定的单个文件。它**不执行项目代码、不联网、不修改项目**。需要这些动作时，应在本工具之外另行取得明确授权。命令状态、finding 转换规则与 hash-chain 限制见 [Mode Audit 完整指南](AUDIT_MODE.md)。

`evidence import` 只保存一个显式普通文件。`project-relative` 路径相对项目根目录；它不证明文件已被 Git 跟踪或属于 `HEAD`。若是外部文件，改用 `--source-kind external --source-path /absolute/path/to/file --source-ref runs/log.txt`；`source-ref` 只是逻辑标签，不认证来源。`evidence add --reference` 仍可保存文字引用，但不保存引用处的字节，也不满足新 `verified` / `closed` 的门禁；新终态需要当前 case 上先前导入的 `observed` / `derived` / `reproduced` 内容证据。导入敏感文件前先确认授权、隐私和本地保留风险。命令与类型专属参数见 [Mode Audit 完整指南](AUDIT_MODE.md)。

`status --json`、`verify --json` 与 `finding list --json` 区分 `evidence_profile`、`content_binding_state` 和 finding 的 `case_state`。这些只是本地绑定/过期状态；`current` 不保证 G0 此刻 approved 或 preflight 通过，应结合 G0 status 与 `preflight_issue`。

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

## 路径 E：我是案例发布者

### 已经公开的案例：导出 Open Demo

当前 LLM4SBR 案例、其 Git 历史和相关教学材料已经公开，因此只能按 Open Demo 发布：

```bash
python scripts/rcsl.py export open-demo \
  --output /absolute/path/to/new-open-demo-bundle \
  --actor "maintainer label" \
  --run-public-checks
python scripts/rcsl.py export verify /absolute/path/to/new-open-demo-bundle
```

`--output` 必须位于公开 RCSL 仓库外、目标尚不存在，而且其直接父目录必须已经存在并可访问。`--run-public-checks` 是可选项；使用时，导出记录保存本次公开检查的命令和结果。不使用时，记录必须清楚显示检查未在本次导出中运行。bundle 包含公开边界说明、manifest、checksums、验证记录、撤回模板和一个不依赖本仓库路径的 public verifier。

导出会先建立冻结的公开源树快照，静态检查和所选公开运行检查都针对该快照。manifest 的 `source_tree_sha256` 绑定实际路径、字节、大小和可执行位；`source_revision_scope` 与 `repository_worktree_state` 则明确 Git `HEAD` 只是 revision 上下文，并记录源 worktree 是 `clean` 还是 `dirty`。

`export verify` 可加入 `--json`。校验成功只表示保留文件与 manifest/checksums 自洽，不说明论文结论正确、训练有效或答案得到安全隔离。

### 从未公开的新案例：只组装私有 staging

只有在 learner-facing、Evaluator 和 Maintainer 材料从创建之初就分离，而且整个案例从未公开时，才可以准备 Blind Challenge staging：

```bash
python scripts/rcsl.py package blind \
  --manifest /absolute/path/to/BLIND_SOURCE.json \
  --challenge-source /absolute/path/to/learner-facing-source \
  --evaluator-source /absolute/path/to/evaluator-source \
  --maintainer-source /absolute/path/to/maintainer-source \
  --output /absolute/path/to/new-private-staging \
  --actor "maintainer label"
python scripts/rcsl.py package verify /absolute/path/to/new-private-staging
```

`BLIND_SOURCE.json` 与三个 source 根目录必须放在公开 RCSL 仓库之外，三个 source 根目录必须彼此不同且互不包含。`--output` 也必须位于公开仓库外、目标尚不存在且直接父目录已经存在；它与三个 source 根目录之间不能相互包含。在 POSIX 上，manifest 文件及其直接父目录不能有任何 group/other 权限位（通常分别设为 `0600` 和 `0700`）。输出根目录采用私有的 `0700` 权限，并分成 `challenge/`、`evaluator/`、`maintainer/` 三个包。Challenge Package 就是 learner-facing package；不要再复制出第四个“Learner Package”。工具生成的状态固定为 `assembled-awaiting-controlled-placement`：这表示本地组装完成，**不表示 Blind Challenge 已发布或具备保密性**。

准备 `BLIND_SOURCE.json` 时，每个 `package_files` 条目都要填写布尔值 `executable`。各角色 `root_digest` 会把 `path`、`sha256`、`size` 和该可执行位一起绑定；复制时保留可执行来源的 owner execute。每个角色 manifest 还会给出带 `license_id`、`sensitivity`、`executable` 的 `source_inventory`，并只保留该角色使用且已移除 `approval_ref` 的许可记录。仓库附带的 manifest 模板只能作为编辑起点；未替换 `REPLACE:`、`replace-*`、`your-*`、`{{...}}`、1970 时间或全零 scoring/source digest 时，`package blind` 会拒绝打包。解析器拒绝所有浮点 JSON、重复/未知字段和以布尔值冒充的整数，要求案例与评分版本满足严格 SemVer，并只接受规范 UTC RFC3339 `YYYY-MM-DDTHH:MM:SS[.fraction]Z` 时间。

校验要求精确 root/payload：Open Demo 的根级支持文件必须完全等于固定 allowlist，每个角色的非生成 payload 必须完全等于其 `source_inventory`。仓库侧验证还逐字节核对受信任 verifier 和 schema 对应的 boundary；blind staging 的 `BUILD_RECORD.json` 绑定工具 revision 的有限范围、worktree 状态以及 packager/verifier 字节摘要。正常组装后，可在任一角色根目录运行 `python verify_package.py`；它在受控兄弟包不存在或不可读时仍只检查本包，但会对容量超限、不可读目录、特殊文件、symlink 和受保护路径 fail closed。归档旧 bundle/staging 时同时保留其工具 revision；若新 checkout 的受信任字节已变化，仓库侧校验会拒绝旧包，应使用记录的对应 revision 复核，而不是重写旧 manifest/checksum。

在任何对外发布前，人类运营方仍必须完成：

1. 证明案例及其 Git 历史从未公开，并人工确认 blind eligibility；
2. 复核来源、许可、隐私、伦理和敏感数据分类；
3. 把 Evaluator Package 与 Maintainer Record 放入独立受控存储，执行最小权限与访问记录；
4. 冻结评分规则，完成独立 evaluator、重复性与测量有效性复核；
5. 人工审查 Challenge Package 和相关历史中的泄题风险；
6. 验证受控执行、凭证、网络和提交处理边界；
7. 完成具名发布签署以及泄漏后的失效、撤回、替换和演练。

`package verify` 可加入 `--json`，但它是会读取三类 staging 的维护者侧命令，绝不能交给学习者或放入公开 Challenge 环境。组装与该受信任 staging 校验会使用私有 `BLIND_SOURCE.json` 中的 `scoring.digest` 对 Challenge 来源 payload 做精确值扫描；隔离后的 Challenge standalone 不知道这个值，只能检查公开规则，其 `PASS` 不能证明不存在未知私有摘要。不要把 `scoring.digest` 或从私有评分材料派生的承诺放进 Challenge；公开 scoring reference 只保留 protocol ID/version。工具还会拒绝版本控制元数据和常见 secret 路径/密钥后缀；未知后缀的文件只要能按 UTF-8 解码，也会参与内容泄题扫描。在 POSIX 上，验证还要求整个 staging 不带 group/other 权限位，但这只是当前 mode 检查，不是 ACL。它不执行上述人工运营门，也不能恢复已经公开的信息。完整规则见 [案例发布模型](CASE_RELEASE_MODEL.md)。

因此当前 **Phase 3A 本地发布工具**只达到 `implemented` + `internally verified`；Phase 3B 尚未 `implemented`，整个 Phase 3 尚未 `field validated`。

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
- 想导出 Open Demo 或为新案例准备受控分包：看 [案例发布模型](CASE_RELEASE_MODEL.md)。
