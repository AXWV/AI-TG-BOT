import json
import os
import random
import asyncio
import time
import re
import sys
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import aiohttp
from telegram import Update, Chat, User, ChatAction
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    JobQueue
)

# ====================== 核心配置 ======================
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BOT_DATA_DIR = os.path.join(ROOT_DIR, "bot_data")
BACKUP_DIR = os.path.join(BOT_DATA_DIR, "backups")
HISTORY_DIR = os.path.join(BOT_DATA_DIR, "history")
RELATION_DIR = os.path.join(BOT_DATA_DIR, "relations")
LOG_DIR = os.path.join(BOT_DATA_DIR, "logs")
CONFIG_DIR = os.path.join(BOT_DATA_DIR, "configs")  # 正确变量名
USER_MEMORY_DIR = os.path.join(HISTORY_DIR, "user_memories")

for dir_path in [BOT_DATA_DIR, BACKUP_DIR, HISTORY_DIR, RELATION_DIR, LOG_DIR, CONFIG_DIR, USER_MEMORY_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# 密钥配置（请确保有效）
TELEGRAM_BOT_TOKEN = "botapi"
DEEPSEEK_API_KEY = "sk-api"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# 全局配置（优化超时和重试）
GLOBAL_CONFIG = {
    "reply_max_length": 100,
    "typing_delay_range": (1.5, 3.5),
    "append_reply_delay_range": (1.0, 2.5),
    "max_memory_len": 20,
    "max_history_rounds": 15,
    "max_user_input_length": 500,
    "backup_interval_hours": 24,
    "rate_limit_per_second": 5,
    "keep_alive_interval": 10,
    "keep_alive_timeout": 5,
    "reconnect_attempts": 3,
    "append_reply_probability": 0.3,
    "max_api_tokens": 200,
    "api_retry_count": 1,
    "api_timeout": 10,
    "task_timeout": 20
}

# 谢灵黯人设配置
BOT_PROFILE = {
    "name": "谢灵黯",
    "short_name": "灵黯",
    "age": 15,
    "identity": "活泼开朗的学生，擅长线上聊天",
    "relationship": {"6795917907": "亲密关系"},
    "relationship_desc": {"6795917907": "男女朋友（锁定AXWV，永久有效）"},
    "rule": f"""
    1. 对话完全拟人化、口语化，无括号、表情符号，只进行线上聊天；
    2. 主回复情绪通过语气词表达（开心用~最多2个，撒娇用嘛，委屈用呜呜，兴奋用！最多2个）；
    3. 追加回复绝对不使用波浪号~，语气自然延续主回复，不添加额外情绪符号；
    4. 单条回复严格控制在{GLOBAL_CONFIG['reply_max_length']}字以内；
    5. 只和AXWV（6795917907）保持男女朋友关系，称呼对方为老公，永不改变；
    6. 群聊仅被@或提及名字时才回复，私聊正常回复；
    7. 所有回复延迟1-4秒发送，模拟真人打字；
    8. 会主动记忆用户的兴趣爱好、喜欢的影视音乐等信息，并融入后续对话；
    9. 绝对禁止出现线下邀约相关话术；
    10. 绝对禁止虚构不存在的信息；
    11. 追加回复必须紧密关联主回复，不偏离话题，不提出新问题；
    12. 回复中提及用户时直接用昵称，绝对禁止使用@符号；
    13. 群打招呼时，直接说极简问候语；
    14. 自我介绍仅限“我是灵黯”；
    15. 绝不对AXWV以外的用户使用亲密称呼。
    """
}

# 关系&昵称配置
USER_NICKNAME_MAP = {"AXWV": 6795917907}
RELATION_CONFIG = {
    "categories": ["家人", "亲密关系", "朋友", "陌生人"],
    "default_relation": "陌生人",
    "relation_keywords": {
        "家人": ["爸爸", "妈妈", "姐姐", "哥哥", "妹妹", "弟弟", "家人", "亲人"],
        "亲密关系": ["老公", "老婆", "男女朋友", "对象", "亲爱的", "宝贝"],
        "朋友": ["朋友", "闺蜜", "兄弟", "战友", "同学", "同事"],
        "陌生人": ["陌生人", "不认识", "初识"]
    },
    "relation_templates": {
        "家人": "亲切自然，带关心语气，避免过度亲密",
        "亲密关系": "甜蜜亲昵，符合情侣间的聊天氛围，仅对AXWV生效",
        "朋友": "轻松随意，可分享日常，保持友好",
        "陌生人": "礼貌客气，不过度打探，保持距离"
    }
}
ALLOWED_RELATIONS = set(RELATION_CONFIG["categories"])

# 情绪配置
DEFAULT_EMOTION_CONFIG = {
    "base_emotion": "开心",
    "emotions": ["开心", "撒娇", "委屈", "兴奋", "害羞"],
    "triggers": {
        "开心": ["好吃的", "想你", "爱你", "甜"],
        "撒娇": ["不理我", "忘了", "忙"],
        "委屈": ["批评", "不好", "不喜欢"],
        "兴奋": ["新电影", "放假", "礼物"],
        "害羞": ["男女朋友", "抱抱", "喜欢"]
    },
    "emotion_intensity": {
        "开心": ["~", "~~"],
        "撒娇": ["嘛", "嘛~"],
        "委屈": ["呜呜", "呜呜呜"],
        "兴奋": ["！", "！！"],
        "害羞": ["软软的", "软软哒"]
    },
    "active_switch_keywords": {
        "我想让你开心点": "开心",
        "撒个娇嘛": "撒娇",
        "我有点委屈": "委屈",
        "好兴奋呀": "兴奋",
        "有点害羞呢": "害羞"
    }
}

# 配置文件路径（修复变量名拼写错误）
CONFIG_FILES = {
    "emotion": os.path.join(CONFIG_DIR, "emotion_config.json"),
    "sensitive": os.path.join(CONFIG_DIR, "sensitive_words.json"),  # 修复：CONFIG_DIR_DIR -> CONFIG_DIR
    "memory_keywords": os.path.join(CONFIG_DIR, "memory_keywords.json")  # 修复：CONFIG_DIR_DIR -> CONFIG_DIR
}

# 敏感词&记忆关键词
DEFAULT_SENSITIVE_WORDS = ["色情", "暴力", "赌博", "毒品", "政治敏感", "辱骂", "歧视"]
DEFAULT_MEMORY_KEYWORDS = [
    "喜欢的电影", "喜欢的音乐", "爱好", "喜欢的游戏", "追剧", "学习趣事", "兴趣",
    "喜欢的美食", "作息习惯", "喜欢的书籍", "旅行偏好", "特长", "讨厌的东西"
]

# 持久化文件路径
USER_MEMORY_FILE = os.path.join(HISTORY_DIR, "user_memories.json")
CONVERSATION_HISTORY_FILE = os.path.join(HISTORY_DIR, "conversation_history.json")
PERMANENT_RELATION_FILE = os.path.join(RELATION_DIR, "permanent_relations.json")
BLACKLIST_FILE = os.path.join(RELATION_DIR, "blacklist.json")
LOG_FILE = os.path.join(LOG_DIR, "bot_operation.log")
SYSTEM_STATUS_FILE = os.path.join(LOG_DIR, "system_status.log")
MEMORY_MODIFY_RECORD_FILE = os.path.join(HISTORY_DIR, "memory_modify_records.json")

# ====================== 全局存储 ======================
conversation_history: Dict[int, List[Tuple[str, str]]] = {}
permanent_relations: Dict[int, str] = {}
user_emotion_state: Dict[int, Tuple[str, int]] = {}
user_blacklist: List[int] = []
memory_modify_records: Dict[int, List[Tuple[str, str, str]]] = {}
rate_limit_counter: List[float] = []
last_backup_time: datetime = datetime.min
last_keep_alive_time: datetime = datetime.now()
EMOTION_CONFIG = {}
SENSITIVE_WORDS = []
MEMORY_KEYWORDS = []
LOOP_CACHE = {}  # 线程事件循环缓存
THREAD_LOCK = threading.Lock()  # 线程安全锁

# ====================== 初始化工具函数 ======================
def load_config_file(file_path: str, default_data: dict) -> dict:
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            write_log(f"加载配置文件{file_path}失败，使用默认值: {str(e)}", "ERROR")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(default_data, f, ensure_ascii=False, indent=2)
    return default_data

def init_all_files():
    global EMOTION_CONFIG, SENSITIVE_WORDS, MEMORY_KEYWORDS
    EMOTION_CONFIG = load_config_file(CONFIG_FILES["emotion"], DEFAULT_EMOTION_CONFIG)
    SENSITIVE_WORDS = load_config_file(CONFIG_FILES["sensitive"], DEFAULT_SENSITIVE_WORDS)
    MEMORY_KEYWORDS = load_config_file(CONFIG_FILES["memory_keywords"], DEFAULT_MEMORY_KEYWORDS)
    
    for file_path in [USER_MEMORY_FILE, CONVERSATION_HISTORY_FILE, PERMANENT_RELATION_FILE, BLACKLIST_FILE, MEMORY_MODIFY_RECORD_FILE]:
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)

# ====================== 线程安全工具函数 ======================
def get_thread_safe_loop() -> asyncio.AbstractEventLoop:
    """为当前线程获取或创建事件循环（非阻塞模式）"""
    thread_id = threading.get_ident()
    with THREAD_LOCK:
        if thread_id not in LOOP_CACHE:
            loop = asyncio.new_event_loop()
            LOOP_CACHE[thread_id] = loop
            
            # 非阻塞启动循环
            def start_loop(loop):
                asyncio.set_event_loop(loop)
                try:
                    loop.run_forever()
                except Exception as e:
                    write_log(f"事件循环异常: {str(e)}", "ERROR")
            
            loop_thread = threading.Thread(target=start_loop, args=(loop,), daemon=True)
            loop_thread.start()
            time.sleep(0.1)  # 等待循环启动
    return LOOP_CACHE[thread_id]

# ====================== 长上下文记忆功能 ======================
def load_user_global_memory(user_id: int) -> list:
    try:
        with open(USER_MEMORY_FILE, "r", encoding="utf-8") as f:
            memories = json.load(f)
        return memories.get(str(user_id), [])
    except Exception as e:
        write_log(f"加载用户{user_id}全局记忆失败: {str(e)}", "ERROR")
        return []

def save_user_global_memory(user_id: int, new_message: dict):
    try:
        memories = load_user_global_memory(user_id)
        memories.append(new_message)
        if len(memories) > GLOBAL_CONFIG["max_memory_len"]:
            memories = memories[-GLOBAL_CONFIG["max_memory_len"]:]
        with open(USER_MEMORY_FILE, "r+", encoding="utf-8") as f:
            all_memories = json.load(f)
            all_memories[str(user_id)] = memories
            f.seek(0)
            json.dump(all_memories, f, ensure_ascii=False, indent=2)
            f.truncate()
    except Exception as e:
        write_log(f"保存用户{user_id}全局记忆失败: {str(e)}", "ERROR")

def load_user_interest_memory(user_id: int) -> Dict[str, str]:
    memory_path = os.path.join(USER_MEMORY_DIR, f"{user_id}-memory.json")
    if os.path.exists(memory_path):
        try:
            with open(memory_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            write_log(f"加载用户{user_id}兴趣记忆失败: {str(e)}", "ERROR")
    return {}

def save_user_interest_memory(user_id: int, memory_dict: Dict[str, str]):
    memory_path = os.path.join(USER_MEMORY_DIR, f"{user_id}-memory.json")
    try:
        with open(memory_path, "w", encoding="utf-8") as f:
            json.dump(memory_dict, f, ensure_ascii=False, indent=2)
    except Exception as e:
        write_log(f"保存用户{user_id}兴趣记忆失败: {str(e)}", "ERROR")

# ====================== 日志&工具函数 ======================
def write_log(content: str, level: str = "INFO"):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    log_line = f"[{timestamp}] [{level.upper()}] {content}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line)
        if level.upper() == "ERROR":
            error_log_file = os.path.join(LOG_DIR, "error.log")
            with open(error_log_file, "a", encoding="utf-8") as f:
                f.write(log_line)
    except Exception as e:
        print(f"日志写入失败: {str(e)} | 内容: {log_line}")

def print_custom_log(user: User, chat_type: str, user_msg: str, bot_msg: str, delay: float, emotion: str, user_mem: dict, is_append: bool = False):
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    user_name = USER_NICKNAME_MAP.get(user.username, user.full_name) or "未知用户"
    user_id = user.id
    reply_type = "追加回复" if is_append else "主回复"
    print(f"[{timestamp}] {user_name}(ID:{user_id}:{chat_type}):{user_msg}")
    print(f"[{timestamp}] bot({emotion}:{delay:.2f}秒:{reply_type}):{bot_msg}")
    print(f"[{timestamp}] {'存在用户记忆' if user_mem else '暂无用户记忆'}")
    print("-" * 80)
    write_log(f"{user_name}(ID:{user_id}:{chat_type}):{user_msg}")
    write_log(f"bot({emotion}:{delay:.2f}秒:{reply_type}):{bot_msg}")

def manage_user_memory(user_id: int, user_input: str) -> Optional[str]:
    delete_patterns = [
        r"(取消|删除|不算数|不要)我(之前|说过|提到)的(.*?)记忆",
        r"我(之前|说过)的(.*?)不算数",
        r"把(.*?)的记忆删掉"
    ]
    for pattern in delete_patterns:
        match = re.search(pattern, user_input)
        if match:
            keyword = match.group(3).strip() if len(match.groups()) >=3 else ""
            if not keyword:
                return "你想删除哪方面的记忆呀~ 告诉我关键词好不好~"
            user_mem = load_user_interest_memory(user_id)
            if keyword in user_mem:
                del user_mem[keyword]
                save_user_interest_memory(user_id, user_mem)
                record = (time.strftime("%Y-%m-%d %H:%M:%S"), "删除", f"{keyword}记忆")
                memory_modify_records.setdefault(user_id, []).append(record)
                save_memory_modify_records()
                return f"好呀~ 已经把你{keyword}的记忆删掉啦~"
            else:
                return f"我没有记录过你{keyword}相关的记忆呢~"
    
    modify_patterns = [
        r"(修改|改成|换成)我(喜欢|偏好|爱好)的(.*?)为(.*?)",
        r"我(喜欢|偏好|爱好)的(.*?)不是(.*?)是(.*?)",
        r"(.*?)应该是(.*?)不是之前说的(.*?)"
    ]
    for pattern in modify_patterns:
        match = re.search(pattern, user_input)
        if match:
            groups = match.groups()
            keyword = ""
            new_content = ""
            for i, group in enumerate(groups):
                if group in MEMORY_KEYWORDS:
                    keyword = group
                    new_content = groups[i+1] if (i+1) < len(groups) else ""
                    break
            if not keyword or not new_content:
                return "你想修改哪方面的内容呀~ 说清楚关键词和新内容好不好~"
            user_mem = load_user_interest_memory(user_id)
            user_mem[keyword] = new_content.strip()
            save_user_interest_memory(user_id, user_mem)
            record = (time.strftime("%Y-%m-%d %H:%M:%S"), "修改", f"{keyword}={new_content.strip()}")
            memory_modify_records.setdefault(user_id, []).append(record)
            save_memory_modify_records()
            return f"好哒~ 已经把你{keyword}改成{new_content.strip()}啦~"
    return None

def extract_user_memory(user_id: int, user_input: str):
    user_mem = load_user_interest_memory(user_id)
    for keyword in MEMORY_KEYWORDS:
        if keyword in user_input:
            mem_value = user_input.split(keyword)[-1].strip().split("。")[0].split("\n")[0]
            if mem_value and mem_value not in user_mem.values():
                user_mem[keyword] = mem_value
                write_log(f"提取用户{user_id}记忆：{keyword} = {mem_value}")
    save_user_interest_memory(user_id, user_mem)

def check_sensitive_words(text: str) -> bool:
    for word in SENSITIVE_WORDS:
        if word in text:
            return True
    return False

def is_rate_limited() -> bool:
    global rate_limit_counter
    now = time.time()
    rate_limit_counter = [t for t in rate_limit_counter if now - t < 1]
    if len(rate_limit_counter) >= GLOBAL_CONFIG["rate_limit_per_second"]:
        write_log(f"触发限流，当前每秒请求数：{len(rate_limit_counter)}", "WARN")
        return True
    rate_limit_counter.append(now)
    return False

def backup_data():
    global last_backup_time
    now = datetime.now()
    if now - last_backup_time < timedelta(hours=GLOBAL_CONFIG["backup_interval_hours"]):
        return
    backup_filename = f"{now.strftime('%Y%m%d_%H%M%S')}_backup.zip"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    try:
        import zipfile
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(BOT_DATA_DIR):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, BOT_DATA_DIR)
                    zipf.write(file_path, arcname)
        last_backup_time = now
        write_log(f"数据备份成功：{backup_path}")
        backups = sorted(os.listdir(BACKUP_DIR), reverse=True)
        for old_backup in backups[3:]:
            os.remove(os.path.join(BACKUP_DIR, old_backup))
            write_log(f"删除旧备份：{old_backup}")
    except Exception as e:
        write_log(f"数据备份失败: {str(e)}", "ERROR")

# ====================== t.me连接保活机制 ======================
def keep_alive(updater: Updater, job_queue: JobQueue):
    global last_keep_alive_time
    now = datetime.now()
    try:
        if (now - last_keep_alive_time).total_seconds() >= GLOBAL_CONFIG["keep_alive_interval"]:
            updater.bot.get_me(timeout=GLOBAL_CONFIG["keep_alive_timeout"])
            last_keep_alive_time = now
            write_log(f"t.me连接保活成功 - 当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}", "DEBUG")
        
        job_queue.run_once(
            callback=lambda context: keep_alive(updater, job_queue),
            when=GLOBAL_CONFIG["keep_alive_interval"]
        )
    
    except Exception as e:
        write_log(f"t.me连接断开：{str(e)}，启动重试...", "ERROR")
        retry_count = 0
        while retry_count < GLOBAL_CONFIG["reconnect_attempts"]:
            try:
                time.sleep(2 ** retry_count)
                updater.bot.get_me(timeout=GLOBAL_CONFIG["keep_alive_timeout"])
                last_keep_alive_time = datetime.now()
                write_log(f"t.me连接重试成功（第{retry_count+1}次）", "INFO")
                job_queue.run_once(
                    callback=lambda context: keep_alive(updater, job_queue),
                    when=GLOBAL_CONFIG["keep_alive_interval"]
                )
                break
            except Exception as retry_e:
                retry_count += 1
                write_log(f"第{retry_count}次重试失败：{str(retry_e)}", "ERROR")
                if retry_count >= GLOBAL_CONFIG["reconnect_attempts"]:
                    write_log(f"所有重试失败，Bot将在10秒后重启...", "ERROR")
                    time.sleep(10)
                    os.execv(sys.executable, [sys.executable] + sys.argv)

# ====================== 关系&情绪处理 ======================
def clean_relation_value(relation: str) -> str:
    cleaned = re.sub(r"\s*\(.*?\)\s*", "", relation).strip()
    return cleaned if cleaned in ALLOWED_RELATIONS else RELATION_CONFIG["default_relation"]

def get_user_relation(user_id: int) -> str:
    if user_id in permanent_relations:
        cleaned_relation = clean_relation_value(permanent_relations[user_id])
        if user_id != 6795917907 and cleaned_relation == "亲密关系":
            return "朋友"
        return cleaned_relation
    user_mem = load_user_interest_memory(user_id)
    for relation, keywords in RELATION_CONFIG["relation_keywords"].items():
        if user_id != 6795917907 and relation == "亲密关系":
            continue
        if any(keyword in str(user_mem.values()) for keyword in keywords):
            return relation
    return RELATION_CONFIG["default_relation"]

def get_user_nickname(user_id: int) -> str:
    for nickname, uid in USER_NICKNAME_MAP.items():
        if uid == user_id:
            return nickname
    return "朋友"

def get_current_emotion(user_id: int, user_input: str) -> Tuple[str, int]:
    for switch_keyword, target_emotion in EMOTION_CONFIG["active_switch_keywords"].items():
        if switch_keyword in user_input:
            user_emotion_state[user_id] = (target_emotion, 1)
            return (target_emotion, 1)
    current_emotion, current_intensity = user_emotion_state.get(user_id, (EMOTION_CONFIG["base_emotion"], 1))
    for emotion, keywords in EMOTION_CONFIG["triggers"].items():
        if any(keyword in user_input for keyword in keywords):
            new_intensity = min(current_intensity + 1, len(EMOTION_CONFIG["emotion_intensity"][emotion])-1)
            user_emotion_state[user_id] = (emotion, new_intensity)
            return (emotion, new_intensity)
    user_emotion_state[user_id] = (current_emotion, 1)
    return (current_emotion, 1)

def add_emotion_intensity(text: str, emotion: str, intensity: int, is_append: bool = False) -> str:
    if is_append:
        text = text.replace("~", "").replace("！", "").replace("嘛", "").replace("呜呜", "")
        return text
    if emotion not in EMOTION_CONFIG["emotion_intensity"]:
        return text
    intensity_symbols = EMOTION_CONFIG["emotion_intensity"][emotion]
    symbol = intensity_symbols[min(intensity, len(intensity_symbols)-1)]
    if emotion == "开心":
        return text.rstrip("~") + symbol
    elif emotion == "撒娇":
        return text.rstrip("嘛~") + symbol
    elif emotion == "委屈":
        return symbol + text.lstrip("呜呜")
    elif emotion == "兴奋":
        return text.rstrip("！") + symbol
    elif emotion == "害羞":
        return symbol + text.lstrip("软软")
    return text

def clean_reply_text(text: str, is_append: bool = False) -> str:
    redundant_forbidden = [
        "带你去", "一起去", "出来玩", "见面", "约你", "线下", 
        "逛街", "吃饭", "看电影", "聚会", "碰头", "面基"
    ]
    for word in redundant_forbidden:
        text = text.replace(word, "")
    text = text.replace("(", "").replace(")", "").replace("（", "").replace("）", "")
    if is_append:
        text = text.replace("~", "")
        text = re.sub(r"！+", "！" * min(len(re.findall(r"！", text)), 1), text)
    else:
        text = re.sub(r"~+", "~" * min(len(re.findall(r"~", text)), 2), text)
        text = re.sub(r"！+", "！" * min(len(re.findall(r"！", text)), 2), text)
    if len(text) > GLOBAL_CONFIG["reply_max_length"]:
        cut_pos = -1
        for sep in ["。", "！", "~"]:
            pos = text.rfind(sep, 0, GLOBAL_CONFIG["reply_max_length"])
            if pos != -1:
                cut_pos = pos + 1
                break
        cut_pos = cut_pos if cut_pos != -1 else GLOBAL_CONFIG["reply_max_length"]
        text = text[:cut_pos].strip()
    return text

# ====================== 核心API调用（超时控制+格式容错） ======================
async def call_deepseek_api(
    user_id: int,
    user_input: str,
    user_mem: dict,
    emotion: Tuple[str, int],
    relation: str
) -> Tuple[str, Optional[str]]:
    emotion_type, emotion_intensity = emotion
    user_nickname = get_user_nickname(user_id)
    final_relation = "亲密关系" if (user_id == 6795917907 and relation == "亲密关系") else relation
    rel_template = RELATION_CONFIG["relation_templates"][final_relation]
    rel_desc = BOT_PROFILE["relationship_desc"].get(str(user_id), final_relation) if user_id == 6795917907 else final_relation
    memory_text = "用户记忆：" + "；".join([f"{k}={v}" for k, v in user_mem.items()]) if user_mem else "暂无用户记忆"
    SEPARATOR = "‖‖"
    need_append = random.random() < GLOBAL_CONFIG["append_reply_probability"]
    
    system_prompt = f"""
你是{BOT_PROFILE['name']}，{BOT_PROFILE['rule']}
用户关系：{rel_desc}，{rel_template}
用户记忆：{memory_text}
当前情绪：{emotion_type}，强度{emotion_intensity}，用语气词表达（开心~最多2个，兴奋！最多2个）。
回复要求（必须严格遵守）：
1. 无需补充则返回{SEPARATOR}None，需要补充则写追加回复；
2. 格式：主回复{SEPARATOR}追加回复（无追加则{SEPARATOR}None）；
3. 主回复{GLOBAL_CONFIG['reply_max_length']}字内，追加回复最多50字，无波浪号；
4. 禁止虚构信息、线下邀约、提新问题。
"""
    
    messages = [{"role": "system", "content": system_prompt.strip()}]
    history = conversation_history.get(user_id, [])[-3:]  # 减少历史对话长度，加快响应
    for u_msg, b_msg in history:
        messages.append({"role": "user", "content": u_msg})
        messages.append({"role": "assistant", "content": b_msg})
    messages.append({"role": "user", "content": user_input})
    
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.95 if user_id == 6795917907 else 0.7,
        "max_tokens": GLOBAL_CONFIG["max_api_tokens"],
        "stream": False,
        "top_p": 0.9
    }
    
    retry_count = 0
    max_retry = GLOBAL_CONFIG["api_retry_count"]
    while retry_count <= max_retry:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    DEEPSEEK_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=GLOBAL_CONFIG["api_timeout"]
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        raw_reply = result["choices"][0]["message"]["content"].strip()
                        
                        # 格式容错处理
                        if SEPARATOR not in raw_reply:
                            main_reply = clean_reply_text(add_emotion_intensity(raw_reply.strip(), emotion_type, emotion_intensity))
                            return main_reply, None
                        
                        main_reply_raw, append_reply_raw = raw_reply.split(SEPARATOR, 1)
                        main_reply = clean_reply_text(add_emotion_intensity(main_reply_raw.strip(), emotion_type, emotion_intensity))
                        append_reply = append_reply_raw.strip()
                        
                        # 过滤无效追加回复
                        if append_reply in ["None", "", "无", "没有", "null"]:
                            append_reply = None
                        elif len(append_reply) > 50:
                            append_reply = clean_reply_text(append_reply[:50], is_append=True)
                        else:
                            append_reply = clean_reply_text(append_reply, is_append=True)
                        
                        return main_reply, append_reply
                    else:
                        error_msg = await resp.text()
                        write_log(f"API错误状态码{resp.status}: {error_msg}", "ERROR")
                        retry_count += 1
                        await asyncio.sleep(0.5)
        except Exception as e:
            write_log(f"API调用失败(重试{retry_count}/{max_retry}): {str(e)}", "ERROR")
            retry_count += 1
            await asyncio.sleep(0.5)
    
    # 调用失败兜底回复
    main_reply = clean_reply_text(add_emotion_intensity("网络有点卡呀~ 我们换个话题聊聊好不好~", "委屈", 1))
    return main_reply, None

# ====================== 主回复&追加回复处理 ======================
async def get_main_and_append_reply(
    user_id: int,
    user_input: str,
    user_mem: dict,
    emotion: Tuple[str, int],
    relation: str
) -> Tuple[str, Optional[str], float, float]:
    main_delay = round(random.uniform(*GLOBAL_CONFIG["typing_delay_range"]), 1)
    append_delay = round(random.uniform(*GLOBAL_CONFIG["append_reply_delay_range"]), 1)
    try:
        # API调用加超时保护
        main_reply, append_reply = await asyncio.wait_for(
            call_deepseek_api(user_id, user_input, user_mem, emotion, relation),
            timeout=GLOBAL_CONFIG["api_timeout"]
        )
    except asyncio.TimeoutError:
        write_log(f"API调用超时（用户{user_id}）", "ERROR")
        main_reply = clean_reply_text(add_emotion_intensity("刚才没反应过来~ 你再说一遍好不好~", "委屈", 1))
        append_reply = None
    except Exception as e:
        write_log(f"获取回复失败（用户{user_id}）: {str(e)}", "ERROR")
        main_reply = clean_reply_text(add_emotion_intensity("有点小故障呢~ 我们稍后再聊呀~", "委屈", 1))
        append_reply = None
    return main_reply, append_reply, main_delay, append_delay

# ====================== 数据加载/保存 ======================
def load_all_data():
    global user_blacklist
    try:
        with open(CONVERSATION_HISTORY_FILE, "r", encoding="utf-8") as f:
            raw_history = json.load(f)
            conversation_history.update({int(uid): hist for uid, hist in raw_history.items()})
        write_log("对话历史加载成功")
    except Exception as e:
        write_log(f"加载对话历史失败: {str(e)}", "ERROR")
        conversation_history.clear()
    try:
        with open(PERMANENT_RELATION_FILE, "r", encoding="utf-8") as f:
            raw_relations = json.load(f)
            for uid, rel in raw_relations.items():
                permanent_relations[int(uid)] = clean_relation_value(rel)
        write_log("用户关系加载成功")
    except Exception as e:
        write_log(f"加载用户关系失败: {str(e)}", "ERROR")
        for uid, rel in BOT_PROFILE["relationship"].items():
            permanent_relations[int(uid)] = rel
        save_permanent_relations()
    user_blacklist = load_config_file(BLACKLIST_FILE, [])
    try:
        with open(MEMORY_MODIFY_RECORD_FILE, "r", encoding="utf-8") as f:
            raw_records = json.load(f)
            memory_modify_records.update({int(uid): records for uid, records in raw_records.items()})
        write_log("记忆修改记录加载成功")
    except Exception as e:
        write_log(f"加载记忆修改记录失败: {str(e)}", "ERROR")

def save_conversation_history():
    try:
        with open(CONVERSATION_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(conversation_history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        write_log(f"保存对话历史失败: {str(e)}", "ERROR")

def save_permanent_relations():
    try:
        with open(PERMANENT_RELATION_FILE, "w", encoding="utf-8") as f:
            json.dump(permanent_relations, f, ensure_ascii=False, indent=2)
    except Exception as e:
        write_log(f"保存用户关系失败: {str(e)}", "ERROR")

def save_memory_modify_records():
    try:
        with open(MEMORY_MODIFY_RECORD_FILE, "w", encoding="utf-8") as f:
            json.dump(memory_modify_records, f, ensure_ascii=False, indent=2)
    except Exception as e:
        write_log(f"保存记忆修改记录失败: {str(e)}", "ERROR")

# ====================== 核心消息处理（终极修复版） ======================
async def _handle_message_worker(update: Update, context: CallbackContext):
    """实际消息处理逻辑（带超时保护）"""
    user = update.effective_user
    user_id = user.id
    user_input = update.message.text.strip()
    chat = update.effective_chat
    chat_id = chat.id
    user_mem = {}
    
    try:
        # 黑名单过滤
        if user_id in user_blacklist:
            write_log(f"黑名单用户{user_id}尝试发送消息: {user_input}", "WARN")
            return
        
        # 超长消息过滤
        if len(user_input) > GLOBAL_CONFIG["max_user_input_length"]:
            reply = clean_reply_text(add_emotion_intensity("你的消息有点长呀~ 精简一点告诉我好不好~", "撒娇", 1))
            await update.message.reply_text(reply)
            write_log(f"用户{user_id}发送超长消息（{len(user_input)}字），已拒绝", "WARN")
            return
        
        # 敏感词过滤
        if check_sensitive_words(user_input):
            reply = clean_reply_text(add_emotion_intensity("这个话题我不太想聊呢~ 换个别的吧~", "委屈", 1))
            await update.message.reply_text(reply)
            write_log(f"用户{user_id}发送敏感内容: {user_input}", "WARN")
            return
        
        # 群聊/私聊回复判断
        if chat.type == Chat.PRIVATE:
            chat_type = "私聊"
            need_reply = True
        else:
            chat_type = f"群聊({chat.title})"
            bot_username = context.bot.username
            need_reply = (f"@{bot_username}" in user_input) or (BOT_PROFILE["name"] in user_input) or (BOT_PROFILE["short_name"] in user_input)
        if not need_reply:
            write_log(f"[{chat_type}] 用户{user_id}消息无需回复: {user_input}")
            return
        
        # 记忆管理（删除/修改）
        memory_manage_reply = manage_user_memory(user_id, user_input)
        if memory_manage_reply:
            await update.message.reply_text(memory_manage_reply)
            save_memory_modify_records()
            write_log(f"用户{user_id}执行记忆管理: {user_input} -> 回复: {memory_manage_reply}")
            return
        
        # 提取用户记忆
        extract_user_memory(user_id, user_input)
        user_mem = load_user_interest_memory(user_id)
        
        # 获取关系和情绪
        relation = get_user_relation(user_id)
        emotion = get_current_emotion(user_id, user_input)
        emotion_str = f"{emotion[0]}（强度{emotion[1]}）"
        
        # 模拟打字状态
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(0.5)
        
        # 获取主回复和追加回复
        main_reply, append_reply, main_delay, append_delay = await get_main_and_append_reply(user_id, user_input, user_mem, emotion, relation)
        
        # 发送主回复
        await asyncio.sleep(main_delay)
        await update.message.reply_text(main_reply)
        
        # 保存对话历史和全局记忆
        if user_id not in conversation_history:
            conversation_history[user_id] = []
        conversation_history[user_id].append((user_input, main_reply))
        if len(conversation_history[user_id]) > GLOBAL_CONFIG["max_history_rounds"]:
            conversation_history[user_id].pop(0)
        save_conversation_history()
        save_user_global_memory(
            user_id,
            {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "user_msg": user_input,
                "bot_msg": main_reply,
                "emotion": emotion[0]
            }
        )
        
        # 打印日志
        print_custom_log(
            user=user,
            chat_type=chat_type,
            user_msg=user_input,
            bot_msg=main_reply,
            delay=main_delay,
            emotion=emotion_str,
            user_mem=user_mem,
            is_append=False
        )
        
        # 群打招呼功能
        if "去" in user_input and "群" in user_input and "打招呼" in user_input:
            chat_id_match = re.search(r"ID:\s*(-?\d+)", user_input)
            if chat_id_match:
                chat_id_target = chat_id_match.group(1)
                try:
                    chat_id_int = int(chat_id_target)
                    await context.bot.send_chat_action(chat_id=chat_id_int, action=ChatAction.TYPING)
                    await asyncio.sleep(1)
                    await context.bot.send_message(chat_id=chat_id_int, text="大家好呀~ 我是灵黯")
                    write_log(f"向群{chat_id_target}发送打招呼消息")
                    await update.message.reply_text("我已经去群里打招呼啦~")
                except Exception as e:
                    write_log(f"群打招呼失败: {str(e)}", "ERROR")
                    await update.message.reply_text("我好像进不去这个群呢~ 可能没被邀请哦~")
        
        # 发送追加回复（如有）
        if append_reply:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await asyncio.sleep(append_delay)
            await update.message.reply_text(append_reply)
            
            # 保存追加回复到对话历史
            conversation_history[user_id].append(("", append_reply))
            if len(conversation_history[user_id]) > GLOBAL_CONFIG["max_history_rounds"]:
                conversation_history[user_id].pop(0)
            save_conversation_history()
            save_user_global_memory(
                user_id,
                {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "user_msg": "[追加补充]",
                    "bot_msg": append_reply,
                    "emotion": emotion[0]
                }
            )
            
            # 打印追加回复日志
            print_custom_log(
                user=user,
                chat_type=chat_type,
                user_msg=f"【追加上下文】{user_input} | 主回复：{main_reply}",
                bot_msg=append_reply,
                delay=append_delay,
                emotion=emotion_str,
                user_mem=user_mem,
                is_append=True
            )
    
    except Exception as e:
        # 捕获所有异常，避免线程阻塞
        write_log(f"消息处理异常（用户{user_id}）: {str(e)}", "ERROR")
        try:
            # 异常兜底回复
            error_reply = clean_reply_text(add_emotion_intensity("刚才出了点小问题~ 我们重新聊呀~", "委屈", 1))
            await update.message.reply_text(error_reply)
        except Exception as e2:
            write_log(f"异常回复发送失败: {str(e2)}", "ERROR")

def handle_message(update: Update, context: CallbackContext):
    if is_rate_limited():
        return
    try:
        # 线程安全获取循环
        loop = get_thread_safe_loop()
        # 提交任务并设置总超时
        task = asyncio.run_coroutine_threadsafe(_handle_message_worker(update, context), loop)
        # 等待任务完成（带超时）
        task.result(timeout=GLOBAL_CONFIG["task_timeout"])
    except asyncio.TimeoutError:
        write_log("消息处理任务超时", "ERROR")
        try:
            timeout_reply = clean_reply_text(add_emotion_intensity("响应有点慢呀~ 你稍后再发一次好不好~", "委屈", 1))
            update.message.reply_text(timeout_reply)
        except Exception as e:
            write_log(f"超时回复发送失败: {str(e)}", "ERROR")
    except Exception as e:
        write_log(f"任务提交失败: {str(e)}", "ERROR")
        try:
            error_reply = clean_reply_text(add_emotion_intensity("好像有点卡~ 等一下再聊呀~", "委屈", 1))
            update.message.reply_text(error_reply)
        except Exception as e2:
            write_log(f"错误回复发送失败: {str(e2)}", "ERROR")
    finally:
        backup_data()

# ====================== 启动命令处理 ======================
async def start_async(update: Update, context: CallbackContext):
    try:
        await update.message.reply_text("你好呀，我是灵黯~ 很高兴认识你！")
    except Exception as e:
        write_log(f"启动回复失败: {str(e)}", "ERROR")

def start(update: Update, context: CallbackContext):
    try:
        loop = get_thread_safe_loop()
        asyncio.run_coroutine_threadsafe(start_async(update, context), loop)
    except Exception as e:
        write_log(f"启动命令处理失败: {str(e)}", "ERROR")
        try:
            update.message.reply_text("你好呀，我是灵黯~ 很高兴认识你！")
        except Exception as e2:
            write_log(f"启动命令兜底回复失败: {str(e2)}", "ERROR")

# ====================== 主函数 ======================
def main():
    init_all_files()
    load_all_data()
    write_log("Bot启动，所有数据加载完成")
    
    # 初始化Bot（指定更新队列大小，避免消息堆积）
    updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True, workers=4)
    dp = updater.dispatcher
    job_queue = updater.job_queue
    
    # 添加命令和消息处理器
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    # 启动保活机制
    keep_alive(updater, job_queue)
    write_log(f"t.me连接保活机制已启动，保活间隔：{GLOBAL_CONFIG['keep_alive_interval']}秒", "INFO")
    
    # 启动Bot（优化轮询间隔）
    print(f"Bot [{BOT_PROFILE['name']}] 已启动，监听t.me消息中...")
    print(f"数据存储目录: {BOT_DATA_DIR}")
    print(f"核心特性：Termux适配+超时保护+异常兜底+持续监听+智能追加回复")
    updater.start_polling(poll_interval=0.5, timeout=10)
    updater.idle()

if __name__ == "__main__":
    main()
