"""Listing 批量 AI 优化：任务进度存 Redis，逐个执行且失败不中断。"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from redis.exceptions import RedisError

from app.database import SessionLocal
from app.models.enums import BatchOptimizeItemStatus, BatchOptimizeStatus
from app.schema.listing import (
    BatchOptimizeItemProgress,
    BatchOptimizeProgressData,
    BatchOptimizeRequest,
    BatchOptimizeSubmitData,
)
from app.services.listing_optimize_service import (
    ListingNotFoundError,
    ListingOptimizeService,
)
from app.services.llm_client import LLMClientError
from app.utils.redis_client import redis_key, safe_redis

logger = logging.getLogger("app.listing.batch_optimize")

MAX_BATCH_SIZE = 50
TASK_TTL_SECONDS = 7 * 24 * 3600  # 7 天
_MEMORY_STORE: dict[str, dict[str, Any]] = {}
_MEMORY_LOCK = threading.Lock()


class BatchOptimizeTaskNotFoundError(LookupError):
    """批量优化任务不存在或已过期。"""


class ListingBatchOptimizeService:
    """
    批量优化编排：

    1. create_task — 去重 listing_ids，初始化进度，返回 task_id
    2. run_task — 逐个调用 ListingOptimizeService；单项失败记 failed 后继续
    3. get_progress — 读 Redis（失败回落进程内内存）
    """

    def create_task(
        self,
        payload: BatchOptimizeRequest,
        *,
        user_id: uuid.UUID,
    ) -> BatchOptimizeSubmitData:
        # 保序去重
        seen: set[uuid.UUID] = set()
        listing_ids: list[uuid.UUID] = []
        for lid in payload.listing_ids:
            if lid in seen:
                continue
            seen.add(lid)
            listing_ids.append(lid)
        if not listing_ids:
            raise ValueError("listing_ids 不能为空")
        if len(listing_ids) > MAX_BATCH_SIZE:
            raise ValueError(f"单批最多 {MAX_BATCH_SIZE} 个 Listing")

        task_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        state = {
            "task_id": task_id,
            "status": BatchOptimizeStatus.queued.value,
            "created_by": str(user_id),
            "created_at": now.isoformat(),
            "started_at": None,
            "completed_at": None,
            "items": [
                {
                    "listing_id": str(lid),
                    "status": BatchOptimizeItemStatus.pending.value,
                    "version_id": None,
                    "product_id": None,
                    "error": None,
                    "finished_at": None,
                }
                for lid in listing_ids
            ],
        }
        self._save_state(task_id, state)
        return BatchOptimizeSubmitData(
            task_id=task_id,
            status=BatchOptimizeStatus.queued,
            total=len(listing_ids),
            created_at=now,
        )

    def run_task(self, task_id: str) -> None:
        """后台执行：独立 DB session；单项异常不中断整批。"""
        state = self._load_state(task_id)
        if state is None:
            logger.warning("批量优化任务不存在 task_id=%s", task_id)
            return
        if state.get("status") == BatchOptimizeStatus.completed.value:
            return

        now = datetime.now(timezone.utc)
        state["status"] = BatchOptimizeStatus.running.value
        state["started_at"] = now.isoformat()
        self._save_state(task_id, state)

        user_id = uuid.UUID(state["created_by"])
        items: list[dict[str, Any]] = list(state.get("items") or [])

        for index, item in enumerate(items):
            if item.get("status") in {
                BatchOptimizeItemStatus.success.value,
                BatchOptimizeItemStatus.failed.value,
            }:
                continue

            listing_id = uuid.UUID(item["listing_id"])
            item["status"] = BatchOptimizeItemStatus.running.value
            items[index] = item
            state["items"] = items
            self._save_state(task_id, state)

            db = SessionLocal()
            try:
                result = ListingOptimizeService(db).optimize(
                    listing_id,
                    user_id=user_id,
                )
                item["status"] = BatchOptimizeItemStatus.success.value
                item["version_id"] = str(result.version.id)
                item["product_id"] = str(result.product_id)
                item["error"] = None
                item["finished_at"] = datetime.now(timezone.utc).isoformat()
            except (ListingNotFoundError, LLMClientError, ValueError) as exc:
                logger.warning(
                    "批量优化单项失败 task=%s listing=%s type=%s",
                    task_id,
                    listing_id,
                    type(exc).__name__,
                )
                item["status"] = BatchOptimizeItemStatus.failed.value
                item["error"] = str(exc)[:500]
                item["finished_at"] = datetime.now(timezone.utc).isoformat()
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "批量优化单项未预期异常 task=%s listing=%s",
                    task_id,
                    listing_id,
                )
                item["status"] = BatchOptimizeItemStatus.failed.value
                item["error"] = f"服务器内部错误: {type(exc).__name__}"
                item["finished_at"] = datetime.now(timezone.utc).isoformat()
            finally:
                db.close()

            items[index] = item
            state["items"] = items
            self._save_state(task_id, state)

        state["status"] = BatchOptimizeStatus.completed.value
        state["completed_at"] = datetime.now(timezone.utc).isoformat()
        state["items"] = items
        self._save_state(task_id, state)
        logger.info(
            "批量优化完成 task=%s success=%s failed=%s",
            task_id,
            sum(
                1
                for i in items
                if i.get("status") == BatchOptimizeItemStatus.success.value
            ),
            sum(
                1
                for i in items
                if i.get("status") == BatchOptimizeItemStatus.failed.value
            ),
        )

    def get_progress(self, task_id: str) -> BatchOptimizeProgressData:
        state = self._load_state(task_id)
        if state is None:
            raise BatchOptimizeTaskNotFoundError(f"批量优化任务不存在: {task_id}")
        return self._to_progress(state)

    # —— 持久化 ——

    def _save_state(self, task_id: str, state: dict[str, Any]) -> None:
        payload = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
        client = safe_redis()
        if client is not None:
            try:
                client.setex(self._redis_key(task_id), TASK_TTL_SECONDS, payload)
                return
            except RedisError:
                logger.warning("Redis 写入批量优化进度失败，回落内存 task=%s", task_id)
        with _MEMORY_LOCK:
            _MEMORY_STORE[task_id] = state

    def _load_state(self, task_id: str) -> dict[str, Any] | None:
        client = safe_redis()
        if client is not None:
            try:
                raw = client.get(self._redis_key(task_id))
                if raw:
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        return data
            except (RedisError, json.JSONDecodeError, TypeError):
                logger.warning("Redis 读取批量优化进度失败 task=%s", task_id)
        with _MEMORY_LOCK:
            state = _MEMORY_STORE.get(task_id)
            return dict(state) if state is not None else None

    @staticmethod
    def _redis_key(task_id: str) -> str:
        return redis_key("listing", "batch_optimize", task_id)

    @staticmethod
    def _to_progress(state: dict[str, Any]) -> BatchOptimizeProgressData:
        items_raw = state.get("items") or []
        items: list[BatchOptimizeItemProgress] = []
        counts = {
            BatchOptimizeItemStatus.pending.value: 0,
            BatchOptimizeItemStatus.running.value: 0,
            BatchOptimizeItemStatus.success.value: 0,
            BatchOptimizeItemStatus.failed.value: 0,
        }
        for row in items_raw:
            status_value = str(row.get("status") or BatchOptimizeItemStatus.pending.value)
            counts[status_value] = counts.get(status_value, 0) + 1
            finished = row.get("finished_at")
            items.append(
                BatchOptimizeItemProgress(
                    listing_id=uuid.UUID(str(row["listing_id"])),
                    status=BatchOptimizeItemStatus(status_value),
                    version_id=(
                        uuid.UUID(str(row["version_id"]))
                        if row.get("version_id")
                        else None
                    ),
                    product_id=(
                        uuid.UUID(str(row["product_id"]))
                        if row.get("product_id")
                        else None
                    ),
                    error=row.get("error"),
                    finished_at=(
                        datetime.fromisoformat(finished) if finished else None
                    ),
                )
            )

        total = len(items)
        done = counts.get(BatchOptimizeItemStatus.success.value, 0) + counts.get(
            BatchOptimizeItemStatus.failed.value, 0
        )
        progress_pct = round((done / total) * 100, 2) if total else 100.0

        created_by = state.get("created_by")
        return BatchOptimizeProgressData(
            task_id=str(state["task_id"]),
            status=BatchOptimizeStatus(str(state.get("status") or "queued")),
            total=total,
            pending=counts.get(BatchOptimizeItemStatus.pending.value, 0),
            running=counts.get(BatchOptimizeItemStatus.running.value, 0),
            success=counts.get(BatchOptimizeItemStatus.success.value, 0),
            failed=counts.get(BatchOptimizeItemStatus.failed.value, 0),
            progress_pct=progress_pct,
            created_by=uuid.UUID(str(created_by)) if created_by else None,
            created_at=datetime.fromisoformat(str(state["created_at"])),
            started_at=(
                datetime.fromisoformat(str(state["started_at"]))
                if state.get("started_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(str(state["completed_at"]))
                if state.get("completed_at")
                else None
            ),
            items=items,
        )


def run_batch_optimize_task(task_id: str) -> None:
    """BackgroundTasks / 线程入口。"""
    ListingBatchOptimizeService().run_task(task_id)
