import csv

# Beauty 商品名称映射脚本：
# globalId2modelId.csv 保存“原始商品 ID -> 模型内部 ID”，
# products_lookup.csv 保存“原始商品 ID -> 商品名”，
# 本脚本把二者合并成 “模型内部 ID -> 商品名” 的 modelId_name.csv。

# File paths
GLOBAL_ID_TO_MODEL_ID_FILE = 'globalId2modelId.csv'
PRODUCTS_LOOKUP_FILE = 'products_lookup.csv'
OUTPUT_FILE = 'modelId_name.csv'


def load_mapping(csv_file_path):
    """从 products_lookup.csv 读取原始商品 ID 到商品名的映射。"""
    mapping = {}
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            if 'global_product_id' not in csv_reader.fieldnames or 'name' not in csv_reader.fieldnames:
                raise ValueError("Required columns (global_product_id, name) not found in CSV.")
            for row in csv_reader:
                mapping[row['global_product_id']] = row['name']
        return mapping
    except FileNotFoundError:
        print(f"Error: File {csv_file_path} not found.")
        return {}
    except Exception as e:
        print(f"Error loading mapping from {csv_file_path}: {e}")
        return {}


def find_name_from_mapping(global_id, mapping):
    """根据原始商品 ID 查询商品名；查不到时返回 None。"""
    return mapping.get(global_id, None)


def create_model_name_dict(global_id_file, mapping_file):
    """合并两个 CSV，生成模型内部 ID 到商品名的字典。"""
    model_name_dict = {}
    try:
        with open(global_id_file, 'r', encoding='utf-8') as data_csv_file:
            data_reader = csv.DictReader(data_csv_file)
            if 'Global_ID' not in data_reader.fieldnames or 'Model_ID' not in data_reader.fieldnames:
                raise ValueError("Required columns (Global_ID, Model_ID) not found in CSV.")

            # Load mapping only once to avoid redundant file reads
            # 商品名映射较大，提前加载一次可以避免每行重复读文件。
            mapping = load_mapping(mapping_file)
            if not mapping:
                print("Error: Empty mapping returned. Cannot proceed.")
                return model_name_dict

            for row in data_reader:
                global_id = row['Global_ID']
                model_id = row['Model_ID']
                name = find_name_from_mapping(global_id, mapping)
                # 如果原始商品名缺失，仍写入 Unknown_xxx，避免下游 prompt 生成时 KeyError。
                model_name_dict[model_id] = name if name is not None else f"Unknown_{global_id}"

                # Optional: Print mapping details
                # if name is not None:
                #     print(f"Model_id: {model_id}, Global ID: {global_id}, Name: {name}")
                # else:
                #     print(f"Model_id: {model_id}, Global ID: {global_id}, Name not found")

        return model_name_dict
    except FileNotFoundError:
        print(f"Error: File {global_id_file} not found.")
        return {}
    except Exception as e:
        print(f"Error processing {global_id_file}: {e}")
        return {}


def save_model_name_dict(model_name_dict, output_file):
    """将模型内部 ID 到商品名的映射保存成 CSV。"""
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(['Model_ID', 'name'])
            for model_id, name in model_name_dict.items():
                csv_writer.writerow([model_id, name])
        print(f"Successfully saved model ID to name mapping to {output_file}")
    except Exception as e:
        print(f"Error saving to {output_file}: {e}")


def main():
    """主流程：生成并保存 Beauty 的 modelId_name.csv。"""
    # Create model ID to name dictionary
    model_name_dict = create_model_name_dict(GLOBAL_ID_TO_MODEL_ID_FILE, PRODUCTS_LOOKUP_FILE)
    print(f"Total mappings created: {len(model_name_dict)}")

    # Save to CSV
    save_model_name_dict(model_name_dict, OUTPUT_FILE)


if __name__ == "__main__":
    main()
