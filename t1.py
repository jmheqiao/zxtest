import json
import os
import time

def load_json(file_path):
    """加载 JSON 文件"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件未找到: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def update_json(base_json, sites_data, lives_data, version):
    """更新 JSON 数据，将新内容追加到原内容前面，并添加版本号"""
    # 添加版本号
    updated_json = {"version": version}
    # 更新 sites 数据
    if sites_data:
        updated_json["sites"] = sites_data + base_json.get("sites", [])
    # 更新 lives 数据
    if lives_data:
        updated_json["lives"] = lives_data + base_json.get("lives", [])
    # 合并其他字段
    for key, value in base_json.items():
        if key not in ["sites", "lives"]:
            updated_json[key] = value
    return updated_json

def replace_version(data, version):
    """递归替换数据中的 "版本号" 为实际版本号"""
    if isinstance(data, str):
        return data.replace("版本号", version)
    elif isinstance(data, list):
        return [replace_version(item, version) for item in data]
    elif isinstance(data, dict):
        return {k: replace_version(v, version) for k, v in data.items()}
    return data

def save_json(file_path, data):
    """保存 JSON 文件"""
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def get_latest_zip_file(directory):
    """获取最新的以 真心 开头的 ZIP 文件"""
    zip_files = [f for f in os.listdir(directory) if f.startswith("真心") and f.endswith(".zip")]
    if not zip_files:
        return None, None
    # 按修改时间排序，获取最新的 ZIP 文件
    latest_file = max(zip_files, key=lambda f: os.path.getmtime(os.path.join(directory, f)))
    version = latest_file[len("真心"):-len(".zip")]  # 提取版本号
    return latest_file, version

def check_zip_updated(zip_file, last_modified_file="last_modified.txt"):
    """检查 ZIP 文件是否有更新"""
    if not os.path.exists(last_modified_file):
        return True  # 如果记录文件不存在，说明 ZIP 文件是新的
    with open(last_modified_file, 'r') as file:
        last_modified = float(file.read().strip())
    current_modified = os.path.getmtime(zip_file)
    return current_modified > last_modified

def update_last_modified(zip_file, last_modified_file="last_modified.txt"):
    """更新 ZIP 文件的最后修改时间记录"""
    current_modified = os.path.getmtime(zip_file)
    with open(last_modified_file, 'w') as file:
        file.write(str(current_modified))

def replace_peizhi_in_t1(data):
    """替换 t1.json 中的 peizhi.json 为 peizhi1.json"""
    if isinstance(data, str):
        return data.replace("peizhi.json", "peizhi1.json")
    elif isinstance(data, list):
        return [replace_peizhi_in_t1(item) for item in data]
    elif isinstance(data, dict):
        return {k: replace_peizhi_in_t1(v) for k, v in data.items()}
    return data

def update_peizhi_with_pei_in(base_path):
    """读取 pei_in.json 并更新 peizhi.json 生成 peizhi1.json"""
    pei_in_path = os.path.join(base_path, "zxdown", "json", "pei_in.json")
    peizhi_path = os.path.join(base_path, "zxdown", "json", "peizhi.json")
    peizhi1_path = os.path.join(base_path, "zxdown", "json", "peizhi1.json")

    # 加载 pei_in.json 和 peizhi.json
    pei_in_data = load_json(pei_in_path)
    peizhi_data = load_json(peizhi_path)

    # 更新 peizhi.json 中的键值
    for key, value in pei_in_data.items():
        peizhi_data[key] = value

    # 保存为 peizhi1.json
    save_json(peizhi1_path, peizhi_data)
    print(f"peizhi1.json 文件已生成，保存路径: {peizhi1_path}。")

def main():
    # 设置文件路径
    base_path = os.path.dirname(os.path.abspath(__file__))  # 获取脚本所在目录
    zxdown_dir = os.path.join(base_path, "zxdown")  # 子目录 zxdown
    jsm_path = os.path.join(zxdown_dir, "FongMi.json")
    sites_path = os.path.join(zxdown_dir, "sites.json")
    lives_path = os.path.join(zxdown_dir, "lives.json")
    output_path = os.path.join(zxdown_dir, "t1.json")  # 保存到 zxdown 子目录

    # 如果 zxdown 子目录不存在，则创建
    if not os.path.exists(zxdown_dir):
        os.makedirs(zxdown_dir)

    # 获取最新的 ZIP 文件和版本号
    zip_file, version = get_latest_zip_file(base_path)
    if not zip_file:
        print("未找到以 真心 开头的 ZIP 文件。")
        return

    # 检查 ZIP 文件是否有更新
    if not check_zip_updated(os.path.join(base_path, zip_file)):
        print(f"ZIP 文件 {zip_file} 未更新，跳过任务。")
        return

    try:
        # 加载基础文件 FongMi.json
        base_json = load_json(jsm_path)

        # 加载 sites.json 文件
        sites_data = load_json(sites_path)["sites"]
        print(f"加载 sites.json 数据完成。")  # 提示加载成功

        # 加载 lives.json 文件
        lives_data = load_json(lives_path)["lives"]
        print(f"加载 lives.json 数据完成。")  # 提示加载成功

        # 更新 JSON 数据，并添加版本号
        updated_json = update_json(base_json, sites_data, lives_data, version)

        # 替换生成文件里的 "版本号" 字符串为实际版本号
        final_json = replace_version(updated_json, version)

        # 替换 t1.json 中的 peizhi.json 为 peizhi1.json
        final_json = replace_peizhi_in_t1(final_json)

        # 保存为 t1.json
        save_json(output_path, final_json)
        print(f"t1.json 文件已生成，保存路径: {output_path}。")

        # 更新 ZIP 文件的最后修改时间记录
        update_last_modified(os.path.join(base_path, zip_file))
        print(f"已更新 ZIP 文件 {zip_file} 的最后修改时间记录。")

        # 更新 peizhi.json 生成 peizhi1.json
        update_peizhi_with_pei_in(base_path)
    except FileNotFoundError as e:
        print(f"错误: {e}")
    except json.JSONDecodeError as e:
        print(f"JSON 解析错误: {e}")

if __name__ == "__main__":
    main()