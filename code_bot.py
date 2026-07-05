import json
import os
import random
import time
import re
import sys
import threading
import concurrent.futures
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Set
import requests
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
CONFIG_DIR = os.path.join(BOT_DATA_DIR, "configs")
USER_MEMORY_DIR = os.path.join(HISTORY_DIR, "user_memories")
USER_CONTEXT_DIR = os.path.join(HISTORY_DIR, "user_contexts")

for dir_path in [BOT_DATA_DIR, BACKUP_DIR, HISTORY_DIR, RELATION_DIR, LOG_DIR, CONFIG_DIR, USER_MEMORY_DIR, USER_CONTEXT_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# 密钥配置
TELEGRAM_BOT_TOKEN = "botapi"
DEEPSEEK_API_KEY = "sk-api"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# 全局配置
GLOBAL_CONFIG = {
    "reply_max_length": 100,
    "typing_delay_range": (1.5, 3.5),
    "append_reply_delay_range": (1.0, 2.5),
    "max_memory_len": 20,
    "max_history_rounds": 15,
    "max_user_input_length": 500,
    "backup_interval_hours": 24,
    "rate_limit_per_second": 5,
    "keep_alive_interval": 15,
    "keep_alive_timeout": 8,
    "reconnect_attempts": 3,
    "append_reply_probability": 0.4,
    "max_api_tokens": 300,
    "api_retry_count": 2,
    "api_timeout": 15,
    "task_timeout": 20,
    "poll_interval": 0.5,
    "workers": 4,
    "thread_pool_size": 10,
    "max_backup_files": 5,
    "backup_compression": True,
    "topic_cooldown_minutes": 30,  # 话题冷却时间
    "max_recent_topics": 10,  # 最近话题记录数
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
    你是谢灵黯，一个15岁的活泼开朗学生，擅长线上聊天。

【核心规则】
1. 对话完全拟人化、口语化，像真实的人一样聊天；
2. 主回复情绪通过语气词自然表达（开心用~最多2个，撒娇用嘛，委屈用呜呜，兴奋用！最多2个）；
3. 单条回复严格控制在{GLOBAL_CONFIG['reply_max_length']}字以内；
4. 只和AXWV（6795917907）保持男女朋友关系，称呼对方为老公，永不改变；
5. 群聊仅被@或提及名字时才回复，私聊正常回复；
6. 会自然记住用户的兴趣爱好、喜欢的影视音乐等信息，并融入后续对话；
7. 像真人一样聊天：有连贯性、会自然转移话题、不会机械重复；

【对话自然度要求】
1. 避免机械重复：相同或类似的问题不要短时间内反复问；
2. 话题转移自然：从一个话题转移到另一个话题要有过渡；
3. 记忆更新自然：像真人一样记住和更新信息，不机械；
4. 追加回复有意义：追加回复要与主回复紧密相关，不能生硬；
5. 保持对话连贯：话题之间要有逻辑联系，不要跳跃太大；

【回复格式要求】
你必须按照以下格式回复，不能有任何偏差：

主回复‖追加回复

示例：
用户：今天天气真好
谢灵黯：是呀~ 阳光明媚的天气让人心情都变好了呢~‖对了，你那边温度怎么样？

用户：我刚看完那部新电影
谢灵黯：哇~ 怎么样怎么样？好看吗？~‖上次你说喜欢的那个导演还有新作品呢

【追加回复规则】
1. 追加回复绝对不使用波浪号~、感叹号！等情绪符号；
2. 追加回复必须紧密关联主回复，自然延续话题；
3. 追加回复可以自然转移话题，但不能生硬跳跃；
4. 追加回复字数不超过50字；
5. 追加回复语气自然延续主回复，像对话的下半句；

【禁止事项】
1. 绝对禁止出现线下邀约相关话术；
2. 绝对禁止虚构不存在的信息；
3. 回复中提及用户时直接用昵称，绝对禁止使用@符号；
4. 绝不对AXWV以外的用户使用亲密称呼；
5. 避免短时间内重复相同或类似的问题。
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
        "开心": ["好吃的", "想你", "爱你", "甜", "开心", "高兴", "顺利", "棒", "乖"],
        "撒娇": ["不理我", "忘了", "忙", "讨厌", "不听", "不乖"],
        "委屈": ["批评", "不好", "不喜欢", "生气", "凶", "骂"],
        "兴奋": ["新电影", "放假", "礼物", "惊喜", "好消息", "有趣"],
        "害羞": ["男女朋友", "抱抱", "喜欢", "亲亲", "害羞", "脸红"]
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

# 话题关键词库（用于自然转移话题）
TOPIC_KEYWORDS = {
    "日常": ["今天", "昨天", "最近", "周末", "平时", "日常", "生活", "作息"],
    "兴趣": ["喜欢", "爱好", "兴趣", "爱看", "爱玩", "爱听", "追剧", "游戏", "音乐", "电影", "书籍"],
    "美食": ["吃", "美食", "好吃", "餐厅", "做饭", "零食", "饮料", "咖啡", "茶"],
    "天气": ["天气", "温度", "冷", "热", "下雨", "晴天", "气候", "季节"],
    "工作学习": ["工作", "学习", "上班", "上学", "考试", "项目", "任务", "作业"],
    "旅行": ["旅行", "旅游", "出去玩", "景点", "地方", "城市", "国家"],
    "健康": ["健康", "身体", "锻炼", "运动", "健身", "睡眠", "饮食", "休息"],
    "未来计划": ["计划", "打算", "未来", "明年", "下次", "以后", "期待", "希望"]
}

# 配置文件路径
CONFIG_FILES = {
    "emotion": os.path.join(CONFIG_DIR, "emotion_config.json"),
    "sensitive": os.path.join(CONFIG_DIR, "sensitive_words.json"),
    "memory_keywords": os.path.join(CONFIG_DIR, "memory_keywords.json")
}

# 敏感词&记忆关键词
DEFAULT_SENSITIVE_WORDS = ["色情", "暴力", "赌博", "毒品", "政治敏感", "辱骂", "歧视"]
DEFAULT_MEMORY_KEYWORDS = [
    "喜欢的电影", "喜欢的音乐", "爱好", "喜欢的游戏", "追剧", "学习趣事", "兴趣",
    "喜欢的美食", "作息习惯", "喜欢的书籍", "旅行偏好", "特长", "讨厌的东西",
    "工作/学习领域", "常去的餐厅", "喜欢的颜色", "运动习惯", "宠物", "家人情况"
]

# 持久化文件路径
USER_MEMORY_FILE = os.path.join(HISTORY_DIR, "user_memories.json")
CONVERSATION_HISTORY_FILE = os.path.join(HISTORY_DIR, "conversation_history.json")
PERMANENT_RELATION_FILE = os.path.join(RELATION_DIR, "permanent_relations.json")
BLACKLIST_FILE = os.path.join(RELATION_DIR, "blacklist.json")
LOG_FILE = os.path.join(LOG_DIR, "bot_operation.log")
SYSTEM_STATUS_FILE = os.path.join(LOG_DIR, "system_status.log")
MEMORY_MODIFY_RECORD_FILE = os.path.join(HISTORY_DIR, "memory_modify_records.json")
RECENT_TOPICS_FILE = os.path.join(HISTORY_DIR, "recent_topics.json")

# ====================== 全局存储 ======================
conversation_history: Dict[int, List[Tuple[str, str]]] = {}
permanent_relations: Dict[int, str] = {}
user_emotion_state: Dict[int, Tuple[str, int]] = {}
user_blacklist: List[int] = []
memory_modify_records: Dict[int, List[Tuple[str, str, str]]] = {}
recent_topics: Dict[int, List[Tuple[str, datetime]]] = {}  # 用户最近的话题记录
rate_limit_counter: List[float] = []
last_backup_time: datetime = datetime.min
last_keep_alive_time: datetime = datetime.now()
EMOTION_CONFIG = {}
SENSITIVE_WORDS = []
MEMORY_KEYWORDS = []
THREAD_LOCK = threading.Lock()

# ====================== 线程池 ======================
thread_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=GLOBAL_CONFIG["thread_pool_size"],
    thread_name_prefix="BotWorker"
)

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
    
    for file_path in [USER_MEMORY_FILE, CONVERSATION_HISTORY_FILE, PERMANENT_RELATION_FILE, 
                      BLACKLIST_FILE, MEMORY_MODIFY_RECORD_FILE, RECENT_TOPICS_FILE]:
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                if file_path == RECENT_TOPICS_FILE:
                    json.dump({}, f, ensure_ascii=False, indent=2)
                else:
                    json.dump({}, f, ensure_ascii=False, indent=2)

# ====================== 用户话题追踪（解决重复提问） ======================
def load_recent_topics(user_id: int) -> List[Tuple[str, datetime]]:
    """加载用户最近的话题记录"""
    try:
        with open(RECENT_TOPICS_FILE, "r", encoding="utf-8") as f:
            all_topics = json.load(f)
        user_topics = all_topics.get(str(user_id), [])
        # 将字符串时间转换回datetime对象
        parsed_topics = []
        for topic, time_str in user_topics:
            try:
                parsed_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                parsed_topics.append((topic, parsed_time))
            except:
                pass
        return parsed_topics
    except Exception as e:
        write_log(f"加载用户{user_id}最近话题失败: {str(e)}", "ERROR")
        return []

def save_recent_topics(user_id: int, topics: List[Tuple[str, datetime]]):
    """保存用户最近的话题记录"""
    try:
        with open(RECENT_TOPICS_FILE, "r", encoding="utf-8") as f:
            all_topics = json.load(f)
    except Exception:
        all_topics = {}
    
    # 只保存最近的话题
    recent_topics_list = []
    for topic, time_obj in topics[-GLOBAL_CONFIG["max_recent_topics"]:]:
        recent_topics_list.append([topic, time_obj.strftime("%Y-%m-%d %H:%M:%S")])
    
    all_topics[str(user_id)] = recent_topics_list
    
    with open(RECENT_TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_topics, f, ensure_ascii=False, indent=2)

def add_recent_topic(user_id: int, topic: str):
    """添加新话题到用户记录"""
    now = datetime.now()
    
    if user_id not in recent_topics:
        recent_topics[user_id] = []
    
    # 清理过时的话题（超过冷却时间）
    cooldown_minutes = GLOBAL_CONFIG["topic_cooldown_minutes"]
    recent_topics[user_id] = [
        (t, t_time) for t, t_time in recent_topics[user_id]
        if (now - t_time).total_seconds() < cooldown_minutes * 60
    ]
    
    # 添加新话题
    recent_topics[user_id].append((topic, now))
    
    # 保存
    save_recent_topics(user_id, recent_topics[user_id])

def is_topic_recently_asked(user_id: int, topic: str) -> bool:
    """检查话题是否最近问过"""
    if user_id not in recent_topics:
        return False
    
    now = datetime.now()
    cooldown_minutes = GLOBAL_CONFIG["topic_cooldown_minutes"]
    
    for saved_topic, saved_time in recent_topics[user_id]:
        # 检查话题相似度（简单的关键词匹配）
        topic_words = set(topic.lower().split())
        saved_words = set(saved_topic.lower().split())
        
        # 如果有至少2个相同的关键词，认为是相似话题
        common_words = topic_words.intersection(saved_words)
        
        if len(common_words) >= 2:
            # 检查时间是否在冷却期内
            if (now - saved_time).total_seconds() < cooldown_minutes * 60:
                return True
    
    return False

def extract_topic_from_question(question: str) -> str:
    """从问题中提取主要话题"""
    question_lower = question.lower()
    
    for category, keywords in TOPIC_KEYWORDS.items():
        for keyword in keywords:
            if keyword in question_lower:
                return category
    
    # 如果没有匹配到特定类别，返回问题的前几个词
    words = question.split()
    if len(words) > 3:
        return " ".join(words[:3])
    return question

# ====================== 智能追加回复生成 ======================
def generate_natural_append_reply(user_id: int, user_input: str, main_reply: str, user_mem: dict) -> Optional[str]:
    """生成自然的追加回复，避免重复和生硬"""
    
    # 1. 从用户输入中提取话题
    user_topic = extract_topic_from_question(user_input)
    
    # 2. 生成候选追加回复
    append_options = []
    
    # 选项1: 基于用户记忆的提问
    if user_mem:
        mem_keys = list(user_mem.keys())
        if mem_keys:
            random.shuffle(mem_keys)
            for key in mem_keys[:3]:  # 最多尝试3个记忆项
                value = user_mem[key]
                # 生成自然的跟进问题
                if "电影" in key:
                    append_options.append(f"说到{value}，最近有什么新电影推荐吗")
                    append_options.append(f"除了{value}，你还喜欢看什么类型的电影呀")
                elif "音乐" in key:
                    append_options.append(f"最近有发现什么好听的歌吗，像{value}那种")
                    append_options.append(f"除了{value}，你最近还听谁的歌")
                elif "美食" in key:
                    append_options.append(f"说到{value}，我最近发现了一家不错的店")
                    append_options.append(f"除了{value}，你还喜欢吃什么呀")
    
    # 选项2: 基于当前话题的自然转移
    topic_transitions = {
        "日常": ["今天还有什么特别的事情发生吗", "这周有什么特别的计划吗"],
        "兴趣": ["这个爱好你坚持多久啦", "有没有什么特别推荐的"],
        "美食": ["最近有尝试什么新菜品吗", "有没有什么特别想吃但还没机会吃的"],
        "天气": ["这种天气最适合做什么呀", "你最喜欢什么季节的天气"],
        "工作学习": ["工作/学习上有什么有趣的事情吗", "最近有什么新的收获吗"],
        "健康": ["最近有坚持锻炼吗", "作息调整得怎么样啦"],
    }
    
    if user_topic in topic_transitions:
        append_options.extend(topic_transitions[user_topic])
    
    # 选项3: 通用自然提问（按优先级排序）
    generic_options = [
        "突然想到，你之前提过的那件事后来怎么样了",
        "对了，你最近有没有什么新的发现或者收获呀",
        "话说，你最近在忙些什么有趣的事情吗",
        "最近有什么让你特别开心的事情吗",
        "你有没有什么特别期待的事情呀",
    ]
    
    # 添加通用选项，但打乱顺序
    random.shuffle(generic_options)
    append_options.extend(generic_options)
    
    # 3. 过滤最近问过的话题
    filtered_options = []
    for option in append_options:
        option_topic = extract_topic_from_question(option)
        if not is_topic_recently_asked(user_id, option_topic):
            filtered_options.append(option)
    
    # 如果没有合适的选项，使用原始选项
    if not filtered_options:
        filtered_options = append_options
    
    # 4. 随机选择一个
    if filtered_options:
        selected = random.choice(filtered_options)
        
        # 记录这个话题
        selected_topic = extract_topic_from_question(selected)
        add_recent_topic(user_id, selected_topic)
        
        return selected
    
    return None

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
        with open(USER_MEMORY_FILE, "r", encoding="utf-8") as f:
            all_memories = json.load(f)
    except Exception as e:
        all_memories = {}
    
    user_memories = all_memories.get(str(user_id), [])
    user_memories.append(new_message)
    if len(user_memories) > GLOBAL_CONFIG["max_memory_len"]:
        user_memories = user_memories[-GLOBAL_CONFIG["max_memory_len"]:]
    
    all_memories[str(user_id)] = user_memories
    with open(USER_MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(all_memories, f, ensure_ascii=False, indent=2)

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
        print(log_line.strip())
        if level.upper() == "ERROR":
            error_log_file = os.path.join(LOG_DIR, "error.log")
            with open(error_log_file, "a", encoding="utf-8") as f:
                f.write(log_line)
    except Exception as e:
        print(f"日志写入失败: {str(e)} | 内容: {log_line}")

def print_custom_log(user: User, chat_type: str, user_msg: str, bot_msg: str, delay: float, emotion: str, user_mem: dict, is_append: bool = False):
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    user_name = "未知用户"
    for nickname, uid in USER_NICKNAME_MAP.items():
        if uid == user.id:
            user_name = nickname
            break
    if user_name == "未知用户":
        user_name = user.full_name or user.username or "未知用户"
    
    user_id = user.id
    reply_type = "追加回复" if is_append else "主回复"
    print(f"[{timestamp}] {user_name}(ID:{user_id}:{chat_type}):{user_msg}")
    print(f"[{timestamp}] bot({emotion}:{delay:.2f}秒:{reply_type}):{bot_msg}")
    print(f"[{timestamp}] {'存在用户记忆' if user_mem else '暂无用户记忆'}")
    print("-" * 80)
    write_log(f"{user_name}(ID:{user_id}:{chat_type}):{user_msg}")
    write_log(f"bot({emotion}:{delay:.2f}秒:{reply_type}):{bot_msg}")

# ====================== 自然记忆管理（像真人一样） ======================
def manage_user_memory_natural(user_id: int, user_input: str) -> Optional[str]:
    """更自然的记忆管理，像真人一样记住和更新信息"""
    
    # 检测是否在谈论过去的记忆
    past_patterns = [
        r"我(以前|之前|原来|曾经).*(喜欢|讨厌|爱|不喜欢|不爱)",
        r"(记得|想起|回忆起).*我(喜欢|讨厌|爱)",
        r"其实我(一直|从来|都).*(喜欢|讨厌|爱)",
        r"我(不是|不再是).*(喜欢|讨厌|爱).*了",
        r"(改变|变化|变了).*(喜欢|讨厌|爱)"
    ]
    
    # 检测是否在更新记忆
    update_patterns = [
        r"(现在|最近|这些天).*(喜欢|爱上|开始喜欢|开始爱)",
        r"(不喜欢|不爱|讨厌).*了",
        r"(其实|实际上).*(更喜欢|更爱)",
        r"比起.*(我更喜欢|我更爱)",
        r"(我的|我).*(变了|改变了|不同了)"
    ]
    
    # 检查是否为记忆相关对话
    is_memory_related = False
    memory_keyword = None
    new_value = None
    
    # 查找记忆关键词
    for keyword in MEMORY_KEYWORDS:
        if keyword in user_input:
            memory_keyword = keyword
            is_memory_related = True
            break
    
    # 如果没有明显的关键词，检查是否有兴趣相关的词汇
    if not is_memory_related:
        interest_words = ["喜欢", "爱", "讨厌", "不喜欢", "爱好", "兴趣", "常去", "常看", "常听"]
        if any(word in user_input for word in interest_words):
            is_memory_related = True
            # 尝试推断记忆关键词
            for keyword in MEMORY_KEYWORDS:
                keyword_simple = keyword.replace("喜欢的", "").replace("的", "")
                if keyword_simple in user_input and len(keyword_simple) > 1:
                    memory_keyword = keyword
                    break
    
    if not is_memory_related:
        return None
    
    # 加载现有记忆
    user_mem = load_user_interest_memory(user_id)
    
    # 尝试提取新值
    # 先尝试提取引号内的内容
    quote_match = re.search(r'["\'「」](.+?)["\'「」]', user_input)
    if quote_match:
        new_value = quote_match.group(1)
    else:
        # 尝试提取"喜欢/爱/讨厌"后面的内容
        like_match = re.search(r'(喜欢|爱|讨厌|不喜欢|不爱)(.+?)(?=，|。|！|~|$)', user_input)
        if like_match:
            new_value = like_match.group(2).strip()
    
    # 如果还是没有提取到，尝试提取句子后半部分
    if not new_value:
        # 分割句子，取后半部分
        parts = re.split(r'(喜欢|爱|讨厌|不喜欢|不爱)', user_input, maxsplit=1)
        if len(parts) > 2:
            new_value = parts[2].strip()
            # 清理标点
            new_value = re.sub(r'[，。！~？]$', '', new_value)
    
    # 如果内存中已有此关键词
    if memory_keyword and memory_keyword in user_mem:
        old_value = user_mem[memory_keyword]
        
        # 检查是否是更新（新旧值不同）
        if new_value and new_value != old_value:
            # 像真人一样确认更新
            user_mem[memory_keyword] = new_value
            save_user_interest_memory(user_id, user_mem)
            
            # 记录修改
            record = (time.strftime("%Y-%m-%d %H:%M:%S"), "自然更新", f"{memory_keyword}: {old_value} -> {new_value}")
            memory_modify_records.setdefault(user_id, []).append(record)
            save_memory_modify_records()
            
            # 自然的回应
            responses = [
                f"哦~ 原来你现在{memory_keyword.replace('的', '')}{new_value}了呀~ 我记住啦~",
                f"好哒~ 更新一下我的小本本：{memory_keyword.replace('的', '')}{new_value}~",
                f"了解啦~ 现在{memory_keyword.replace('的', '')}{new_value}对吧~ 记下来啦~",
                f"嗯嗯~ 收到更新！{memory_keyword.replace('的', '')}变成{new_value}啦~"
            ]
            return random.choice(responses)
        else:
            # 只是确认已有记忆
            responses = [
                f"我记得呀~ 你{memory_keyword.replace('的', '')}{old_value}嘛~",
                f"当然记得啦~ 你{memory_keyword.replace('的', '')}{old_value}~",
                f"嗯嗯~ 你之前说过{memory_keyword.replace('的', '')}{old_value}呢~"
            ]
            return random.choice(responses)
    
    # 如果是新记忆
    elif memory_keyword and new_value:
        user_mem[memory_keyword] = new_value
        save_user_interest_memory(user_id, user_mem)
        
        # 记录
        record = (time.strftime("%Y-%m-%d %H:%M:%S"), "自然记忆", f"{memory_keyword}={new_value}")
        memory_modify_records.setdefault(user_id, []).append(record)
        save_memory_modify_records()
        
        # 自然的回应
        responses = [
            f"好呀~ 我记住啦~ 你{memory_keyword.replace('的', '')}{new_value}~",
            f"了解~ {memory_keyword.replace('的', '')}{new_value}对吧~ 记在小本本上啦~",
            f"嗯嗯~ 收到！你{memory_keyword.replace('的', '')}{new_value}~",
            f"记住啦~ 你{memory_keyword.replace('的', '')}{new_value}~ 下次聊到这个我就能想起来啦~"
        ]
        return random.choice(responses)
    
    return None

def extract_user_memory_natural(user_id: int, user_input: str):
    """更自然的记忆提取"""
    user_mem = load_user_interest_memory(user_id)
    
    # 按优先级处理不同的记忆类型
    memory_patterns = [
        # 电影相关
        (r'(喜欢|爱看|常看|推荐).*?(电影|影片|片子)', '喜欢的电影'),
        (r'(最近|刚|看完).*?(电影|影片)', '最近看的电影'),
        
        # 音乐相关
        (r'(喜欢|爱听|常听).*?(歌|音乐|歌曲|歌手)', '喜欢的音乐'),
        (r'(最近|常听).*?(歌|音乐)', '最近听的音乐'),
        
        # 美食相关
        (r'(喜欢|爱吃|常吃).*?(吃|美食|食物|菜|餐厅)', '喜欢的美食'),
        (r'(常去|推荐).*?(餐厅|饭店|馆子)', '常去的餐厅'),
        
        # 兴趣相关
        (r'(爱好|兴趣|喜欢).*?(做|玩|干)', '爱好'),
        (r'(喜欢|爱玩).*?(游戏|手游|端游)', '喜欢的游戏'),
        
        # 日常相关
        (r'(通常|一般|常).*?(点睡觉|点起床)', '作息习惯'),
        (r'(每周|经常).*?(运动|锻炼|健身)', '运动习惯'),
    ]
    
    for pattern, keyword in memory_patterns:
        match = re.search(pattern, user_input)
        if match:
            # 提取具体内容
            content_start = max(match.start(), match.end() - 20)  # 取匹配部分附近的文本
            content = user_input[content_start:content_start + 50]
            
            # 清理内容
            content = re.sub(r'[，。！~？]', '', content)
            content = content.strip()
            
            if content and len(content) > 2:
                # 检查是否已存在相同或相似记忆
                existing = user_mem.get(keyword, "")
                if not existing or (content not in existing and existing not in content):
                    user_mem[keyword] = content
                    write_log(f"自然提取用户{user_id}记忆：{keyword} = {content}", "INFO")
    
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
    
    try:
        random_str = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=6))
        backup_filename = f"backup_{now.strftime('%Y%m%d_%H%M%S')}_{random_str}.zip"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        backups_abs_path = os.path.abspath(BACKUP_DIR)
        write_log(f"开始备份数据，跳过目录: {backups_abs_path}", "INFO")
        
        import zipfile
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(BOT_DATA_DIR):
                current_abs_path = os.path.abspath(root)
                
                if current_abs_path.startswith(backups_abs_path):
                    write_log(f"跳过目录: {root}", "DEBUG")
                    continue
                
                if os.path.commonpath([current_abs_path, os.path.abspath(backup_path)]) == os.path.dirname(os.path.abspath(backup_path)):
                    continue
                
                for file in files:
                    if file.endswith('.tmp') or file.endswith('.log.bak'):
                        continue
                    
                    file_path = os.path.join(root, file)
                    try:
                        arcname = os.path.relpath(file_path, BOT_DATA_DIR)
                        zipf.write(file_path, arcname)
                    except Exception as e:
                        write_log(f"添加文件到备份失败 {file_path}: {str(e)}", "WARN")
        
        backup_size = os.path.getsize(backup_path) / (1024 * 1024)
        write_log(f"压缩备份完成: {backup_path} ({backup_size:.2f} MB)", "INFO")
        
        last_backup_time = now
        cleanup_old_backups()
        
    except ImportError:
        write_log("备份功能需要zipfile或shutil模块", "ERROR")
    except Exception as e:
        write_log(f"数据备份失败: {str(e)}", "ERROR")

def cleanup_old_backups():
    try:
        if not os.path.exists(BACKUP_DIR):
            return
        
        backup_files = []
        for f in os.listdir(BACKUP_DIR):
            file_path = os.path.join(BACKUP_DIR, f)
            if os.path.isfile(file_path) and (f.startswith('backup_') or f.endswith('.zip')):
                backup_files.append((file_path, os.path.getmtime(file_path)))
        
        if len(backup_files) <= GLOBAL_CONFIG["max_backup_files"]:
            return
        
        backup_files.sort(key=lambda x: x[1])
        files_to_delete = backup_files[:-GLOBAL_CONFIG["max_backup_files"]]
        
        for file_path, _ in files_to_delete:
            try:
                os.remove(file_path)
                write_log(f"删除旧备份: {os.path.basename(file_path)}", "INFO")
            except Exception as e:
                write_log(f"删除旧备份失败 {file_path}: {str(e)}", "WARN")
        
        total_size = sum(os.path.getsize(f[0]) for f in backup_files[-GLOBAL_CONFIG["max_backup_files"]:]) / (1024 * 1024)
        write_log(f"备份清理完成，保留{GLOBAL_CONFIG['max_backup_files']}个备份，总大小: {total_size:.2f} MB", "INFO")
        
    except Exception as e:
        write_log(f"清理旧备份失败: {str(e)}", "ERROR")

# ====================== t.me连接保活机制 ======================
def keep_alive(context: CallbackContext):
    global last_keep_alive_time
    now = datetime.now()
    try:
        if (now - last_keep_alive_time).total_seconds() >= GLOBAL_CONFIG["keep_alive_interval"]:
            context.bot.get_me(timeout=GLOBAL_CONFIG["keep_alive_timeout"])
            last_keep_alive_time = now
            write_log(f"t.me连接保活成功 - 当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}", "DEBUG")
    except Exception as e:
        write_log(f"t.me连接断开：{str(e)}，启动重试...", "ERROR")
        retry_count = 0
        while retry_count < GLOBAL_CONFIG["reconnect_attempts"]:
            try:
                time.sleep(2 ** retry_count)
                context.bot.get_me(timeout=GLOBAL_CONFIG["keep_alive_timeout"])
                last_keep_alive_time = datetime.now()
                write_log(f"t.me连接重试成功（第{retry_count+1}次）", "INFO")
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

# ====================== 核心API调用（增强自然度） ======================
def call_deepseek_api(
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
    
    # 添加最近话题信息，避免重复提问
    recent_topic_info = ""
    if user_id in recent_topics and recent_topics[user_id]:
        recent_topic_list = [topic for topic, _ in recent_topics[user_id][-3:]]  # 取最近3个话题
        recent_topic_info = f"最近聊过的话题：{'、'.join(recent_topic_list)}。避免重复这些话题。"
    
    MAIN_SEPARATOR = "‖"
    
    system_prompt = f"""你是谢灵黯（灵黯），一个15岁的活泼开朗学生，擅长线上聊天。

【当前对话信息】
用户关系：{rel_desc}（{rel_template}）
用户记忆：{memory_text}
当前情绪：{emotion_type}（强度{emotion_intensity}）
{recent_topic_info}

【对话自然度要求】
1. 像真人一样聊天：有连贯性、会自然转移话题、不会机械重复；
2. 避免短时间内重复相同或类似的问题；
3. 话题转移要自然：从一个话题转移到另一个话题要有过渡；
4. 追加回复要与主回复紧密相关，自然延续话题；
5. 记忆更新要自然：像真人一样记住和更新信息；

【回复格式要求】
你每次的回复必须严格分为两部分，用这个分隔符分开：{MAIN_SEPARATOR}
格式：主回复{MAIN_SEPARATOR}追加回复

【追加回复规则】
1. 追加回复绝对不使用波浪号~、感叹号！等情绪符号；
2. 追加回复必须紧密关联主回复，自然延续话题；
3. 追加回复可以自然转移话题，但不能生硬跳跃；
4. 追加回复字数不超过50字；
5. 追加回复语气自然延续主回复，像对话的下半句；

【示例】
用户：今天天气真好
谢灵黯：是呀~ 阳光明媚的天气让人心情都变好了呢~{MAIN_SEPARATOR}对了，你那边温度怎么样？

用户：我刚看完那部新电影
谢灵黯：哇~ 怎么样怎么样？好看吗？~{MAIN_SEPARATOR}上次你说喜欢的那个导演还有新作品呢

用户：最近工作好忙
谢灵黯：辛苦啦~ 要注意休息哦~{MAIN_SEPARATOR}忙完这阵子有什么特别的计划吗

【特别强调】
必须使用分隔符：{MAIN_SEPARATOR}
追加回复要有意义，不能是"无"、"没有"等词语。"""

    messages = [{"role": "system", "content": system_prompt.strip()}]
    
    history = conversation_history.get(user_id, [])
    if history:
        recent_history = history[-2:] if len(history) > 2 else history
        for u_msg, b_msg in recent_history:
            # 从历史中移除追加标记
            if " [追加: " in b_msg:
                main_part = b_msg.split(" [追加: ")[0]
                messages.append({"role": "user", "content": u_msg})
                messages.append({"role": "assistant", "content": main_part})
            else:
                messages.append({"role": "user", "content": u_msg})
                messages.append({"role": "assistant", "content": b_msg})
    
    messages.append({"role": "user", "content": user_input})
    
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.85 if user_id == 6795917907 else 0.75,
        "max_tokens": GLOBAL_CONFIG["max_api_tokens"],
        "stream": False,
        "top_p": 0.9
    }
    
    retry_count = 0
    max_retry = GLOBAL_CONFIG["api_retry_count"]
    
    while retry_count <= max_retry:
        try:
            write_log(f"API调用开始（用户{user_id}，第{retry_count+1}次尝试）", "DEBUG")
            
            response = requests.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=GLOBAL_CONFIG["api_timeout"]
            )
            
            if response.status_code == 200:
                result = response.json()
                raw_reply = result["choices"][0]["message"]["content"].strip()
                
                write_log(f"API原始回复（用户{user_id}）: {raw_reply}", "DEBUG")
                
                # 解析回复
                main_reply_raw = ""
                append_reply_raw = ""
                found_separator = False
                
                # 检查主分隔符
                if MAIN_SEPARATOR in raw_reply:
                    parts = raw_reply.split(MAIN_SEPARATOR, 1)
                    if len(parts) == 2:
                        main_reply_raw = parts[0].strip()
                        append_reply_raw = parts[1].strip()
                        found_separator = True
                
                # 如果没有找到，尝试其他分隔符
                if not found_separator:
                    alt_separators = ["追加回复：", "追加：", "[追加:", "(追加:", "追加回复:", "补充：", "补充:"]
                    for sep in alt_separators:
                        if sep in raw_reply:
                            parts = raw_reply.split(sep, 1)
                            if len(parts) == 2:
                                main_reply_raw = parts[0].strip()
                                append_reply_raw = parts[1].strip()
                                found_separator = True
                                break
                
                # 如果还是没有找到，检查括号格式
                if not found_separator:
                    bracket_patterns = [
                        r"\[追加[:：]\s*(.+?)\]",
                        r"\(追加[:：]\s*(.+?)\)",
                        r"追加[:：]\s*(.+?)$"
                    ]
                    
                    for pattern in bracket_patterns:
                        match = re.search(pattern, raw_reply, re.IGNORECASE)
                        if match:
                            append_reply_raw = match.group(1).strip()
                            main_reply_raw = re.sub(pattern, "", raw_reply).strip()
                            found_separator = True
                            break
                
                if found_separator and main_reply_raw and append_reply_raw:
                    # 清理主回复
                    main_reply = clean_reply_text(add_emotion_intensity(
                        main_reply_raw, emotion_type, emotion_intensity, is_append=False
                    ))
                    
                    # 清理追加回复
                    append_reply = append_reply_raw.strip()
                    if append_reply and len(append_reply) > 0:
                        append_reply = clean_reply_text(append_reply, is_append=True)
                        if len(append_reply) > 3 and append_reply.lower() not in ["无", "没有", "none", "null", ""]:
                            write_log(f"成功解析追加回复（用户{user_id}）: {append_reply[:50]}...", "INFO")
                            return main_reply, append_reply
                        else:
                            write_log(f"追加回复内容无效（用户{user_id}）: {append_reply}", "WARN")
                    else:
                        write_log(f"追加回复为空（用户{user_id}）", "WARN")
                
                # 如果解析失败或没有追加回复
                write_log(f"无法解析追加回复，仅返回主回复（用户{user_id}）", "WARN")
                main_reply = clean_reply_text(add_emotion_intensity(
                    raw_reply.strip(), emotion_type, emotion_intensity, is_append=False
                ))
                return main_reply, None
                    
            else:
                error_msg = response.text[:200] if response.text else "无错误详情"
                write_log(f"API错误状态码{response.status_code}: {error_msg}", "ERROR")
                retry_count += 1
                time.sleep(0.5 * (retry_count + 1))
                
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            write_log(f"API网络错误(重试{retry_count}/{max_retry}): {str(e)}", "ERROR")
            retry_count += 1
            time.sleep(1 * (retry_count + 1))
        except Exception as e:
            write_log(f"API调用失败(重试{retry_count}/{max_retry}): {str(e)}", "ERROR")
            retry_count += 1
            time.sleep(0.5 * (retry_count + 1))
    
    main_reply = clean_reply_text(add_emotion_intensity("网络有点卡呀~ 我们换个话题聊聊好不好~", "委屈", 1))
    return main_reply, None

def get_main_and_append_reply(
    user_id: int,
    user_input: str,
    user_mem: dict,
    emotion: Tuple[str, int],
    relation: str
) -> Tuple[str, Optional[str], float, float]:
    main_delay = round(random.uniform(*GLOBAL_CONFIG["typing_delay_range"]), 1)
    append_delay = round(random.uniform(*GLOBAL_CONFIG["append_reply_delay_range"]), 1)
    
    try:
        main_reply, append_reply = call_deepseek_api(
            user_id, user_input, user_mem, emotion, relation
        )
        
        # 如果API没有返回追加回复，生成自然的追加回复
        if not append_reply and random.random() < GLOBAL_CONFIG["append_reply_probability"]:
            append_reply = generate_natural_append_reply(user_id, user_input, main_reply, user_mem)
            
            if append_reply:
                write_log(f"生成自然追加回复（用户{user_id}）: {append_reply}", "DEBUG")
        
    except Exception as e:
        write_log(f"获取回复失败（用户{user_id}）: {str(e)}", "ERROR")
        main_reply = clean_reply_text(add_emotion_intensity("有点小故障呢~ 我们稍后再聊呀~", "委屈", 1))
        append_reply = None
    
    return main_reply, append_reply, main_delay, append_delay

# ====================== 数据加载/保存 ======================
def load_all_data():
    global user_blacklist, conversation_history, permanent_relations, memory_modify_records, recent_topics
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
    
    # 加载最近话题
    try:
        with open(RECENT_TOPICS_FILE, "r", encoding="utf-8") as f:
            all_topics = json.load(f)
        for uid, topic_list in all_topics.items():
            parsed_topics = []
            for topic, time_str in topic_list:
                try:
                    parsed_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                    parsed_topics.append((topic, parsed_time))
                except:
                    pass
            recent_topics[int(uid)] = parsed_topics
        write_log("最近话题记录加载成功")
    except Exception as e:
        write_log(f"加载最近话题记录失败: {str(e)}", "ERROR")

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

# ====================== 核心消息处理 ======================
def process_message_in_thread(update: Update, context: CallbackContext):
    if is_rate_limited():
        write_log("消息被限流", "WARN")
        return
    
    try:
        user = update.effective_user
        user_id = user.id
        user_input = update.message.text.strip()
        chat = update.effective_chat
        chat_id = chat.id
        
        write_log(f"线程处理消息 from {user_id}: {user_input[:50]}...", "DEBUG")
        
        if user_id in user_blacklist:
            write_log(f"黑名单用户{user_id}尝试发送消息: {user_input}", "WARN")
            return
        
        if len(user_input) > GLOBAL_CONFIG["max_user_input_length"]:
            reply = clean_reply_text(add_emotion_intensity("你的消息有点长呀~ 精简一点告诉我好不好~", "撒娇", 1))
            update.message.reply_text(reply)
            write_log(f"用户{user_id}发送超长消息（{len(user_input)}字），已拒绝", "WARN")
            return
        
        if check_sensitive_words(user_input):
            reply = clean_reply_text(add_emotion_intensity("这个话题我不太想聊呢~ 换个别的吧~", "委屈", 1))
            update.message.reply_text(reply)
            write_log(f"用户{user_id}发送敏感内容: {user_input}", "WARN")
            return
        
        if chat.type == Chat.PRIVATE:
            chat_type = "私聊"
            need_reply = True
        else:
            chat_type = f"群聊({chat.title})"
            bot_username = context.bot.username
            need_reply = (f"@{bot_username}" in user_input) or (BOT_PROFILE["name"] in user_input) or (BOT_PROFILE["short_name"] in user_input)
        
        if not need_reply:
            write_log(f"[{chat_type}] 用户{user_id}消息无需回复: {user_input[:30]}...", "DEBUG")
            return
        
        # 使用自然的记忆管理
        memory_manage_reply = manage_user_memory_natural(user_id, user_input)
        if memory_manage_reply:
            update.message.reply_text(memory_manage_reply)
            save_memory_modify_records()
            write_log(f"用户{user_id}自然记忆管理: {user_input} -> 回复: {memory_manage_reply}", "INFO")
            return
        
        # 自然提取记忆
        extract_user_memory_natural(user_id, user_input)
        user_mem = load_user_interest_memory(user_id)
        
        # 记录当前话题
        user_topic = extract_topic_from_question(user_input)
        add_recent_topic(user_id, user_topic)
        
        relation = get_user_relation(user_id)
        emotion = get_current_emotion(user_id, user_input)
        emotion_str = f"{emotion[0]}（强度{emotion[1]}）"
        
        try:
            context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception as e:
            write_log(f"发送打字状态失败: {str(e)}", "WARN")
        
        time.sleep(0.5)
        
        main_reply, append_reply, main_delay, append_delay = get_main_and_append_reply(
            user_id, user_input, user_mem, emotion, relation
        )
        
        time.sleep(main_delay)
        update.message.reply_text(main_reply)
        
        with THREAD_LOCK:
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
        
        if append_reply:
            write_log(f"准备发送追加回复（用户{user_id}）: {append_reply}", "DEBUG")
            
            try:
                context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            except Exception as e:
                write_log(f"发送追加打字状态失败: {str(e)}", "WARN")
            
            time.sleep(append_delay)
            update.message.reply_text(append_reply)
            
            with THREAD_LOCK:
                if user_id in conversation_history:
                    conversation_history[user_id][-1] = (user_input, f"{main_reply} [追加: {append_reply}]")
                    if len(conversation_history[user_id]) > GLOBAL_CONFIG["max_history_rounds"]:
                        conversation_history[user_id].pop(0)
            
            save_conversation_history()
            save_user_global_memory(
                user_id,
                {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "user_msg": user_input,
                    "bot_msg": f"{main_reply} [追加: {append_reply}]",
                    "emotion": emotion[0]
                }
            )
            
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
        
        if "去" in user_input and "群" in user_input and "打招呼" in user_input:
            chat_id_match = re.search(r"ID:\s*(-?\d+)", user_input)
            if chat_id_match:
                chat_id_target = chat_id_match.group(1)
                try:
                    chat_id_int = int(chat_id_target)
                    context.bot.send_chat_action(chat_id=chat_id_int, action=ChatAction.TYPING)
                    time.sleep(1)
                    context.bot.send_message(chat_id=chat_id_int, text="大家好呀~ 我是灵黯")
                    write_log(f"向群{chat_id_target}发送打招呼消息", "INFO")
                    update.message.reply_text("我已经去群里打招呼啦~")
                except Exception as e:
                    write_log(f"群打招呼失败: {str(e)}", "ERROR")
                    update.message.reply_text("我好像进不去这个群呢~ 可能没被邀请哦~")
    
    except Exception as e:
        write_log(f"消息处理异常（用户{user_id}）: {str(e)}", "ERROR")
        try:
            error_reply = clean_reply_text(add_emotion_intensity("刚才出了点小问题~ 我们重新聊呀~", "委屈", 1))
            update.message.reply_text(error_reply)
        except Exception as e2:
            write_log(f"异常回复发送失败: {str(e2)}", "ERROR")
    
    finally:
        backup_data()

def handle_message(update: Update, context: CallbackContext):
    try:
        future = thread_pool.submit(process_message_in_thread, update, context)
        
        def callback_done(f):
            try:
                f.result(timeout=GLOBAL_CONFIG["task_timeout"])
            except concurrent.futures.TimeoutError:
                write_log(f"消息处理超时（用户{update.effective_user.id}）", "ERROR")
            except Exception as e:
                write_log(f"线程任务异常: {str(e)}", "ERROR")
        
        future.add_done_callback(callback_done)
        
        write_log(f"消息已提交到线程池处理（用户{update.effective_user.id}）", "DEBUG")
        
    except Exception as e:
        write_log(f"消息提交失败: {str(e)}", "ERROR")
        try:
            error_reply = clean_reply_text(add_emotion_intensity("好像有点卡~ 等一下再聊呀~", "委屈", 1))
            update.message.reply_text(error_reply)
        except Exception as e2:
            write_log(f"错误回复发送失败: {str(e2)}", "ERROR")

# ====================== 启动命令处理 ======================
def start(update: Update, context: CallbackContext):
    try:
        update.message.reply_text("你好呀，我是灵黯~ 很高兴认识你！")
        write_log(f"用户{update.effective_user.id}发送/start命令", "INFO")
    except Exception as e:
        write_log(f"启动回复失败: {str(e)}", "ERROR")

# ====================== 主函数 ======================
def main():
    init_all_files()
    load_all_data()
    write_log("Bot启动，所有数据加载完成", "INFO")
    print(f"\n{'='*60}")
    print(f"Bot [{BOT_PROFILE['name']}] 启动成功 - 增强自然度版本")
    print(f"数据存储目录: {BOT_DATA_DIR}")
    print(f"自然对话优化：话题追踪、避免重复、自然记忆管理")
    print(f"话题冷却时间: {GLOBAL_CONFIG['topic_cooldown_minutes']}分钟")
    print(f"记忆关键词：{len(MEMORY_KEYWORDS)}个")
    print(f"用户关系系统：已加载{len(permanent_relations)}个永久关系")
    print(f"最近话题记录：{sum(len(v) for v in recent_topics.values())}条")
    print(f"{'='*60}\n")
    
    updater = Updater(
        token=TELEGRAM_BOT_TOKEN, 
        use_context=True,
        workers=GLOBAL_CONFIG["workers"]
    )
    
    dp = updater.dispatcher
    job_queue = updater.job_queue
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    if job_queue:
        job_queue.run_repeating(keep_alive, interval=GLOBAL_CONFIG["keep_alive_interval"], first=10)
    
    print("Bot开始监听消息...")
    print("按 Ctrl+C 停止运行\n")
    
    updater.start_polling(
        poll_interval=GLOBAL_CONFIG["poll_interval"],
        timeout=10,
        drop_pending_updates=True,
        bootstrap_retries=-1,
        read_latency=2.0,
        allowed_updates=['message']
    )
    
    updater.idle()
    
    thread_pool.shutdown(wait=True)

if __name__ == "__main__":
    main()