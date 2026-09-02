# 知识产权管理系统 · IP Management System

> 面向企业 IP 岗位的一体化资产台账：把散落在 Excel 里的专利、商标、年费缴纳与发明人奖金，收敛成一套结构化、可追溯、带 AI 助手与可视化导出的内部系统。
>
> A full-stack internal platform for IP asset management — patents, trademarks, annuity (annual fee) tracking, and inventor bonus workflows, with an NL2SQL AI assistant and one-click reporting exports.

![Backend](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)
![Frontend](https://img.shields.io/badge/Frontend-Vue_3_+_Element_Plus-4FC08D?logo=vue.js&logoColor=white)
![DB](https://img.shields.io/badge/DB-SQLite_(WAL)-003B57?logo=sqlite&logoColor=white)
![AI](https://img.shields.io/badge/AI-NL2SQL_+_规则引擎-FF6F00?logo=openai&logoColor=white)
![Export](https://img.shields.io/badge/Export-PPT_/_PDF_/_HTML-EA4C89)
![License](https://img.shields.io/badge/License-MIT-blue)

---

## 📖 项目简介 · Overview

覆盖知识产权"**申请 → 授权 → 年费维持 → 发明人奖励**"的完整生命周期。
系统支持多用户协作、数据看板、报表导出（**PPT / PDF / HTML**），并内置一个**中文自然语言 AI 助手**——直接用中文提问即可查数据、自动生成可视化图表。

**核心亮点**：

- **🏗️ 单进程一键部署**：前端（Vue 3）构建产物由后端（FastAPI）直接托管并带 SPA 兜底路由，团队访问一个地址即可使用，**无需 Nginx / 独立前端服务器，生产环境不需要 Node.js**。
- **🤖 AI 助手（NL2SQL + 规则引擎）**：中文提问 → 自动生成 SQL → 执行 → 用自然语言回答并附结果表与 ECharts 图表；内置规则引擎命中高频问题时**秒级响应**，模型离线时仍可回答。
- **💰 年费用自动计算与一键补写**：**：基于国知局公开阶梯标准（发明 20 / 实用新型 10 / 外观 15 年）+ 费减比例（85% / 70%）自动推算应缴金额与到期日，并审计漏写年份。**
- **🔗 奖金↔专利三级名称匹配**：历史奖金常以"英文 + （中文）"混合记录，专利库对不上。系统实现**归一化 → 片段精确 → 双向包含**三级匹配，自动打通关联。
- **📊 汇报材料导出**：看板图表一键导出 **PPT（原生图表）/ PDF（中文字体 + 矢量图）/ 自包含 HTML**，支持按模块筛选与 AI 分析页。
- **🔐 安全与可追溯**：JWT 鉴权 + bcrypt 密码哈希；关键写操作落审计日志；敏感配置走环境变量，`.env` 不入库。

---

## 🛠 技术栈 · Tech Stack

| 层 | 技术 |
| --- | --- |
| 后端 | Python · **FastAPI** · SQLAlchemy · Pydantic · SQLite (WAL) |
| 前端 | Vue 3 · Vite · Element Plus · ECharts |
| AI | 本地大模型（OpenAI 兼容 /chat/completions） + 正则规则引擎兜底 |
| 导出 | python-pptx · reportlab · openpyxl · 内联 CSS HTML |
| 安全 | bcrypt（密码） · JWT（鉴权） · 审计日志 |
| 部署 | 单进程 uvicorn（静态资源 + SPA 兜底路由） |

---

## ✨ 功能 · Features

### 专利台账
五类专利统一管理（发明 / 实用新型 / 外观 / 软著 / 软产），覆盖申请号、授权号、IPC 分类、发明人（含贡献比例）、代理机构、快速审查与费减标记。按类型、状态、申请年、授权年多维筛选。

### 商标台账
尼斯分类（1–45 类）多选、图形商标预览、注册范围库分组管理；自动计算有效期与**续展提醒**（90 天内到期自动进入待续展清单）。

### 年费管理
按专利类型与费减比例**批量生成年费计划**，支持待缴 / 已缴 / 逾期 / 滞纳金四种状态、滞纳金自动计算。
内置**完整性审核**：对比"按类型应有年份"与"实有记录"，标出漏写年份并支持一键补写（只补缺失、不覆盖已有）。

### 发明人奖金
批次 → 条目 → 明细三级链路。按奖励规则（受理 / 授权 / PCT 叠加）自动计算应发金额，按发明人贡献比例拆分到个人；支持审批流、Excel 批量导入与发放状态跟踪。

### 数据看板
ECharts 绘制类型分布、申请趋势、部门奖金分布、发明人 TOP10 等图表，支持**按年份筛选**。

### 汇报材料导出
- **PPT**：按模板版式生成，图表为 PPT 原生对象（可二次编辑）
- **PDF**：reportlab 矢量绘制，注册中文字体避免乱码
- **HTML**：自包含单文件（内联 CSS + ECharts），双击即开，便于邮件分发
- 三种格式均支持**按模块筛选**与可选的 **AI 分析页**

### 🤖 AI 助手
- 中文自然语言提问，自动生成并执行 SQL，**用自然语言回答 + 结果表 + 图表**
- **规则引擎优先**：高频问题（被驳回专利 / 待续展商标 / 年费缴纳情况…）走确定性规则，秒回且结果 100% 可控
- 模型不可达时自动降级为规则引擎，**新电脑零配置也能演示**

### 文件中心与导入导出
专利 / 商标文档按业务实体归档；支持 Excel 批量导入导出（含中英文表头自适应解析）。

---

## 🚀 快速开始 · Quick Start

### 环境要求
- Python **3.10+**
- Node.js **18+**（仅开发模式需要；生产部署直接用已构建的 `backend/static`）

### 一键启动（推荐，**不需要前端开发**）

```bash
cd backend
python -m venv venv
source venv/bin/activate              # Windows: venv\Scripts\activate
pip install -r requirements.txt
python seed_demo.py                  # 生成虚构演示数据（固定随机种子，重复执行幂等）
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 <http://localhost:8000>，登录：

| 账号 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `admin123` | 管理员 |
| `demo` | `demo123` | 普通成员 |

### 前端开发模式（可选）

```bash
cd frontend
npm install
npm run dev        # 默认 5173 端口，API 自动代理到后端
npm run build      # 构建产物输出到 backend/static，供后端单进程托管
```

### 项目根目录还提供了一键启动脚本

- `启动系统.bat`（Windows）：自动建 venv → 装依赖 → 生成数据 → 启动并打开浏览器
- `start.sh`（macOS / Linux）：同上

---

## 📁 项目结构 · Structure

```
ip-system/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口、静态托管、SPA 兜底
│   │   ├── config.py            # 配置（敏感项全部走环境变量，不入库）
│   │   ├── models.py            # 18 张表的 SQLAlchemy 模型
│   │   ├── fee_calculator.py    # 年费阶梯计算 + 完整性审核
│   │   ├── patent_match.py      # 奖金 ↔ 专利 三级名称匹配
│   │   ├── ai_bridge.py         # 大模型抽象层（none / local / cloud 三档）
│   │   └── routers/             # 业务路由
│   ├── seed_demo.py             # 虚构演示数据生成器（固定种子）
│   └── requirements.txt
└── frontend/src/                # Vue 3 页面与组件
```

---

## ⚙️ 配置 · Configuration

| 变量 | | 默认值 |
| --- | --- | --- |
| `DATABASE_URL` | 数据库连接串 | `sqlite:///backend/ip_system.db` |
| `SECRET_KEY` | JWT 签名密钥 | 首次启动自动生成并写入 `.env` |
| `AI_MODE` | `none` / `local` / `cloud` | `none` |
| `AI_LOCAL_BASE_URL` | 本地大模型地址 | 空 |
| `PORT` | 监听端口 | `8000` |

> **所有敏感配置走环境变量或 `backend/.env`，不写入代码**。
> AI 为**可选项**——不配置时规则引擎仍可回答常见问题，其余功能完全不受影响。

---

## 📄 文档 · Documentation

完整的需求说明 / 数据表设计 / 部署清单（含本系统的需求设计文档与脱敏开发过程）见仓库根目录 `docs/`：

- `docs/01-IP管理系统-需求与设计文档.md`
- `docs/03-数据表设计.md`
- `docs/05-IT协调与资源申请清单.md`

---

## 📄 许可 · License

[MIT](LICENSE) — 代码可自由使用与修改。

> 本项目中的专利、商标、发明人、机构等数据均为 `seed_demo.py` 生成的虚构演示数据；
> 年费金额参考国家知识产权局**公开**收费标准。