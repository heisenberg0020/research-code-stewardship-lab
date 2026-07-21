import pandas as pd

# MovieLens 电影名称映射脚本：
# movies.dat 提供原始 MovieLens 电影 ID、电影名和类型；
# globalId2ModelId.csv 提供原始 ID 到模型内部 ID 的映射；
# 本脚本合并二者，生成 modelId_name.csv，供 prompt 生成脚本使用。

# File paths
MOVIES_FILE = 'movies.dat'
GLOBAL_ID_FILE = 'globalId2ModelId.csv'
OUTPUT_FILE = 'modelId_name.csv'


def load_movies_data(file_path):
    """读取 movies.dat，得到原始电影 ID、电影名和类型。"""
    columns = ['id', 'movie_name', 'genres']
    try:
        # MovieLens-1M 的 dat 文件使用 :: 分隔，编码通常为 latin-1。
        df = pd.read_csv(file_path, sep='::', engine='python', header=None, names=columns, encoding='latin-1')
        print("First 10 rows of movies data:")
        print(df.head(10))
        return df
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
        return None
    except Exception as e:
        print(f"Error loading movies data: {e}")
        return None


def load_global_id_mapping(file_path):
    """读取原始电影 ID 到模型内部 ID 的映射。"""
    try:
        df = pd.read_csv(file_path)
        return df
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
        return None
    except Exception as e:
        print(f"Error loading global ID mapping: {e}")
        return None


def merge_and_save_data(movies_df, global_id_df, output_file):
    """把电影元数据和 ID 映射合并，并保存为 modelId_name.csv。"""
    if movies_df is None or global_id_df is None:
        print("Error: Cannot proceed with merging due to missing data.")
        return

    try:
        # Merge dataframes
        # left_on/right_on 指定原始电影 ID 字段；how='left' 保留 movies_df 中所有电影。
        merged_df = pd.merge(movies_df, global_id_df, left_on='id', right_on='Global_ID', how='left')
        result_df = merged_df[['Model_ID', 'movie_name', 'genres']]

        # Save to CSV
        result_df.to_csv(output_file, index=False)
        print(f"Successfully saved merged data to {output_file}")
    except Exception as e:
        print(f"Error during merging or saving: {e}")


def main():
    """主流程：读取 MovieLens 元数据，合并内部 ID，保存可读名称表。"""
    # Load data
    movies_df = load_movies_data(MOVIES_FILE)
    global_id_df = load_global_id_mapping(GLOBAL_ID_FILE)

    # Merge and save
    merge_and_save_data(movies_df, global_id_df, OUTPUT_FILE)


if __name__ == "__main__":
    main()
