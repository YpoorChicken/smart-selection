"""应用启动初始化数据。"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.enums import UserRole
from app.models.user import User
from app.utils.security import hash_password

logger = logging.getLogger("app.bootstrap")

ADMIN_EMAIL = "zhangsan@126.com"
ADMIN_INITIAL_PASSWORD = "Zs123456"


def seed_initial_data() -> None:
    """
    幂等初始化 SDD 所需基础数据和测试管理员。

    初始账号角色为 ops_lead（运营主管），便于演示竞品刷新、Listing 写操作等。
    管理员密码仅在首次创建时哈希入库；后续启动不会覆盖已修改密码。
    生产部署应在首次登录后立即修改此初始密码。
    """
    with SessionLocal() as db:
        _ensure_admin(db)
        db.commit()


def _ensure_admin(db: Session) -> None:
    existing = db.scalar(select(User).where(User.email == ADMIN_EMAIL))
    if existing is not None:
        return

    db.add(
        User(
            email=ADMIN_EMAIL,
            password_hash=hash_password(ADMIN_INITIAL_PASSWORD),
            display_name="张运营",
            role=UserRole.ops_lead,
            is_active=True,
        )
    )
    logger.info("已创建初始管理员账号：%s（密码未写入日志）", ADMIN_EMAIL)

