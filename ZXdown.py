import os
import zipfile
import shutil
import filecmp
import logging
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import MessageMediaDocument
from telethon.sessions import StringSession

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 从环境变量中读取配置信息
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
string_session = os.getenv('STRING_SESSION')
channel_username = os.getenv('CHANNEL_USERNAME')
group_username = os.getenv('GROUP_USERNAME')

# 目录配置
current_dir = os.path.dirname(os.path.abspath(__file__))
zxdown_dir = os.path.join(current_dir, 'zxdown')
zx_updated_files_dir = os.path.join(current_dir, 'zx_updated_files')

logger.info(f"当前目录：{current_dir}")
logger.info(f"zxdown目录：{zxdown_dir}")
logger.info(f"更新文件目录：{zx_updated_files_dir}")

# 创建Telegram客户端
client = TelegramClient(StringSession(string_session), api_id, api_hash)

def decode_filename(zip_info):
    """
    解码 ZIP 文件名，优先检测 ZIP 的 EFS 标志（UTF-8 编码），
    若无则尝试常见编码组合
    """
    original = zip_info.filename
    # 检查 EFS 标志（0x800），表示使用 UTF-8
    if zip_info.flag_bits & 0x800:
        try:
            return original.encode('utf-8').decode('utf-8')
        except UnicodeDecodeError:
            pass

    # 常见编码组合尝试列表（按优先级排序）
    encodings = [
        ('cp437', 'gbk'),      # Windows 简体中文
        ('cp437', 'big5'),     # 繁体中文
        ('cp932', 'shift_jis'),# 日文
        ('iso-8859-1', 'gbk'),
        ('iso-8859-1', 'big5'),
        ('gb18030', 'gb18030') # 更全面的中文编码
    ]

    for src_enc, dst_enc in encodings:
        try:
            # 处理特殊字符（如无法转换的字节用替换字符忽略）
            return original.encode(src_enc).decode(dst_enc, errors='replace')
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue

    # 最终尝试使用 UTF-8 并忽略错误
    try:
        return original.encode('utf-8').decode('utf-8', errors='replace')
    except UnicodeDecodeError:
        return original  # 保底返回原始名称

def extract_zip_with_timestamps(zip_path, extract_to):
    """解压 ZIP 文件并修复中文乱码"""
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for zip_info in zip_ref.infolist():
            # 解码文件名
            decoded_name = decode_filename(zip_info)
            logger.info(f"原始文件名: {zip_info.filename} → 解码后: {decoded_name}")

            # 构建安全路径（防止目录穿越）
            safe_name = os.path.normpath(decoded_name).lstrip(os.sep)
            target_path = os.path.join(extract_to, safe_name)

            # 创建父目录
            parent_dir = os.path.dirname(target_path)
            os.makedirs(parent_dir, exist_ok=True)

            # 解压并重命名（解决编码不一致问题）
            extracted_temp = zip_ref.extract(zip_info, extract_to)
            
            # 如果临时文件名与目标不同，则重命名
            if os.path.abspath(extracted_temp) != os.path.abspath(target_path):
                shutil.move(extracted_temp, target_path)
                logger.info(f"重命名: {os.path.basename(extracted_temp)} → {safe_name}")

            # 设置时间戳（精确到秒）
            if zip_info.date_time:
                try:
                    dt = datetime(*zip_info.date_time)
                    mod_time = dt.timestamp()
                    os.utime(target_path, (mod_time, mod_time))
                except Exception as e:
                    logger.error(f"时间戳设置失败: {target_path}, 错误: {e}")

def sync_dirs(src, dst):
    """同步目录并保留时间戳"""
    if not os.path.exists(dst):
        os.makedirs(dst)
    
    dcmp = filecmp.dircmp(src, dst)
    # 处理新增/修改文件
    for file in dcmp.diff_files + dcmp.left_only:
        src_path = os.path.join(src, file)
        dst_path = os.path.join(dst, file)
        if os.path.isdir(src_path):
            shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
        else:
            shutil.copy2(src_path, dst_path)
        logger.info(f"同步文件: {file}")

    # 递归处理子目录
    for sub_dir in dcmp.common_dirs:
        sync_dirs(os.path.join(src, sub_dir), os.path.join(dst, sub_dir))

def parse_date_from_filename(filename):
    """从文件名中提取日期部分并转换为日期对象"""
    import re
    date_pattern = r'真心(\d{8})'
    match = re.search(date_pattern, filename)
    if match:
        date_str = match.group(1)
        try:
            return datetime.strptime(date_str, '%Y%m%d')
        except ValueError:
            logger.warning(f"无法解析文件名中的日期: {filename}")
    return None

async def main():
    try:
        logger.info("启动Telegram客户端...")
        await client.start()
        
        # 创建必要目录
        os.makedirs(zx_updated_files_dir, exist_ok=True)
        os.makedirs(zxdown_dir, exist_ok=True)

        logger.info("开始扫描频道消息...")
        latest_zip = None
        latest_date = None
        latest_msg_id = None

        async for message in client.iter_messages(channel_username, reverse=True):
            # 仅处理包含文档附件的消息
            if not message.media or not isinstance(message.media, MessageMediaDocument):
                continue

            attachment = message.file
            if not attachment.name.lower().endswith('.zip'):
                continue

            zip_name = attachment.name
            logger.info(f"发现ZIP文件: {zip_name}")

            # 检查文件名是否符合要求
            if not (zip_name.startswith("真心") and '"' not in zip_name):
                logger.info(f"文件不符合要求，跳过处理。要求：以'真心'开头且不含双引号")
                continue

            # 提取文件名中的日期
            file_date = parse_date_from_filename(zip_name)
            if not file_date:
                logger.warning(f"无法提取日期，跳过文件: {zip_name}")
                continue

            # 记录最新的文件及其消息ID
            if (latest_date is None) or (file_date > latest_date):
                latest_zip = zip_name
                latest_date = file_date
                latest_msg_id = message.id
                logger.info(f"找到更新的文件: {zip_name}，日期: {file_date.strftime('%Y-%m-%d')}，消息ID: {latest_msg_id}")

        if not latest_zip:
            logger.info("未找到符合条件的文件，退出脚本")
            return

        local_zip = os.path.join(current_dir, latest_zip)

        # 检查是否已存在相同文件
        if os.path.exists(local_zip):
            logger.info("本地已存在最新版本，无需更新")
            return

        # 使用消息ID直接获取消息
        if latest_msg_id is not None:
            logger.info(f"获取消息ID: {latest_msg_id} 对应的消息...")
            message = await client.get_messages(channel_username, ids=latest_msg_id)
            if message and message.media and isinstance(message.media, MessageMediaDocument):
                # 下载文件
                logger.info(f"开始下载最新文件: {latest_zip}")
                await message.download_media(file=local_zip)
                logger.info(f"文件已保存至: {local_zip}")
            else:
                logger.error(f"无法获取消息ID: {latest_msg_id} 的消息内容")
                return
        else:
            logger.error("未找到有效消息ID，无法下载文件")
            return

        # 解压文件
        logger.info("开始解压...")
        extract_zip_with_timestamps(local_zip, zxdown_dir)
        
        # 同步到更新目录
        logger.info("同步文件到更新目录...")
        sync_dirs(zxdown_dir, zx_updated_files_dir)

        # 发送通知（可选）
        if group_username:
            await client.send_message(
                group_username,
                f"✅ 已下载最新文件\n文件名: {latest_zip}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            logger.info("已发送通知到群组")

        # 清理旧版本（保留最近3个）
        zip_files = sorted(
            [f for f in os.listdir(current_dir) if f.endswith('.zip')],
            key=lambda f: os.path.getmtime(os.path.join(current_dir, f)),
            reverse=True
        )
        for old_zip in zip_files[3:]:
            file_path = os.path.join(current_dir, old_zip)
            os.remove(file_path)
            logger.info(f"已清理旧版本: {old_zip}")

    except Exception as e:
        logger.error(f"运行时错误: {str(e)}")
        raise
    finally:
        await client.disconnect()

if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())
