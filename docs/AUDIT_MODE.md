# Mode Audit：真实研究审计闭环

> **状态：已实现的 canonical CLI。** Mode Audit 管理一个 clean Git 项目的本地证据生命周期；它不执行项目代码、不联网、不修改目标项目，也不产生科学判决。

[English](AUDIT_MODE_EN.md) · [双模式路线图](DUAL_MODE_ROADMAP.md) · [G0 与能力模型](COMPETENCY_MODEL.md)

## 不可绕过的边界

- 审计绑定的是一个**具体 Git `HEAD` commit**，不是“某个目录的大致当前状态”。
- `PROJECT` 必须是 clean Git 工作树；`WORKSPACE` 必须在项目目录之外，且 `init` 的输出路径必须不存在。
- 默认只读取目标项目和 Git 元数据。所有新记录只写入 `WORKSPACE`。
- G0 是人类填写、复核和记录的**声明式研究契约**。`--actor` 和 `--reviewer` 是本地可追溯标签，**不是**身份认证、签名或访问控制。
- 要运行项目、联网、访问额外/受保护材料、修改源码或使用更大预算，须采用另一套明确授权的工具流程；这些操作不由 Mode Audit 隐式执行。

先确认项目状态：

```bash
PROJECT="/absolute/path/to/clean-git-project"
git -C "$PROJECT" status --porcelain   # 必须没有输出
git -C "$PROJECT" rev-parse --verify HEAD
```

## 生命周期与本地产物

```text
clean Git commit + G0 draft
→ 完成契约 + named approved gate
→ preflight
→ findings / evidence / reasoned transitions
→ local verify + rendered review report
```

`audit init` 创建以下公开模板，并把 G0 gate 初始设为 `draft`：

| 本地产物 | 用途 |
| --- | --- |
| `research-contract-template.md` | G0：范围、来源/权利、允许 claim、权限、预算与停止条件 |
| `evidence-passport-template.md` | 一条 finding 的位置、契约、证据链、因果影响与限制 |
| `triage-card-template.md` | 信号、影响面、最小决定性证据和下一安全动作 |
| `delegation-contract-template.md` | Agent 可做/不可做的事、验收、预算与人工检查点 |
| 本地 snapshots、event ledger 与报告 | 可更新的当前 metadata/finding snapshots、追加式 lifecycle events 和可读交接结果 |

## 精确 CLI 参考

以下以 `rcsl` 表示 CLI（例如在仓库根目录执行 `python scripts/rcsl.py`）。

| 命令 | 作用与关键前置条件 | 不代表什么 |
| --- | --- | --- |
| `rcsl train overview`；`rcsl train doctor`；`rcsl train start --level 1..4`；`rcsl train validate` | Mode Train 的课程导航、环境诊断、分级入口和公开检查 | 训练模型或给出科学 verdict |
| `rcsl audit init --project PROJECT --output WORKSPACE --level 1..4 --actor ACTOR [--reason TEXT]` | 拒绝 dirty/non-Git 项目及项目内 workspace；绑定 clean `HEAD`；创建 G0 `draft` | 认证 actor、执行项目、批准 G0 或任何结论 |
| `rcsl audit status WORKSPACE [--json]` | 读取绑定、G0、finding、ledger、preflight 摘要 | 判断科学正确性 |
| `rcsl audit lint WORKSPACE` | 仅当**四份模板都完整**（必需标题、无未替换 `{{...}}`）时报告完整 | 批准 G0 或判断 finding 成立 |
| `rcsl audit gate check WORKSPACE [--json]` | 检查 research contract 是否完整、当前 bytes 是否匹配已记录 gate | 授予权限或认证 reviewer |
| `rcsl audit gate record WORKSPACE --decision draft\|approved\|blocked --reviewer REVIEWER --rationale TEXT [--actor ACTOR]` | 记录命名人类的 G0 决定；不写 `--actor` 时使用 reviewer 标签 | 验证身份、理由真实性或科学结论 |
| `rcsl audit preflight WORKSPACE [--json]` | 要求**完整 research contract + 当前 bytes 的 `approved` gate + clean 未漂移 `HEAD` + 一致 ledger** | 执行代码、联网或证明研究正确 |
| `rcsl audit rebaseline WORKSPACE --actor ACTOR --reason TEXT` | 显式绑定新的 clean `HEAD`；G0 重置为 `draft`，旧 findings 标记为 stale | 把旧证据迁移为新 commit 证据或关闭旧 finding |
| `rcsl audit finding add WORKSPACE --id ID --title TEXT --layer L1\|L2\|L3\|L4\|cross-cutting --competency C1..C7 --severity critical\|high\|medium\|low\|info --claim TEXT --first-contract TEXT --actor ACTOR` | 在已通过 preflight 的当前基线上记录 `open` finding | 证明 claim 为真 |
| `rcsl audit finding list WORKSPACE [--json]` | 显示当前 finding snapshots | 重新评估其科学充分性 |
| `rcsl audit finding transition WORKSPACE --finding ID --to open\|triaged\|accepted\|mitigated\|verified\|closed\|dismissed\|blocked --actor ACTOR --rationale TEXT` | 追加合法、有理由的状态转换 | 擦除先前记录或自动认定修复可信 |
| `rcsl audit evidence add WORKSPACE --finding ID --id ID --kind asserted\|observed\|derived\|reproduced\|contradicted --reference TEXT --summary TEXT --actor ACTOR` | 在已通过 preflight 的当前基线上追加 typed evidence | 证明证据充分、独立或无偏 |
| `rcsl audit verify WORKSPACE [--json]` | 检查本地 metadata、snapshots 和 hash-chain 一致性 | 验证远程历史、身份或科学结论 |
| `rcsl audit report build WORKSPACE --output PATH [--format markdown\|json]` | 在 workspace 根目录中创建一个**不存在**的 Markdown/JSON review record（默认 Markdown）；不接受子目录、外部路径，以及大小写不敏感匹配 `.rcsl-write.lock`、`audit-workspace.json`、`audit-events.jsonl` 或四份模板的保留文件名 | 创建 scientific PASS 或发布批准 |

### G0、lint 与 preflight 的区别

1. `init` 后，G0 一定是 `draft`。
2. `lint` 只有在四份模板全都填写完后才会 `COMPLETE`；它仍只是结构检查。
3. `gate record --decision approved` 只在 `research-contract-template.md` 完整时可记录，并绑定到当前合约 bytes。
4. `preflight` 的前置是**完整 research contract + current approved gate**，另外还要目标项目 clean、`HEAD` 未漂移且 ledger 一致；它不要求把每个 finding 判为正确。
5. `finding add` 和 `evidence add` 都要求 preflight 通过。进入 `verified`（因此也包括随后 `closed`）必须已有 evidence、当前 baseline 和通过的 preflight。

## 最小可复制 E2E 流程

这段命令在临时目录创建一个空的 Git fixture，再完成完整记录闭环。它不会运行被审计项目、不会联网，也不是一份真实科学审计；真实项目必须由人类诚实填写四份模板，不能使用这里的合成填充值。

```bash
# 在 RCSL 仓库根目录运行。临时目录保留给你检查；无需覆盖任何已有路径。
rcsl() { python scripts/rcsl.py "$@"; }
ROOT="$(mktemp -d "${TMPDIR:-/tmp}/rcsl-audit-e2e.XXXXXX")"
PROJECT="$ROOT/project"
WORKSPACE="$ROOT/workspace"

mkdir "$PROJECT"
git -C "$PROJECT" init -q
printf '# RCSL audit E2E fixture\n' > "$PROJECT/README.md"
git -C "$PROJECT" add README.md
git -C "$PROJECT" -c user.name='RCSL E2E' -c user.email='rcsl-e2e@example.invalid' \
  commit -qm 'initial fixture'

rcsl audit init --project "$PROJECT" --output "$WORKSPACE" --level 2 \
  --actor 'E2E Auditor' --reason 'Temporary clean Git lifecycle test.'

# 仅为临时 E2E fixture 填充公开模板；真实审计应由人类填写真实内容。
WORKSPACE="$WORKSPACE" python - <<'PY'
import os
import re
from pathlib import Path

workspace = Path(os.environ["WORKSPACE"])
for path in workspace.glob("*-template.md"):
    text = path.read_text(encoding="utf-8")
    path.write_text(
        re.sub(r"\{\{[^{}\n]+\}\}", "Synthetic bounded fixture value", text),
        encoding="utf-8",
    )
PY

rcsl audit lint "$WORKSPACE"
rcsl audit gate record "$WORKSPACE" --decision approved \
  --reviewer 'E2E Research Owner' --actor 'E2E Auditor' \
  --rationale 'Completed temporary contract reviewed for the bounded fixture.'
rcsl audit gate check "$WORKSPACE" --json
rcsl audit preflight "$WORKSPACE" --json

rcsl audit finding add "$WORKSPACE" --id F-001 \
  --title 'Checkpoint lineage requires review' --layer L2 --competency C2 \
  --severity medium \
  --claim 'The reported model may not match the declared checkpoint lineage.' \
  --first-contract 'Each reported run must identify the evaluated checkpoint.' \
  --actor 'E2E Auditor'
rcsl audit evidence add "$WORKSPACE" --finding F-001 --id E-001 --kind observed \
  --reference 'README.md@HEAD' \
  --summary 'The temporary fixture records an observation for lifecycle testing.' \
  --actor 'E2E Auditor'

rcsl audit finding transition "$WORKSPACE" --finding F-001 --to triaged \
  --actor 'E2E Auditor' --rationale 'Signal has been scoped.'
rcsl audit finding transition "$WORKSPACE" --finding F-001 --to accepted \
  --actor 'E2E Auditor' --rationale 'The bounded finding is accepted for mitigation.'
rcsl audit finding transition "$WORKSPACE" --finding F-001 --to mitigated \
  --actor 'E2E Auditor' --rationale 'Mitigation record is ready for verification.'
rcsl audit preflight "$WORKSPACE"
rcsl audit finding transition "$WORKSPACE" --finding F-001 --to verified \
  --actor 'E2E Research Owner' --rationale 'Evidence exists and the current baseline passes preflight.'
rcsl audit finding transition "$WORKSPACE" --finding F-001 --to closed \
  --actor 'E2E Research Owner' --rationale 'Verified temporary finding formally closed.'

rcsl audit verify "$WORKSPACE" --json
rcsl audit finding list "$WORKSPACE" --json
rcsl audit report build "$WORKSPACE" --output "$WORKSPACE/review.md" --format markdown
rcsl audit status "$WORKSPACE" --json
echo "Inspect the temporary workspace: $WORKSPACE"
```

如需在真实项目的新 commit 上继续审计，先人工审阅变更，然后：

```bash
rcsl audit rebaseline "$WORKSPACE" --actor 'Research Owner' \
  --reason 'Reviewed a deliberate upstream commit change; prior evidence stays attached to its old baseline.'
```

Rebaseline 会使旧 findings 成为 `stale`，并将 G0 重新设为 `draft`。必须重新完成 research contract、记录新的 `approved` gate 并通过 preflight，才能对新 baseline 添加 finding 或 evidence。

## Finding 与 evidence 的工作规则

1. **先分诊，再断言。** `open` 是待审计的 claim；证据不足时可转为 `blocked`、`dismissed` 或保留待后续审查，不要把猜测写成已证实违反。
2. **按首个失效契约定级。** L1 语义、L2 流水线、L3 科学有效性、L4 Agent 治理；后果可跨层，主分类不应重复计数。
3. **一条 finding，一条因果链。** `claim` 与 `first-contract` 应说明位置、规则、影响和已知限制；evidence 只连接具体的 asserted/observed/derived/reproduced/contradicted 记录。
4. **记录而不是手改历史。** CLI 会刷新当前 metadata/finding snapshots，并把 gate、finding transition、evidence 和 rebaseline 理由追加到 event ledger；更正旧结论时应使用新的生命周期动作，不要直接改 JSON/JSONL。
5. **terminal states 有额外门槛。** `open → triaged → accepted → mitigated → verified → closed` 是示例合法路径；`verified`/`closed` 需要 evidence、current baseline 和 preflight，不能跳过中间状态。

## 状态词的诚实含义

| 状态词 | 可以说明 | 绝不能说明 |
| --- | --- | --- |
| `structure` | 四份模板的格式和占位符状态满足 lint 要求 | finding 为真或结论正确 |
| `ledger` | 留存的本地 events、metadata 与 finding snapshots 的哈希关系自洽 | 历史未被删除/整体替换，或已被可信第三方见证 |
| `current` | 目标工作树 clean，且 `HEAD` 与 active baseline 一致 | 代码忠实、实验公平或无风险 |
| `review-ready` | 当前 G0、Git baseline 与 ledger 通过 preflight，且报告中没有旧 baseline 的 stale finding；可以开始人工阅读 | `lint` 已完成、存在 finding/evidence、finding 已闭环、证据充分，或审稿人、PI、独立复现实质批准了结论 |

`structure`、`ledger`、`current` 和 `review-ready` 都只描述记录/流程。**它们以及 `audit lint`、`audit verify` 都不是 scientific PASS。**

## 哈希链、身份与安全的限制

本地 hash chain 只让**仍被留存的本地历史**中的编辑、重排或断裂更容易被发现。它不能：

- 认证 `--actor`、`--reviewer`、时间戳或批准来源；
- 阻止本机写入者删除记录、整体替换 workspace 或重算新链；
- 证明远程 Git 历史、外部文件、命令输出或引用内容未被篡改；
- 提供访问控制、保密性、法律合规或科学有效性。

一次生命周期动作会更新 snapshot 并追加 event；它们不是跨文件数据库事务。如果进程、磁盘或机器在多文件写入中途故障，下一次 `verify` 会 fail closed，工作区也可能保留 `.rcsl-write.lock`。此时应先保留/备份现场并人工检查，不要通过手改或重算 hash 来“修复”历史。

需要更强保证时，应另行采用受控存储、代码托管审计记录、签名、独立复核和组织政策；这些能力不能被描述成默认 CLI 防护。

## 何时停止并升级

保留已有记录并使用 `blocked`，或停止等待人类决定，如果出现：

- research contract 缺少允许范围、数据权利、预算、保护边界或 claim 限制；
- 项目 dirty、不是 Git 项目，或 workspace 位于项目内；
- 需要项目执行、联网、受保护材料、代码修改或额外预算；
- 存在潜在密钥/隐私暴露、许可不清、受保护评价泄漏或高影响 claim；
- 证据只能支持“未知”，而不能支持更强 finding 状态。

Mode Audit 的好结果有时是暂停、缩小 claim 或请求批准。它从不以“项目能运行”替代研究负责人对可信度和发布的最终决定。
