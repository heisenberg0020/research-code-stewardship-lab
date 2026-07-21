# 论文与源码映射（无答案）

## 1. Intent Localization

论文第 8 页公式 (4)–(5)，Algorithm 1 第 1–6 行：先计算 inference embedding
与所有 item text embedding 的余弦相似度，再取 Top-r，最后让“被选 item”与
“它自己的相似度”相乘并求和。

原项目相关位置：`Intent_Localization.py` 的 top-5 检索与加权段，以及
`generate_llm_embeddings.py::localize_embeddings`。

## 2. Local / Global 行为表示

论文第 10 页公式 (6)：local 表示是最后一个真实点击；global 表示由整条 session
经过 soft attention 聚合得到。padding 不属于 session 内容。

原项目相关位置：`model_LLM.py::compute_scores` 中 `ht`、`alpha` 和 `a`。

## 3. DirectAU

论文第 10 页公式 (7)–(9)：文本表示先投影到行为 latent space；alignment 比较
相同 view 的语义/行为表示；uniformity 由同一分布中的样本对距离定义。

原项目相关位置：`alignment`、`uniformity`、`calculate_loss`。

## 4. 双视角融合

论文第 10 页公式 (10)–(12)：

- long-term inference 与 global behavior 对应；
- short-term inference 与 local behavior 对应；
- 最终拼接的是加权 local 分支和加权 global 分支。

原项目相关位置：`linear_four`、`linear_five` 和 `linear_transform`。

## 5. 预测与联合优化

论文第 11 页公式 (13)–(15)：session 表示与 item-ID embedding 点积得到 logits；
padding item 0 不参与候选；标签需与去掉 padding 后的 logits 下标对齐；总损失为
推荐损失加上由 tau 缩放的辅助损失。

## 可用的不变量思路

以下只是实验方向，不说明哪份代码违反它们：

- 修改 mask=0 位置的 hidden，global/session 输出是否应该改变？
- 打乱 batch 样本顺序再还原，按“分布中样本对”定义的 loss 是否应该改变？
- Top-r item 不在 item 表前 r 行时，检索到的 item 与权重是否仍一一对应？
- 让 long 与 short 输入明显正交，能否追踪它们分别进入 global 与 local 分支？
