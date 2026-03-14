"""
时区工具模块
项目统一使用北京时间（Asia/Shanghai）
"""
from datetime import datetime
from pytz import timezone, utc

# 北京时区
BEIJING_TZ = timezone('Asia/Shanghai')


def get_beijing_time() -> datetime:
    """获取当前北京时间（带时区信息）"""
    return datetime.now(BEIJING_TZ)


def get_beijing_date_str() -> str:
    """获取当前北京日期字符串"""
    return get_beijing_time().strftime('%Y-%m-%d')


def get_beijing_datetime_str() -> str:
    """获取当前北京日期时间字符串"""
    return get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')


def utc_to_beijing(dt: datetime) -> datetime:
    """将UTC时间转换为北京时间"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # 无时区信息，假设是UTC
        dt = utc.localize(dt)
    return dt.astimezone(BEIJING_TZ)


def beijing_to_utc(dt: datetime) -> datetime:
    """将北京时间转换为UTC时间（用于数据库存储）"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # 无时区信息，先设为北京时间
        dt = BEIJING_TZ.localize(dt)
    return dt.astimezone(utc)


def ensure_beijing_time(dt: datetime) -> datetime:
    """
    确保时间对象是北京时间
    - 如果无时区，假设是北京时间并添加时区
    - 如果有时区，转换为北京时间
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return BEIJING_TZ.localize(dt)
    return dt.astimezone(BEIJING_TZ)


def format_beijing_time(dt: datetime, fmt: str = '%Y-%m-%d %H:%M') -> str:
    """格式化北京时间为字符串"""
    beijing_dt = ensure_beijing_time(dt)
    return beijing_dt.strftime(fmt) if beijing_dt else '?'


# 为模板和序列化使用的默认时间格式
DEFAULT_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
DATE_FORMAT = '%Y-%m-%d'
TIME_FORMAT = '%H:%M'
