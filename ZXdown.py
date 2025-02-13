import os
import zipfile
import shutil
import filecmp
import time
import logging
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaDocument
from telethon.sessions import StringSession
import hashlib

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('script.log'),
        logging.StreamHandler()
    ]
)

# 从环境变量中读取配置信息
required_env_vars = ['API_ID', 'API_HASH', 'STRING_SESSION', 'CHANNEL_USERNAME', 'GROUP_USERNAME']
for var in required_env_vars:
    if not os.getenv(var):
        logging.error(f"环境变量 {var} 未配置")
        exit(1)

api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
string_session = os.getenv('STRING_SESSION')
PROXY_HOST = os.getenv('PROXY_HOST', '127.0.0.1')
PROXY_PORT = int(os.getenv('PROXY_PORT', 7890))
proxy = ('socks5', PROXY_HOST, PROXY_PORT)
channel_username = os.getenv('CHANNEL_USERNAME')
group_username = os.getenv('GROUP_USERNAME')

# 获取当前py文件所在的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
zxdown_dir = os.path.join(current_dir, 'zxdown')
zxdown_lib_dir = os.path.join(zxdown_dir, 'lib')
zx_updated_files_dir = os.path.join(current_dir, 'zx_updated_files')  # 修改后的更新文件目录名称

logging.info(f"当前目录：{current_dir}")
logging.info(f"zxdown目录：{zxdown_dir}")
logging.info(f"zxdown_lib目录：{zxdown_lib_dir}")
logging.info(f"更新文件目录：{zx_updated_files_dir}")

# 创建Telegram客户端
client = TelegramClient(StringSession(string_session), api_id, api_hash, proxy=proxy)

def extract_zip_with_timestamps(zip_path, extract_to):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for zip_info in zip_ref.infolist():
            zip_ref.extract(zip_info, extract_to)
            file_path = os.path.join(extract_to, zip_info.filename)
            mod_time = time.mktime(zip_info.date_time + (0, 0, -1))
            os.utime(file_path, (mod_time, mod_time))

def copy_with_timestamps(src, dst):
    shutil.copy2(src, dst)
    src_stat = os.stat(src)
    os.utime(dst, (src_stat.st_atime, src_stat.st_mtime))

def file_hash(file_path):
    with open(file_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

async def main():
    logging.info("开始获取频道最新消息...")

    # 创建更新文件目录
    if not os.path.exists(zx_updated_files_dir):
        os.makedirs(zx_updated_files_dir)
        logging.info(f"更新文件目录已创建：{zx_updated_files_dir}")
    else:
        logging.info(f"更新文件目录已存在：{zx_updated_files_dir}")

    # 获取频道最新消息
    async for message in client.iter_messages(channel_username, limit=1):
        if message.media:
            attachment_name = message.file.name
            logging.info(f"获取到最新消息的附件名称：{attachment_name}")
            zip_files = [f for f in os.listdir(current_dir) if f.endswith('.zip')]
            if attachment_name in zip_files:
                logging.info("附件名称与当前目录内的zip文件名称一致，无需更新，脚本退出。")
                return

            logging.info("附件名称与当前目录内的zip文件名称不一致，开始下载...")
            await message.download_media(file=os.path.join(current_dir, attachment_name))
            logging.info(f"附件下载完成，保存路径：{os.path.join(current_dir, attachment_name)}")

            if not os.path.exists(zxdown_dir):
                os.makedirs(zxdown_dir)
                logging.info(f"创建了新的./zxdown目录：{zxdown_dir}")
            else:
                logging.info(f"保留旧的./zxdown目录：{zxdown_dir}")

            extract_zip_with_timestamps(os.path.join(current_dir, attachment_name), zxdown_dir)
            logging.info(f"附件已解压到./zxdown目录内，保留了文件的原始修改日期")

            for old_zip in zip_files:
                if old_zip != attachment_name:
                    os.remove(os.path.join(current_dir, old_zip))
                    logging.info(f"旧的zip文件已删除：{old_zip}")

            update_files = []
            current_files = [f for f in os.listdir(zx_updated_files_dir) if f not in [os.path.basename(__file__), attachment_name]]

            if not current_files:
                logging.info("更新文件目录内没有其它文件，开始拷贝所有文件...")
                copy_with_timestamps(os.path.join(zxdown_dir, 'custom_spider.jar'), zx_updated_files_dir)
                update_files.append('custom_spider.jar')
                for file in os.listdir(zxdown_lib_dir):
                    if not file.endswith('.md5'):
                        copy_with_timestamps(os.path.join(zxdown_lib_dir, file), zx_updated_files_dir)
                        update_files.append(file)
            else:
                logging.info("更新文件目录内有其它文件，开始进行对比和更新...")
                if not os.path.exists(os.path.join(zx_updated_files_dir, 'custom_spider.jar')) or \
                   file_hash(os.path.join(zxdown_dir, 'custom_spider.jar')) != file_hash(os.path.join(zx_updated_files_dir, 'custom_spider.jar')):
                    copy_with_timestamps(os.path.join(zxdown_dir, 'custom_spider.jar'), zx_updated_files_dir)
                    update_files.append('custom_spider.jar')
                for file in os.listdir(zxdown_lib_dir):
                    if not file.endswith(('.md5', '.txt')):
                        if not os.path.exists(os.path.join(zx_updated_files_dir, file)) or \
                           file_hash(os.path.join(zxdown_lib_dir, file)) != file_hash(os.path.join(zx_updated_files_dir, file)):
                            copy_with_timestamps(os.path.join(zxdown_lib_dir, file), zx_updated_files_dir)
                            update_files.append(file)

            attachment_info = f"真心最新版本：{attachment_name}\n"
            update_info = f"更新的文件有：{', '.join(update_files)}\n" if update_files else "无文件更新\n"
            content_info = message.text.split('更新内容', 1)[1] if '更新内容' in message.text else "无更新内容"
            await client.send_message(group_username, attachment_info + update_info + content_info)
            logging.info(f"更新信息已转发到群组：{group_username}")

with client:
    client.loop.run_until_complete(main())
    logging.info("脚本执行完毕")
