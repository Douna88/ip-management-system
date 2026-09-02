# 知识产权管理系统 · IP Management System

> 面向企业 IP 岗位的一体化资产台账：把散落在 Excel 里的专利、商标、年费缴纳与发明人奖金，收敛成一套结构化、可追溯、带 AI 助手与可视化导出的内部系统。
>
> A full-stack internal platform for IP asset management — patents, trademarks, annuity (annual fee) tracking, and inventor bonus workflows, with an NL2SQL AI assistant and one-click reporting exports.



![Backend](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi\&logoColor=white)

![Frontend](https://img.shields.io/badge/Frontend-Vue_3_+_Element_Plus-4FC08D?logo=vue.js\&logoColor=white)

![DB](https://img.shields.io/badge/DB-SQLite_\(WAL\)-003B57?logo=sqlite\&logoColor=white)

![AI](https://img.shields.io/badge/AI-NL2SQL_+_规则引擎-FF6F00?logo=openai\&logoColor=white)

![Export](https://img.shields.io/badge/Export-PPT_/_PDF_/_HTML-EA4C89)

![License](https://img.shields.io/badge/License-MIT-blue)

---

## 📖 项目简介 · Overview

覆盖知识产权"**申请 → 授权 → 年费维持 → 发明人奖励**"的完整生命周期。  
系统支持多用户协作、数据看板、报表导出（**PPT / PDF / HTML**），并内置一个**中文自然语言 AI 助手**——直接用中文提问即可查数据、自动生成可视化图表。

**核心亮点**：

- **🏗️ 单进程一键部署**：前端（Vue 3）构建产物由后端（FastAPI）直接托管并带 SPA 兜底路由，团队访问一个地址即可使用，**无需 Nginx / 独立前端服务器，生产环境不需要 Node.js**。
- **🤖 AI 助手（NL2SQL + 规则引擎）**：中文提问 → 自动生成 SQL → 执行 → 用自然语言回答并附结果表与 ECharts 图表；内置规则引擎命中高频问题时**秒级响应**，模型离线时仍可回答。
- **💰 年费自动计算与完整性审核**：按国知局公开阶梯标准（发明 20 年 / 实用新型 10 年 / 外观 15 年）+ 费减比例（85% / 70%）自动推算每年应缴金额与截止日，并**审计漏写年份、一键补写**。
- **🔗 奖金三级名称匹配**：历史奖金常以"英文原文 + （中文名）"混合文本记录，与专利库对不上。系统实现**归一化精确 → 括号片段精确 → 双向包含**三级匹配，自动打通"专利 ↔ 奖金"关联。
- **📊 汇报材料导出**：看板图表一键导出 **PPT（原生图表）/ PDF（中文字体 + 矢量图）/ 自包含 HTML**，支持按模块选择性导出与 AI 分析页。
- **🔐 安全与可追溯**：JWT 鉴权 + bcrypt 密码哈希；关键写操作落审计日志；敏感配置走环境变量，`.env` 不入库。

---

## 🛠 技术栈 · Tech Stack

| 层  | 技术                                                          |
| -- | ----------------------------------------------------------- |
| 后端 | Python · **FastAPI** · SQLAlchemy · Pydantic · SQLite (WAL) |
| 前端 | Vue 3 · Vite · Element Plus · ECharts                       |
| AI | 本地大模型（OpenAI 兼容 `/chat/completions`） + 正则规则引擎兜底             |
| 导出 | python-pptx · reportlab · openpyxl · 内联 CSS HTML            |
| 安全 | bcrypt（密码） · JWT（鉴权） · 审计日志                                 |
| 部署 | 单进程 uvicorn（静态资源托管 + SPA 兜底路由）                              |

---

## ✨ 功能 · Features

### 专利台账

发明 / 实用新型 / 外观 / 软著 / 软产五类统一管理，字段覆盖申请号、授权号、IPC 分类、发明人（含贡献比例）、代理机构、快速审查与费减标记。支持按类型、状态、申请年、授权年多维筛选。

### 商标台账

尼斯分类（1–45 类）多选、图形商标预览、注册范围库分组管理；自动计算有效期与**续展提醒**（90 天内到期自动进入待续展清单）。

### 年费管理

按专利类型与费减比例**批量生成年费计划**，支持待缴 / 已缴 / 逾期 / 滞纳金四种状态、滞纳金自动计算（每超 1 个月加收 5%）。  
内置**完整性审核**：对比"按类型应有年份"与"实有记录"，标出漏写年份并支持一键补写（只补缺失，不覆盖已有记录）。

### 发明人奖金

批次 → 条目 → 明细三级链路。按奖励规则（受理 / 授权 / PCT 叠加）自动计算应发金额，按发明人贡献比例拆分到个人；支持审批流、Excel 批量导入与发放状态跟踪。

### 数据看板

看板汇总专利 / 商标 / 年费 / 奖金核心指标，ECharts 绘制类型分布、申请趋势、部门奖金分布、发明人 TOP10 等图表，支持**按年份筛选**。

### 汇报材料导出

- **PPT**：按模板版式生成，图表为 PPT 原生对象（可二次编辑）
- **PDF**：reportlab 绘制，注册中文字体（微软雅黑 / 宋体）避免乱码，矢量图表不失真
- **HTML**：自包含单文件（内联 CSS + ECharts），双击即开，便于邮件分发
- 三种格式均支持**按模块筛选**与可选的 **AI 分析页**

### 🤖 AI 助手

- 中文自然语言提问，自动生成并执行 SQL，**用自然语言回答 + 结果表 + 图表**，不向用户暴露 SQL
- **规则引擎优先**：高频问题（年费待缴、被驳回专利、待续展商标、部门奖金分布…）走确定性规则，秒回且结果 100% 可控
- 模型不可达时自动降级为规则引擎，核心问答不中断

### 文件中心与导入导出

专利 / 商标文档按业务实体归档；支持 Excel 批量导入导出（含中英文表头自适应解析）。

---

## 🚀 快速开始 · Quick Start

### 环境要求

- Python **3.10+**
- Node.js **18+**（仅开发模式需要；生产部署可直接用已构建的 `backend/static`）

### 1. 后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 生成演示数据（固定随机种子，任何人生成结果一致）
python seed_demo.py

# 启动服务
python -m uvicorn app.main:app --reload --port 8000
```

启动后访问 <http://localhost:8000>，登录账号：

| 账号      | 密码         | 角色   |
| ------- | ---------- | ---- |
| `admin` | `admin123` | 管理员  |
| `demo`  | `demo123`  | 普通成员 |

> `seed_demo.py` 生成的是**完全虚构**的演示数据（42 件专利、32 件商标、6 个奖金批次及完整年费计划），  
> 固定随机种子，不含任何真实企业信息。重复执行会先清空业务表再重建。

### 2. 前端（开发模式，可选）

```bash
cd frontend
npm install
npm run dev
```

开发模式默认访问 <http://localhost:5173>，API 请求代理到后端 8000 端口。

### 3. 生产部署（单进程）

```bash
cd frontend
npm run build          # 产物输出到 backend/static

cd ../backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

后端会直接托管 `backend/static` 并对未知路径做 SPA 兜底，**不需要 Nginx，也不需要 Node.js 运行时**。

---

## 📁 项目结构 · Structure

```
ip-system/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口、静态托管、SPA 兜底
│   │   ├── config.py            # 配置（敏感项全部走环境变量）
│   │   ├── models.py            # 18 张表的 SQLAlchemy 模型
│   │   ├── schemas.py           # Pydantic 校验
│   │   ├── security.py          # JWT + bcrypt
│   │   ├── fee_calculator.py    # 年费阶梯计算 + 完整性审核
│   │   ├── patent_match.py      # 奖金 ↔ 专利 三级名称匹配
│   │   ├── ai_bridge.py         # 大模型抽象层（none/local/cloud 三档）
│   │   └── routers/             # 业务路由：专利/商标/年费/奖金/AI/导出…
│   ├── seed_demo.py             # 虚构演示数据生成器（固定种子）
│   ├── requirements.txt
│   └── uploads/                 # 上传文件（运行时生成，不入库）
└── frontend/
    ├── src/
    │   ├── views/               # 页面：专利/商标/年费/奖金/看板/报表
    │   ├── components/          # AI 助手等公共组件
    │   └── api/                 # axios 封装
    └── vite.config.js           # 构建产物直出 backend/static
```

---

## ⚙️ 配置说明 · Configuration

所有环境相关配置均通过环境变量或 `backend/.env` 注入，**不写入代码**：

| 变量                  | 说明                               | 默认值                              |
| ------------------- | -------------------------------- | -------------------------------- |
| `DATABASE_URL`      | 数据库连接串                           | `sqlite:///backend/ip_system.db` |
| `SECRET_KEY`        | JWT 签名密钥                         | 首次启动自动生成并写入 `.env`               |
| `AI_MODE`           | AI 开关：`none` / `local` / `cloud` | `none`                           |
| `AI_LOCAL_BASE_URL` | 本地大模型地址（OpenAI 兼容）               | 空                                |
| `AI_LOCAL_MODEL`    | 本地模型名称                           | 空                                |
| `PORT`              | 监听端口                             | `8000`                           |

> AI 为**可选项**：不配置时规则引擎仍可回答常见问题，其余功能完全不受影响。

---

## 🧩 设计取舍 · Design Notes

- **SQLite + WAL**：面向部门级（数十人）使用场景，零运维成本；开启 WAL 后读写并发不互相阻塞，配合 `busy_timeout` 避免偶发锁冲突。模型层与业务层解耦，可平滑迁移至 PostgreSQL。
- **规则引擎优先于大模型**：NL2SQL 存在偶发写错 SQL 的风险，因此把高频、可枚举的问题固化成确定性规则，兼顾响应速度与结果可控性，模型仅处理长尾复杂问题。
- **导出图表用原生对象而非截图**：PPT 使用 `python-pptx` 原生图表、PDF 用 reportlab 矢量绘制，保证导出物在任意设备上清晰且可二次编辑。
- **AI 结果必须人工确认**：AI 解析的政策规则默认处于"待确认"状态，人工增删改后自动退回待确认，避免模型幻觉直接生效。

---

## 📄 许可 · License

[MIT](LICENSE) — 代码可自由使用与修改。

> 项目中的专利、商标、发明人、机构等数据均为 `seed_demo.py` 生成的虚构演示数据，  
> 年费金额参考国家知识产权局公开收费标准。
