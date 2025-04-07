import json
import os
import time

def remove_json_comments(text):
    """移除 JSON 内容中的注释（// 开头的行内和整行注释）"""
    in_string = False
    escape = False
    result = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == '"' and not escape:
            in_string = not in_string
            result.append(c)
        elif not in_string and c == '/' and (i + 1 < n) and text[i+1] == '/':
            while i < n and text[i] not in ('\n', '\r'):
                i += 1
            continue
        else:
            if c == '\\':
                escape = not escape
            else:
                escape = False
            result.append(c)
        i += 1
    return ''.join(result)

def load_json(file_path, strip_comments=False):
    """加载 JSON 文件，可选去除注释"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件未找到: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
        if strip_comments:
            content = remove_json_comments(content)
        return json.loads(content)

def update_json(base_json, sites_data, lives_data, version):
    """更新 JSON 数据（version字段前置，新数据前置）"""
    # 创建新字典确保version成为首个字段
    updated_json = {"version": version}
    # 合并原字典的其他字段
    for key, value in base_json.items():
        if key not in ["version"]:
            updated_json[key] = value
    
    # 处理数组合并（新数据前置）
    if sites_data:
        updated_json["sites"] = sites_data + base_json.get("sites", [])
    if lives_data:
        updated_json["lives"] = lives_data + base_json.get("lives", [])
    
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
    """保存 JSON 文件（保持字典顺序）"""
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def get_latest_zip_file(directory):
    """获取最新的以 真心 开头的 ZIP 文件"""
    zip_files = [f for f in os.listdir(directory) if f.startswith("真心") and f.endswith(".zip")]
    if not zip_files:
        return None, None
    latest_file = max(zip_files, key=lambda f: os.path.getmtime(os.path.join(directory, f)))
    version = latest_file[len("真心"):-len(".zip")]
    return latest_file, version

def check_zip_updated(zip_file, last_modified_file="last_modified.txt"):
    """检查 ZIP 文件是否有更新"""
    if not os.path.exists(last_modified_file):
        return True
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

    pei_in_data = load_json(pei_in_path)
    peizhi_data = load_json(peizhi_path, strip_comments=True)

    for key, value in pei_in_data.items():
        peizhi_data[key] = value

    save_json(peizhi1_path, peizhi_data)

def main():
    base_path = os.path.dirname(os.path.abspath(__file__))
    zxdown_dir = os.path.join(base_path, "zxdown")
    jsm_path = os.path.join(zxdown_dir, "FongMi.json")
    sites_path = os.path.join(zxdown_dir, "sites.json")
    lives_path = os.path.join(zxdown_dir, "lives.json")
    output_path = os.path.join(zxdown_dir, "t1.json")  # 修改输出文件名

    if not os.path.exists(zxdown_dir):
        os.makedirs(zxdown_dir)

    zip_file, version = get_latest_zip_file(base_path)
    if not zip_file:
        print("未找到以 真心 开头的 ZIP 文件。")
        return

    if not check_zip_updated(os.path.join(base_path, zip_file)):
        print(f"ZIP 文件 {zip_file} 未更新，跳过任务。")
        return

    try:
        # 加载基础配置（保留注释处理）
        base_json = load_json(jsm_path, strip_comments=True)
        
        # 加载新数据
        sites_data = load_json(sites_path)["sites"]
        lives_data = load_json(lives_path)["lives"]

        # 合并数据（关键修改点）
        updated_json = update_json(base_json, sites_data, lives_data, version)
        final_json = replace_version(updated_json, version)
        final_json = replace_peizhi_in_t1(final_json)

        # 保存结果
        save_json(output_path, final_json)
        print(f"t1.json 生成成功：{output_path}")

        # 更新记录文件
        update_last_modified(os.path.join(base_path, zip_file))
        update_peizhi_with_pei_in(base_path)
        
    except Exception as e:
        print(f"处理异常：{str(e)}")

if __name__ == "__main__":
    main()
