# RCSL Mode Train：本地学习进度与人工复核

[English](TRAIN_MODE_EN.md) · [课程主页](../LLM4SBR_research_audit_training_v2/README.md) · [能力模型](COMPETENCY_MODEL.md) · [Mode Audit](AUDIT_MODE.md)

Mode Train 用公开的 LLM4SBR Open Demo 练习研究代码审计，并把 L1–L4 Evidence Passport、跨层 Capstone、重做与人工反馈保存在一个学习者自有的本地工作区。核心流程只依赖 Python 标准库，创建后可以离线暂停和恢复。

本版把学习者实际可见的案例冻结为一份显式清单：当前初始化会列入 122 个公开 Open Demo 输入及其准确字节、大小和 SHA-256 摘要；不会遍历或读取教师/完成后材料。后续校验依据工作区已保存的清单及材料，而非运行时新的源文件列表，所以旧 attempt 不会因仓库加入新练习文件而被改写。提交、rubric 和人工复核都引用该案例内容摘要。仓库 `HEAD` 只记录有限的来源背景，不能代替案例身份。只有自动合成测试，尚未完成真实学习者与独立审阅者试点，因此最多是 `internally verified`。

> **重要边界：**worksheet 自动检查只判断 Markdown 结构是否完整；案例与审阅包校验只核对保留的字节和引用。它们不读取教师材料，不判断答案含义、科学正确性或成熟度，也不认证学习者或审阅者身份。当前公开案例依靠 honor isolation，不是安全隔离的 Blind Challenge。

## 1. 创建外部学习工作区

从仓库根目录运行：

```bash
python scripts/rcsl.py train progress init \
  --output /absolute/path/to/my-rcsl-progress \
  --learner "your declared label"
```

`--output` 必须是仓库外一个尚不存在的目录，也不能位于任何 `DO_NOT_OPEN_UNTIL_FINISHED` 路径中。命令拒绝覆盖已有文件或跟随工作区符号链接。

新工作区包含：

```text
my-rcsl-progress/
├── README.md
├── RUBRIC.md
├── CAPSTONE_BRIEF.md
├── progress.json
├── case/
│   ├── LLM4SBR_research_audit_training_v2/...
│   └── skills/research-code-audit-training/assets/...
└── worksheets/
    ├── L1.md
    ├── L2.md
    ├── L3.md
    ├── L4.md
    └── capstone.md
```

- `worksheets/*.md` 是你编辑的草稿。
- `case/` 是初始化时冻结的公开案例副本。优先阅读这份副本，以便审阅者复核你实际使用的版本；它不是答题目录，不要修改。修改任何已绑定的案例字节会被校验拒绝。仓库以后有新提交也不会暗中改写这个工作区。
- `RUBRIC.md` 和 `CAPSTONE_BRIEF.md` 是固定参考文件；改变它们会使工作区校验失败。
- `progress.json` 是权威进度记录，包含冻结的提交快照、人工复核历史和本地操作去重记录。不要手工编辑它。

旧版 `schema_version: 1` 工作区没有保留完整公开案例，无法事后证明当时看到的准确字节；本版不会偷偷把当前仓库内容当作旧案例迁移。保留旧记录作历史参考，需要新的内容绑定时另建 v2 工作区并重新提交。

## 2. 完成并检查一份 Evidence Passport

推荐按 L1、L2、L3、L4、Capstone 的顺序学习；CLI 不用自动解锁规则替代人的学习安排。先阅读对应公开 brief 与 frozen contract，再编辑工作区中的对应 worksheet。例如完成 L1 后运行：

**唯一可提交的答题入口是工作区的 `worksheets/L1.md` 等文件。**课程目录内原有的 `ANSWER_SHEET.md` 只是公开学习模板/参考，不会被 `train progress submit` 读取；不要在两个位置分别维护答案。

```bash
python scripts/rcsl.py train progress check \
  /absolute/path/to/my-rcsl-progress --target L1
```

目标可取 `L1`、`L2`、`L3`、`L4` 或 `capstone`。`check` 会报告缺失小节、空小节和未替换的模板提示：结构完整时退出码为 `0`，不完整时为 `1`。即使显示 `COMPLETE`，语义、科学正确性和成熟度仍是 `NOT PERFORMED` / `NOT ASSESSED`。

若需要机器可读结果：

```bash
python scripts/rcsl.py train progress check \
  /absolute/path/to/my-rcsl-progress --target L1 --json
```

## 3. 冻结提交与重做

结构完整后，把 worksheet 的准确字节冻结为一次不可变尝试：

```bash
python scripts/rcsl.py train progress submit \
  /absolute/path/to/my-rcsl-progress \
  --target L1 \
  --note "first evidence-chain attempt"
```

提交会得到类似 `L1-A001` 的 attempt ID 和 SHA-256 摘要，但状态只是 `AWAITING HUMAN REVIEW`。之后继续编辑 worksheet 不会改写旧快照；再次提交会创建 `L1-A002`，并通过 `retry_of` 指向上一次尝试。新尝试只继承历史，不继承上一尝试的有效人工结论。

脚本或不确定重试时，可显式加入稳定的 `--operation-id`：

```bash
python scripts/rcsl.py train progress submit \
  /absolute/path/to/my-rcsl-progress \
  --target L1 \
  --note "first evidence-chain attempt" \
  --operation-id submit-l1-v1
```

同一个 operation ID 与完全相同的操作内容会返回原结果；把同一 ID 用于不同内容会被拒绝。

## 4. 记录具名人工复核

提交后，先在工作区内生成一份针对指定 attempt 的原始审阅包，再校验它：

```bash
python scripts/rcsl.py train progress packet build \
  /absolute/path/to/my-rcsl-progress \
  --target L1 --attempt latest \
  --output /absolute/path/to/my-rcsl-progress/L1-A001-review-packet.json
python scripts/rcsl.py train progress packet verify \
  /absolute/path/to/my-rcsl-progress/L1-A001-review-packet.json
```

审阅包是单文件自足材料：校验不需要原始案例仓库或学习者工作区，但运行 `verify` 仍需一份可信的 RCSL 工具/checkout。它输出 attempt ID、案例内容摘要与 packet SHA-256。包里有 `attempt.worksheet_snapshot`（准确冻结答案）及 122 份案例材料的 base64 原始字节；base64 是编码，不是脱敏或保密。审阅者应查看包里的准确答案、案例与 `RUBRIC.md`，必要时解码案例材料，并自行判断证据、风险、成熟度和决定。向另一人发送这个**未脱敏**包可能暴露学习者答案或个人信息，必须由工作区负责人自行决定接收者与分享范围；程序不会自动发送。独立复核的内容一致性不等于独立的科学评判，也不证明包的作者身份。

包里的 `resource_aliases.RUBRIC.md` 指向 `skills/research-code-audit-training/assets/maturity-rubric.md`，该 artifact 解码后的字节与工作区顶层 `RUBRIC.md` 相同；只有审阅包时就读这一项。`CAPSTONE_BRIEF.md` 也有对应别名。

packet SHA-256 按包的 JSON 内容稳定计算，**不是**排版后的 `.json` 文件原始字节摘要；不要用 `sha256sum` 的文件结果替代命令输出。

`packet verify` 核对包内材料、案例清单与答卷引用的一致性；它不认证材料真正来自原仓库，也不重新证明公开输入清单对教学任务足够完整。审阅者应保留可信来源的清单/工具版本并自己判断范围。

审阅者记录声明性的人工判断时，填入刚才 `verify` 显示的准确 packet SHA-256；下面的占位值须替换：

```bash
python scripts/rcsl.py train progress review \
  /absolute/path/to/my-rcsl-progress \
  --target L1 \
  --attempt latest \
  --reviewer "reviewer label" \
  --decision revise \
  --recognize demonstrated \
  --prove partial \
  --direct cannot-assess \
  --steward cannot-assess \
  --rationale "The first break is identified, but causal proof is incomplete." \
  --strengths "Precise location and a plausible competing hypothesis." \
  --gaps "Add an independent recomputation and bound the claim impact." \
  --packet-sha256 PACKET_SHA256_FROM_VERIFY
```

以后编辑可写的 worksheet 草稿不会改变既有 attempt 的历史审阅包；只有再次提交形成新 attempt 才会有新的包摘要。已冻结案例材料若被改动则直接拒绝校验，而不是悄悄换包。填错或引用另一 attempt 的摘要会被拒绝。摘要仅表明所声明的 review 指向这个冻结包，不能证明审阅者真的读过它。每档观察值只能是 `not-observed`、`partial`、`demonstrated` 或 `cannot-assess`；决定只能是 `pass`、`revise` 或 `blocked`。CLI 只检查记录内部一致性：

- L1–L4 的 `pass` 必须把 Recognize 与 Prove 声明为 `demonstrated`。
- Capstone 的 `pass` 必须把 Recognize、Prove、Direct、Steward 全部声明为 `demonstrated`。
- 这两条规则不证明判断真实或充分；Capstone 仍必须由人类实际复核后才能通过。

同一尝试可保留多位审阅者的记录。系统不平均分歧：不同的当前决定显示为 `review-disagreement`，供人类依据证据解释或裁决。同一审阅者后来新增的记录成为其当前记录，旧记录仍留在历史中。

## 5. 查看、暂停与恢复

```bash
python scripts/rcsl.py train progress status \
  /absolute/path/to/my-rcsl-progress
```

`status` 对每个目标分别显示：

| 维度 | 含义 |
| --- | --- |
| `attempt` | 是否已有冻结提交 |
| `structure` | 当前可编辑 worksheet 的结构是否完整 |
| `human-review` | 最新尝试是待复核、需重做、被阻塞、人工通过或存在分歧 |
| `draft_changes_since_submission` | 当前草稿是否与最新冻结尝试不同（JSON 输出） |
| `evidence_gaps` | 当前人工复核明确记录的证据缺口 |

工作区可在任何时点关闭；再次运行 `status`、`check`、`submit` 或 `review` 就能继续。有效但未完成的工作区中，`status` 仍返回成功，因为“学习未完成”不是文件错误。加入 `--json` 可读取稳定的机器可读摘要。

只有五个目标各自的最新尝试都达到 `human-passed`，并且没有已通过后尚未提交的草稿修改，总体状态才是 `human-reviewed-complete`。若存在这类修改，状态会显式变为 `human-reviewed-complete-with-unsubmitted-draft`，人工结论仍只绑定旧 attempt 摘要。这些状态都不是科学认证。

## 6. 完成跨层 Capstone

完成 L1–L4 后，阅读工作区中的 `CAPSTONE_BRIEF.md`，在 `worksheets/capstone.md` 中处理一个公开的合成研究事故。现有六份冻结公开工件可在工作区 `case/LLM4SBR_research_audit_training_v2/capstone_artifacts/` 查看：`change.diff`、`run_config.json`、`run_ledger.csv`、`agent_events.csv`、`approvals.csv`、`claim_note.md`。在答案中引用准确路径与行、JSON key 或 row/event ID，而非凭叙述猜测结论。它们只提供可审查线索，不是完整源码、原始指标或认证审批；欠缺的材料应明确要求，不可编造。回答必须覆盖 G0 停止/继续决定、影响面、L1–L4 首个失效契约、证据保全与竞争假设、Human–Agent 委派、claim/发布边界、修复验证、利益相关方更新和人工签署。

Capstone 的检查与提交命令和其他目标相同：

```bash
python scripts/rcsl.py train progress check \
  /absolute/path/to/my-rcsl-progress --target capstone
python scripts/rcsl.py train progress submit \
  /absolute/path/to/my-rcsl-progress --target capstone
```

结构完整不会自动通过。必须另行记录具名人工 `pass`，而且四档成熟度都由该审阅者明确声明为 `demonstrated`。

## 7. 导出可分享摘要

导出文件必须位于工作区内，父目录必须已经存在，且不能覆盖已有或保留文件：

```bash
python scripts/rcsl.py train progress export \
  /absolute/path/to/my-rcsl-progress \
  --output /absolute/path/to/my-rcsl-progress/progress-report.md \
  --format markdown
```

`--format` 可取 `markdown` 或 `json`。导出会省略学习者标签、worksheet 快照和可能带身份信息的自由文本 feedback/gap，只保留是否记录过 gap；审阅者标签会转换为 `reviewer-1` 等别名。它保留案例内容摘要、结构状态、最新提交摘要、当前人工决定和成熟度观察。完整反馈只留在本地 `progress.json` 与 `status --json` 中。与未脱敏的 reviewer packet 不同，导出是可读摘要，不是认证书、签名或科学 `PASS`。

### 不要混淆两种 export

`train progress export` 只导出一位学习者的脱敏进度摘要。案例维护者使用的 `python scripts/rcsl.py export open-demo ...` 会生成另一个目录级公开发布包，两者不是同一格式。后者会冻结本次公开源树、在该快照上运行所选检查，并用 `source_tree_sha256` 绑定实际导出内容；它还要求精确 root/payload，仓库侧验证会核对受信任 verifier 与 boundary。这些行为与学习进度记录无关。前者不能发布案例，后者也不是个人成绩单；二者都不能生成或认证 Blind Challenge。当前 LLM4SBR 已经公开，只能保持 Open Demo。完整发布边界见 [案例发布模型](CASE_RELEASE_MODEL.md)。

## 记录与信任边界

- `progress.json` 在一次写入中原子替换，并用本地互斥锁避免两个写入者同时更新；意外遗留锁时，应先确认没有活跃写入者，再按错误提示处理。
- 加载工作区时会严格检查 schema、固定资源摘要、冻结快照摘要、attempt/review 引用和声明一致性；发现异常会拒绝继续。
- 案例 manifest 是明确的公开文件列表和本地内容绑定；审阅包校验只核对包内保留的字节、答案与引用，不验证案例设计、授权身份或科学结论。
- 这些是本地一致性措施，不是外部不可篡改存储。能写入工作区的人仍可能重写完整历史。
- `--learner` 和 `--reviewer` 都只是声明标签，不是登录身份、数字签名或权限证明。
- `train validate` 检查仓库中的公开训练包；`train progress check` 检查你工作区的一份 worksheet。二者都不判断科学正确性。
