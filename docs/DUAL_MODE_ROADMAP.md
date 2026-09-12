# RCSL 双模式路线图

**目标：**让 RCSL 同时服务于可重复的能力训练（**Mode Train**）和有边界的真实研究审计（**Mode Audit**），但不把自动结构检查包装成科学判断，也不把已有公开题重新包装成“未见盲题”。

[English](DUAL_MODE_ROADMAP_EN.md) · [能力模型](COMPETENCY_MODEL.md) · [案例发布模型](CASE_RELEASE_MODEL.md) · [离线静态视图](VIEW_MODE.md)

## 不变原则

1. **本地优先：**CLI + Markdown/JSON 是权威接口；任何未来 UI 只是同一模型的可选视图。
2. **标准库优先：**核心导航、模板、schema 和包检查默认只依赖 Python 标准库；重型运行时保持可选。
3. **原项目只读：**审计命令默认不改论文、源码、数据或已有结果；新产物只写到用户明确指定的输出目录。
4. **人类最终决策：**Agent 可以搜集、执行受限检查和起草；人类冻结 G0、批准权限、解释证据、允许 claim 并关闭事故。
5. **结构不等于科学：**`PASS` 仅表示给定版本的结构、格式或有限运行契约通过；它不证明论文忠实性、实验公平性、安全性或结论为真。

## 两种模式与共同内核

| 项目 | Mode Train：训练 | Mode Audit：真实审计 |
| --- | --- | --- |
| 目的 | 在准备好的案例中练习发现“能跑但不可信”的研究错误 | 对用户授权范围内的论文、源码、实验与 Agent 行动形成可审计判断 |
| 输入 | 版本化案例、公开 brief、学习者答案表、公开检查 | 用户提供的研究契约、只读来源、允许范围、输出目录与审批规则 |
| 输出 | Evidence Passport、进度记录、capstone 交付 | Research Contract、Triage Card、Evidence Passport、命名的 G0 gate 决定、本地 lifecycle ledger 与 review report |
| 人类角色 | 按规则独立推理、保留证据、接受/请求反馈 | 冻结 G0、划定权限与风险、批准运行和最终结论 |
| 不承诺 | 真实盲测、自动评分等于科学正确 | 无人值守审计、自动发布、自动修改原项目 |

两种模式复用同一**共同内核**：

```text
G0 Research Contract / Case Manifest
→ Triage Card + Delegation Contract
→ Evidence Passport（位置 · 契约 · 命令/产物 · 因果影响 · 边界）
→ 命名的 G0 gate 决定 + 本地 lifecycle ledger
→ 渲染的 Markdown/JSON review report：项目 baseline、G0、findings/evidence 摘要与已知限制
```

纵轴始终按照**首个失效契约**使用 L1 语义、L2 流水线、L3 科学有效性、L4 Agent 治理归类。七项负责人能力和四档成熟度见 [能力模型](COMPETENCY_MODEL.md)。

## 优先级总览

| 阶段 | 状态 | 优先级 | 主要风险 |
| --- | --- | --- | --- |
| Phase 0：当前基线 | **完成** | P0 | 公开案例被误解为盲测或科学认证 |
| Phase 1：显式 Train/Audit 与真实闭环 | **本轮已完成** | P0 | 默认写入/执行越权，或把工具输出误解为结论 |
| Phase 2：进度、人工 Rubric 与 Capstone | **已完成** | P1 | 机械化打分、泄题、把学习增益说得过强 |
| Phase 3：Demo 导出与 Blind Challenge 分包 | **3A 本地工具完成；3B 受控运营待完成** | P2 | 伪盲测、访问控制缺失、许可证和评价有效性问题 |
| Phase 4：可选 UI/Registry/集成 | **4A 离线静态视图完成；4B Dashboard/托管/集成待定** | P3 | 过早平台化、隐私/锁定、CLI 与 UI 语义漂移 |

---

## Phase 0：当前基线（完成）

**目的：**提供一个诚实、可运行的公开训练起点。

| 项目 | 内容 |
| --- | --- |
| 已有产物 | L1–L4 四级训练包；G0/能力/发布模型文档；source-blind 论文学习协议；公开导航、环境诊断和公开检查入口；CI 与公开验证记录 |
| 验收标准 | 公开 Level 1–4 检查可在支持环境运行；文档说明首个失效契约、答案隔离边界和 `public PASS` 的限制；公开入口不依赖教师材料 |
| 非目标 | 不把 LLM4SBR 或任何当前公开案例说成未见题、保密考试、生产安全审计或论文复现证明 |
| 依赖 | 已有训练包、Python 环境、公开来源和人工维护 |
| 退出条件 | **已满足。**后续功能必须保持这些边界，不以“体验更好”为由降低透明度 |

## Phase 1：显式 Train/Audit 命令与真实审计闭环（本轮已完成）

**目的：**让用户从一开始知道自己在“做训练”还是“审计真实项目”，并让 Audit 有从 G0 到人工决策的完整闭环。

| 项目 | 内容 |
| --- | --- |
| 具体产物 | 明确的命令族：`rcsl train overview`、`rcsl train doctor`、`rcsl train start --level 1..4`、`rcsl train validate`；以及 `rcsl audit init`、`status`、`lint`、`gate check`、`gate record`、`preflight`、`rebaseline`、`finding add/list/transition`、`evidence add`、`verify`、`report build`。四份本地模板为 `research-contract-template.md`、`evidence-passport-template.md`、`triage-card-template.md`、`delegation-contract-template.md`；只写入 `--output` 所指定的项目外审计工作区；临时 clean-Git E2E 测试 |
| 闭环 | `audit init` 绑定 clean `HEAD` 并创建 G0 `draft` → 人类完成 research contract 与其余模板 → `audit lint` → `audit gate record --decision approved` → `audit preflight` → finding/evidence 与有理由的状态转换 → `audit verify` 与本地 Markdown/JSON review report |
| 验收标准 | 临时 Git fixture 走通“init → 完成模板/lint → G0 approve/preflight → finding/evidence → 合法 `verified`/`closed` transition → verify/report”；`audit init` 要求直接父目录已存在并通过固定父/新目录句柄独占写入，`report build` 固定 workspace 身份、拒绝覆盖并在 POSIX 输出 `0600`；路径替换测试证明不会写入重定向目标。测试还确认目标 `HEAD`、工作树状态与已追踪文件保持不变；Audit 默认不执行项目、不联网、不读隔离答案，所有状态不是科学判决 |
| 非目标 | 让 Agent 自主定义问题、运行任意脚本、直接修复原项目、自动批准发布或给出不带证据的正确性 verdict |
| 依赖 | 稳定 CLI schema、公开模板、项目只读/外部 workspace 策略、本地 hash-chain lifecycle、临时 Git E2E 测试与人工 review 规则 |
| 退出条件 | **已满足。**标准库 CLI 已在全新临时 clean-Git 目录中完成上述闭环；测试确认该 fixture 的目标 `HEAD`、工作树状态与已追踪文件保持不变，文档给出每条命令的权限与边界 |

**风险控制：**Audit 命令只读取目标项目或记录本地审计材料，preflight 也不授予执行权限。G0 不完整或没有当前 `approved` gate 时，工具应拒绝后续动作或返回 `needs-human-decision`，而不是猜测。

## Phase 2：学习者进度、人工 Rubric 与跨层 Capstone（已完成）

**目的：**把“运行过题目”升级为可观察的能力成长，同时不把答案猜对或自动分数当作科学判断能力。

| 项目 | 内容 |
| --- | --- |
| 具体产物 | `train progress init/status/check/submit/review/export` 命令族；仓库外的学习者工作区与单一原子更新的 `progress.json`；L1–L4 Evidence Passport 和 Capstone worksheet；Recognize / Prove / Direct / Steward 人工 rubric；不可变提交快照、重做关系、多审阅者反馈与脱敏 Markdown/JSON 导出 |
| 实现闭环 | `progress init` → 编辑 worksheet → `check` 结构 → `submit` 冻结尝试 → `review` 记录具名人工判断 → 根据 evidence gaps 重做 → `status` 离线恢复 → `export` 生成不覆盖的脱敏摘要。当前草稿、最新冻结提交与历史尝试保持可区分 |
| 验收标准 | 进度可离线暂停和恢复；状态把 worksheet 结构、尝试状态、人工 review、未判断的科学正确性分开；多审阅者差异不被平均；Capstone 要求 G0、分诊、委派、影响面、claim 边界、修复和利益相关方沟通；公开工作流不读取或导出答案映射 |
| 非目标 | 全球排行榜、以候选字母自动判定研究能力、用一次完成宣称学习效果、把隐藏答案放入客户端评分器 |
| 依赖 | Phase 1 的共同产物和 schema；版本化人工 rubric；公开合成事故；答案隔离与复核设计；标准库原子写入和本地互斥锁 |
| 退出条件 | **已满足。**学习者能在本地完成、暂停、恢复和导出证据记录；系统保留两位审阅者各自的 rubric 观察、决定与 gap 说明以支持人工解释分歧；Capstone 只能通过明确的具名人工 `pass`，且四档观察必须全部声明为 `demonstrated` |

**风险控制：**CLI 只检查小节、内容和模板提示，绝不自动推导语义、科学正确性或成熟度；`progress.json` 的摘要与原子写入只提供本地一致性，不提供身份认证或外部不可篡改性。当前案例保持 `open-demo-honor-isolation`；在没有预注册研究之前，不声称课程提升了真实研究质量。完整命令见 [Mode Train 指南](TRAIN_MODE.md)。

## Phase 3：Open Demo 导出与真正 Blind Challenge 分包（部分完成）

**目的：**支持诚实的公开教学发布，并为未来受控盲测建立正确的包边界。

| 项目 | 内容 |
| --- | --- |
| Phase 3A：本地工具（已完成） | `export open-demo --output NEW_DIR --actor LABEL [--run-public-checks]` 为当前 LLM4SBR Open Demo 生成可独立复核的冻结快照；`export verify BUNDLE [--json]` 检查精确 root/payload，并在受信任 checkout 中逐字节核对 verifier/boundary。`package blind --manifest ... --challenge-source ... --evaluator-source ... --maintainer-source ... --output NEW_PRIVATE_STAGING --actor LABEL` 生成 `0700` 私有 staging；`package verify STAGING [--json]` 复核三包、精确来源清单、可执行位、BUILD_RECORD、有界泄题规则与 POSIX 私有 mode |
| 3A 验收标准 | Open Demo 与 Blind 输出都位于公开仓库外、目标尚不存在且直接父目录已存在；Blind manifest 与三个来源也位于公开仓库外，三个来源彼此不同且互不包含，Blind 输出与任一来源也不能相互包含；POSIX manifest/直接父目录无 group/other 权限。严格 JSON 拒绝浮点数、重复/未知字段和布尔整数替代，版本满足严格 SemVer，时间采用规范 UTC RFC3339 `YYYY-MM-DDTHH:MM:SS[.fraction]Z`，模板占位值 fail closed。每个角色的非生成 payload 精确等于 `source_inventory`，BUILD_RECORD 绑定 tool revision scope/worktree state 与 packager/verifier 摘要；正常组装后的三个角色都能从自身根目录通过 standalone 自验，不读取兄弟包，并对容量、不可读目录、symlink/special file 和受保护路径 fail closed。仓库侧信任校验与对应工具 revision 绑定，受信任字节变化后旧包必须切换到其记录的工具版本复核。Challenge 不含受控映射/摘要/元数据；blind staging 唯一状态为 `assembled-awaiting-controlled-placement`，mode 检查不冒充 ACL |
| Phase 3B：受控运营（待完成） | 为一个全新且从未公开的案例提供独立私有 evaluator/maintainer 存储、最小权限、访问记录、冻结评分规则、许可复核、独立 evaluator、受控执行、人工泄题审查、具名发布签署与泄漏失效/撤回演练 |
| 非目标 | 把当前 LLM4SBR 或任何已公开案例重新压缩、加密或换目录后称为“未见盲题”；把本地打包器当成访问控制、保密保证或测量有效性保证 |
| 依赖 | 3A 已由标准库本地工具和合成测试覆盖；3B 仍依赖独立的私有评测存储、最小权限、访问记录、冻结评分规则、许可审查、独立评测者与泄露失效流程 |
| 整体退出条件 | **尚未满足。**必须由新建且从未公开的案例在受控环境完成分包、人工泄题审查、独立评分和泄露演练；当前公开 LLM4SBR 继续明确标为 Open Demo |

**关键事实：**历史公开过的题目不会因为重新打包而变成未见题。真正的 Blind Challenge 必须使用新的、从未公开且有运维能力保护的案例；本地打包和 `package verify` 只能执行文件、摘要、精确包边界与当前 POSIX mode 契约，不能验证 ACL、回收已经泄露的信息或替代人工运营门。Phase 3A 的本地工具完成不改变 Phase 3B 和 Phase 3 整体仍未完成的事实。详见 [案例发布模型](CASE_RELEASE_MODEL.md)。

## Phase 4：可选视图、Registry 与集成（4A 已完成）

**目的：**在共同内核稳定后，降低导航成本和提升案例可发现性，而不把 RCSL 变成依赖中心化服务的平台。

| 项目 | 内容 |
| --- | --- |
| Phase 4A：离线静态视图（已完成） | `view build --open-demo PATH [--open-demo PATH ...] --output NEW_EXTERNAL_DIR [--audit-workspace PATH] [--training-workspace PATH]` 与 `view verify VIEW [--json]`；至少一个经仓库侧受信任校验器复核的 Open Demo；固定输出 `index.html`、`style.css`、`VIEW_BOUNDARY.md`、`VIEW_MANIFEST.json`、`CHECKSUMS.sha256`、`data/CASE_REGISTRY.json` 和可选的 Audit/Training evidence snapshot |
| 4A 验收标准 | 输出位于公开仓库外、尚不存在且直接父目录已存在，不与输入重叠；build 不执行 package/项目代码且不联网；页面完全离线、无 JavaScript、无外链/CDN/server/network；Case Registry 只含 allowlist 字段，不含 actor/reviewer/受控评分摘要；Audit/Training evidence 保留 `not_assessed`、known limitations 与人工判断边界并明确标为本地敏感；所有 view 使用 POSIX `0700`/`0600`；Blind staging/role package 在读取 payload 前 fail closed；固定 root/payload、manifest/checksum、动态依赖和 mode 可复核 |
| Phase 4B：交互与托管（待定） | 只有真实需求与治理就绪后，才考虑交互式 Dashboard、托管 Case Registry、多用户同步、编辑器/CI/学习平台集成与更丰富的 Evidence Passport 浏览；它不是 4A 的默认延伸 |
| 非目标 | 强制登录、把私有研究材料上传到中心服务、让 view 成为权威记录、由 UI 替代人工批准、用渲染或校验状态推断科学正确、让 Blind 材料绕过 Phase 3B、把本地快照描述成经过安全审查的可部署网站 |
| 依赖 | 4A 复用 Phase 1–3A 的稳定 schema、受信任 Open Demo verifier、Audit report data 与 Training 脱敏导出；4B 仍需真实协作需求、隐私/安全/无障碍审查、威胁模型，以及清晰的治理、托管与维护责任 |
| 退出条件 | **4A 已满足。**无 UI 仍可完成所有 Train/Audit 工作；静态 view 是可丢弃重建的只读 projection，断网或关闭它不会损失案例、证据或人类决定。**Phase 4B 和 Phase 4 整体不因此宣告完成。** |

**风险控制：**4A 只接受至少一个 verified Open Demo，并明确拒绝 Blind staging 与三类 role package。包含 Audit/Training evidence 的 view 只能留在本地；`0700`/`0600` 是当前 POSIX mode 检查，不是 ACL、加密或防复制。`view verify` 只检查快照契约，不证明科学正确、源 workspace 仍同步或托管安全。完整边界见 [离线静态视图指南](VIEW_MODE.md)。只有在真实用户需要跨设备协作且治理到位后，再考虑 4B。

## 决策门

| 何时 | 必须回答的问题 |
| --- | --- |
| 进入 Audit | 原项目是否是 clean Git 工作树？workspace 是否在项目外且尚不存在？G0 是否已从 `draft` 开始，供后续由人类完成和复核？ |
| 允许执行 | Audit 本身不会执行项目；若需运行代码、联网、访问受保护材料、改写源码或扩大预算，是否另有明确授权的工具流程？ |
| 形成结论 | Evidence Passport 是否区分事实、推断、假设、未知项和允许 claim？ |
| 发布案例 | 它是 Open Demo 还是 Blind Challenge？声明是否诚实匹配控制能力？ |
| 生成静态 view | 是否至少有一个受信任验证的 Open Demo？是否拒绝 Blind 输入？若加入 Audit/Training evidence，是否保持本地私有且完整展示 `not_assessed` 与 known limitations？ |
| 上线 Dashboard/托管/集成 | 是否仍能离线、本地、可导出地保留全部证据与人类决策？隐私、安全、无障碍、权限与维护责任是否已明确？ |
