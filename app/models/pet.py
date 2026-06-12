from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from beanie import Document


class PetSpecies(str, Enum):
    DOG = "dog"
    CAT = "cat"
    FISH = "fish"
    BIRD = "bird"
    REPTILE = "reptile"
    HORSE = "horse"
    OTHER = "other"


class PetGender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class Pet(Document):
    tenant_id: str
    owner_id: str                              # 关联用户
    name: str                                  # 宠物名称
    species: PetSpecies = PetSpecies.OTHER     # 宠物种类
    breed: str = ""                            # 宠物品种
    gender: PetGender = PetGender.UNKNOWN     # 宠物性别
    birth_date: Optional[datetime] = None     # 宠物生日
    weight_kg: Optional[float] = None         # 宠物体重
    avatar_url: str = ""                      # 宠物头像
    tags: list[str] = []                      # 宠物标签
    chip_id: Optional[str] = None             # 宠物芯片 ID
    medical_notes: str = ""                   # 医疗备注（脱敏后展示）
    is_deleted: bool = False                   # 软删除
    created_at: datetime = datetime.now(timezone.utc)   # 创建时间
    updated_at: datetime = datetime.now(timezone.utc)   # 更新时间

    class Settings:
        name = "pets"
        indexes = [
            "tenant_id",
            "owner_id",
            [("tenant_id", 1), ("name", 1)],
            "chip_id",
        ]
