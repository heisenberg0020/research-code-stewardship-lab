import argparse
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from tqdm import tqdm
from transformers import AutoModel, AutoTokenizer


# 这个脚本用于补齐 main.py 训练所需的 LLM 语义 embedding 文件。
# 它不微调大语言模型，而是把 session 中的 item 名称组织成“长期/短期兴趣文本”，
# 再用 HuggingFace 文本编码模型生成 768 维向量，并保存成 main.py 期望的 xlsx 格式。
# 如果开启 --localize-topk，会先把 session 文本向量定位到最相似的真实 item 名称向量，
# 用 top-k item 向量的加权平均作为最终 embedding，近似论文中的 intent localization 步骤。


def parse_args():
    parser = argparse.ArgumentParser(description="Generate LLM-style session embeddings for LLM4SBR.")
    parser.add_argument("--dataset", default="ml-1m", choices=["ml-1m", "Beauty"], help="数据集名称")
    parser.add_argument("--split", default="train", choices=["train", "test"], help="生成训练集还是测试集 embedding")
    parser.add_argument("--view", default="long", choices=["long", "short"], help="长期兴趣或短期兴趣 embedding")
    parser.add_argument("--model-name", default="bert-base-uncased", help="HuggingFace 文本编码模型")
    parser.add_argument("--batch-size", type=int, default=64, help="文本编码 batch size")
    parser.add_argument("--max-length", type=int, default=256, help="Tokenizer 最大长度")
    parser.add_argument("--recent-k", type=int, default=5, help="short view 使用最近多少个 item")
    parser.add_argument("--localize-topk", type=int, default=5, help="用 top-k item 名称向量做定位；0 表示关闭")
    parser.add_argument("--llm-output-xlsx", default=None, help="可选：读取已有 LLM 输出 xlsx，并编码其中的文本列")
    parser.add_argument("--text-column", default="Value", help="--llm-output-xlsx 中要编码的文本列名")
    parser.add_argument("--max-samples", type=int, default=None, help="调试用：只生成前 N 条样本")
    parser.add_argument("--project-dir", default=".", help="LLM4SBR-main 所在目录")
    parser.add_argument("--overwrite", action="store_true", help="输出文件已存在时覆盖")
    return parser.parse_args()


def load_pickle_sequences(project_dir, dataset, split):
    """读取 Data/{dataset}/{split}.txt，返回输入序列列表和标签列表。"""
    file_path = Path(project_dir) / "Data" / dataset / f"{split}.txt"
    if not file_path.exists():
        raise FileNotFoundError(f"找不到序列文件：{file_path}")
    with file_path.open("rb") as f:
        seqs, labels = pickle.load(f)
    return seqs, labels


def load_item_names(project_dir, dataset):
    """读取模型内部 item id 到可读名称的映射。

    当前项目中的 Search_data 名称表没有显式 ID 列，默认第 1 行数据对应模型 ID 1。
    """
    project_dir = Path(project_dir)
    if dataset == "ml-1m":
        name_path = project_dir / "Search_data" / dataset / "movie_name.xlsx"
    else:
        name_path = project_dir / "Search_data" / dataset / "name.xlsx"

    if not name_path.exists():
        raise FileNotFoundError(f"找不到 item 名称表：{name_path}")

    df = pd.read_excel(name_path)
    if "name" not in df.columns:
        first_col = df.columns[0]
        df = df.rename(columns={first_col: "name"})

    names = ["<PAD>"] + df["name"].fillna("").astype(str).tolist()
    return names


def sequence_to_text(seq, item_names, view, recent_k):
    """把 item id 序列转换成长期/短期兴趣描述文本。"""
    valid_ids = [int(item_id) for item_id in seq if int(item_id) > 0]
    if view == "short":
        valid_ids = valid_ids[-recent_k:]

    item_texts = []
    for item_id in valid_ids:
        if item_id < len(item_names):
            item_texts.append(item_names[item_id])
        else:
            item_texts.append(f"item_{item_id}")

    joined_items = " ; ".join(item_texts)
    if view == "long":
        return (
            "The user's long-term preference can be inferred from the following clicked items: "
            f"{joined_items}. Represent the stable semantic interests of this session."
        )
    return (
        "The user's short-term intent can be inferred from the most recent clicked items: "
        f"{joined_items}. Represent the immediate semantic intent of this session."
    )


def mean_pool(last_hidden_state, attention_mask):
    """按 attention mask 对 token hidden states 做平均池化。"""
    mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    summed = torch.sum(last_hidden_state * mask, dim=1)
    counts = torch.clamp(mask.sum(dim=1), min=1e-9)
    return summed / counts


@torch.no_grad()
def encode_texts(texts, tokenizer, model, device, batch_size, max_length, desc):
    """批量编码文本，并返回 L2 normalize 后的 numpy 矩阵。"""
    all_embeddings = []
    model.eval()
    for start in tqdm(range(0, len(texts), batch_size), desc=desc):
        batch_texts = texts[start:start + batch_size]
        tokens = tokenizer(
            batch_texts,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="pt",
        )
        tokens = {key: value.to(device) for key, value in tokens.items()}
        outputs = model(**tokens)
        pooled = mean_pool(outputs.last_hidden_state, tokens["attention_mask"])
        pooled = F.normalize(pooled, p=2, dim=1)
        all_embeddings.append(pooled.cpu())
    return torch.cat(all_embeddings, dim=0).numpy()


def localize_embeddings(session_embeddings, item_embeddings, topk, batch_size):
    """把 session embedding 定位到最相似的 top-k item embedding 上。"""
    if topk <= 0:
        return session_embeddings

    item_tensor = torch.tensor(item_embeddings, dtype=torch.float32)
    session_tensor = torch.tensor(session_embeddings, dtype=torch.float32)
    localized_batches = []
    topk = min(topk, item_tensor.shape[0])

    for start in tqdm(range(0, session_tensor.shape[0], batch_size), desc="Localizing"):
        batch = session_tensor[start:start + batch_size]
        scores = torch.matmul(batch, item_tensor.T)
        values, indices = torch.topk(scores, k=topk, dim=1)
        weights = torch.softmax(values, dim=1).unsqueeze(-1)
        topk_item_embs = item_tensor[indices]
        localized = torch.sum(weights * topk_item_embs, dim=1)
        localized = F.normalize(localized, p=2, dim=1)
        localized_batches.append(localized)

    return torch.cat(localized_batches, dim=0).numpy()


def embedding_to_cell(embedding):
    """转成 main.py 可解析的字符串格式：[[...768 floats...]]。"""
    return str([embedding.astype(float).tolist()])


def output_path(project_dir, dataset, split, view):
    prefix = "tra" if split == "train" else "tes"
    column_prefix = "long" if view == "long" else "short"
    filename = f"{prefix}_session_{column_prefix}_emb.xlsx"
    return Path(project_dir) / "Search_data" / dataset / filename


def load_llm_texts(xlsx_path, text_column):
    """读取 Qwen/其他 LLM 已生成的回答文本。"""
    df = pd.read_excel(xlsx_path)
    if text_column not in df.columns:
        raise ValueError(f"{xlsx_path} 中找不到列 {text_column}，现有列：{list(df.columns)}")
    return df[text_column].fillna("").astype(str).tolist()


def main():
    args = parse_args()
    project_dir = Path(args.project_dir).resolve()
    out_path = output_path(project_dir, args.dataset, args.split, args.view)
    if out_path.exists() and not args.overwrite:
        raise FileExistsError(f"输出文件已存在：{out_path}。如需覆盖请加 --overwrite")

    seqs, _ = load_pickle_sequences(project_dir, args.dataset, args.split)
    if args.max_samples is not None:
        seqs = seqs[:args.max_samples]

    item_names = load_item_names(project_dir, args.dataset)
    if args.llm_output_xlsx:
        session_texts = load_llm_texts(args.llm_output_xlsx, args.text_column)
        if args.max_samples is not None:
            session_texts = session_texts[:args.max_samples]
        if len(session_texts) != len(seqs):
            raise ValueError(
                f"LLM 文本数量 {len(session_texts)} 与 {args.split}.txt 样本数 {len(seqs)} 不一致"
            )
    else:
        session_texts = [
            sequence_to_text(seq, item_names, args.view, args.recent_k)
            for seq in seqs
        ]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    print(f"Loading encoder: {args.model_name}")
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    model = AutoModel.from_pretrained(args.model_name).to(device)

    session_embeddings = encode_texts(
        session_texts,
        tokenizer,
        model,
        device,
        args.batch_size,
        args.max_length,
        desc=f"Encoding {args.split}-{args.view} sessions",
    )

    if args.localize_topk > 0:
        item_texts = item_names[1:]
        item_embeddings = encode_texts(
            item_texts,
            tokenizer,
            model,
            device,
            args.batch_size,
            args.max_length,
            desc="Encoding item names",
        )
        session_embeddings = localize_embeddings(
            session_embeddings,
            item_embeddings,
            args.localize_topk,
            args.batch_size,
        )

    column_name = "longterm_emb" if args.view == "long" else "shortterm_emb"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({column_name: [embedding_to_cell(emb) for emb in session_embeddings]}).to_excel(
        out_path,
        index=False,
    )
    print(f"Saved {len(session_embeddings)} embeddings to {out_path}")


if __name__ == "__main__":
    main()
