# Company Profile JSON Schema

profile.json 的完整字段定义。所有字段均为可选（允许部分信息缺失），但建议尽可能填全。

## 顶层结构

```json
{
  "company_name": "string — 公司全称",
  "one_line_intro": "string — 一句话介绍（≤50字，适合开发信开头）",
  "full_intro": "string — 完整公司介绍（100-300字，适合公司介绍段落）",
  "location": "string — 所在城市/地区",
  "industry": "string — 所属行业",
  "established": "string — 成立时间（年份）",
  "scale": "string — 公司规模（人数/年产值/厂房面积等）",
  "website": "string — 公司官网 URL",

  "products": [],
  "core_competencies": [],
  "target_customer_types": [],
  "case_studies": [],
  "certifications": [],
  "cooperation_models": [],
  "unique_selling_points": [],
  "customer_matching_guide": [],

  "boundaries": {},
  "metadata": {}
}
```

## products[] — 主营产品/服务

```json
{
  "name": "string — 产品/服务名称",
  "description": "string — 产品描述（50-150字）",
  "target_customers": "string — 这类产品适合打什么客户",
  "key_selling_points": ["string — 该产品的关键卖点（3-5个）"]
}
```

**填写指南**：
- `target_customers` 要具体，比如"欧美品牌商的 OEM 采购团队"而不是泛泛的"客户"
- `key_selling_points` 要有差异化，避免"质量好、价格优"这种空话

## core_competencies[] — 核心竞争力

```json
{
  "competency": "string — 竞争力名称（如：价格优势、快速交付、定制能力）",
  "description": "string — 具体说明（100字以内）",
  "evidence": "string — 支撑证据（数据、认证、案例等）"
}
```

**常见竞争力类型**：
- 价格优势（对比同行的具体数据）
- 交付速度（如"标准产品 3 天出货，定制产品 15 天"）
- 定制能力（如"支持从设计到成品的全程定制"）
- 质量保证（认证、检测、售后）
- 供应链能力（原材料渠道、库存管理）
- 技术能力（研发团队、专利、技术创新）
- 规模优势（产能、厂房面积、设备数量）
- 服务能力（售后、技术支持、响应速度）

## target_customer_types[] — 适合开发的客户类型

```json
{
  "type": "string — 客户类型名称",
  "why_suitable": "string — 为什么我们适合这类客户（100字以内）",
  "pitch_focus": ["string — 面对这类客户时开发信应该重点说什么（3-5个）"]
}
```

**常见客户类型**：
- 品牌商（Brand Owner）— 有自有品牌，需要 OEM/ODM
- 批发商（Wholesaler）— 大量采购，关注价格和库存
- 分销商（Distributor）— 有渠道，需要稳定供应
- 零售商（Retailer）— 终端销售，关注产品差异化和包装
- 跨境电商卖家（E-commerce Seller）— Amazon/Shopify 等，关注 SKU 丰富度和发货速度
- 项目采购（Project Buyer）— 工程/政府项目，关注资质和交付能力
- 外贸采购团队（Trading Company）— 采购代理，关注性价比和服务

## case_studies[] — 成功案例

```json
{
  "project": "string — 项目/案例名称（中文）",
  "project_en": "string — 英文项目名",
  "client_type": "string — 客户类型",
  "industry": "string — 所属行业",
  "country": "string — 国家/地区",
  "products_used": ["string — 具体使用的产品类型"],
  "area_or_quantity": "string — 面积/数量/规模描述",
  "problem_solved": "string — 解决了什么问题",
  "result": "string — 交付结果/客户反馈",
  "key_highlight": "string — 一句话亮点（≤30字，嵌入开发信用）",
  "usable_in_outreach": "boolean — 是否可用于开发信（考虑客户隐私）"
}
```

**填写指南**：
- `project` 和 `project_en` 分别为中英文名称，便于不同场景使用
- `country` 填写国家或地区，如"阿联酋（迪拜）"、"美国（加利福尼亚）"
- `products_used` 填写具体产品类型（如 `["铝合金吊顶板 600×600mm", "铝蜂窝板"]`），不要写笼统的产品类目
- `area_or_quantity` 填写可量化的规模数据，如"15,000 ㎡"、"5,000 套"、"200 吨"
- `problem_solved` 和 `result` 要具体可量化，比如"帮助客户降低了 30% 的采购成本"
- `key_highlight` 是专为开发信设计的一句话精华，要求：
  - 包含具体数字（面积、数量、时间等）
  - 突出核心优势（速度、规模、质量等）
  - ≤30 个字，可直接嵌入开发信
  - 例："45天交付15,000㎡防火吊顶"、"为500强企业提供OEM定制15年"
- `usable_in_outreach` 设为 false 的情况：涉及客户机密、未获授权使用客户名称
- 即使 `usable_in_outreach` 为 false，案例数据仍可用于训练 AI 理解公司能力
- 案例数量目标：**至少 10 个**，按行业/地区分类，同类只保留最有代表性的 2-3 个

## certifications[] — 证书与资质

```json
["string — 证书/认证名称（如 ISO 9001, CE, FCC, UL）"]
```

## cooperation_models[] — 合作模式

```json
{
  "model": "string — 合作模式名称（如 OEM, ODM, 经销, 代理）",
  "description": "string — 模式说明",
  "customer_value": "string — 这种模式能给客户带来什么价值"
}
```

## unique_selling_points[] — 独特卖点

```json
["string — 与同行相比最值得强调的点（5-8个，每个≤30字）"]
```

**填写指南**：
- 每条卖点要独特、具体、可验证
- 避免空泛的"质量第一、客户至上"
- 优先选择竞争对手难以复制的优势

## customer_matching_guide[] — 客户匹配建议

```json
{
  "customer_type": "string — 客户类型（与 target_customer_types 对应）",
  "priority_points": ["string — 面对此类客户时优先强调的卖点"],
  "avoid_topics": ["string — 应该避免提及的话题"]
}
```

**这是给后续开发信 Skill 用的"匹配指南"**。它告诉 AI：面对不同类型的客户，应该说什么、不应该说什么。

## boundaries — 信息边界

```json
{
  "claims_we_can_make": ["string — 可以在开发信中说的内容"],
  "claims_we_cannot_make": ["string — 不能乱说的内容"],
  "sensitive_topics": ["string — 敏感话题，需要谨慎处理"]
}
```

**这个字段至关重要**。它防止后续开发信 Skill 生成不实内容。

示例：
```json
{
  "claims_we_can_make": [
    "通过 ISO 9001:2015 认证",
    "15 年行业经验，服务超过 500 家客户",
    "月产能 50,000 件",
    "支持 OEM/ODM 定制"
  ],
  "claims_we_cannot_make": [
    "不能声称是行业第一/最大/最好（除非有权威排名证明）",
    "不能承诺未经确认的具体价格",
    "不能编造不存在的案例或客户",
    "不能夸大产能或规模"
  ],
  "sensitive_topics": [
    "不主动提及具体客户名称（除非获得授权）",
    "不讨论竞争对手",
    "不主动提及最低起订量（除非客户问起）"
  ]
}
```

## metadata — 元数据

```json
{
  "created_at": "ISO 8601 日期字符串",
  "updated_at": "ISO 8601 日期字符串",
  "source_urls": ["string — 数据来源的 URL"],
  "source_documents": ["string — 数据来源的文档名/路径"],
  "profile_completeness": "float 0-1 — 档案完整度评估",
  "notes": "string — 需要后续补充或确认的事项"
}
```

`profile_completeness` 由 AI 根据已填写字段评估：
- 0.0-0.3：基础信息不足，需要大量补充
- 0.3-0.6：有基本框架，部分字段缺失
- 0.6-0.8：较完整，可用于开发信生成
- 0.8-1.0：非常完整，覆盖所有关键维度
