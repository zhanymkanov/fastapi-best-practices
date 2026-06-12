from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.core.security import mask_sensitive
from app.models.pet import Pet, PetSpecies, PetGender


class PetService:

    @classmethod
    async def find_all(
        cls,
        tenant_id: str,
        owner_id: Optional[str] = None,
        species: Optional[str] = None,
        is_deleted: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Pet], int]:
        """分页查询宠物列表"""
        # 多租户隔离，构建基础查询条件
        query: dict = {"tenant_id": tenant_id, "is_deleted": is_deleted}
        if owner_id:
            query["owner_id"] = owner_id
        if species:
            query["species"] = species  # 可按种类筛选

        # 获取总数和分页数据
        total = await Pet.find(query).count()
        items = await Pet.find(query).skip((page - 1) * page_size).limit(page_size).to_list()
        return items, total

    @classmethod
    async def get(cls, pet_id: str, tenant_id: str) -> Optional[Pet]:
        """获取单个宠物"""
        return await Pet.find_one({"_id": pet_id, "tenant_id": tenant_id, "is_deleted": False})

    @classmethod
    async def get_by_chip(cls, chip_id: str, tenant_id: str) -> Optional[Pet]:
        """按芯片 ID 查找（去重用）"""
        return await Pet.find_one({"chip_id": chip_id, "tenant_id": tenant_id})

    @classmethod
    async def insert(cls, tenant_id: str, owner_id: str, data: dict) -> Pet:
        """创建宠物档案"""
        # 构建宠物对象，赋予默认值
        pet = Pet(
            tenant_id=tenant_id,  # 多租户隔离
            owner_id=owner_id,  # 宠物主人
            name=data.get("name", ""),  # 宠物名称
            species=data.get("species", PetSpecies.OTHER),  # 种类（狗/猫/其他）
            breed=data.get("breed", ""),  # 品种
            gender=data.get("gender", PetGender.UNKNOWN),  # 性别
            birth_date=data.get("birth_date"),  # 生日
            weight_kg=data.get("weight_kg"),  # 体重（kg）
            avatar_url=data.get("avatar_url", ""),  # 头像 URL
            tags=data.get("tags", []),  # 标签（如"爱好运动"）
            chip_id=data.get("chip_id"),  # 芯片 ID（识别用）
            medical_notes=data.get("medical_notes", ""),  # 医疗备注
        )
        await pet.insert()  # 保存到 MongoDB
        return pet

    @classmethod
    async def update(cls, pet_id: str, tenant_id: str, data: dict) -> Optional[Pet]:
        """更新宠物档案"""
        # 先验证宠物存在（多租户隔离）
        pet = await cls.get(pet_id, tenant_id)
        if not pet:
            return None

        # 过滤掉 None 值和系统字段，避免误改
        update_data = {k: v for k, v in data.items() if v is not None and k not in ("_id", "tenant_id", "created_at")}
        update_data["updated_at"] = datetime.now(timezone.utc)  # 更新时间戳

        await pet.update({"$set": update_data})  # MongoDB 更新操作
        return await cls.get(pet_id, tenant_id)  # 返回更新后的最新数据

    @classmethod
    async def soft_delete(cls, pet_id: str, tenant_id: str) -> bool:
        """软删除宠物档案（逻辑删除，不真实删除数据）"""
        pet = await cls.get(pet_id, tenant_id)
        if not pet:
            return False
        # 标记为已删除，方便后续恢复或审计
        await pet.update({"$set": {"is_deleted": True, "updated_at": datetime.now(timezone.utc)}})
        return True

    @classmethod
    async def get_safe_pet(cls, pet: Pet) -> dict:
        """返回脱敏后的宠物数据（隐藏敏感字段如芯片 ID）"""
        return {
            "id": str(pet.id),
            "tenant_id": pet.tenant_id,
            "owner_id": pet.owner_id,
            "name": pet.name,
            # Enum 类型提取 value，避免序列化问题
            "species": pet.species.value if hasattr(pet.species, "value") else pet.species,
            "breed": pet.breed,
            "gender": pet.gender.value if hasattr(pet.gender, "value") else pet.gender,
            "birth_date": pet.birth_date,
            "weight_kg": pet.weight_kg,
            "avatar_url": pet.avatar_url,
            "tags": pet.tags,
            "chip_id": mask_sensitive(pet.chip_id) if pet.chip_id else None,  # 脱敏芯片 ID
            "is_deleted": pet.is_deleted,
            "created_at": pet.created_at,
            "updated_at": pet.updated_at,
        }
