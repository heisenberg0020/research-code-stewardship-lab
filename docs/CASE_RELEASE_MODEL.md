# RCSL 案例发布模型

本模型规定如何把“论文 + 源码 + 实验协议”发布为可复用的研究代码审计案例。目标是让案例的范围、证据与边界可追溯，而不是用一次 `PASS` 冒充科学正确性或安全盲测。

[English](CASE_RELEASE_MODEL_EN.md) · [能力模型](COMPETENCY_MODEL.md) · [四级训练包](../LLM4SBR_research_audit_training_v2/README.md) · [路线图](DUAL_MODE_ROADMAP.md)

## 1. 发布单位：一个版本化 Case File

每个案例应拥有稳定的 `case-id` 和语义版本，例如 `llm4sbr-audit/v1.0.0`。版本记录必须回答“它审计的到底是哪一套材料与协议”。

| Case File 字段 | 必须记录的内容 |
| --- | --- |
| 范围与来源 | 论文版本、上游源码 revision、数据/第三方许可、允许与排除的材料 |
| G0 研究契约 | 允许 claim、保护边界、指标/预算、权限与停止条件 |
| 纵轴覆盖 | L1–L4 中每个案例训练的首个失效契约和适用证据 |
| 公开表面 | 学习者可读文档、候选、公开检查、答案表和已知限制 |
| 验证记录 | 公开检查版本、独立复核、已知盲区和不作出的声明 |
| 维护状态 | 当前、已替代、上游变化后待复审、撤回或已归档 |

上游论文、源码、数据协议或 G0 发生实质变化时，旧 Case File 应标记为**待复审**，不能静默沿用“已验证”的描述。

## 2. 发布前的最小关卡

```text
G0 研究契约冻结
→ 论文—代码—实验映射
→ L1–L4 设计规格与公开/受控表面划分
→ 公开检查、泄题审查和独立复核
→ 发布 Case File、版本与已知边界
→ 变更监控、复审、替代或撤回
```

| 关卡 | 人类必须批准的决定 | 不足时的动作 |
| --- | --- | --- |
| G0 | 范围、风险、保护材料、claim 和授权边界 | 暂停，不以默认值补齐 |
| 设计 | 首个失效契约、错误家族、证据标准与学习目标 | 修正规格，不生成/发布候选 |
| 验证 | 公开检查覆盖什么、不能覆盖什么；是否存在泄题或误导 | 修复案例或降低声明 |
| 发布 | 许可、来源、版本、维护责任人与已知限制 | 不发布或明确标为实验性 |
| 维护 | 上游变化、报告的问题、复审和撤回 | 标记 stale、发布补丁或撤回 |

## 3. 两种发布模式

### Open Demo：当前公开案例的诚实定位

当前公开训练材料属于 **Open Demo / honor isolation**：

- 学习者在完成公开 brief、公开检查和证据记录前，承诺不主动查找教师材料；
- 公开检查只验证公开包的结构、格式或受限运行契约；
- 公开 Git 仓库内的约定性隔离不构成访问控制、保密保护或对抗性防泄漏；
- 不应把结果称为盲测成绩、保密考试成绩、真实攻击面安全性或独立科学复现。

Open Demo 适合教学、示例、公开讨论和工具回归。它的价值是透明的工作流与可复现的证据格式，而不是答案保密。

当前发布工具只允许导出已经公开的 LLM4SBR Open Demo：

```bash
python scripts/rcsl.py export open-demo \
  --output /absolute/path/to/new-open-demo-bundle \
  --actor "maintainer label" \
  --run-public-checks
python scripts/rcsl.py export verify /absolute/path/to/new-open-demo-bundle
```

`--output` 必须位于公开 RCSL 仓库外、目标尚不存在，而且其直接父目录必须已经存在并可访问。`--run-public-checks` 可省略；验证记录必须忠实区分“本次实际运行”和“本次未运行”。导出包含边界说明、manifest、checksums、公开验证记录、撤回模板与独立 public verifier。`export verify` 也支持 `--json`。

导出器会先冻结本次允许公开的源树，再在这个冻结快照上执行内置静态检查，以及在指定 `--run-public-checks` 时执行公开运行检查。`PACKAGE_MANIFEST.json` 用 `source_tree_sha256` 绑定实际快照中的路径、字节、大小和可执行位，并同时记录 `source_revision_scope: repository-head-not-byte-identity` 与 `repository_worktree_state`（`clean` 或 `dirty`）。因此 Git `HEAD` 只是来源上下文，不被误写成这批字节的身份；实际导出内容由源树摘要绑定，`VALIDATION_RECORD.json` 也记录其 `validated_source_tree_sha256`。

`--actor` 只是构建记录中的声明标签，不是登录身份、签名或发布权限证明。

核心输出结构为：

```text
new-open-demo-bundle/
├── RELEASE_BOUNDARY.md
├── PACKAGE_MANIFEST.json
├── CHECKSUMS.sha256
├── VALIDATION_RECORD.json
├── REVOCATION_NOTICE_TEMPLATE.md
├── verify_package.py
└── LLM4SBR_research_audit_training_v2/  # 显式排除教师侧目录的公开树
```

接收者可以在 bundle 内运行 `python verify_package.py`，无需依赖原仓库路径。它会对 `CHECKSUMS.sha256`、manifest、精确根目录文件集、Open Demo 来源树摘要、验证记录和公开边界字段做自包含复核。维护者从受信任的 RCSL checkout 运行 `export verify` 时还会把 `verify_package.py` 与 `RELEASE_BOUNDARY.md` 逐字节比对当前 schema 的受信任生成内容，并拒绝重新计算 checksum 后替换验证器或边界的 bundle。bundle 内自验不能自行建立这条外部信任根，也不是签名。仓库侧的受信任字节检查与工具版本相绑定：归档旧 bundle 时应同时保留对应 RCSL revision；更新后的工具若生成了不同 verifier/boundary，会 fail closed，而不会静默把旧实现当成当前受信任版本。

该导出保存的是版本化公开证据。checksums 能发现生成后保留字节的变化，但不是数字签名或外部不可篡改证明；独立 verifier 只复核 bundle 自身声明的公开契约。导出、公开检查或校验成功都不证明论文结论、教学有效性、答案保密或安全性。

### Blind Challenge：未来真正盲测的分包

需要评估学习者、Agent 或流程的泛化能力时，必须从第一天采用分包，而不是先公开再“隐藏”。

| 包 | 可访问者 | 内容 | 必须不包含 |
| --- | --- | --- | --- |
| **Challenge Package（公开）** | 参赛者/学习者 | brief、允许材料、候选、公开 smoke check、提交格式和规则 | 答案映射、变异账本、隐藏 probe、私有数据或评价标签 |
| **Evaluator Package（受控）** | 授权评测者 | 答案映射、私有验证、评分器、评价标签与抗泄漏检查 | 公开仓库、参赛者环境、普通下载分发 |
| **Maintainer Record（受控）** | 案例负责人 | 来源/许可、G0、设计决策、变异理由、风险、事故与撤回记录 | 不必要的参赛者身份或敏感原始数据 |

最低控制措施：独立私有仓库或受控制品库、最小权限、评测版本与 checksum、访问/发布记录、无答案的公开 Git 历史，以及发现泄露后的失效与替换流程。访问控制仍不等于测量有效性；Blind Challenge 还需要冻结评分规则、重复性和独立评审。

本地分包接口是：

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

`BLIND_SOURCE.json` 与三个 source 根目录都必须位于公开 RCSL 仓库之外；三个 source 根目录还必须彼此不同且互不包含。输出目录也必须位于公开仓库外、目标尚不存在且直接父目录已经存在；它与任一 source 根目录都不能相互包含。在 POSIX 系统上，source manifest 文件及其直接父目录都不能授予任何 group/other 权限位（通常分别使用 `0600` 与 `0700`）；这只是本地 mode 前置检查，不是 ACL 或完整祖先目录审计。`BLIND_SOURCE.json` 是人工负责的显式 allowlist 与来源声明；其中的 never-public、许可、设计、泄题与 release-preparation 批准是可审计声明，不是互联网范围的自动证明或身份认证。

manifest 中每个 `package_files` 条目都必须显式给出布尔值 `executable`，并与来源文件的状态一致。每个角色的 `root_digest` 以规范化的 `path`、`sha256`、`size` 和 `executable` 共同计算；任一字节、大小或可执行声明不符都会拒绝组装。复制时，可执行来源保留 owner execute，非可执行来源不被擅自升级为可执行。

可从 [`blind-source-manifest-template.json`](../skills/research-code-audit-training/assets/blind-source-manifest-template.json) 建立 source manifest，并把 [`access-log-template.md`](../skills/research-code-audit-training/assets/access-log-template.md) 与 [`revocation-notice-template.md`](../skills/research-code-audit-training/assets/revocation-notice-template.md) 纳入受控运营记录。**这个 shipped manifest 只是编辑起点，不能直接打包**：所有 `REPLACE:`、`replace-*`、`your-*`、`{{...}}` 占位符、1970 年时间和全零 scoring/source digest 都必须用真实、可复核的值替换，否则 `package blind` 会 fail closed。输入采用严格 JSON：拒绝重复/未知键、非有限数以及所有浮点数；schema version、大小等计数字段必须是真正的 JSON 整数而不能用布尔值冒充，案例与评分版本必须满足严格 SemVer。时间必须采用规范 UTC RFC3339 `YYYY-MM-DDTHH:MM:SS[.fraction]Z`，不接受空格、缺秒、`t` 或 `+00:00` 替代 `Z`。模板记录声明和证据引用，本身不执行权限或撤回。

`Challenge Package` 就是 learner-facing package。输出根目录采用 `0700` 私有权限，并保存 `challenge/`、`evaluator/`、`maintainer/` 三个独立包及其 manifest/checksum 记录。输出状态固定为 `assembled-awaiting-controlled-placement`。`package verify` 支持 `--json`，只检查当前本地 staging 的完整性与分包边界。在 POSIX 系统上，它还拒绝 staging 中任何带 group/other 权限位的目录或文件；这只是当前文件 mode 检查，**不是 ACL、远程存储策略或跨主机访问控制验证**。它是会读取三包的维护者侧命令，不能交给学习者或放入公开 Challenge 环境。

```text
new-private-staging/
├── CONTROL_MANIFEST.json
├── BUILD_RECORD.json
├── challenge/   # learner-facing candidate；含自己的 verifier 与有限 leakage 记录
├── evaluator/   # controlled candidate
└── maintainer/  # controlled record；保留 source manifest、access/revocation 模板
```

每个角色包都有自己的 `RELEASE_BOUNDARY.md`、`PACKAGE_MANIFEST.json`、`CHECKSUMS.sha256` 和 `verify_package.py`。角色 manifest 的 `source_inventory` 保留该角色每个来源文件的 `license_id`、`sensitivity` 和 `executable` 等绑定信息；其中的 `licenses` 只保留该角色实际使用的许可，并移除维护者侧 `approval_ref`。学习者最多接收 `challenge/`，并只在该目录内运行自己的 verifier；不能接收 staging 根目录、`CONTROL_MANIFEST.json`、`BUILD_RECORD.json`、Evaluator Package 或 Maintainer Record。

验证采用精确集合而不是“已列文件的子集”：Open Demo 的根级非来源文件必须等于固定 allowlist；每个角色包中，除固定生成文件外的全部 payload 必须精确等于 `source_inventory`，路径、摘要、大小和可执行位都要一致。仓库侧 `export verify` / `package verify` 还要求每个角色的 verifier 和角色专属 boundary 与受信任生成内容逐字节相同；仅修改文件、manifest 和 checksum 仍不能把额外 payload、替换过的 verifier 或弱化过的 boundary 洗白。

根目录的 `CONTROL_MANIFEST.json` 通过摘要绑定 `BUILD_RECORD.json`。后者记录 `tool_revision`、固定的 `tool_revision_scope: repository-head-not-byte-identity`、`tool_worktree_state`、当前受信任 packager 字节摘要、standalone verifier 字节摘要，以及未联网、未执行包内代码和尚待受控放置的状态。维护者侧 `package verify` 会复核这些字段和两个实现摘要；Git `HEAD` 仍只是工具来源上下文，实际实现身份由摘要补充绑定。归档 staging 应连同 `BUILD_RECORD.json` 指向的工具 revision 一起保留；若当前 checkout 的 packager/verifier 已改变，维护者侧校验会拒绝旧包，应切换到对应工具 revision 复核，而不是修改旧包的 manifest/checksum。正常组装出的三个角色包可各自在自身根目录运行 `python verify_package.py`，这条自验不依赖兄弟包。

Challenge 泄题扫描不仅检查已知文本后缀：任何能够按 UTF-8 解码的文件，即使后缀未知，也会参与内容与导入模式扫描；不能按 UTF-8 解码的文件仍接受路径检查。版本控制元数据与常见 secret 路径/密钥后缀会被拒绝。组装阶段与受信任 checkout 中的 staging 校验可以读取私有 `BLIND_SOURCE.json`，因此还会使用其中的 `scoring.digest` 对 Challenge 来源 payload 做精确值扫描；隔离后的 Challenge standalone 有意不知道这个私有值，只能复核公开规则，其 `PASS` 不证明不存在未知私有摘要。不得把 `scoring.digest` 或从私有评分材料派生的承诺放入 Challenge；Challenge 只保留 scoring protocol ID/version。该扫描仍是有界的自动防线，不能发现所有语义泄题、编码内容、外部历史或旁路信号，仍必须经过人工泄题审查。

每个 standalone verifier 都实行 fail-closed 的容量与文件系统边界：限制 JSON、单文件、文件数和总字节数；拒绝 symlink、special file、路径碰撞以及任何 `DO_NOT_OPEN_UNTIL_FINISHED` 路径组件；目录遍历遇到不可读目录或其他 I/O 错误时失败，而不是跳过后继续报告 `PASS`。角色 standalone 只读取自己的目录，因此 Challenge 可在受控兄弟包不可见或不可读时独立校验。

这个状态不是“Blind Challenge 已发布”。本地文件权限不是跨主机访问控制，有限泄题扫描不是无泄漏证明，checksums 不是身份签名，分包也不会验证评分规则的科学有效性。尤其不能把当前 LLM4SBR 或其他历史公开案例放入该流程后称为未见题；已经公开的信息无法通过重压缩、移动、加密或重新命名收回。

## 4. 发布证据包

一个发布不只是一组文件。应随 Case File 发布或保存以下证据：

1. **来源与许可记录**：论文、上游 revision、数据和第三方材料的范围；
2. **G0 研究契约**：目标、风险、保护边界、预算、审批与 claim；
3. **契约地图**：每个 Level 的首个失效契约、可观察不变量和首选证据；
4. **公开验证记录**：命令、环境、版本、结果与明确未覆盖的风险；
5. **学习与公平性说明**：前置知识、预计工作量、无障碍/语言考虑、已知误导点；
6. **维护与撤回政策**：问题报告入口、上游变化处理、何时标记 stale 或撤回。

任何报告都应把事实、推断、假设、建议和未知项分开。`public PASS` 应写成“此版本的公开验证器通过”，绝不能写成“论文结论已证明”或“案例绝对安全”。

## 5. 变更、事故与撤回

| 事件 | 立即动作 | 对用户的说明 |
| --- | --- | --- |
| 上游源码/论文改变 | 标记待复审，暂停强结论 | 说明受影响的 Case File 版本和范围 |
| 发现答案泄露或不公平提示 | 在 Blind Challenge 中使受影响版本失效；Open Demo 中明确暴露 | 说明不能再测量什么，以及替代版本计划 |
| 公开检查失效 | 标记验证状态，修复后重新记录 | 区分工具回归与科学结论风险 |
| 来源、许可、安全或伦理问题 | 停止分发相关材料，保护证据并升级 | 说明材料范围、临时限制与后续复核 |
| 发现训练结论过强 | 降低/撤回措辞，补充边界 | 不把“已发布”当作继续传播的理由 |

事故关闭由人类负责人批准，并至少留下时间线、影响面、修正、再验证和预防措施。Agent 可以协助收集和起草，但不能单独宣布案例安全、有效或已关闭。

## 6. 已实现的本地工具边界

- **Open Demo：**可为当前 LLM4SBR 案例生成不覆盖的公开 bundle；公开检查在冻结源树快照上运行，manifest 以 `source_tree_sha256` 绑定实际内容并区分 Git revision 上下文与 worktree 状态，接收者可从 bundle 内独立复核 manifest 与 checksums。
- **Blind staging：**可从三个已经分离的来源组装私有本地三包 staging，绑定显式 allowlist、字节、大小、可执行位、角色来源清单与许可过滤，并检查 learner-facing 边界、有界泄题规则及 POSIX 私有 mode；其唯一状态是 `assembled-awaiting-controlled-placement`。
- **共同限制：**工具不读取受控包来替人判断内容是否科学充分，不认证 `--actor` 身份，不提供远程访问控制，也不宣布案例已经发布、保密、有效或未见。

## 7. Blind Challenge 尚未完成的人工运营门

在任何 `assembled-awaiting-controlled-placement` 进入真实评测前，必须由有责任的运营方完成并记录：

1. **从未公开资格：**确认案例、完整 Git 历史、制品与日志从未向学习者或公众暴露；当前 LLM4SBR 不合格。
2. **来源与权利：**复核论文、源码、数据、第三方许可、隐私、安全与伦理边界。
3. **受控放置：**把 Evaluator Package 和 Maintainer Record 移入独立受控存储，应用最小权限、密钥管理和访问记录；公开位置只能出现 Challenge Package。
4. **评测有效性：**冻结评分规则，完成可重复性、独立 evaluator、公平性与测量有效性复核。
5. **人工泄题审查：**审查 Challenge Package、元数据、文件名、构建日志和全部相关版本历史；有限自动扫描不能替代这一步。
6. **受控执行：**验证评测环境、网络、凭证、提交处理、保留期限和参与者隐私策略。
7. **发布签署：**由具名人类负责人批准版本、声明和剩余风险，而不是从 packager 状态自动升级。
8. **泄漏演练：**实际演练失效、通知、撤回、替换、访问复核和证据保全。

因此 Phase 3 只能分为“3A 本地工具完成”和“3B 受控运营待完成”。只有一个新建、从未公开的案例在独立环境走完上述门槛，Phase 3 整体退出条件才算满足。
