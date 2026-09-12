# Phase 4A：离线静态视图

[English](VIEW_MODE_EN.md) · [开始指南](GETTING_STARTED.md) · [双模式路线图](DUAL_MODE_ROADMAP.md)

RCSL 的 `view` 命令把已经存在的 Open Demo、Mode Audit 工作区和 Mode Train 进度记录投影为一个**完全离线、只读、可丢弃重建**的静态目录。它用于降低浏览证据与边界的成本，不是第三种运行模式，也不是 Dashboard、托管服务或新的权威数据源。

权威状态仍保存在原 Open Demo bundle、Audit workspace 和 Training workspace 中。不要在生成的 HTML 或 JSON 里继续编辑工作；源记录改变后，应生成一个新的 view。

## 快速开始

先确保输出目录的直接父目录已经存在。`--output` 必须指向仓库外一个尚不存在的新目录，并且不得与任一输入重叠：

```bash
python scripts/rcsl.py view build \
  --open-demo /absolute/path/to/verified-open-demo \
  --audit-workspace /absolute/path/to/audit-workspace \
  --training-workspace /absolute/path/to/training-workspace \
  --output /absolute/path/to/new-local-view

python scripts/rcsl.py view verify /absolute/path/to/new-local-view
```

`--open-demo` 可重复指定，至少需要一个、最多支持 32 个；Audit 和 Training 输入都是可选的。生成后直接用浏览器打开 `index.html` 即可，不需要启动服务器、安装前端依赖或连接网络。

如果只需要查看公开案例，可以只传 Open Demo：

```bash
python scripts/rcsl.py view build \
  --open-demo /absolute/path/to/verified-open-demo \
  --output /absolute/path/to/new-public-only-view
```

## 接受与拒绝的输入

| 输入 | build 前的处理 | 视图中的范围 |
| --- | --- | --- |
| Open Demo bundle | 使用仓库侧受信任校验器重新验证精确 root、payload、manifest、checksums、boundary 与 verifier | 只进入 allowlist 内的案例字段和公开边界；不带 actor、reviewer 或任何受控评分摘要 |
| Mode Audit workspace | 读取现有本地工作区并生成受边界约束的 evidence snapshot | 项目 baseline、G0、finding/evidence 摘要、当前状态与已知限制；它仍是本地敏感材料 |
| Mode Train workspace | 使用稳定的脱敏导出逻辑生成 evidence snapshot | 结构/尝试/人工复核状态，以及 `gap_recorded` / `evidence_gap_count` 信号；不导出 gap 正文、原始学习者/审阅者身份标签或自由文本反馈，以 pseudonymous `reviewer_alias` 保留复核分歧，也不导出答案映射 |

Case Registry 的 case allowlist 固定为：`case_id`、`case_version`、`release_mode`、`release_state`、`exposure_state`、`source_revision`、`source_revision_scope`、`repository_worktree_state`、`source_tree_sha256`、`package_manifest_sha256`、`package_checksums_sha256`、`package_file_count`、`licenses`、`known_limitations`、`claims_not_made`、`static_validation`、`public_runtime_checks`、`scientific_correctness` 与 `measurement_validity`。它不保留生成时间、actor、reviewer、原始文件清单或任何 controlled 字段。

至少要提供一个 Open Demo；Audit/Training 不能单独生成 view。`view build` 对 Blind staging、Challenge/Evaluator/Maintainer role package 和形似这些私有包的输入 **fail closed**。受保护的教师答案路径也会在读取前被拒绝。Phase 3A 的 `assembled-awaiting-controlled-placement` 不是可以进入 viewer 的发布状态。若确实需要查看受控 Blind 材料，应在未来经过独立威胁建模、权限设计和 Phase 3B 运营门后另行设计，不能把当前静态视图当作绕过路径。

## 输出内容

一个 view 使用固定、可校验的目录边界：

```text
new-local-view/
├── index.html
├── style.css
├── VIEW_BOUNDARY.md
├── VIEW_MANIFEST.json
├── CHECKSUMS.sha256
└── data/
    ├── CASE_REGISTRY.json
    └── evidence/
        ├── audit-<digest>.json
        └── training-<digest>.json
```

- `index.html` 是唯一页面，内容在生成时完成 HTML escaping；它不含 JavaScript。
- `style.css` 是同目录的自包含样式；页面不加载字体、图片、CDN 或其他外部资源。
- `VIEW_BOUNDARY.md` 说明用途、当前隐私分类和不能从该 view 推导出的结论。
- `VIEW_MANIFEST.json` 绑定 view schema、输入类型、文件清单和摘要，但不保存源文件系统路径。
- `CHECKSUMS.sha256` 绑定允许保留的文件字节。
- `data/CASE_REGISTRY.json` 只保存经 allowlist 筛选的 Open Demo 发现信息。
- `data/evidence/*.json` 保存 Audit/Training 的本地快照；没有相应输入时不会生成该类型文件。

`data/evidence/` 即使为空也会保留。对相同的已验证源记录、相同的被检查 Git 状态和同一受信任实现，输出与参数顺序、输出路径无关并保持逐字节一致；view 不写入新的时间、绝对源路径、hostname、PID 或随机 ID。

如果 build 在创建目标后失败，它会优先避免递归删除可能已被外部进程替换的子项，因此可能留下一个**未验证、不可使用**的 partial 目录。先人工检查并安全处理该目录，再换一个全新的输出路径重试；只有 build 成功且 `view verify` 通过的目录才可作为 view 使用。

页面没有脚本、外链、CDN、请求接口、服务端或网络回退。build 不执行 package/项目代码，也不联网；若加入 Audit workspace，其权威适配器仍可能只读检查 Git 元数据。页面内容在 build 时排好；断网或关闭页面不会修改或丢失源记录。

## 敏感性与权限

包含 Audit 或 Training evidence 的 view 会固定标记为 `local-sensitive-not-deployable`，应始终视为**本地敏感产物**：

- 不要部署到 GitHub Pages、对象存储、公共 Web 服务器或聊天附件；
- 不要因为字段已经缩减就推断它可以公开；项目路径、claim、finding、反馈或证据摘要仍可能敏感；
- 已知 workspace/project root 的逐字替换会显示为 `[local-path-redacted]`，绝对 evidence reference 显示为 `[local-reference-redacted]`；再加上身份字段删除仍只是有界脱敏，无法识别别名、换一种写法的路径、自由文本里的姓名或秘密，不构成匿名化；
- 所有 Phase 4A view 在 POSIX 上都使用 `0700` 目录和 `0600` 文件，校验器也会检查当前 mode；这些检查不是 ACL、加密、身份认证或防复制机制；
- 若需分享，由负责人回到原始权威记录，重新做人类脱敏与发布批准，不要直接发布本地 view。

只包含 Open Demo 的 view 会声明为 `open-demo-only-offline`，仍是使用上述私有 mode 的本地生成快照。可以在明确审查其内容和许可证后另行决定如何使用，但 Phase 4A 不提供安全托管或发布批准。

## 页面必须诚实保留的状态

静态视图不得把结构状态升级为科学判断。它始终显示来源中存在的：

- `not_assessed` 或等价的未评估状态；
- known limitations、evidence-gap 信号/计数与人工决定边界；
- Open Demo / honor-isolation 身份；
- Audit baseline 与记录状态，而不是“项目已正确”；
- Training 的结构、提交和 review 状态，而不是自动能力评分。

viewer 不计算新的 scientific PASS，不平均不同 reviewer 的判断，不替人类关闭 finding，不判断论文忠实性，也不把 Open Demo 改称 Blind Challenge。

## `view verify` 能证明什么

```bash
python scripts/rcsl.py view verify /absolute/path/to/local-view
python scripts/rcsl.py view verify /absolute/path/to/local-view --json
```

成功表示：该目录满足当前 view schema、固定 root/payload、manifest/checksum、静态资源和敏感 mode 契约，并且没有出现 viewer 明令禁止的动态或外部依赖。build 在报告成功前也会运行这套完整校验。Phase 4A 不生成 standalone verifier；`view verify` 依赖一个受信任的 RCSL checkout，并会从保留 JSON 重新渲染和逐字节比较固定页面资源。它**不能**证明：

- 输入中的科学主张、finding、修复或人工判断正确；
- view 与之后已经变化的源工作区仍同步；
- checksums 是签名或能认证作者；
- HTML 在任意托管环境都安全；
- 本地 mode 提供 ACL、加密、保密或撤回能力；
- Blind Challenge 的答案隔离、受控发布或 Phase 3B 已完成。

额外文件或目录、symlink、特殊文件、大小/数量超限、严格 JSON/schema 违规、摘要或页面篡改均会 fail closed；自行重算 manifest/checksums 也不能使被替换的 HTML 或固定资源通过受信任校验。

`view verify` 只验证生成快照本身；源记录改变后，请重新执行 `view build` 到另一个全新目录。

## Phase 4A 的明确边界

Phase 4A 完成的是本地、无 JavaScript 的静态 projection 与一致性验证。它不等于：

- Phase 4B 交互式 Dashboard；
- 中心化或托管 Case Registry；
- 多用户同步、登录、权限管理或协作审批；
- 编辑器、CI 或学习平台集成；
- 公网部署经过安全与隐私审查。

只有在真实协作需求、数据治理、威胁模型、无障碍与长期维护责任明确后，才应讨论这些后续能力。无论未来 UI 如何变化，Train/Audit 的本地 CLI、原始 Markdown/JSON 和人类决策仍是权威接口。
