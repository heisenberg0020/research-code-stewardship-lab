import pandas as pd
import json
import csv
import pickle
from collections import Counter

# MovieLens-1M 数据预处理脚本：
# 1. 读取 ratings.dat；
# 2. 按用户和 10 分钟时间窗划分匿名 session；
# 3. 过滤低频 item 和过短 session；
# 4. 将电影原始 ID 映射为模型内部连续 ID；
# 5. 生成 train/test pickle 和给 LLM 使用的 prompt JSON。

# File paths
RATINGS_FILE = 'ratings.dat'
MOVIE_NAME_FILE = 'modelId_name.csv'
GLOBAL_ID_FILE = 'globalId2ModelId.csv'
TRAIN_FILE = 'Seq/train.txt'
TEST_FILE = 'Seq/test.txt'
ALL_TRAIN_SEQ_FILE = 'Seq/all_train_seq.txt'
TEST_JSON_FILE = 'Text/tes_session_long.json'

def load_and_preprocess_data(file_path):
    """读取 MovieLens ratings.dat，并构造 session 标识。"""
    column_names = ["UserId", "ItemId", "Rating", "Timestamp"]
    try:
        df = pd.read_csv(file_path, sep="::", engine="python", header=None, names=column_names)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='s')
        # 把时间戳向下取整到 10 分钟，同一用户同一时间窗内的行为视作同一 session。
        df['Date'] = df['Timestamp'].dt.floor('10T')
        df['SessionID'] = df.groupby(['UserId', 'Date']).ngroup() + 1
        return df.sort_values(by=['SessionID', 'UserId', 'Date', 'Timestamp'])
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
        return None
    except Exception as e:
        print(f"Error loading data: {e}")
        return None

def create_sessions(data_df):
    """按 SessionID 分组，按时间顺序还原每条 session 的电影点击序列。"""
    result_list = []
    grouped = data_df.groupby('SessionID')
    for session_id, group in grouped:
        sorted_group = group.sort_values(by='Timestamp')
        item_id_list = sorted_group['ItemId'].tolist()
        result_list.append(item_id_list)
    return result_list

def filter_sessions(result_list, min_count=5, min_length=2):
    """过滤低频 item 和过短 session。

    只有出现次数不少于 min_count 的 item 才保留；
    一条 session 中如果包含低频 item，整条 session 会被丢弃。
    """
    flat_list = [item for sublist in result_list for item in sublist]
    count_dict = Counter(flat_list)
    filtered_nums = {num for num, count in count_dict.items() if count >= min_count}
    return [seq for seq in result_list if len(seq) >= min_length and all(num in filtered_nums for num in seq)]

def map_items_to_ids(result_list):
    """将 MovieLens 原始电影 ID 映射为从 1 开始的模型内部 ID。"""
    item_dict = {}
    item_ctr = 1
    handle_seq = []
    for seq in result_list:
        outseq = []
        for item in seq:
            item_str = str(item)
            if item_str in item_dict:
                outseq.append(item_dict[item_str])
            else:
                item_dict[item_str] = item_ctr
                outseq.append(item_ctr)
                item_ctr += 1
        handle_seq.append(outseq)
    return item_dict, handle_seq, item_ctr

def save_item_mapping(item_dict, output_file):
    """保存原始电影 ID 到模型内部 ID 的映射，供名称合并脚本使用。"""
    df_id = pd.DataFrame(list(item_dict.items()), columns=['Global_ID', 'Model_ID'])
    df_id.to_csv(output_file, index=False)

def split_data(handle_seq, split_ratio=0.9):
    """按顺序把 session 列表切分为训练集和测试集。"""
    split_index = int(split_ratio * len(handle_seq))
    return handle_seq[:split_index], handle_seq[split_index:]

def count_clicks(train_seq, test_seq):
    """统计训练集与测试集总点击数。"""
    clicks = sum(len(seq) for seq in train_seq) + sum(len(seq) for seq in test_seq)
    return clicks

def process_sequences(seq_list):
    """把每条 session 转成一个“前缀 -> 最后一个 item”的样本。

    与 Beauty 脚本不同，这里每条 session 只生成一个样本，
    即输入 seq[:-1]，标签 seq[-1]。
    """
    out_seqs = []
    labs = []
    for seq in seq_list:
        if len(seq) > 1:  # Ensure sequence has at least 2 items
            out_seqs.append(seq[:-1])
            labs.append(seq[-1])
    return out_seqs, labs

def compute_avg_sequence_length(train_seqs, test_seqs):
    """计算输入序列平均长度。"""
    total_length = sum(len(seq) for seq in train_seqs) + sum(len(seq) for seq in test_seqs)
    total_seqs = len(train_seqs) + len(test_seqs)
    return total_length / total_seqs if total_seqs > 0 else 0

def load_movie_names(file_path):
    """读取模型内部 ID 到电影名/类型的映射。"""
    id2name_dict = {}
    try:
        with open(file_path, 'r', newline='', encoding='utf-8') as csv_file:
            csv_reader = csv.reader(csv_file)
            next(csv_reader, None)  # Skip header if present
            for row in csv_reader:
                if len(row) >= 3:
                    key, value_1, value_2 = row[0], row[1], row[2]
                    id2name_dict[key] = f"{value_1} -- {value_2}"
        return id2name_dict
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
        return {}
    except Exception as e:
        print(f"Error loading movie names: {e}")
        return {}

def create_prompts(seq_list, id2name_dict):
    """把电影点击序列转换成 LLM prompt。"""
    seqs_text_list = []
    for seq in seq_list:
        seq_texts = "The order in which users click on items is as follows:\n"
        for i, item_id in enumerate(seq, 1):
            item_name = id2name_dict.get(str(item_id), str(item_id))
            seq_texts += f"{i}. {item_name}_{item_id}\n"
        seq_texts += "Please guess an item that the user is interested in in the long-term. (Only output the item name without any explanation.)"
        seqs_text_list.append({"prompt": seq_texts})
    return seqs_text_list

def save_data(data, file_path):
    """保存 pickle 文件，供模型训练脚本读取。"""
    try:
        with open(file_path, 'wb') as f:
            pickle.dump(data, f)
    except Exception as e:
        print(f"Error saving to {file_path}: {e}")

def main():
    """执行 MovieLens-1M 的预处理与测试 prompt 生成流程。"""
    # Load and preprocess data
    data_df = load_and_preprocess_data(RATINGS_FILE)
    if data_df is None:
        return

    # Create and filter sessions
    # 先构造 session，再删除低频 item 和长度不足的 session。
    result_list = create_sessions(data_df)
    result_list = filter_sessions(result_list)
    print("Sample filtered sessions:", result_list[:5])

    # Map items to IDs
    item_dict, handle_seq, item_ctr = map_items_to_ids(result_list)
    print(f"Total unique items: {item_ctr}")
    print("Sample mapped sequences:", handle_seq[:5])

    # Save item mapping
    save_item_mapping(item_dict, GLOBAL_ID_FILE)

    # Save original sequences
    save_data(handle_seq, 'seq_origin.pkl')

    # Split data into train and test
    train_seq, test_seq = split_data(handle_seq)
    print("Sample training sequences:", train_seq[:5])
    print("Sample test sequences:", test_seq[:5])
    print(f"Training sequences: {len(train_seq)}")
    print(f"Test sequences: {len(test_seq)}")

    # Count total clicks
    total_clicks = count_clicks(train_seq, test_seq)
    print(f"Total clicks: {total_clicks}")

    # Process sequences for training and testing
    # tra_seqs/tes_seqs 是模型输入，tra_labs/tes_labs 是下一步预测目标。
    tra_seqs, tra_labs = process_sequences(train_seq)
    tes_seqs, tes_labs = process_sequences(test_seq)
    print("Sample training sequences:", tra_seqs[:10])
    print("Sample training labels:", tra_labs[:10])

    # Compute and print average sequence length
    avg_length = compute_avg_sequence_length(tra_seqs, tes_seqs)
    print(f"Average sequence length: {avg_length:.2f}")

    # Save processed sequences
    save_data((tra_seqs, tra_labs), TRAIN_FILE)
    save_data((tes_seqs, tes_labs), TEST_FILE)
    save_data(train_seq, ALL_TRAIN_SEQ_FILE)

    # Load movie names and create prompts
    # 这里只为测试集生成 long-term prompt；如需训练集或 short-term prompt，需要改路径和模板。
    id2name_dict = load_movie_names(MOVIE_NAME_FILE)
    seqs_text_list = create_prompts(tes_seqs, id2name_dict)

    # Save prompts to JSON
    try:
        with open(TEST_JSON_FILE, 'w', encoding='utf-8') as json_file:
            json.dump(seqs_text_list, json_file, indent=2)
    except Exception as e:
        print(f"Error saving JSON to {TEST_JSON_FILE}: {e}")

if __name__ == "__main__":
    main()
