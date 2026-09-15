# Visual Compiler：动效资产卡自动编排工程规范

> 落地裁定（2026-09-14）：本规范分两期。**一期采用**：§2 schema 元数据、§3 Beat、§4 Visual Intent、§6.1 Hard Filter、§6.2/6.3 语义检索（**用本地 WeKnora**：BM25 + dense embedding + pgvector，卡片元数据与 md 文档 ingest 进独立 KB；用户已确认 /Users/bainazi/Documents/outtt/other/8other_coding/WeKnora）、§6.4 打分、§7 Agent 权限、§8 ShotSpec（=storyboard.json 现契约）、§16 渲染前校验（=lint/card_lint）、§21 模板生命周期（tier: injectable/raw）、§23 Phase 1-2。**暂缓**：独立 reranker 权重调优（一期用 §6.4 固定权重）、T001 目录迁移（registry.json 即注册表）。二期启动条件：一期指标（§19）连续两个 job 达标。
>
> WeKnora 集成约定：KB 名 `asset-cards`；每张卡 ingest 两条文档——① registry 元数据 JSON（id/visual_intent/content_types/slots/energy/duration）② references/shots 的 md 卡文档（意图/参数表/已知坑）；检索入口 `weknora` CLI 或 HTTP API，beat 文本 → Top-K 卡 slug → 按 §6.4 权重与本地方案（Hard Filter + 打分）合并排序。WeKnora 不可用时自动降级纯本地方案（Hard Filter + 关键词打分），检索层永不阻塞渲染。

## 0. 目标

输入一段视频文案，自动完成：

文案 → 语义分段 → Beat → 视觉意图 → 动效卡检索 → 参数填充 → 时间编排 → QA → 渲染

1. 不让 Agent 重写动效 TSX。
2. 不让 Agent 临时创造新动画。
3. 157+ 张现有动效卡成为有限动作空间。
4. 相同输入尽可能得到相同模板选择。
5. 降低 Token 消耗和生成结果方差。
6. 新模板只能经过人工验证后进入正式模板库。

## 1. 现有资产卡不改结构

每张资产卡 = 卡 tsx（动效骨架，锁死）+ registry 条目（检索元数据 + 槽位 arities）。
Agent 永远不能在正常生产流程中修改卡 tsx。

## 2. schema 标准（registry.json 条目扩展）

```json
{
  "slug": "sc-card-flip-reveal",
  "tier": "injectable",
  "arities": {"TEXT": 3, "SLOTS": 0},
  "durationInFrames": 150,
  "category3": "visual",
  "visual_intent": ["before_after", "data"],
  "information_structure": ["list"],
  "content_types": ["text", "number"],
  "motion": ["rotate", "scale"],
  "energy": "medium",
  "duration_sec": {"min": 4, "max": 5}
}
```

## 3. Beat 定义

Beat = 文案中一个独立表达单元（S1 已产出：script.segments[].beat）。
semantic_role 有限集合：hook / problem / claim / comparison / change / cause / effect /
example / evidence / process / timeline / quote / conclusion / cta。

## 4. Visual Intent（一期枚举）

comparison / before_after / data / timeline / process / cause_effect / quote /
emphasis / hierarchy / relationship / scene / character / ui / list / transition

## 5-6. 检索架构（一期：Hard Filter + 打分，无 embedding）

```
需求(beat→intent) → Hard Filter(tier=injectable ∧ intent∩ ∧ 时长) → 打分 → Top-K
score = 0.50 intent_match + 0.30 category3_fit + 0.20 近期未用奖励
（近期禁忌：近 2 镜同卡排除；全片 cap 由 lint._cap 管）
score 全部低于阈值（0.5）→ BEAT_CARDS 保底王（兜底确定性）。
```

## 7. Agent 权限

允许：拆 Beat / 判 intent / 检索 / 选卡 / 填 slots / 调整 schema 允许的参数。
禁止：改卡 tsx / 临时动画 / 临时 CSS / 自设计转场。无合适卡 → 标 degraded + 进移植队列。

## 8. ShotSpec = storyboard.json 现契约

shots[]: {id, recipe_ref(=template_id), time, config(=slots), sfx, layers}。不引入新格式。

## 16. 渲染前校验

schema 校验（validate_file）+ lint（多样性/时长/连续）+ card_lint（卡接线等级）。
失败 = BLOCK_RENDER（现状已如此）。

## 19. 核心质量指标

Template Reuse Rate >95% / NO_TEMPLATE <5% / Validation Failure <1% / Render Failure→0。
消融基线：scripts/ablation.py（每次路由层改动必跑）。

## 21. 模板生命周期

experimental(import_shotcraft raw) → verified(injectable+渲染验证) → deprecated(撤下)。
## 23. Phase 1-2 实施顺序

P1 元数据生成（gen_card_metadata.py）→ P2 intent 映射 + Hard Filter + 打分（variety.retrieve）→
P3 接入 S3 路由 + 消融验证 → P4 指标记录。
