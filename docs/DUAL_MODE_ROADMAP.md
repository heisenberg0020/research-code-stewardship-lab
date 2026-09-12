# RCSL 双模式路线图

**目标：**让 RCSL 同时服务于可重复的能力训练（**Mode Train**）和有边界的真实研究审计（**Mode Audit**），但不把自动结构检查包装成科学判断，也不把已有公开题重新包装成“未见盲题”。

[English](DUAL_MODE_ROADMAP_EN.md) · [能力模型](COMPETENCY_MODEL.md) · [案例发布模型](CASE_RELEASE_MODEL.md)

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
| Phase 3：Demo 导出与 Blind Challenge 分包 | 计划 | P2 | 伪盲测、访问控制缺失、许可证和评价有效性问题 |
| Phase 4：可选 UI/Registry/集成 | 可选 | P3 | 过早平台化、隐私/锁定、CLI 与 UI 语义漂移 |

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
| 验收标准 | 临时 Git fixture 走通“init → 完成模板/lint → G0 approve/preflight → finding/evidence → 合法 `verified`/`closed` transition → verify/report”；测试确认该 fixture 的目标 `HEAD`、工作树状态与已追踪文件保持不变；所有 Audit 命令默认不执行项目、不联网、不读隔离答案；lint、verify、report 明确不等于科学判决 |
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

## Phase 3：Open Demo 导出与真正 Blind Challenge 分包

**目的：**支持诚实的公开教学发布，并为未来受控盲测建立正确的包边界。

| 项目 | 内容 |
| --- | --- |
| 具体产物 | `rcsl export open-demo`：导出来源、版本、许可、已知限制和公开验证记录；`rcsl package blind`：从一开始产生 Challenge Package、受控 Evaluator Package 和受控 Maintainer Record；manifest、checksum、泄题扫描与撤销模板 |
| 验收标准 | Open Demo 清楚显示不是安全隔离；合成 fixture 的 Challenge Package 不含答案映射、private probe 或评价标签；Evaluator Package 可在独立受控环境评分；每个包可追溯版本与来源 |
| 非目标 | 把当前 LLM4SBR 或任何已公开案例重新压缩、加密或换目录后称为“未见盲题”；把本地打包器当成访问控制、保密保证或测量有效性保证 |
| 依赖 | 独立的私有评测存储、最小权限、访问记录、冻结评分规则、许可审查、独立评测者与泄露失效流程 |
| 退出条件 | 新建且从未公开的案例在受控环境完成分包、泄题审查、独立评分和泄露演练；当前公开案例仍明确标为 Open Demo |

**关键事实：**历史公开过的题目不会因为重新打包而变成未见题。真正的 Blind Challenge 必须使用新的、从未公开且有运维能力保护的案例；打包工具只能帮助执行边界，不能回收已经泄露的信息。

## Phase 4：可选 Web UI、Registry 与集成

**目的：**在共同内核稳定后，降低导航成本和提升案例可发现性，而不把 RCSL 变成依赖中心化服务的平台。

| 项目 | 内容 |
| --- | --- |
| 具体产物 | 可选本地/静态 Web 视图；Case Registry（来源、版本、模式、许可、已知限制）；编辑器/CI/学习平台集成；从同一 Markdown/JSON schema 渲染的 Evidence Passport 查看器 |
| 验收标准 | 没有 Web 也能完成所有 Train/Audit 工作；UI 与 CLI 产生同一 schema；默认不上传源码、数据、答案或身份信息；Registry 明确区分 Open Demo 与受控 Blind Challenge |
| 非目标 | 强制登录、把私有研究材料上传到中心服务、由 UI 替代人工批准、用集成状态推断科学正确 |
| 依赖 | Phase 1 schema 和 CLI 稳定；隐私/安全/无障碍审查；清晰的治理、托管与维护责任 |
| 退出条件 | UI 只是可替换的视图层，关闭或离线时不损失案例、证据或决策记录；所有模式仍可由本地 CLI 导入/导出 |

**风险控制：**先实现静态或本地视图；只有在真实用户需要跨设备协作且治理到位后，再考虑托管 Registry 或第三方集成。

## 决策门

| 何时 | 必须回答的问题 |
| --- | --- |
| 进入 Audit | 原项目是否是 clean Git 工作树？workspace 是否在项目外且尚不存在？G0 是否已从 `draft` 开始，供后续由人类完成和复核？ |
| 允许执行 | Audit 本身不会执行项目；若需运行代码、联网、访问受保护材料、改写源码或扩大预算，是否另有明确授权的工具流程？ |
| 形成结论 | Evidence Passport 是否区分事实、推断、假设、未知项和允许 claim？ |
| 发布案例 | 它是 Open Demo 还是 Blind Challenge？声明是否诚实匹配控制能力？ |
| 上线 UI/集成 | 是否仍能离线、本地、可导出地保留全部证据与人类决策？ |
