# Mode Audit：真实研究审计闭环

> **状态：`implemented` + `internally verified`，尚未 `field validated`。** Mode Audit 管理一个 clean Git 项目的本地证据生命周期；它不执行项目代码、不联网、不修改目标项目，也不产生科学判决。

[English](AUDIT_MODE_EN.md) · [双模式路线图](DUAL_MODE_ROADMAP.md) · [G0 与能力模型](COMPETENCY_MODEL.md)

## 不可绕过的边界

- 审计绑定的是一个**具体 Git `HEAD` commit**。G0 获批时还保存当时的研究契约字节和 case manifest；这不是“某个目录的大致当前状态”。
- `PROJECT` 必须是 clean Git 工作树；`WORKSPACE` 必须在项目目录之外，`init` 的输出路径必须不存在，而且其直接父目录必须已经存在并可访问。
- 默认只读取目标项目和 Git 元数据。`evidence import` 只读取你明确指定的一个项目内或外部文件；所有新记录只写入 `WORKSPACE`。
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
→ 完成契约 + named approved gate + content-bound case
→ preflight
→ findings / 显式导入文件字节 / reasoned transitions
→ local verify + rendered review report
```

`audit init` 创建以下公开模板，并把 G0 gate 初始设为 `draft`。初始化会固定已解析父目录和新工作区的目录句柄，以相对、no-follow、exclusive-create 写入；结束前复核新目录的 device/inode 身份，因此路径在创建中被替换或重定向时会 fail closed，不会覆盖重定向目标中的同名文件。

| 本地产物 | 用途 |
| --- | --- |
| `research-contract-template.md` | G0：范围、来源/权利、允许 claim、权限、预算与停止条件 |
| `evidence-passport-template.md` | 一条 finding 的位置、契约、证据链、因果影响与限制 |
| `triage-card-template.md` | 信号、影响面、最小决定性证据和下一安全动作 |
| `delegation-contract-template.md` | Agent 可做/不可做的事、验收、预算与人工检查点 |
| 本地 snapshots、event ledger 与报告 | 可更新的当前 metadata/finding snapshots、追加式 lifecycle events 和可读交接结果 |
| content-addressed case/evidence store | G0 当时的研究契约与明确导入的单个文件字节；保留旧 case，支持本地摘要复核 |

## 精确 CLI 参考

以下以 `rcsl` 表示 CLI（例如在仓库根目录执行 `python scripts/rcsl.py`）。

| 命令 | 作用与关键前置条件 | 不代表什么 |
| --- | --- | --- |
| `rcsl train overview`；`rcsl train doctor`；`rcsl train start --level 1..4`；`rcsl train validate` | Mode Train 的课程导航、环境诊断、分级入口和公开检查 | 训练模型或给出科学 verdict |
| `rcsl audit init --project PROJECT --output WORKSPACE --level 1..4 --actor ACTOR [--reason TEXT]` | 要求已存在的直接父目录；拒绝 dirty/non-Git 项目、项目内 workspace 和已有输出；以固定父/工作区目录句柄独占写入并绑定 clean `HEAD`；创建 G0 `draft` | 认证 actor、执行项目、批准 G0 或任何结论 |
| `rcsl audit status WORKSPACE [--json]` | 读取绑定、G0、finding、留存的本地记录和 preflight 摘要；JSON 中区分 `evidence_profile` 与 `content_binding_state` | 判断科学正确性 |
| `rcsl audit lint WORKSPACE` | 仅当**四份模板都完整**（必需标题、无未替换 `{{...}}`）时报告完整 | 批准 G0 或判断 finding 成立 |
| `rcsl audit gate check WORKSPACE [--json]` | 检查 research contract 是否完整、当前 bytes 是否匹配已记录 gate | 授予权限或认证 reviewer |
| `rcsl audit gate record WORKSPACE --decision draft\|approved\|blocked --reviewer REVIEWER --rationale TEXT [--actor ACTOR]` | 记录命名人类的 G0 决定；`approved` 同时保存当前研究契约字节、Git `HEAD` 和 content-bound CaseRef；不写 `--actor` 时使用 reviewer 标签 | 验证身份、理由真实性或科学结论 |
| `rcsl audit preflight WORKSPACE [--json]` | 要求**完整 research contract + 当前 bytes 的 `approved` gate + clean 未漂移 `HEAD` + 自洽的留存本地记录** | 执行代码、联网或证明研究正确 |
| `rcsl audit rebaseline WORKSPACE --actor ACTOR --reason TEXT` | 显式绑定新的 clean `HEAD`；G0 重置为 `draft`，旧 findings 标记为 stale | 把旧证据迁移为新 commit 证据或关闭旧 finding |
| `rcsl audit finding add WORKSPACE --id ID --title TEXT --layer L1\|L2\|L3\|L4\|cross-cutting --competency C1..C7 --severity critical\|high\|medium\|low\|info --claim TEXT --first-contract TEXT --actor ACTOR` | 在已通过 preflight 的当前基线上记录 `open` finding | 证明 claim 为真 |
| `rcsl audit finding list WORKSPACE [--json]` | 显示当前 finding snapshots；JSON 的 `case_state` 区分 current/stale/legacy | 重新评估其科学充分性 |
| `rcsl audit finding transition WORKSPACE --finding ID --to open\|triaged\|accepted\|mitigated\|verified\|closed\|dismissed\|blocked --actor ACTOR --rationale TEXT` | 追加合法、有理由的声明式生命周期转换；新 `verified` / `closed` 还要求当前 case 上已有 `observed` / `derived` / `reproduced` 的内容证据 | 擦除先前记录、独立验证修复或自动认定修复可信 |
| `rcsl audit evidence add WORKSPACE --finding ID --id ID --kind asserted\|observed\|derived\|reproduced\|contradicted --reference TEXT --summary TEXT --actor ACTOR` | 保存文字引用与摘要，供分诊和兼容旧记录；**不**保存引用处的文件字节，不满足新终态的内容证据门禁 | 证明引用内容、证据充分、独立或无偏 |
| `rcsl audit evidence import WORKSPACE --finding ID --id ID --type artifact\|command-result\|environment --kind asserted\|observed\|derived\|reproduced\|contradicted --source-kind project-relative\|external --source-path PATH [--source-ref REF] --summary TEXT --actor ACTOR` | 从明确指定的**一个**普通文件保存字节与摘要，关联当前 CaseRef、ArtifactRef 和 RecordRef；见下方类型专属参数 | 执行命令、认证来源或判断内容科学正确 |
| `rcsl audit verify WORKSPACE [--json]` | 检查留存的本地 metadata、snapshots、event/RecordRef、case 与导入字节的摘要关系是否自洽 | 验证远程历史、身份、原始来源或科学结论 |
| `rcsl audit recover WORKSPACE [--json]` | 显式完成 `.rcsl-audit-pending.json` 记录的一次中断提交并重新验证；没有 pending 时只验证并报告 clean | 回滚历史、选择性丢弃 event 或修复未知篡改 |
| `rcsl audit report build WORKSPACE --output PATH [--format markdown\|json]` | 在 workspace 根目录中以 exclusive-create 创建一个**不存在**的 Markdown/JSON review record（默认 Markdown）；在 POSIX 上输出为 `0600`；固定并复核 workspace 目录身份，不接受 symlink、子目录、外部路径，以及大小写不敏感匹配 `.rcsl-write.lock`、`.rcsl-audit-pending.json`、`audit-workspace.json`、`audit-events.jsonl` 或四份模板的保留文件名 | 创建 scientific PASS、签名或发布批准 |

### G0、lint 与 preflight 的区别

1. `init` 后，G0 一定是 `draft`。
2. `lint` 只有在四份模板全都填写完后才会 `COMPLETE`；它仍只是结构检查。
3. `gate record --decision approved` 只在 `research-contract-template.md` 完整时可记录，并绑定到当前合约 bytes。
4. `preflight` 的前置是**完整 research contract + current approved gate**，另外还要目标项目 clean、`HEAD` 未漂移且留存的本地记录自洽；它不要求把每个 finding 判为正确。
5. `finding add`、`evidence add` 和 `evidence import` 都要求当前 baseline 与 preflight。新进入声明式 `verified`（因此也包括随后 `closed`）必须有当前 case 的 `observed`、`derived` 或 `reproduced` **内容证据**；文字引用、`asserted` 和 `contradicted` 不满足门禁。这不判断证据是否充分、独立或正确。

### 内容证据导入：来源、类型与人类责任

`--source-kind project-relative` 的 `--source-path` 是相对目标项目根目录的单个文件路径（例如 `config/split.yaml`），**不得**加 `--source-ref`。它只读取已锚定项目根内的显式常规文件，**不**检查文件是否由 Git 跟踪、也不证明它的字节属于所记录的 `HEAD`。`--source-kind external` 的 `--source-path` 是一个绝对文件路径，还必须用 `--source-ref` 给它一个 POSIX 相对形式的逻辑标签（例如 `runs/2026-09-16/split-check.txt`）；这个标签不是认证来源，外部机器路径也不充当来源身份。两者都只接受最终选中的非 symlink 普通文件，不递归搜索、执行文件或联网。项目相对路径的父组件必须是非 symlink 目录；外部文件的父路径别名可在选择时 resolve 一次，再由目录描述符锚定，而不是保证整条父路径从未经过 symlink。受保护目录不可读取。导入前请自行确认授权、许可、隐私和是否适合把字节复制进审计工作区。

三种 `--type` 需要各自参数：`artifact` 加 `--artifact-role TEXT`；`environment` 加 `--environment-scope TEXT`；`command-result` 加 `--declared-command TEXT --exit-code INT`。其中 `declared-command` 和 `exit-code` 是你对**已经在工具之外运行**的命令作出的声明，CLI 不执行它，也不证明输出由该命令生成。`--kind` 则说明证据在推理中的角色，不是文件类型。`--summary` 应写明你观察到的事实、未验证的推断和下一步人工复核。

```bash
# 选择真实存在且你获准审阅的项目文件；不要把示例路径照搬成事实。
rcsl audit evidence import "$WORKSPACE" --finding F-001 --id E-001 \
  --type artifact --artifact-role split-config --kind observed \
  --source-kind project-relative --source-path config/split.yaml \
  --summary '记录这份配置字节；切分结果仍需人工重算。' --actor researcher

# 由你在工具之外生成并审查的单个外部结果文件。
rcsl audit evidence import "$WORKSPACE" --finding F-001 --id E-002 \
  --type command-result --kind reproduced --source-kind external \
  --source-path /absolute/path/to/split-check.txt \
  --source-ref runs/split-check.txt --declared-command 'python check_split.py' \
  --exit-code 0 --summary '保留本次结果字节；来源和结论仍需人工复核。' \
  --actor researcher
```

G0 的 `approved` 保存当时的契约字节；之后手改契约或目标 `HEAD` 漂移都会让 preflight 失效。`rebaseline` 使旧 CaseRef 与旧 finding 保持可读但 stale；新 G0 获批后生成新 case，旧内容证据不能自动转为新 case 的证据。未有内容绑定的新 `draft` 或旧工作区都呈现 `evidence_profile=reference-only`；旧记录保持可读，但不能借文字引用进入新 `verified` / `closed`。

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
rcsl audit evidence import "$WORKSPACE" --finding F-001 --id E-001 \
  --type artifact --artifact-role fixture-source --kind observed \
  --source-kind project-relative --source-path README.md \
  --summary '保存临时 fixture 的 README 字节；这只是生命周期测试。' \
  --actor 'E2E Auditor'

rcsl audit finding transition "$WORKSPACE" --finding F-001 --to triaged \
  --actor 'E2E Auditor' --rationale 'Signal has been scoped.'
rcsl audit finding transition "$WORKSPACE" --finding F-001 --to accepted \
  --actor 'E2E Auditor' --rationale 'The bounded finding is accepted for mitigation.'
rcsl audit finding transition "$WORKSPACE" --finding F-001 --to mitigated \
  --actor 'E2E Auditor' --rationale 'Mitigation record is ready for verification.'
rcsl audit preflight "$WORKSPACE"
rcsl audit finding transition "$WORKSPACE" --finding F-001 --to verified \
  --actor 'E2E Research Owner' --rationale 'Current-case content bytes were retained and preflight passed for this fixture.'
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

Rebaseline 会使旧 findings 与旧内容 case 成为 `stale`，并将 G0 重新设为 `draft`。必须重新完成 research contract、记录新的 `approved` gate 并通过 preflight，才能对新 baseline 添加 finding 或 evidence。旧 case manifest 仍留存并接受摘要复核，但不会被自动迁移。

## Finding 与 evidence 的工作规则

1. **先分诊，再断言。** `open` 是待审计的 claim；证据不足时可转为 `blocked`、`dismissed` 或保留待后续审查，不要把猜测写成已证实违反。
2. **按首个失效契约定级。** L1 语义、L2 流水线、L3 科学有效性、L4 Agent 治理；后果可跨层，主分类不应重复计数。
3. **一条 finding，一条因果链。** `claim` 与 `first-contract` 应说明位置、规则、影响和已知限制；`evidence add` 只是文字引用，`evidence import` 才保存明确文件的字节，两者可并存但保证不同。
4. **记录而不是手改历史。** CLI 会刷新当前 metadata/finding snapshots，并把 gate、finding transition、evidence 和 rebaseline 理由追加到 event ledger；更正旧结论时应使用新的生命周期动作，不要直接改 JSON/JSONL。
5. **部分声明式生命周期状态有内容证据门槛。** `open → triaged → accepted → mitigated → verified → closed` 是示例合法路径；新 `verified` / `closed` 需要当前 case 上至少一条先前导入的 `observed` / `derived` / `reproduced` 内容证据、current baseline 和 preflight，不能跳过中间状态。旧历史状态保持可读，但不表示系统完成了独立验证或科学认证。

## 状态词的诚实含义

| 状态词 | 可以说明 | 绝不能说明 |
| --- | --- | --- |
| `contract_structure=complete` | research contract 满足结构和占位符要求 | G0 已批准、finding 为真或结论正确 |
| `g0-prerequisites-met` | research contract 完整，声明式 `approved` 决定匹配当前 bytes | clean Git baseline、全部 preflight 条件或 reviewer 身份真实性 |
| `local-records-consistent` | 留存的本地 events、metadata 与 finding snapshots 的哈希关系自洽 | 历史未被删除/整体替换，或已被可信第三方见证 |
| `evidence_profile=content-bound-v1` | 工作区有留存的 G0 case；契约、旧/新 case 和已导入文件的保留字节通过本地内容绑定检查，是否 current 要另看 binding state | 文件来源真实、命令真的运行或研究结论正确 |
| `evidence_profile=reference-only` | 工作区尚无内容绑定（包括初始化后的 `draft` 或旧记录），仅有文字引用语义 | 引用目标字节已保存或可凭引用进入新终态 |
| `content_binding_state=current/stale/absent`；`case_state=current/stale/legacy` | 留存 CaseRef 是否匹配当前 baseline/`HEAD`/合约字节，以及 finding 是否属于该 case；rebaseline 后旧 case 保留但 stale | `current` 代表 G0 此刻 approved、preflight 通过、证据充分或科学可信；即使 gate 变为 `draft`/`blocked` 而字节没变，binding 也可能仍为 `current`，须结合 G0 status 与 `preflight_issue` 判断 |
| `current` | finding 所绑定 baseline 是 active baseline；preflight 还会另外检查目标工作树 clean 且 `HEAD` 未漂移 | 代码忠实、实验公平或无风险 |
| `preflight-passed` | 当前 G0、Git baseline 与留存本地记录通过本次 preflight | 已存在 finding/evidence、finding 已闭环或结论获批 |
| `preflight-current` | preflight 通过，且报告没有来自旧 baseline 或旧 case 的 stale finding；即使 finding/evidence 数量为零也可能成立 | 已完成实质审计、证据充分或可以发布科学结论 |
| `preflight-not-current` | preflight 未通过，或报告仍含旧 baseline/case 的 stale finding；应结合 `preflight_issue` 与 stale 数量判断 | 每个本地记录都损坏，或某项科学结论为假 |
| `verified` / `closed` | 新转换经过合法路径，并满足当前 case 的先前内容证据、current baseline 与 preflight 门槛；历史标签保持可读 | evidence 真实、充分、独立，或系统/第三方已验证修复与结论 |

这些状态只描述声明、留存记录与流程。**它们以及 `audit lint`、`audit verify` 都不是 scientific PASS。**

CLI 的 `status --json` / `verify --json` 把已保留的绑定称为 `retained_case_ref`；它在 `stale` 时仍会存在，不能当作获批的当前 case。底层兼容字段 `verification.current_case_ref` 和 JSON 报告的 `current_case_ref` 也表示同一份留存绑定，必须结合 `content_binding_state` 判断。

## 哈希链、身份与安全的限制

本地 hash chain 只让**仍被留存的本地历史**中的编辑、重排或断裂更容易被发现。它不能：

- 认证 `--actor`、`--reviewer`、时间戳或批准来源；
- 阻止本机写入者删除记录、整体替换 workspace 或重算新链；
- 证明远程 Git 历史、外部文件的原始来源、声明命令的真实执行，或引用内容未被篡改；
- 提供访问控制、保密性、法律合规或科学有效性。

Content-bound store 可重新核对**已保留**的契约、case manifest 和导入字节；`CaseRef` / `ArtifactRef` / `RecordRef` 绑定本地对象与事件，不能证明作者、来源真实性、科学正确、证据充分或独立复现。即使哈希与保留字节相符，同权限本机写入者仍可能整体替换 namespace 并重建自洽历史。

导入会先在 content-addressed store 保存字节，再提交 finding/event；若后一步失败或中断，store 内可能保留一个合法但尚未被 event 引用的 orphan blob。CLI 不自动垃圾回收它。尤其在导入外部敏感文件前，负责人应先确认复制和本地保留的风险与授权。

一次生命周期动作会先完成 snapshot、event 数量与字节容量的写前验证，再写入并同步短生命周期的 `.rcsl-audit-pending.json`，最后替换 snapshot 和 event ledger。若进程、磁盘或机器在中途故障，所有普通读写都会 fail closed 并提示运行 `rcsl audit recover WORKSPACE`；恢复只做确定性的 roll-forward，且不会重复追加同一 event。未知的第三种文件状态仍会拒绝恢复，必须先保留现场并人工检查。不要通过手改或重算 hash 来“修复”历史。

`.rcsl-write.lock` 是长期保留的固定 advisory-lock 文件，不是需要清理的 stale state；协作进程在本机 POSIX 上使用 shared/exclusive `flock`，进程退出时锁由系统释放。它只协调遵守该协议的本地进程，不覆盖非 POSIX 环境，也不能阻止不协作的同权限写入者。

写前容量检查、恢复意图、单文件原子替换与目录同步，以及工作区初始化/报告导出的固定目录句柄、独占创建、身份复核和 POSIX `0600`，是防止半提交、意外覆盖和常见路径替换竞态的 fail-closed 措施；它们不是通用事务数据库、数字签名、ACL 或恶意本机写入者无法绕过的安全边界。

需要更强保证时，应另行采用受控存储、代码托管审计记录、签名、独立复核和组织政策；这些能力不能被描述成默认 CLI 防护。

## 何时停止并升级

保留已有记录并使用 `blocked`，或停止等待人类决定，如果出现：

- research contract 缺少允许范围、数据权利、预算、保护边界或 claim 限制；
- 项目 dirty、不是 Git 项目，或 workspace 位于项目内；
- 需要项目执行、联网、受保护材料、代码修改或额外预算；
- 存在潜在密钥/隐私暴露、许可不清、受保护评价泄漏或高影响 claim；
- 证据只能支持“未知”，而不能支持更强 finding 状态。

Mode Audit 的好结果有时是暂停、缩小 claim 或请求批准。它从不以“项目能运行”替代研究负责人对可信度和发布的最终决定。
