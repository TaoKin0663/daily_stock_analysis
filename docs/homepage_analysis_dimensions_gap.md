# 首页股票最终需求分析维度如下
一、公司概况
1.1 基本信息
1.2 业务模式
1.3 市值与行业地位
1.4 护城河分析
二、财务数据分析
2.1 营收增长
2.2 盈利能力
2.3 资产负债结构
2.4 现金流状况
三、技术分析
3.1 股价走势
3.2 技术指标分析
3.3 关键支撑/阻力位
四、市场情绪分析
4.1 机构评级与预期
4.2 资金流向与筹码分布
4.3 市场情绪矛盾点
五、竞品对比
5.1 主要竞争对手
5.2 市场份额对比
5.3 财务指标对比
5.4 技术路线与竞争策略
六、估值与健康度分析
6.1 PE/PB估值
6.2 DCF估值分析
6.3 财务健康度评估
七、主要风险分析
7.1 行业竞争风险
7.2 政策风险
7.3 地缘风险
八、结论与投资建议
8.1 短期投资建议（1-3个月）
8.2 中长期投资建议（6-12个月）
8.3 长期投资建议（1-3年）
九、投资要点总结

# 首页股票分析维度 — 现状与目标差异分析

> 生成日期：2026-06-01 | 对比基准：`apps/dsa-web/src/pages/HomePage.tsx` 及其渲染链

---

## 总览

| 大类 | 目标子项数 | 已有（完整） | 已有（部分） | 完全缺失 | 覆盖率 |
|------|:---------:|:---------:|:---------:|:------:|:---:|
| 一、公司概况 | 4 | 0 | 1 | 3 | ~15% |
| 二、财务数据分析 | 4 | 0 | 1 | 3 | ~25% |
| 三、技术分析 | 3 | 0 | 2 | 1 | ~35% |
| 四、市场情绪分析 | 3 | 0 | 1 | 2 | ~15% |
| 五、竞品对比 | 4 | 0 | 0 | 4 | 0% |
| 六、估值与健康度 | 3 | 0 | 0 | 3 | 0% |
| 七、主要风险分析 | 3 | 0 | 0 | 3 | 0% |
| 八、结论与投资建议 | 3 | 0 | 1 | 2 | ~15% |
| 九、投资要点总结 | 1 | 0 | 1 | 0 | ~50% |
| **合计** | **28** | **0** | **7** | **21** | **~12%** |

---

## 逐项详细对比

### 一、公司概况

#### 1.1 基本信息 ✅ 已实现（best-effort）

| 数据点 | 当前状态 | 展示位置 |
|--------|:---:|---------|
| 股票名称 | ✅ 已有 | `ReportOverview` 卡片头部 |
| 股票代码 | ✅ 已有 | `ReportOverview` 卡片头部 |
| 当前价格 | ✅ 已有 | `ReportOverview` 卡片头部 |
| 涨跌幅 | ✅ 已有 | `ReportOverview` 卡片头部 |
| 分析日期 | ✅ 已有 | `ReportOverview` 卡片头部 |
| 公司全称 | ✅ 已有 | `ReportOverview` 基本信息区，来自 `details.companyProfile.fullName` |
| 所属行业 | ✅ 已有 | `details.companyProfile.industry`，缺失时回退到 `belongBoards` 行业板块 |
| 上市日期 | ✅ 已有 | `details.companyProfile.listingDate` |
| 总股本 / 流通股本 | ✅ 已有 | `details.companyProfile.totalShareCapital` / `floatShareCapital` |
| 员工规模 | ✅ 已有 | `details.companyProfile.employeeCount` |
| 公司官网 | ✅ 已有 | `details.companyProfile.website` |
| 公司基本介绍 | ✅ 已有 | `details.companyProfile.companyIntro`，缺失时回退 `mainBusiness` / `businessScope` |
| 核心管理层 | ✅ 已有 | 法定代表人来自 `details.companyProfile.legalRepresentative`；实际控制人来自 `details.companyProfile.actualController` / `actualControllerHoldRatio` |

**现有组件：** `ReportOverview.tsx` 股票头部卡片与基本信息区。公司资料为数据源 best-effort 获取，单个字段不可得时前端显示 `--`，不阻塞分析主流程。

**数据来源与调试方式：**

- A 股公司资料主源来自 AkShare `stock_profile_cninfo`（巨潮资讯公司概况），并 best-effort 使用 `stock_value_em` 补充总股本 / 流通股本字段；美股来自 yfinance `Ticker.info`。
- 港股公司资料来自 AkShare `stock_hk_company_profile_em`，员工人数、公司网址、公司介绍等字段取自该接口；总股本 / 流通股本 best-effort 来自 `stock_hk_financial_indicator_em`。
- A 股实际控制人 best-effort 来自 AkShare `stock_hold_control_cninfo`，按股票代码筛选最新记录；若数据源无返回，前端显示 `--`。
- 后端聚合字段位置：`fundamental_context.company_profile`；API 返回字段位置：`report.details.company_profile`；前端 camelCase 后读取 `details.companyProfile`。
- 后端日志关键字：`[company_profile]`。CLI 分析默认查看 `stock_analysis_YYYYMMDD.log` / `stock_analysis_debug_YYYYMMDD.log`；API 服务默认查看 `api_server_YYYYMMDD.log` / `api_server_debug_YYYYMMDD.log`，实际目录以启动时“日志目录”输出或 `LOG_DIR` 配置为准。
- 异步分析完成后可在浏览器 Network 查看 `/api/v1/analysis/status/{task_id}` 响应中的 `result.report.details.company_profile`。
- 历史详情可在浏览器 Network 查看 `/api/v1/history/{record_id}` 响应中的 `details.company_profile`。
- 本地可执行 `python scripts/debug_company_profile.py 600519 --timeout 5` 直接检查数据源返回与 API 字段提取结果。
- 若字段为 `null`，优先检查是否为旧报告、基础面 pipeline 未开启、数据源超时 / 空返回，或只查看了异步分析的初始 accepted 响应而非最终 status 响应。

#### 1.2 业务模式 ✅ 已实现

后端 LLM Prompt 要求新报告生成结构化 `business_model`，API 透传为 `details.businessModel`，前端通过 `BusinessModelSection` 在首页概览和完整报告抽屉中展示。

**展示规则：**

- `businessModel.items[]` 使用动态维度标题，不固定套用“产品结构 / 客户结构 / 技术路线 / 交付能力”；银行、医药、互联网、资源、地产等行业由 LLM 根据公司特点选择更贴切维度。
- `businessModel.summary` 在底部以“核心业务模式”摘要块展示，形式参考竞品截图。
- 老报告或 LLM 缺失结构化字段时，不做历史迁移，前端不展示 1.2 业务模式区块，避免与 1.1 公司基本介绍重复。

#### 1.3 市值与行业地位 ❌ 完全缺失

- `belongBoards` 仅展示板块关联和涨跌信号，不含市值排名、行业分位等
- 后端无市值相关数据字段

#### 1.4 护城河分析 ❌ 完全缺失

无任何护城河/竞争优势相关内容。

---

### 二、财务数据分析

**整体状态：⚠️ 已部分覆盖 2.1 营收增长与 2.2 盈利能力，其他财务维度仍缺失。**

| 维度 | 后端数据 | 前端展示 |
|------|:---:|:---:|
| 2.1 营收增长 | ✅ 已有 | ✅ 已有 |
| 2.2 盈利能力（毛利率/净利率/ROE） | ✅ 已有 | ✅ 已有 |
| 2.3 资产负债结构 | ❌ 无 | ❌ 无 |
| 2.4 现金流状况 | ❌ 无 | ❌ 无 |

> **注：** `details.financialReport.revenueGrowth.rows` 已用于 2.1 营收增长展示，数据来自 AkShare `stock_lrb_em` 年度利润表；`details.financialReport.profitability.rows` 已用于 2.2 盈利能力展示，数据来自 AkShare `stock_financial_analysis_indicator_em`。资产负债结构、现金流状况仍待补齐。

**TypeScript 类型定义（`analysis.ts`）：**
```typescript
export interface FinancialReport {
  reportDate?: string | null;
  revenue?: number | null;
  revenueYoy?: number | null;
  netProfitParent?: number | null;
  operatingCashFlow?: number | null;
  roe?: number | null;
  revenueGrowth?: {
    rows?: Array<{
      fiscalYear?: number;
      reportDate?: string;
      revenue?: number | null;
      revenueYoy?: number | null;
      announcementDate?: string | null;
    }>;
    unit?: string;
    frequency?: string;
    source?: string;
  };
  profitability?: {
    rows?: Array<{
      period?: string;
      reportDate?: string | null;
      grossMargin?: number | null;
      netMargin?: number | null;
      roe?: number | null;
    }>;
    unit?: string;
    frequency?: string;
    source?: string;
  };
}
```

**2.1 已实现展示：**

- 后端：`data_provider/fundamental_adapter.py` 使用 AkShare `stock_lrb_em` 对应的东方财富年度利润表接口，按 `SECURITY_CODE` + `REPORT_DATE` 定向查询后规范为 `financial_report.revenue_growth.rows[]`，避免全市场分页拉取超时。
- API：`report.details.financial_report.revenue_growth.rows[]`，前端 camelCase 后为 `details.financialReport.revenueGrowth.rows[]`。
- 前端：`FinancialRevenueGrowthSection` 在首页报告和完整报告抽屉展示表格与柱状图，表格列为 `年度 / 营业收入（亿） / 同比增长率`，图表展示年度营业收入（亿）并在 tooltip 中补充同比增长率。
- 完整报告：抽屉工具栏支持通过浏览器打印流程保存为 PDF，打印内容包含公司基本信息、营收增长表格/图表、盈利能力文字分析/图表和 Markdown 正文。

**2.2 已实现展示：**

- 后端：`data_provider/fundamental_adapter.py` 使用 AkShare `stock_financial_analysis_indicator_em` 获取财务分析指标，规范为 `financial_report.profitability.rows[]`，字段包括 `period / report_date / gross_margin / net_margin / roe`；`src/analyzer.py` 将这些指标交给 LLM，要求输出动态 `profitability_analysis`。
- API：结构化指标为 `report.details.financial_report.profitability.rows[]`，LLM 文字为 `report.details.profitability_analysis`；前端 camelCase 后分别为 `details.financialReport.profitability.rows[]` 与 `details.profitabilityAnalysis`。
- 前端：`FinancialProfitabilitySection` 在首页报告和完整报告抽屉优先展示 LLM 生成的 summary/items 文字分析，并保留“盈利能力趋势（毛利率）”图表；不再展示盈利能力表格。
- 兜底展示：如果 LLM 没有返回 `profitability_analysis`，但 `financial_report.profitability.rows[]` 或财报顶层盈利指标存在有效毛利率/净利率/ROE，则显示一条由结构化指标生成的盈利能力摘要并继续展示图表。
- 缺失数据：接口不可用、字段缺失且没有任何有效盈利指标时不展示 2.2 区块，不输出“数据缺失，无法判断”占位内容。

**2.1 / 2.2 调试方式：**

- 新报告完成后先看 Network 中 `/api/v1/analysis/status/{task_id}` 的 `result.report.details.financial_report`。
- 2.1 成功时应存在 `financial_report.revenue_growth.rows[]`；2.2 图表成功时应存在 `financial_report.profitability.rows[]`，LLM 文字成功时应存在 `profitability_analysis.summary` 或 `profitability_analysis.items[]`；若 LLM 文字缺失但结构化指标存在，前端会显示兜底指标摘要。
- 2.2 数据源使用 AkShare `stock_financial_analysis_indicator_em(symbol="300308.SZ", indicator="按报告期")`，字段按东财文档映射：`XSMLL` → 毛利率、`XSJLL` → 净利率、`ROEJQ` → ROE。
- Agent 模式保存的上下文快照为顶层 `fundamental_context`，API 详情提取已兼容该结构；标准模式仍使用 `enhanced_context.fundamental_context`。
- 任务完成后首页会刷新历史并自动打开最新完成报告，避免仍停留在旧历史报告导致看不到新字段。
- 基础面缓存 key 已带 `fin-report-v2` schema 版本，避免旧缓存继续返回缺少 2.1 / 2.2 的结果；若服务未重启，仍可能使用旧进程代码和内存缓存。

---

### 三、技术分析

#### 3.1 股价走势 ⚠️ 部分覆盖

| 数据点 | 当前状态 | 说明 |
|--------|:---:|------|
| 当前价格 | ✅ 已有 | `meta.currentPrice` |
| 涨跌幅 | ✅ 已有 | `meta.changePct` |
| 历史K线图 | ❌ 缺失 | 无图表组件 |
| 阶段趋势判断 | ❌ 缺失 | 后端 `trend_analysis` 字段存在但前端未渲染 |
| 均线排列（MA5/10/20） | ❌ 缺失 | 后端 `data_perspective.trend_status.ma_alignment` 存在，前端未用 |

#### 3.2 技术指标分析 ⚠️ 后端有数据，前端未渲染

后端 LLM Prompt 已要求生成以下数据（均在 `AnalysisResult` / `dashboard JSON` 中），但 **前端完全未展示**：

| 数据字段 | 后端存在 | 前端展示 |
|---------|:---:|:---:|
| `ma_analysis`（均线系统分析） | ✅ | ❌ |
| `volume_analysis`（量能分析，含量比/换手率） | ✅ | ❌ |
| `pattern_analysis`（K线形态分析） | ✅ | ❌ |
| `technical_analysis`（技术面综合分析） | ✅ | ❌ |
| `trend_analysis`（走势形态分析） | ✅ | ❌ |
| `data_perspective.price_position`（MA偏离度/支撑阻力） | ✅ | ❌ |
| `data_perspective.chip_structure`（筹码结构：获利比例/平均成本/集中度） | ✅ | ❌ |

#### 3.3 关键支撑/阻力位 ⚠️ 部分覆盖

| 数据点 | 当前状态 | 说明 |
|--------|:---:|------|
| 策略点位（理想买入/二次买入/止损/止盈） | ✅ 已有 | `ReportStrategy` 组件 |
| 基于技术分析的支撑/阻力位拆解 | ❌ 缺失 | 仅有价格，无分析逻辑说明 |
| 筹码分布支撑/压力区 | ❌ 缺失 | 后端有数据，前端未渲染 |

**现有组件：** `ReportStrategy.tsx`

---

### 四、市场情绪分析

#### 4.1 机构评级与预期 ❌ 完全缺失

无机构评级、目标价、盈利预测等内容。

#### 4.2 资金流向与筹码分布 ⚠️ 后台有数据，前端未渲染

- 后端 `chip_structure` 包含获利比例/平均成本/集中度/筹码健康度
- 前端仅展示板块强弱信号（`details.sectorRankings`）
- 无主力资金流向、北向资金等内容

#### 4.3 市场情绪矛盾点 ⚠️ 部分覆盖

| 数据点 | 当前状态 | 说明 |
|--------|:---:|------|
| 情绪评分（0-100）+ 标签 | ✅ 已有 | `ScoreGauge` 仪表盘 |
| 情绪分项拆解 | ❌ 缺失 | 无分项指标说明 |
| 多空分歧 / 矛盾信号 | ❌ 缺失 | 无矛盾点分析 |
| 新闻情绪 | ❌ 缺失 | 新闻列表存在但无情绪归因 |

**现有组件：** `ScoreGauge.tsx`（仪表盘）、`ReportNews.tsx`（纯列表无情绪标记）

---

### 五、竞品对比

**整体状态：❌ 此类下所有维度完全缺失。**

| 维度 | 后端数据 | 前端展示 |
|------|:---:|:---:|
| 5.1 主要竞争对手 | ❌ | ❌ |
| 5.2 市场份额对比 | ❌ | ❌ |
| 5.3 财务指标对比 | ❌ | ❌ |
| 5.4 技术路线与竞争策略 | ❌ | ❌ |

> 当前分析完全未涉及竞品维度。后端 LLM Prompt 未要求生成竞品相关内容。

---

### 六、估值与健康度分析

**整体状态：❌ 此类下所有维度完全缺失。**

| 维度 | 后端数据 | 前端展示 |
|------|:---:|:---:|
| 6.1 PE/PB 估值 | ⚠️ 类型定义存在 | ❌ |
| 6.2 DCF 估值分析 | ❌ | ❌ |
| 6.3 财务健康度评估 | ❌ | ❌ |

> TypeScript `FinancialReport` 接口定义了 `pe`、`pb`、`ps` 字段，但后端未实际填充这些数据，前端也未渲染。

---

### 七、主要风险分析

**整体状态：❌ 此类下所有维度完全缺失。**

| 维度 | 后端数据 | 前端展示 |
|------|:---:|:---:|
| 7.1 行业竞争风险 | ❌ | ❌ |
| 7.2 政策风险 | ❌ | ❌ |
| 7.3 地缘风险 | ❌ | ❌ |

> 后端 `risk_warning` 字段存在（为 narrative text），但前端 `ReportSummary` 未将其传递给任何子组件渲染。后端 LLM Prompt 中的 `intelligence.risk_alerts[]` 也存在但未在前端使用。

---

### 八、结论与投资建议

#### 8.1 短期投资建议（1-3个月） ⚠️ 部分覆盖

| 数据点 | 当前状态 | 说明 |
|--------|:---:|------|
| `trendPrediction`（趋势预测） | ✅ 已有 | `ReportOverview` 中展示 |
| `operationAdvice`（操作建议） | ✅ 已有 | `ReportOverview` 中展示 |
| 具体时间框架建议 | ❌ 缺失 | 无 1-3 个月的明确周期划分 |
| 仓位建议 | ❌ 缺失 | 后端 `battle_plan.position_strategy` 存在，前端未渲染 |

#### 8.2 中长期投资建议（6-12个月） ❌ 完全缺失

- 后端 `medium_term_outlook` 字段存在但前端未渲染
- 无 6-12 个月的明确投资建议

#### 8.3 长期投资建议（1-3年） ❌ 完全缺失

- 无长期视角的投资建议
- 无价值投资框架相关内容

---

### 九、投资要点总结

#### 9.1 投资要点总结 ⚠️ 部分覆盖

| 数据点 | 当前状态 | 说明 |
|--------|:---:|------|
| `analysisSummary`（核心洞察） | ✅ 已有 | 一段文字总结 |
| 结构化要点分列 | ❌ 缺失 | 无要点列表 |
| 多空逻辑对比 | ❌ 缺失 | 无正面/负面因子分列 |
| 操作清单 | ❌ 缺失 | 后端 `battle_plan.action_checklist[]` 存在，前端未渲染 |

---

## 当前组件渲染树

```
HomePage
├── StockAutocomplete + 分析按钮（头部）
├── TaskPanel（侧边栏）
├── HistoryList（侧边栏）
└── ReportSummary（主内容区）
    └── isHistory 模式
        ├── ReportOverview
        │   ├── 股票头部卡片（名称/代码/价格/涨跌幅/日期）
        │   ├── 核心洞察（分析摘要文字）
        │   ├── 操作建议卡片
        │   ├── 趋势预测卡片
        │   ├── 关联板块列表（含涨跌信号）
        │   └── 市场情绪 ScoreGauge 仪表盘
        ├── ReportStrategy
        │   └── 4个策略点位（理想买入/二次买入/止损/止盈）
        ├── ReportNews
        │   └── 新闻列表（标题+摘要，最多8条）
        ├── ReportDetails
        │   └── 调试信息（记录ID/原始JSON/快照JSON）
        └── ReportMarkdown（抽屉浮层）
            └── 完整 Markdown 报告（react-markdown 渲染）
```

## 后端已产出但前端未渲染的数据

这些数据 LLM 已经生成、经过 Schema 校验并存入了数据库，但前端没有对应的 UI 展示：

| 后端字段 | 内容 | 建议前端展示位置 |
|---------|------|---------------|
| `trend_analysis` | 走势形态分析 | 三、技术分析 |
| `short_term_outlook` | 短期展望 | 八、结论与投资建议 |
| `medium_term_outlook` | 中期展望 | 八、结论与投资建议 |
| `technical_analysis` | 技术面综合分析 | 三、技术分析 |
| `ma_analysis` | 均线系统分析 | 三、技术分析 |
| `volume_analysis` | 量能分析 | 三、技术分析 |
| `pattern_analysis` | K线形态分析 | 三、技术分析 |
| `fundamental_analysis` | 基本面分析 | 二、财务数据分析 |
| `sector_position` | 板块行业分析 | 一、公司概况 |
| `company_highlights` | 公司亮点/风险 | 一、公司概况 |
| `news_summary` | 新闻摘要 | 四、市场情绪分析 |
| `market_sentiment` | 市场情绪 | 四、市场情绪分析 |
| `hot_topics` | 相关热点 | 四、市场情绪分析 |
| `key_points` | 核心看点 | 九、投资要点总结 |
| `risk_warning` | 风险提示 | 七、主要风险分析 |
| `buy_reason` | 买入理由 | 八、结论与投资建议 |
| `core_conclusion` | 核心结论（含信号类型/时效性/仓位建议） | 首页顶部 |
| `data_perspective.chip_structure` | 筹码结构（获利比例/平均成本/集中度） | 三/四 |
| `data_perspective.price_position` | 价格位置（MA偏离/支撑阻力） | 三、技术分析 |
| `data_perspective.volume_analysis` | 量能分析（量比/换手率） | 三、技术分析 |
| `battle_plan.position_strategy` | 仓位策略 | 八、结论与投资建议 |
| `battle_plan.action_checklist` | 操作清单 | 九、投资要点总结 |
| `intelligence.risk_alerts` | 风险提醒 | 七、主要风险分析 |
| `intelligence.positive_catalysts` | 利好催化 | 一/八 |
| `intelligence.earnings_outlook` | 业绩展望 | 二、财务数据分析 |
| `financial_report`（结构化） | 财报数据 | 二、财务数据分析 |
| `dividend_metrics`（结构化） | 分红指标 | 二、财务数据分析 |

---

## 关键差距总结

1. **已有但需增强（6项）：** 基本信息、股价走势、关键支撑/阻力位、短期投资建议、技术指标分析、投资要点总结 → 需补充更多子维度、增强交互
2. **后端有数据但前端未渲染（~18个字段）：** 均线分析、量能分析、形态分析、基本面分析、行业板块、风险提醒、仓位策略等 → **前端工作量主要在这里**
3. **前后端均缺失（~14项）：** 市占率、护城河、竞品对比、DCF估值、机构评级、财务指标对比等 → **后端 LLM Prompt 需大幅扩展**

## 下一步建议

1. **短期（利用现有数据）：** 先把后端已产出但前端未渲染的 18 个字段对应的 UI 组件补上，最快见效
2. **中期（扩展 LLM Prompt）：** 在 System Prompt 中增加对竞品、估值、风险等维度的要求
3. **长期（外部数据源）：** 如需真实的财务数据、机构评级、DCF 模型，考虑接入外部数据 API（如 Tushare、东方财富、Wind 等）
