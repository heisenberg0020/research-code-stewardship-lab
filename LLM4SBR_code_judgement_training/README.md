# LLM4SBR 代码判错训练

这个训练包包含 5 份接口完全相同的 PyTorch 实现：`candidate_A.py` 到
`candidate_E.py`。其中只有 1 份与论文公式及约定一致，其余 4 份各自含有一种
细小、可运行、可反向传播、但会改变训练或预测结果的语义错误。

错误不是语法错误，也不会通过 shape mismatch 暴露。每份错误代码相对正确实现
只改动约 5% 的有效代码行（按非空、非注释逻辑行计算为 4.55%–5.68%）。

## 依据

- 论文：[LLM4SBR（arXiv:2402.13840）](https://arxiv.org/abs/2402.13840)
- 原项目核心模型：[model_LLM.py](https://github.com/tsinghua-fib-lab/LLM4SBR/blob/main/model_LLM.py)
- 原项目意图定位：[Intent_Localization.py](https://github.com/tsinghua-fib-lab/LLM4SBR/blob/main/Intent_Localization.py)
- 建议精读论文 PDF 第 8–11 页，尤其是公式 (4)–(15) 和 Algorithm 1。
- `PAPER_AND_SOURCE_MAP.md` 给出公式到代码职责的映射，但不透露答案。

候选代码是从原项目中抽出的“可独立验证核心”，覆盖意图定位、DirectAU、
长短期视角融合、候选打分和联合损失。这样不用下载 BERT/Qwen 或跑完整
MovieLens 训练，也能用小实验验证算法语义。

## 任务

1. 判断 A–E 中哪一份正确。
2. 对另外四份分别指出错误位置。
3. 说明错误违反哪条公式、张量语义或训练不变量。
4. 说明它为什么仍能运行，以及它可能怎样损害结果。
5. 最好为每个判断设计一个最小反例，而不只是看 diff。

请把结论写到 `ANSWER_SHEET.md`。完成前不要打开
`DO_NOT_OPEN_UNTIL_FINISHED/`。

## 运行

本机已发现 `ml` Conda 环境带 PyTorch 2.12：

```bash
conda run -n ml python run_all.py
```

如果当前 Python 已安装 PyTorch，也可以：

```bash
python run_all.py
```

`run_all.py` 只做公平的 smoke test：所有候选使用相同随机种子和相同合成
batch，各执行前向、反向和一次优化。五份都应显示 `PASS`；数值不同不是正确性
证明，因为你尚不知道哪个数值才符合论文。

## 推荐训练方法

- 第一轮：只读论文和五份代码，限时 30 分钟。
- 第二轮：写针对性的张量小实验，检查 padding 不变性、检索索引与权重对应、
  batch 排列不变性、long/short 与 global/local 的配对。
- 第三轮：填写答案后再打开答案目录，逐条给自己的“证据质量”打分。

评分建议：正确候选 20 分；四个错误各 15 分；四个最小反例各 5 分。
