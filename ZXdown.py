import os
import zipfile
import shutil
import filecmp
import time
import logging
from datetime import datetime
from telethon import TelegramClient, events
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
PROXY_HOST = os.getenv('PROXY_HOST', '127.0.0.1')
PROXY_PORT = int(os.getenv('PROXY_PORT', 7890))
proxy = ('socks5', PROXY_HOST, PROXY_PORT) if PROXY_HOST and PROXY_PORT else None
channel_username = os.getenv('CHANNEL_USERNAME')
group_username = os.getenv('GROUP_USERNAME')

# 获取当前py文件所在的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
zxdown_dir = os.path.join(current_dir, 'zxdown')
zxdown_lib_dir = os.path.join(zxdown_dir, 'lib')
zx_updated_files_dir = os.path.join(current_dir, 'zx_updated_files')

logger.info(f"当前目录：{current_dir}")
logger.info(f"zxdown目录：{zxdown_dir}")
logger.info(f"zxdown_lib目录：{zxdown_lib_dir}")
logger.info(f"更新文件目录：{zx_updated_files_dir}")

# 创建Telegram客户端
client = TelegramClient(
    StringSession(string_session),
    api_id, api_hash,
    proxy=None
)

def extract_zip_with_timestamps(zip_path, extract_to):
    """解压ZIP文件并保留时间戳，处理中文文件名乱码"""
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for zip_info in zip_ref.infolist():
            # 处理文件名编码问题
            original_filename = zip_info.filename
            try:
                # 尝试UTF-8解码
                file_name = original_filename.encode('utf-8').decode('utf-8')
            except UnicodeDecodeError:
                try:
                    # 尝试CP437解码后转为GBK
                    file_name = original_filename.encode('cp437').decode('gbk')
                except Exception as e:
                    logger.warning(f"文件名解码失败，使用原始名称: {original_filename}, 错误: {e}")
                    file_name = original_filename

            # 构建完整解压路径
            target_path = os.path.join(extract_to, file_name)
            if os.path.sep in file_name:
                # 创建必要的目录
                parent_dir = os.path.dirname(target_path)
                os.makedirs(parent_dir, exist_ok=True)

            # 解压文件并保留元数据
            zip_ref.extract(zip_info, extract_to)
            
            # 处理可能的名称不一致问题
            extracted_path = os.path.join(extract_to, original_filename)
            if os.path.exists(extracted_path) and extracted_path != target_path:
                os.rename(extracted_path, target_path)
                logger.info(f"重命名文件: {original_filename} -> {file_name}")

            # 设置正确的时间戳
            if zip_info.date_time:
                try:
                    dt = datetime(*zip_info.date_time)
                    mod_time = dt.timestamp()
                    os.utime(target_path, (mod_time, mod_time))
                except Exception as e:
                    logger.error(f"设置时间戳失败: {target_path}, 错误: {e}")

def sync_dirs(src, dst):
    """同步两个目录，保留时间戳"""
    if not os.path.exists(dst):
        os.makedirs(dst)
    
    dcmp = filecmp.dircmp(src, dst)
    # 处理新增或修改的文件
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
        sync_dirs(
            os.path.join(src, sub_dir),
            os.path.join(dst, sub_dir)
        )

async def main():
    try:
        logger.info("启动Telegram客户端...")
        await client.start()
        
        # 创建必要目录
        os.makedirs(zx_updated_files_dir, exist_ok=True)
        os.makedirs(zxdown_dir, exist_ok=True)

        logger.info("获取频道最新消息...")
        async for message in client.iter_messages(channel_username, limit=1):
            if not message.media or not isinstance(message.media, MessageMediaDocument):
                logger.warning("最新消息没有文档附件")
                return

            attachment = message.file
            if not attachment.name.lower().endswith('.zip'):
                logger.warning("附件不是ZIP文件")
                return

            zip_name = attachment.name
            # 检查文件名是否包含“真心”
            if "真心" not in zip_name:
                logger.info(f"文件名不包含'真心'，跳过下载：{zip_name}")
                return

            local_zip = os.path.join(current_dir, zip_name)

            # 检查是否已存在相同文件
            if os.path.exists(local_zip):
                logger.info("本地已存在最新版本，无需更新")
                return

            # 下载ZIP文件
            logger.info(f"开始下载 {zip_name}...")
            await message.download_media(file=local_zip)
            logger.info(f"下载完成，保存至 {local_zip}")

            # 解压文件
            logger.info("开始解压文件...")
            extract_zip_with_timestamps(local_zip, zxdown_dir)
            
            # 同步到更新目录
            logger.info("同步文件到更新目录...")
            sync_dirs(zxdown_dir, zx_updated_files_dir)

            # 可选：发送通知到群组
            if group_username:
                await client.send_message(
                    group_username,
                    f"✅ 已成功更新文件库\n版本: {zip_name[:-4]}\n更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                logger.info("已发送更新通知到群组")

            # 清理旧版本（保留最近3个版本）
            zip_files = sorted(
                [f for f in os.listdir(current_dir) if f.endswith('.zip')],
                key=lambda f: os.path.getmtime(os.path.join(current_dir, f)),
                reverse=True
            )
            for old_zip in zip_files[3:]:
                os.remove(os.path.join(current_dir, old_zip))
                logger.info(f"清理旧版本: {old_zip}")

    except Exception as e:
        logger.error(f"程序运行出错: {str(e)}")
        raise
    finally:
        await client.disconnect()

if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())
