"""Listing 关键词挖掘服务（SDD §3.5）。"""

from __future__ import annotations

import logging
import math
import re
import uuid
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session, selectinload

from app.models.category import Category
from app.models.competitor_binding import CompetitorBinding
from app.models.enums import KeywordCategory
from app.models.product import Product
from app.schema.listing import (
    CategorizedKeywords,
    ExtractKeywordsData,
    KeywordItem,
    SuggestKeywordsData,
)

logger = logging.getLogger("app.listing.keywords")

DEFAULT_EXTRACT_LIMIT = 40
MAX_KEYWORD_LIMIT = 100
DEFAULT_SUGGEST_LIMIT = 30
SUGGEST_PRODUCT_SAMPLE = 200

# 英文词 / 中文连续段
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-']+|[0-9]+(?:\.[0-9]+)?|[A-Za-z]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
# 仅 ALL-CAPS 短词作品牌启发式（电商标题多为 Title Case，不能当品牌信号）
_BRAND_ALLCAPS_RE = re.compile(r"^[A-Z]{2,12}$")

_EN_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "for",
        "to",
        "in",
        "on",
        "at",
        "by",
        "with",
        "from",
        "into",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "your",
        "you",
        "our",
        "we",
        "they",
        "their",
        "new",
        "set",
        "pack",
        "pcs",
        "pc",
        "piece",
        "pieces",
        "size",
        "color",
        "colour",
        "free",
        "shipping",
        "amazon",
        "shopee",
        "best",
        "top",
        "hot",
        "sale",
        "deals",
        "deal",
        "gift",
        "gifts",
        # gift 在场景词表保留；停用词里去掉 gift 以免冲突 — 下面场景表优先
    }
    - {"gift", "gifts"}
)

_CJK_STOPWORDS = frozenset(
    {
        "的",
        "了",
        "和",
        "与",
        "及",
        "或",
        "一个",
        "一种",
        "可以",
        "进行",
        "使用",
        "适用",
        "包邮",
        "正品",
        "热销",
        "新品",
        "特价",
        "优惠",
        "官方",
        "旗舰",
        "店",
        "店铺",
    }
)

# 跨境场景/用途词（命中即 scenario）
_SCENARIO_TERMS = frozenset(
    {
        "outdoor",
        "indoors",
        "indoor",
        "travel",
        "camping",
        "hiking",
        "office",
        "home",
        "kitchen",
        "bathroom",
        "bedroom",
        "garden",
        "car",
        "bike",
        "beach",
        "party",
        "wedding",
        "school",
        "workout",
        "gym",
        "yoga",
        "running",
        "sports",
        "baby",
        "kids",
        "pet",
        "dogs",
        "cats",
        "gift",
        "gifts",
        "christmas",
        "halloween",
        "summer",
        "winter",
        "spring",
        "autumn",
        "fall",
        "daily",
        "everyday",
        "portable",
        "waterproof",
        "wireless",
        "bluetooth",
        "usb",
        "rechargeable",
        "men",
        "women",
        "unisex",
        "户外",
        "旅行",
        "露营",
        "徒步",
        "办公",
        "家用",
        "厨房",
        "浴室",
        "卧室",
        "花园",
        "车载",
        "沙滩",
        "派对",
        "婚礼",
        "学校",
        "健身",
        "瑜伽",
        "跑步",
        "运动",
        "婴儿",
        "儿童",
        "宠物",
        "送礼",
        "圣诞",
        "夏季",
        "冬季",
        "春季",
        "秋季",
        "日常",
        "便携",
        "防水",
        "无线",
        "充电",
        "男士",
        "女士",
        "居家",
        "通勤",
        "出差",
    }
)

# 常见跨境品牌词（可扩展；未命中仍靠大小写启发式）
_KNOWN_BRANDS = frozenset(
    {
        "apple",
        "samsung",
        "sony",
        "nike",
        "adidas",
        "anker",
        "bose",
        "logitech",
        "xiaomi",
        "huawei",
        "dyson",
        "philips",
        "lg",
        "dell",
        "hp",
        "lenovo",
        "asus",
        "gopro",
        "canon",
        "nikon",
        "kindle",
        "nintendo",
        "microsoft",
        "google",
        "amazonbasics",
    }
)


class ProductNotFoundError(LookupError):
    """商品不存在。"""


class CategoryNotFoundError(LookupError):
    """品类不存在。"""


class KeywordMiningService:
    """
    关键词挖掘：

    1. extract_keywords — 自营标题 + 竞品标题高频词
    2. categorize_keywords — 核心 / 长尾 / 品牌 / 场景
    3. suggest_keywords — 品类热门搜索词
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # —— 对外 API ——

    def extract_keywords(
        self,
        product_id: uuid.UUID,
        *,
        limit: int = DEFAULT_EXTRACT_LIMIT,
    ) -> ExtractKeywordsData:
        """从商品标题、关键词字段与活跃竞品标题提取高频词并分类。"""
        product = self.db.get(Product, product_id)
        if product is None:
            raise ProductNotFoundError(f"商品不存在: {product_id}")

        competitor_titles = self._load_competitor_titles(product_id)
        corpus = self._build_product_corpus(product, competitor_titles)
        ranked = self._mine_from_corpus(corpus, limit=limit)
        categorized = self.categorize_keywords(
            [item.keyword for item in ranked],
            frequency_map={item.keyword.lower(): item.frequency for item in ranked},
            doc_count_map={item.keyword.lower(): item.doc_count for item in ranked},
            total_docs=max(len(corpus), 1),
        )
        # 用分组结果回填 keywords 的 category，保持与 categorized 一致
        cat_by_key = {
            item.keyword.lower(): item.category
            for group in (
                categorized.core,
                categorized.long_tail,
                categorized.brand,
                categorized.scenario,
            )
            for item in group
        }
        keywords = [
            item.model_copy(
                update={"category": cat_by_key.get(item.keyword.lower(), item.category)}
            )
            for item in ranked
        ]

        return ExtractKeywordsData(
            product_id=product.id,
            product_title=product.title,
            source_count=len(corpus),
            competitor_count=len(competitor_titles),
            keywords=keywords,
            categorized=categorized,
            generated_at=datetime.now(timezone.utc),
        )

    def categorize_keywords(
        self,
        keywords: list[str] | list[KeywordItem],
        *,
        frequency_map: dict[str, int] | None = None,
        doc_count_map: dict[str, int] | None = None,
        total_docs: int = 1,
    ) -> CategorizedKeywords:
        """将关键词分为核心词 / 长尾词 / 品牌词 / 场景词。"""
        if not keywords:
            return CategorizedKeywords()

        items: list[KeywordItem] = []
        for entry in keywords:
            if isinstance(entry, KeywordItem):
                items.append(entry)
                continue
            kw = entry.strip()
            if not kw:
                continue
            key = kw.lower()
            freq = (frequency_map or {}).get(key, (frequency_map or {}).get(kw, 1))
            docs = (doc_count_map or {}).get(key, (doc_count_map or {}).get(kw, 1))
            items.append(
                KeywordItem(
                    keyword=kw,
                    frequency=freq,
                    doc_count=docs,
                    category=KeywordCategory.core,
                    score=float(freq),
                )
            )

        buckets: dict[KeywordCategory, list[KeywordItem]] = {
            KeywordCategory.core: [],
            KeywordCategory.long_tail: [],
            KeywordCategory.brand: [],
            KeywordCategory.scenario: [],
        }
        docs_total = max(total_docs, 1)
        for item in items:
            category = self._classify_term(
                item.keyword,
                frequency=item.frequency,
                doc_count=item.doc_count,
                total_docs=docs_total,
            )
            buckets[category].append(item.model_copy(update={"category": category}))

        return CategorizedKeywords(
            core=buckets[KeywordCategory.core],
            long_tail=buckets[KeywordCategory.long_tail],
            brand=buckets[KeywordCategory.brand],
            scenario=buckets[KeywordCategory.scenario],
        )

    def suggest_keywords(
        self,
        category_id: uuid.UUID,
        *,
        limit: int = DEFAULT_SUGGEST_LIMIT,
    ) -> SuggestKeywordsData:
        """基于品类下商品标题/关键词聚合热门搜索词。"""
        category = self.db.get(Category, category_id)
        if category is None:
            raise CategoryNotFoundError(f"品类不存在: {category_id}")

        category_ids = self._category_subtree_ids(category)
        stmt: Select[tuple[Product]] = (
            select(Product)
            .where(Product.category_id.in_(category_ids))
            .order_by(desc(Product.review_count), desc(Product.updated_at))
            .limit(SUGGEST_PRODUCT_SAMPLE)
        )
        products = list(self.db.scalars(stmt).all())
        corpus: list[str] = []
        for product in products:
            corpus.extend(self._texts_from_product(product))

        ranked = self._mine_from_corpus(corpus, limit=limit)
        categorized = self.categorize_keywords(
            ranked,
            total_docs=max(len(corpus), 1),
        )

        return SuggestKeywordsData(
            category_id=category.id,
            category_name=category.name,
            platform=category.platform.value,
            product_sample_size=len(products),
            keywords=ranked,
            categorized=categorized,
            generated_at=datetime.now(timezone.utc),
        )

    # —— 内部：语料与挖掘 ——

    def _load_competitor_titles(self, product_id: uuid.UUID) -> list[str]:
        stmt = (
            select(CompetitorBinding)
            .where(
                CompetitorBinding.own_product_id == product_id,
                CompetitorBinding.is_active.is_(True),
            )
            .options(selectinload(CompetitorBinding.competitor_product))
        )
        titles: list[str] = []
        for binding in self.db.scalars(stmt).all():
            competitor = binding.competitor_product
            if competitor is not None and competitor.title:
                titles.append(competitor.title)
        return titles

    def _build_product_corpus(
        self,
        product: Product,
        competitor_titles: list[str],
    ) -> list[str]:
        corpus = self._texts_from_product(product)
        corpus.extend(t for t in competitor_titles if t and t.strip())
        return corpus

    def _texts_from_product(self, product: Product) -> list[str]:
        texts: list[str] = []
        if product.title:
            texts.append(product.title)
        if product.keywords:
            texts.append(product.keywords)
        if product.bullet_points:
            for bullet in product.bullet_points:
                if isinstance(bullet, str) and bullet.strip():
                    texts.append(bullet)
        return texts

    def _mine_from_corpus(
        self,
        corpus: list[str],
        *,
        limit: int,
    ) -> list[KeywordItem]:
        safe_limit = max(1, min(limit, MAX_KEYWORD_LIMIT))
        if not corpus:
            return []

        freq: Counter[str] = Counter()
        doc_freq: Counter[str] = Counter()
        display: dict[str, str] = {}

        for text in corpus:
            tokens = self._extract_terms(text)
            if not tokens:
                continue
            seen_in_doc: set[str] = set()
            for raw in tokens:
                key = raw.lower()
                if not self._is_valid_term(key, raw):
                    continue
                freq[key] += 1
                if key not in seen_in_doc:
                    doc_freq[key] += 1
                    seen_in_doc.add(key)
                # 保留首次见到的展示形态（品牌大小写）
                display.setdefault(key, raw)

        total_docs = max(len(corpus), 1)
        scored: list[tuple[str, float, int, int]] = []
        for key, count in freq.items():
            docs = doc_freq[key]
            # TF × log(1 + DF)：跨标题复现的词加权更高
            score = float(count) * math.log1p(docs)
            # 仅出现一次且极短的噪声降权
            if docs == 1 and len(key) <= 2:
                score *= 0.35
            scored.append((key, score, count, docs))

        scored.sort(key=lambda row: (-row[1], -row[2], row[0]))
        items: list[KeywordItem] = []
        for key, score, count, docs in scored[:safe_limit]:
            keyword = display.get(key, key)
            category = self._classify_term(
                keyword,
                frequency=count,
                doc_count=docs,
                total_docs=total_docs,
            )
            items.append(
                KeywordItem(
                    keyword=keyword,
                    frequency=count,
                    doc_count=docs,
                    category=category,
                    score=round(score, 4),
                )
            )
        return items

    def _extract_terms(self, text: str) -> list[str]:
        """英文 unigram/bigram/trigram + 中文 bi/trigram。"""
        if not text or not text.strip():
            return []

        terms: list[str] = []

        # 英文与数字词
        en_words = _WORD_RE.findall(text)
        cleaned_en: list[str] = []
        for word in en_words:
            lower = word.lower()
            if lower in _EN_STOPWORDS or len(lower) < 2:
                continue
            if lower.isdigit() and len(lower) > 4:
                continue
            cleaned_en.append(word)
            terms.append(word)

        for n in (2, 3):
            for i in range(0, len(cleaned_en) - n + 1):
                chunk = cleaned_en[i : i + n]
                # 跳过全是数字的短语
                if all(w.replace(".", "", 1).isdigit() for w in chunk):
                    continue
                phrase = " ".join(chunk)
                if len(phrase) <= 40:
                    terms.append(phrase)

        # 中文 n-gram
        for run in _CJK_RE.findall(text):
            if run in _CJK_STOPWORDS:
                continue
            if len(run) >= 2:
                terms.append(run)
            for n in (2, 3):
                if len(run) < n:
                    continue
                for i in range(0, len(run) - n + 1):
                    gram = run[i : i + n]
                    if gram not in _CJK_STOPWORDS:
                        terms.append(gram)

        return terms

    def _is_valid_term(self, key: str, raw: str) -> bool:
        if not key or len(key) < 2:
            return False
        if key in _EN_STOPWORDS or key in _CJK_STOPWORDS:
            return False
        # 纯符号/过长
        if len(key) > 60:
            return False
        # 单字符中文已在提取阶段过滤
        if re.fullmatch(r"[\u4e00-\u9fff]", key):
            return False
        return True

    def _classify_term(
        self,
        keyword: str,
        *,
        frequency: int,
        doc_count: int,
        total_docs: int,
    ) -> KeywordCategory:
        lower = keyword.lower().strip()
        tokens = lower.split()
        token_count = len(tokens) if " " in lower else (
            1 if re.fullmatch(r"[A-Za-z0-9\-']+", keyword) else max(1, len(keyword) // 2)
        )

        # 场景词优先（用途/场景信号对 Listing 优化更关键）
        if lower in _SCENARIO_TERMS or any(t in _SCENARIO_TERMS for t in tokens):
            return KeywordCategory.scenario
        for term in _SCENARIO_TERMS:
            # 中文子串场景命中（如「便携式户外灯」含「户外」）
            if not re.fullmatch(r"[A-Za-z\-]+", term) and term in lower:
                return KeywordCategory.scenario

        # 品牌词：已知表，或短 ALL-CAPS（如 "LG"、"JBL"）；Title Case 不作品牌信号
        if lower in _KNOWN_BRANDS or any(t in _KNOWN_BRANDS for t in tokens):
            return KeywordCategory.brand
        if " " not in keyword and _BRAND_ALLCAPS_RE.match(keyword):
            return KeywordCategory.brand

        # 长尾：多词英文短语，或中文较长复合，或低频窄覆盖
        has_cjk = bool(re.search(r"[\u4e00-\u9fff]", keyword))
        is_phrase = " " in keyword or (has_cjk and len(keyword) >= 4)
        coverage = doc_count / max(total_docs, 1)
        if is_phrase and (token_count >= 3 or coverage < 0.35):
            return KeywordCategory.long_tail
        if is_phrase and token_count >= 2 and frequency <= 2:
            return KeywordCategory.long_tail

        return KeywordCategory.core

    def _category_subtree_ids(self, root: Category) -> list[uuid.UUID]:
        """含自身与全部子孙品类（开发期品类树通常不深，BFS 即可）。"""
        ids = [root.id]
        frontier = [root.id]
        while frontier:
            stmt = select(Category.id).where(Category.parent_id.in_(frontier))
            children = list(self.db.scalars(stmt).all())
            frontier = [cid for cid in children if cid not in ids]
            ids.extend(frontier)
        return ids
