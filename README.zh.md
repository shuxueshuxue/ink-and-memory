# Ink & Memory

<p align="center">
  <img src="assets/banner.png" alt="Ink & Memory 横幅" width="700"/>
</p>

<p align="center">
  中文 · <a href="README.md">English</a>
</p>

> *书写、反思、倾听内心的声音。*

**Ink & Memory** 是一款受《极乐迪斯科》启发的日记工作室。当你写作时，一群性格迥异的内心声音会加入对话——提供视角、提出问题，或者点出你处境的荒诞之处。

这不只是一个笔记本，而是一个日常写作伴侣。它保存你的作品、整理你的思绪，帮助你发现自己思维中的模式。它同时支持中英文，并能根据你的输入自动切换。

---

## 它有什么不同

<p align="center">
  <img src="assets/writing-area.png" alt="写作界面" width="700"/>
</p>

**简洁的写作空间。** 没有工具栏的干扰，只有一个平静的书写界面，自动保存让你无需担心丢失任何内容。

**一组内心声音。** 当你打字时，不同的角色会高亮你的短语并给出他们的见解——从善于观察的「照镜者」到黑色幽默的「幽默者」。它们以淡雅的水彩高亮出现在边栏，从不打断你的思路。

**可视化的时间线。** 每次写作都会保存到日历中。每一天都会根据你的内容生成一张独特的图片——一本与你一同成长的视觉日记。

**完全可定制。** 不喜欢某个声音？编辑它。想要新的视角？创建自己的卡组。把你的作品分享到社区，或者发现别人的创作。

---

## 这些声音

这些声音被组织成三个卡组。启用与你共鸣的，禁用其余的。

### 内省卡组
*用于处理情绪和理解自我*

| | 声音 | 作用 |
|---|---|---|
| ❤️ | **接纳者** | 提供温柔的认可与支持 |
| 👁️ | **照镜者** | 反映你可能没注意到的模式 |
| 👊 | **启动者** | 用微小的第一步打破拖延 |
| 🧭 | **连接者** | 找到连接你思绪的隐藏线索 |
| 🎭 | **幽默者** | 用黑色幽默化解沉重 |

### 学者卡组
*提供智识和学术视角*

| | 声音 | 作用 |
|---|---|---|
| 🧭 | **语言学家** | 分析结构、语义、含义 |
| 👁️ | **画家** | 关注意象、美学、情绪 |
| 💡 | **物理学家** | 应用能量和系统的原理 |
| 🧠 | **计算机科学家** | 用算法和复杂度思考 |
| ❤️ | **医生** | 提供健康和心理学视角 |
| 🧭 | **历史学家** | 提供背景和历史模式 |

### 哲学卡组
*通过不同哲学流派审视人生*

| | 声音 | 作用 |
|---|---|---|
| 🛡️ | **斯多葛派** | 强调你能控制和不能控制的 |
| 💨 | **道家** | 指向无为和顺其自然 |
| 🤔 | **存在主义者** | 追问选择、自由、意义 |
| 👊 | **实用主义者** | 关注什么真正有效 |

### 创建你自己的

每个声音只是一个系统提示词、一个图标和一种颜色。复刻任何卡组来定制它。创建能表达你喜欢的思想家、关注生活特定方面、或者仅仅让你发笑的声音。在社区商店分享它们。

---

## 开始使用

### 你需要
- Python 3.11+ 和 [uv](https://github.com/astral-sh/uv)
- Node.js 18+

### 后端设置

```bash
cd backend
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

复制 `models.json` 文件并配置你的大语言模型：

```json
{
  "models": {
    "gemini-3-flash-preview": {
      "endpoint": "https://openrouter.ai/api/v1",
      "api_key": "your-key-here",
      "model": "google/gemini-3-flash-preview"
    }
  },
  "roles": {
    "voice_analysis": "gemini-3-flash-preview",
    "voice_chat": "gemini-3-flash-preview"
  }
}
```

完整配置选项（包括图片生成设置）请参考 `backend/models.json.example`。

然后启动服务器：

```bash
python server.py  # 运行在 http://localhost:8765
```

### 手动初始化数据库

首次启动前需要手动创建 SQLite 表结构：

```bash
cd backend
python database.py
```

### 前端设置

```bash
cd frontend
npm install
npm run dev  # 运行在 http://localhost:5173
```

---

## 它如何工作

声音系统使用**基于轨迹的能量模型**：

1. **能量累积**——随着你的输入而增长
2. **阈值触发**——分析你最近写下的内容
3. **声音扫描**——寻找与其个性匹配的短语
4. **评论出现**——以水彩高亮的形式出现在边栏

这创造了一种自然的节奏——声音们自然地加入，而不是不断打断。

---

## 技术栈

**前端：** React 19 + TypeScript，Vite，带有自定义扩展的 TipTap 编辑器

**后端：** FastAPI + Python，PolyCLI 用于 LLM 编排，SQLite WAL 模式

**AI：** 多模型支持（GPT-4、Claude、DeepSeek、Gemini），通过 Pydantic 实现结构化输出

**架构：** 基于卡组的声音系统，父子关系继承，社区商店用于分享

---

## 路线图

- 更多声音和社区创建的卡组
- 更丰富的写作模式可视化
- 移动端应用，随时随地写作
- 协作功能

---

## 部署

将 Ink & Memory 部署到 **Google Cloud Run**（前后端分离，SQLite 通过 Cloud Storage FUSE 持久化）：

```bash
export GCP_PROJECT_ID=your-project-id
./deploy/google-cloud/deploy.sh setup-storage  # 一次性：GCS bucket + 服务账号
./deploy/google-cloud/deploy.sh setup-env      # 一次性：secrets + 环境变量
./deploy/google-cloud/deploy.sh deploy         # 每次发版执行
```

完整说明见 [docs/deploy/overview.md](docs/deploy/overview.md)。

---

## 参与贡献

这是一个开源项目，我们欢迎你的参与。

- **发现了 bug？** 提一个 issue
- **有想法？** 我们来讨论
- **想写代码？** 欢迎 PR
- **创建了很棒的卡组？** 分享给社区

---

<p align="center">
  <i>你的思想值得被倾听——哪怕是被你自己。</i>
</p>
