# 动漫数字人 · Anime-Digital-Human

直播间数字人：观众评论 → AI 回答 → 语音合成 → 嘴型动画。潮玩盲盒带货场景。

> 核心指标：能实时答、不瞎编（知识库命中率 ≥90%、端到端延迟 ≤10s）。

---

## 🎬 Demo（嘴型同步视频）

| 视频 | 观众评论 | 回答（节选） |
|---|---|---|
| [demo_0_价格](demo/demo_0_价格.mp4) | 这个多少钱？ | 单盒 69，端盒更划算 |
| [demo_1_正品](demo/demo_1_正品.mp4) | 是正品吗？ | 正品、官方授权、支持验真 |
| [demo_2_隐藏款](demo/demo_2_隐藏款.mp4) | 隐藏款概率是多少？ | 以官方公布为准，整箱必出一个 |
| [demo_3_发货](demo/demo_3_发货.mp4) | 什么时候发货？ | 48 小时内发货，默认顺丰 |

形象为偏写实动漫半身像，1728×2154、25fps，仅嘴部/眼部动，身体保持静止。

---

## 🏗️ 架构

```
观众评论
   │
   ▼
[本地] RAG 检索  ──►  BGE 向量化 + ChromaDB（防瞎编，命中则照抄标准答案）
   │
   ▼
[本地] DeepSeek 生成回答（没 key 时降级为 FAQ 标准答案）
   │
   ▼
[本地] edge-tts 合成语音
   │
   ▼  上传
[远端] SadTalker 推理（GPU）→ 嘴型同步视频
   │
   ▼  下载
推回直播间
```

- **脑**：DeepSeek
- **记忆**：ChromaDB + BGE（`BAAI/bge-small-zh-v1.5`）
- **嘴**：edge-tts
- **脸**：SadTalker（AutoDL GPU，face_alignment + 3DMM + audio2exp + facerender）

---

## 📁 目录结构

```
├── README.md
├── 复盘_数字人实现.md            # 踩坑与修复全过程复盘
├── MRD-电商数字人直播系统.md      # 产品文档
├── PRD-电商数字人直播系统.md
├── 潮玩-话术脚本与知识库.md
├── demo/                         # 嘴型同步成品视频
│   ├── demo_0_价格.mp4
│   ├── demo_1_正品.mp4
│   ├── demo_2_隐藏款.mp4
│   └── demo_3_发货.mp4
└── src/                          # 实现代码
    ├── main.py                   # 音频闭环主入口
    ├── kb.py                     # RAG 记忆
    ├── gen_audios.py             # 批量生成 demo 音频
    ├── faq.json                  # 知识库
    ├── face_test.py              # 人脸检测冒烟测试
    ├── patch_croper.py           # SadTalker 补丁
    ├── batch_infer.sh            # 远端批量推理脚本
    ├── remote.py / upload.py     # AutoDL 连接工具（密码走环境变量）
    └── .env.example              # 配置模板
```

---

## 🚀 快速开始

### 1. 本地音频闭环（脑 + 记忆 + 嘴）

```bash
cd src
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt                        # 见下
cp .env.example .env                                  # 填入 DEEPSEEK_API_KEY
python kb.py build                                    # 首次建索引
python main.py "这个多少钱？"                          # 生成 answer.wav
```

### 2. 远端嘴型驱动（脸，需 GPU）

SadTalker 部署在 AutoDL 实例上，`remote.py` / `upload.py` 负责连远端：

```bash
python remote.py "nvidia-smi"                                  # 测连通
python upload.py "answer.wav=/root/autodl-tmp/answer.wav"      # 传音频
# 远端跑推理（完整命令与踩坑见 复盘_数字人实现.md）
```

### 依赖

```
openai  edge-tts  chromadb  sentence-transformers  python-dotenv  paramiko
```

---

## ⚠️ 说明

- **敏感信息**：`DEEPSEEK_API_KEY`、`AUTODL_PWD` 等一律放在 `.env`（已 gitignore），提交的是 `.env.example` 占位模板。
- **实时性现状**：8 秒音频约 90 秒出片，瓶颈在 `seamlessClone`（回贴全图），距 10s 目标还差，是后续优化重点。
- 完整实现细节、坑位与修复见 [`复盘_数字人实现.md`](复盘_数字人实现.md)。
