# Resource Connector — 四层架构工程设计稿

Status: Draft  
Updated: 2026-06-28
Scope: 工程设计 — 资源连接器认证层、数据层、操作层、任务层详细设计

> [Input] `docs/design/notion-session/overview.md`,
>      `docs/design/notion-session/connector-interaction.md`
> [Output] 资源连接器四层架构的完整工程设计，含接口定义、数据结构、错误处理、扩展点
> [Pos] resource-connector-layer-design in `docs/design/claude-agent/notion-point`
> [Sync] 2026-06-22: 初始设计 — 四层架构工程设计稿
> [Sync] 2026-06-22: 迁移至 claude-agent/notion-point — 工作空间映射相关设计独立管理
> [Sync] 2026-06-28: 数据层收敛为 canonical snapshot 权威状态；Agent 初始化读取连接器数据层快照，`NotionCache` 不再作为跨 Agent source of truth。

---

## 目录

1. [设计概览](#1-设计概览)
2. [认证层设计（Auth Layer）](#2-认证层设计auth-layer)
3. [数据层设计（Data Layer）](#3-数据层设计data-layer)
4. [操作层设计（Operation Layer）](#4-操作层设计operation-layer)
5. [任务层设计（Task Layer）](#5-任务层设计task-layer)
6. [层间协议与依赖关系](#6-层间协议与依赖关系)
7. [扩展点与多平台适配](#7-扩展点与多平台适配)
8. [实现文件索引](#8-实现文件索引)

---

## 1. 设计概览

### 1.1 架构全景

```
┌──────────────────────────────────────────────────────────────────┐
│                   Resource Connector (资源连接器)                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                  Task Layer (任务层)                         │  │
│  │  调度编排层 — 编排认证、同步、操作等跨层工作流                    │  │
│  │  • 定时 Sync 调度       • 批量 Import 编排                   │  │
│  │  • 重试策略管理         • 任务状态机                          │  │
│  └────────────────────────┬───────────────────────────────────┘  │
│                           │ 调用                                  │
│  ┌────────────────────────┼───────────────────────────────────┐  │
│  │              Operation Layer (操作层)                        │  │
│  │  业务操作封装 — 将平台 API 映射为统一业务语义                    │  │
│  │  • Page CRUD            • Database Query                    │  │
│  │  • Search               • Block Read/Write                  │  │
│  └────────────────────────┬───────────────────────────────────┘  │
│                           │ 依赖                                  │
│  ┌────────────────────────┼───────────────────────────────────┐  │
│  │               Data Layer (数据层)                            │  │
│  │  数据与快照映射 — canonical snapshot + .notion/ 虚拟索引       │  │
│  │  • SnapshotStore        • PreToolUse 只读解析                 │  │
│  │  • 快照版本生成         • 增量/全量同步                       │  │
│  └────────────────────────┬───────────────────────────────────┘  │
│                           │ 依赖                                  │
│  ┌────────────────────────┼───────────────────────────────────┐  │
│  │                Auth Layer (认证层)                           │  │
│  │  认证与凭证管理 — 连接平台的身份凭证生命周期                     │  │
│  │  • ntn login 编排       • Token 刷新/校验                    │  │
│  │  • NOTION_HOME 管理     • 认证状态机                          │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| 单一职责 | 每层仅关注自身领域，不越层调用 |
| 向下依赖 | 上层可调用下层，下层不感知上层 |
| 接口抽象 | 每层通过 Protocol/ABC 定义接口，实现可替换 |
| 错误隔离 | 每层定义自身错误类型，向上抛出统一异常 |
| 可测试性 | 每层可独立 mock 测试，不依赖真实平台 |

### 1.3 各层实现优先级

| 层 | 本期状态 | 依赖 |
|----|---------|------|
| Auth Layer | ✅ 实现 | 无 |
| Data Layer | ✅ 实现 | Auth Layer |
| Operation Layer | ⏳ 设计完成，按需实现 | Auth Layer + Data Layer |
| Task Layer | ⏳ 设计完成，按需实现 | 全部下层 |

---

## 2. 认证层设计（Auth Layer）

### 2.1 职责边界

认证层负责：
- 管理用户与外部平台的认证凭证生命周期
- 提供统一的认证状态查询接口
- 封装平台特定的认证协议（OAuth、Device Code、CLI Login）
- 自动检测凭证过期并触发续期

认证层**不**负责：
- 数据获取（属于 Data Layer）
- 业务操作（属于 Operation Layer）
- 调度编排（属于 Task Layer）

### 2.2 认证状态机

```
                    ┌─────────────┐
                    │  INITIAL    │
                    │  (未配置)    │
                    └──────┬──────┘
                           │ 用户发起认证
                           ▼
                    ┌─────────────┐
          ┌────────│  PENDING    │
          │        │  (等待确认)  │
          │        └──────┬──────┘
          │               │ 用户浏览器确认
          │               ▼
          │        ┌─────────────┐
          │        │ AUTHENTICATED│◄──── Token 刷新成功
          │        │  (已认证)    │
          │        └──────┬──────┘
          │               │ Token 过期 / API 401
          │               ▼
          │        ┌─────────────┐
          └───────►│  EXPIRED    │
   超时/取消       │  (已过期)    │
                   └──────┬──────┘
                          │ 用户重新认证
                          ▼
                   ┌─────────────┐
                   │  PENDING    │
                   └─────────────┘
```

### 2.3 接口定义

```python
# backend/notion/auth.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

class AuthStatus(Enum):
    INITIAL = "initial"
    PENDING = "pending"
    AUTHENTICATED = "authenticated"
    EXPIRED = "expired"

@dataclass
class AuthCredential:
    """认证凭证数据对象。"""
    status: AuthStatus
    notion_home: Path
    token_path: Optional[Path] = None
    expires_at: Optional[str] = None  # ISO 8601
    last_verified_at: Optional[str] = None

@dataclass
class LoginInitResult:
    """登录发起结果。"""
    verification_url: str
    verification_code: str
    poll_interval_seconds: int = 5

class AuthLayerProtocol(ABC):
    """认证层抽象接口 — 所有平台认证必须实现。"""

    @abstractmethod
    async def init_login(self, user_id: str) -> LoginInitResult:
        """发起认证流程，返回验证 URL 和验证码。"""
        ...

    @abstractmethod
    async def poll_login(self, user_id: str) -> AuthCredential:
        """轮询认证完成状态。"""
        ...

    @abstractmethod
    async def verify_status(self, user_id: str) -> AuthCredential:
        """验证当前认证状态是否有效。"""
        ...

    @abstractmethod
    async def revoke(self, user_id: str) -> None:
        """撤销认证，清理凭证。"""
        ...

    @abstractmethod
    def get_env(self, user_id: str) -> dict[str, str]:
        """获取执行 CLI 命令所需的环境变量。"""
        ...
```

### 2.4 Notion 认证层实现

```python
# backend/notion/auth_impl.py

class NotionAuthLayer(AuthLayerProtocol):
    """Notion 平台认证层实现 — 基于 ntn CLI。"""

    def __init__(self, config_base: Path):
        self._config_base = config_base  # 用户配置根目录

    async def init_login(self, user_id: str) -> LoginInitResult:
        """执行 ntn login --no-browser，解析 stdout 提取验证信息。"""
        notion_home = self._get_user_notion_home(user_id)
        env = self._build_env(notion_home)

        proc = await asyncio.create_subprocess_exec(
            "ntn", "login", "--no-browser",
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        # 解析 verification URL 和 code
        return self._parse_login_output(stdout.decode())

    async def poll_login(self, user_id: str) -> AuthCredential:
        """执行 ntn login poll，阻塞等待用户确认。"""
        ...

    async def verify_status(self, user_id: str) -> AuthCredential:
        """执行 ntn auth status，检查 token 有效性。"""
        ...

    async def revoke(self, user_id: str) -> None:
        """执行 ntn logout，清理本地 token。"""
        ...

    def get_env(self, user_id: str) -> dict[str, str]:
        """构建 NOTION_HOME + PATH 环境变量。"""
        notion_home = self._get_user_notion_home(user_id)
        return {
            **os.environ,
            "NOTION_HOME": str(notion_home),
        }

    # --- 内部方法 ---

    def _get_user_notion_home(self, user_id: str) -> Path:
        return self._config_base / user_id / "notion"

    def _build_env(self, notion_home: Path) -> dict[str, str]:
        return {"NOTION_HOME": str(notion_home), **os.environ}

    def _parse_login_output(self, output: str) -> LoginInitResult:
        """从 ntn login 输出中提取 verificationUrl 和 verificationCode。"""
        ...
```

### 2.5 错误类型

```python
class AuthError(Exception):
    """认证层基础异常。"""
    pass

class AuthLoginTimeoutError(AuthError):
    """认证登录超时（用户未在规定时间内确认）。"""
    pass

class AuthTokenExpiredError(AuthError):
    """Token 已过期，需要重新认证。"""
    pass

class AuthCLINotFoundError(AuthError):
    """ntn CLI 未安装或不在 PATH 中。"""
    pass

class AuthRevokedError(AuthError):
    """认证已被用户或平台主动撤销。"""
    pass
```

### 2.6 安全约束

| 约束 | 实施方式 |
|------|---------|
| Token 不存入数据库 | Token 仅存于 NOTION_HOME 文件系统 |
| Token 路径权限 | `chmod 600` 确保仅当前进程用户可读 |
| 环境隔离 | 每个用户独立 NOTION_HOME 目录 |
| 传输安全 | 不在 API Response 中返回 token 明文 |
| 超时保护 | poll_login 设置最大等待时间（默认 300s） |

---

## 3. 数据层设计（Data Layer）

### 3.1 职责边界

数据层负责：

- 从 Operation Layer 的 Notion 远程读取结果中物化 `CanonicalWorkspaceSnapshot`
- 维护 current snapshot 指针、历史版本和审计字段
- 为任意 Agent 初始化提供同一 `workspaceId + connectorId + snapshotVersion` 下的一致快照
- 通过 `.notion/` 虚拟索引解析 snapshot 内容
- 记录 `sourceRevision` / `syncCursor`，为写入 proposal 做乐观并发校验

数据层**不**负责：

- 认证管理（调用 Auth Layer 获取 env）
- Notion 业务 API 细节（属于 Operation Layer）
- 调度触发（由 Task Layer 驱动）
- Agent 本地摘要、排序或 prompt 裁剪
- 在 Agent Read 时直接调用远程 Notion

### 3.2 数据架构

```
┌──────────────────────────────────────────────────────────────┐
│                         Data Layer                            │
│                                                              │
│  ┌───────────────────────┐     ┌──────────────────────────┐  │
│  │ Canonical Snapshot    │     │ .notion/ Virtual Index   │  │
│  │ Store                 │────►│ read-only view           │  │
│  │                       │     │                          │  │
│  │ current pointer       │     │ snapshot.json            │  │
│  │ snapshot history      │     │ connector.json           │  │
│  │ sourceRevision        │     │ index.json               │  │
│  │ syncCursor            │     │ databases/<id>.json      │  │
│  │ audit metadata        │     │ pages/<id>.json          │  │
│  └──────────┬────────────┘     └──────────┬───────────────┘  │
│             │                             │                  │
│             │ Agent init / attach          │ PreToolUse Read  │
│             ▼                             ▼                  │
│       ClaudeAgentService             Claude Agent            │
└──────────────────────────────────────────────────────────────┘
```

### 3.3 接口定义

```python
# backend/notion/data.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class SnapshotIdentity:
    workspace_id: str
    resource_connector_id: str
    snapshot_version: str
    source_revision: str
    sync_cursor: str
    fetched_at: str

@dataclass
class SyncResult:
    """同步结果。"""
    synced_databases: int
    synced_pages: int
    failed_items: list[str]
    duration_ms: int
    sync_type: str  # "full" | "incremental"
    snapshot_identity: SnapshotIdentity

class DataLayerProtocol(ABC):
    """数据层抽象接口。"""

    @abstractmethod
    async def sync_full(self, workspace_id: str, connector_id: str) -> SyncResult:
        """全量同步并物化新的 canonical snapshot。"""
        ...

    @abstractmethod
    async def sync_incremental(self, workspace_id: str, connector_id: str) -> SyncResult:
        """增量同步并在有变更时物化新的 canonical snapshot。"""
        ...

    @abstractmethod
    async def get_current_snapshot(
        self, workspace_id: str, connector_id: str
    ) -> dict[str, Any]:
        """返回当前 canonical snapshot；任意 Agent 初始化都通过此接口读取。"""
        ...

    @abstractmethod
    async def get_snapshot(
        self, workspace_id: str, connector_id: str, snapshot_version: str
    ) -> dict[str, Any]:
        """返回指定版本 snapshot，用于审计、冲突和旧版本只读查看。"""
        ...

    @abstractmethod
    def resolve_virtual_path(self, path: str, snapshot: dict[str, Any]) -> dict[str, Any] | None:
        """从已 attach 的 snapshot 解析 `.notion/` 虚拟路径。"""
        ...
```

### 3.4 Snapshot 数据合同

最小方案代码已落地在 `backend/libs/claude_agent_kit/server/notion_snapshot.py`：

| 类型 / 函数 | 作用 |
|---|---|
| `SnapshotLifecycleState` | 定义 `pending_sync`、`snapshot_ready`、`stale`、`conflict` 等状态 |
| `SnapshotMetadata` | 保存 `workspace_id`、`resource_connector_id`、`snapshot_version`、`source_revision`、`sync_cursor`、`fetched_at` |
| `CanonicalWorkspaceSnapshot` | 连接器数据层返回给 Agent 的只读快照 |
| `AgentDerivedContext` | Agent 本地派生视图，不作为权威状态 |
| `SnapshotWriteProposal` | 写入 proposal 的 base snapshot identity |
| `get_notion_snapshot_resource_data()` | 从 snapshot 解析 `.notion/` 虚拟路径 |
| `write_proposal_is_stale()` | 判断 proposal 是否因快照变更而过期 |

### 3.5 PreToolUse 拦截映射表

| 虚拟路径 | 映射数据源 | 触发条件 |
|---------|-----------|---------|
| `.notion/snapshot.json` | `snapshot.metadata` | Agent Read |
| `.notion/connector.json` | `snapshot.connector + metadata` | Agent Read |
| `.notion/index.json` | `snapshot.index + metadata` | Agent Read |
| `.notion/databases.json` | `snapshot.databases + metadata` | Agent Read |
| `.notion/databases/<db_id>.json` | `snapshot.database_pages[db_id] + metadata` | Agent Read |
| `.notion/pages/<page_id>.json` | `snapshot.pages[page_id] + metadata` | Agent Read |

如果页面未被物化在当前 snapshot 中，返回 snapshot-scoped miss，不在 Read hook 中远程 lazy load。

### 3.6 快照版本策略

| 事件 | 处理 |
|---|---|
| 首次连接器同步成功 | 创建 `snapshotVersion=1`，current pointer 指向该版本 |
| 手动刷新或增量同步有变更 | 创建新版本，旧版本进入 `snapshot_superseded` |
| Agent 初始化 | 读取 current pointer 指向的 snapshot；同版本多 Agent 必须一致 |
| 写入 proposal 提交前 | 比较 base `snapshotVersion/sourceRevision/syncCursor` 与 current snapshot |
| 远程写入确认后 | 重新 sync 并创建新 snapshot，而不是直接 patch 旧 snapshot |

### 3.7 增量同步设计

```python
@dataclass
class SyncCheckpoint:
    """同步检查点 — 记录上次同步位置。"""
    connector_id: str
    last_sync_at: str               # ISO 8601
    last_cursor: Optional[str]      # Notion API 分页游标
    source_revision: str

class IncrementalSyncStrategy:
    """增量同步策略。"""

    async def detect_changes(
        self, checkpoint: SyncCheckpoint, auth_env: dict
    ) -> list[str]:
        """检测自上次同步以来的变更 page_id 列表。"""
        # 使用 ntn api v1/search 的 sort 参数按 last_edited_time 降序
        # 比较 checkpoint.last_sync_at，提取变更页面
        ...

    async def materialize_snapshot(self, changed_ids: list[str]) -> SnapshotIdentity:
        """将变更合并为新的 canonical snapshot。"""
        ...
```

### 3.8 错误类型

```python
class DataLayerError(Exception):
    """数据层基础异常。"""
    pass

class SnapshotNotReadyError(DataLayerError):
    """连接器尚未物化可用 snapshot。"""
    pass

class SnapshotConflictError(DataLayerError):
    """写入 proposal 的 base identity 与 current snapshot 不匹配。"""
    pass

class SyncError(DataLayerError):
    """同步过程失败。"""
    pass

class RateLimitError(DataLayerError):
    """API 限流。"""
    retry_after_seconds: int
```

---

## 4. 操作层设计（Operation Layer）

### 4.1 职责边界

操作层负责：
- 将平台 API 操作映射为统一业务语义
- 封装 CRUD 操作的参数校验与响应解析
- 提供幂等操作保障
- 管理操作的权限校验

操作层**不**负责：
- 认证管理（通过 Auth Layer 获取凭证）
- 快照版本管理（操作结果交给 Data Layer 物化 snapshot）
- 调度编排（由 Task Layer 驱动批量操作）

### 4.2 操作类型分类

```
Operation Layer
  │
  ├── Read Operations (只读操作)
  │     ├── search         — 搜索 Page/Database
  │     ├── get_page       — 获取单页完整内容
  │     ├── query_database — 查询 Database Row Pages
  │     └── get_blocks     — 获取 Page 的 Block 列表
  │
  ├── Write Operations (写操作 — 后续实现)
  │     ├── create_page    — 创建新页面
  │     ├── update_page    — 更新页面属性
  │     ├── append_blocks  — 追加 Block 内容
  │     └── delete_block   — 删除 Block
  │
  └── Meta Operations (元操作)
        ├── list_users     — 列出工作空间用户
        └── get_self       — 获取当前认证用户信息
```

### 4.3 接口定义

```python
# backend/notion/operations.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class SearchFilter:
    """搜索过滤条件。"""
    object_type: Optional[str] = None   # "page" | "database"
    query: Optional[str] = None
    page_size: int = 100
    start_cursor: Optional[str] = None

@dataclass
class SearchResult:
    """搜索结果。"""
    results: list[dict]
    has_more: bool
    next_cursor: Optional[str]

@dataclass
class DatabaseQuery:
    """数据库查询条件。"""
    database_id: str
    filter: Optional[dict] = None       # Notion filter object
    sorts: Optional[list[dict]] = None  # Notion sorts array
    page_size: int = 100
    start_cursor: Optional[str] = None

@dataclass
class OperationResult:
    """操作结果通用包装。"""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    request_id: Optional[str] = None

class OperationLayerProtocol(ABC):
    """操作层抽象接口。"""

    # --- Read Operations ---

    @abstractmethod
    async def search(self, filter: SearchFilter) -> SearchResult:
        """搜索 Notion 工作空间内容。"""
        ...

    @abstractmethod
    async def get_page(self, page_id: str) -> OperationResult:
        """获取页面完整内容（属性 + Blocks）。"""
        ...

    @abstractmethod
    async def query_database(self, query: DatabaseQuery) -> SearchResult:
        """查询指定 Database 下的 Row Pages。"""
        ...

    @abstractmethod
    async def get_blocks(self, block_id: str) -> OperationResult:
        """获取指定 Block 的子 Block 列表。"""
        ...

    # --- Write Operations (Future) ---

    @abstractmethod
    async def create_page(
        self, parent_id: str, parent_type: str, properties: dict, children: list[dict]
    ) -> OperationResult:
        """在指定 parent 下创建新 Page。"""
        ...

    @abstractmethod
    async def update_page(self, page_id: str, properties: dict) -> OperationResult:
        """更新 Page 的属性值。"""
        ...

    @abstractmethod
    async def append_blocks(self, block_id: str, children: list[dict]) -> OperationResult:
        """向指定 Block 追加子 Block。"""
        ...

    @abstractmethod
    async def delete_block(self, block_id: str) -> OperationResult:
        """删除（归档）指定 Block。"""
        ...
```

### 4.4 Notion 操作层实现

```python
# backend/notion/operations_impl.py

class NotionOperationLayer(OperationLayerProtocol):
    """Notion 操作层实现 — 基于 ntn api CLI 调用。"""

    def __init__(self, auth_layer: AuthLayerProtocol, user_id: str):
        self._auth = auth_layer
        self._user_id = user_id

    async def search(self, filter: SearchFilter) -> SearchResult:
        """通过 ntn api v1/search 执行搜索。"""
        env = self._auth.get_env(self._user_id)
        payload = self._build_search_payload(filter)
        result = await self._exec_ntn_api("v1/search", payload, env)
        return self._parse_search_result(result)

    async def get_page(self, page_id: str) -> OperationResult:
        """
        组合调用：
        1. ntn api v1/pages/<page_id>  → 获取属性
        2. ntn api v1/blocks/<page_id>/children → 获取内容
        """
        env = self._auth.get_env(self._user_id)
        page_data = await self._exec_ntn_api(f"v1/pages/{page_id}", None, env)
        blocks_data = await self._exec_ntn_api(
            f"v1/blocks/{page_id}/children", None, env
        )
        return OperationResult(
            success=True,
            data={"page": page_data, "blocks": blocks_data},
        )

    async def query_database(self, query: DatabaseQuery) -> SearchResult:
        """通过 ntn api v1/databases/<id>/query 查询。"""
        env = self._auth.get_env(self._user_id)
        payload = self._build_query_payload(query)
        result = await self._exec_ntn_api(
            f"v1/databases/{query.database_id}/query", payload, env
        )
        return self._parse_search_result(result)

    # --- 内部方法 ---

    async def _exec_ntn_api(
        self, endpoint: str, payload: Optional[dict], env: dict
    ) -> dict:
        """封装 ntn api 调用，统一超时与错误处理。"""
        args = ["ntn", "api", endpoint]
        if payload:
            args.extend(["--data", json.dumps(payload)])

        proc = await asyncio.create_subprocess_exec(
            *args,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=30.0
        )

        if proc.returncode != 0:
            raise OperationError(
                f"ntn api {endpoint} failed: {stderr.decode()}"
            )
        return json.loads(stdout)
```

### 4.5 操作权限矩阵

| 操作 | 只读连接器 | 读写连接器 | 说明 |
|------|-----------|-----------|------|
| search | ✅ | ✅ | 搜索始终允许 |
| get_page | ✅ | ✅ | 读取始终允许 |
| query_database | ✅ | ✅ | 查询始终允许 |
| get_blocks | ✅ | ✅ | 读取始终允许 |
| create_page | ❌ | ✅ | 需写权限 |
| update_page | ❌ | ✅ | 需写权限 |
| append_blocks | ❌ | ✅ | 需写权限 |
| delete_block | ❌ | ✅ | 需写权限 |

### 4.6 幂等性保障

```python
@dataclass
class IdempotencyKey:
    """幂等键 — 用于写操作去重。"""
    operation: str        # "create_page" | "update_page" | ...
    connector_id: str
    target_id: str        # page_id 或 parent_id
    content_hash: str     # 操作内容的 SHA256
    created_at: str

class IdempotencyGuard:
    """幂等性守卫 — 防止重复操作。"""

    def __init__(self, ttl_seconds: int = 300):
        self._keys: dict[str, IdempotencyKey] = {}
        self._ttl = ttl_seconds

    def check_and_record(self, key: IdempotencyKey) -> bool:
        """检查操作是否已执行。返回 True 表示是重复操作。"""
        existing = self._keys.get(key.content_hash)
        if existing and not self._is_expired(existing):
            return True  # 重复操作
        self._keys[key.content_hash] = key
        return False
```

### 4.7 错误类型

```python
class OperationError(Exception):
    """操作层基础异常。"""
    pass

class OperationNotPermittedError(OperationError):
    """操作权限不足（只读连接器尝试写操作）。"""
    pass

class OperationTimeoutError(OperationError):
    """操作执行超时。"""
    pass

class OperationConflictError(OperationError):
    """操作冲突（如并发更新同一 Page）。"""
    pass

class ResourceNotFoundError(OperationError):
    """目标资源不存在。"""
    resource_id: str
```

---

## 5. 任务层设计（Task Layer）

### 5.1 职责边界

任务层负责：
- 编排跨层工作流（认证 → 同步 → 校验）
- 管理定时任务调度（定时同步、过期检测）
- 批量操作的并发控制与进度追踪
- 任务生命周期管理（创建、执行、重试、完成、失败）

任务层**不**负责：
- 底层 API 调用（委托 Operation Layer）
- 快照内容解析（通知 Data Layer 物化 snapshot）
- 认证流程细节（委托 Auth Layer）

### 5.2 任务状态机

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  CREATED │────►│ RUNNING  │────►│ COMPLETED│     │  FAILED  │
│  (已创建) │     │  (执行中) │     │  (已完成) │     │  (已失败) │
└──────────┘     └─────┬────┘     └──────────┘     └──────────┘
                       │                                  ▲
                       │ 失败                              │
                       ├──────────────────────────────────┘
                       │
                       │ 可重试
                       ▼
                ┌──────────┐
                │ RETRYING │
                │  (重试中) │
                └─────┬────┘
                      │ 重试成功/失败
                      ├──────────► COMPLETED
                      └──────────► FAILED (超过最大重试次数)
```

### 5.3 接口定义

```python
# backend/notion/tasks.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Any

class TaskStatus(Enum):
    CREATED = "created"
    RUNNING = "running"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskType(Enum):
    FULL_SYNC = "full_sync"
    INCREMENTAL_SYNC = "incremental_sync"
    PAGE_FETCH = "page_fetch"
    BATCH_IMPORT = "batch_import"
    AUTH_VERIFY = "auth_verify"
    SNAPSHOT_ARCHIVE_CLEANUP = "snapshot_archive_cleanup"

@dataclass
class TaskConfig:
    """任务配置。"""
    max_retries: int = 3
    retry_delay_seconds: int = 5
    retry_backoff_multiplier: float = 2.0
    timeout_seconds: int = 120
    concurrency_limit: int = 5

@dataclass
class TaskProgress:
    """任务进度。"""
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    current_item: Optional[str] = None

    @property
    def percentage(self) -> float:
        if self.total_items == 0:
            return 0.0
        return (self.completed_items / self.total_items) * 100

@dataclass
class Task:
    """任务实体。"""
    task_id: str
    task_type: TaskType
    connector_id: str
    status: TaskStatus = TaskStatus.CREATED
    config: TaskConfig = field(default_factory=TaskConfig)
    progress: TaskProgress = field(default_factory=TaskProgress)
    retry_count: int = 0
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

class TaskLayerProtocol(ABC):
    """任务层抽象接口。"""

    @abstractmethod
    async def submit(self, task_type: TaskType, connector_id: str, **kwargs) -> Task:
        """提交新任务。"""
        ...

    @abstractmethod
    async def execute(self, task_id: str) -> Task:
        """执行任务。"""
        ...

    @abstractmethod
    async def cancel(self, task_id: str) -> Task:
        """取消任务。"""
        ...

    @abstractmethod
    async def get_status(self, task_id: str) -> Task:
        """获取任务状态。"""
        ...

    @abstractmethod
    async def list_tasks(
        self, connector_id: str, status: Optional[TaskStatus] = None
    ) -> list[Task]:
        """列出连接器的任务。"""
        ...

    @abstractmethod
    async def register_schedule(
        self, task_type: TaskType, connector_id: str, cron_expr: str
    ) -> str:
        """注册定时任务。"""
        ...

    @abstractmethod
    async def unregister_schedule(self, schedule_id: str) -> None:
        """取消定时任务注册。"""
        ...
```

### 5.4 任务编排器

```python
# backend/notion/task_orchestrator.py

class TaskOrchestrator:
    """任务编排器 — 协调各层完成复杂工作流。"""

    def __init__(
        self,
        auth_layer: AuthLayerProtocol,
        data_layer: DataLayerProtocol,
        operation_layer: OperationLayerProtocol,
    ):
        self._auth = auth_layer
        self._data = data_layer
        self._ops = operation_layer
        self._running_tasks: dict[str, Task] = {}

    async def execute_full_sync(self, task: Task) -> Task:
        """
        全量同步工作流：
        1. 验证认证状态
        2. 获取 Database 列表
        3. 逐 DB 查询 Row Pages
        4. 获取 Standalone Pages
        5. Data Layer 物化 canonical snapshot
        6. 更新 current snapshot pointer
        """
        task.status = TaskStatus.RUNNING
        task.started_at = _now_iso()

        try:
            # Step 1: 验证认证
            credential = await self._auth.verify_status(task.connector_id)
            if credential.status != AuthStatus.AUTHENTICATED:
                raise TaskExecutionError("认证已过期，请重新认证")

            # Step 2: 获取 Database 列表
            db_result = await self._ops.search(
                SearchFilter(object_type="database")
            )
            databases = db_result.results
            task.progress.total_items = len(databases) + 1  # +1 for standalone pages

            # Step 3: 逐 DB 查询 Row Pages
            database_rows = {}
            for db in databases:
                db_id = db["id"]
                query_result = await self._ops.query_database(
                    DatabaseQuery(database_id=db_id)
                )
                database_rows[db_id] = query_result.results
                task.progress.completed_items += 1

            # Step 4: 获取 Standalone Pages
            page_result = await self._ops.search(
                SearchFilter(object_type="page")
            )
            standalone_pages = page_result.results
            task.progress.completed_items += 1

            # Step 5: 物化 canonical snapshot
            sync_result = await self._data.sync_full(task.workspace_id, task.connector_id)
            task.metadata["snapshot_version"] = sync_result.snapshot_identity.snapshot_version

            # Step 6: 完成
            task.status = TaskStatus.COMPLETED
            task.completed_at = _now_iso()

        except Exception as e:
            task = await self._handle_failure(task, e)

        return task

    async def execute_incremental_sync(self, task: Task) -> Task:
        """
        增量同步工作流：
        1. 验证认证状态
        2. 检测变更页面
        3. 同步变更内容
        4. 有变更时物化新 snapshot
        """
        ...

    async def _handle_failure(self, task: Task, error: Exception) -> Task:
        """统一失败处理 — 判断是否重试。"""
        task.error_message = str(error)

        if task.retry_count < task.config.max_retries and self._is_retryable(error):
            task.status = TaskStatus.RETRYING
            task.retry_count += 1
            delay = task.config.retry_delay_seconds * (
                task.config.retry_backoff_multiplier ** (task.retry_count - 1)
            )
            await asyncio.sleep(delay)
            return await self.execute_full_sync(task)  # 重试
        else:
            task.status = TaskStatus.FAILED
            task.completed_at = _now_iso()
            return task

    def _is_retryable(self, error: Exception) -> bool:
        """判断错误是否可重试。"""
        retryable_types = (RateLimitError, OperationTimeoutError, SyncError)
        return isinstance(error, retryable_types)
```

### 5.5 定时调度配置

```python
@dataclass
class ScheduleConfig:
    """定时调度配置。"""
    # 增量同步：每 30 分钟
    incremental_sync_cron: str = "*/30 * * * *"
    # 全量同步：每天凌晨 3 点
    full_sync_cron: str = "0 3 * * *"
    # 认证校验：每小时
    auth_verify_cron: str = "0 * * * *"
    # 快照归档清理：每天凌晨 4 点
    snapshot_archive_cleanup_cron: str = "0 4 * * *"

class TaskScheduler:
    """任务调度器 — 管理定时任务注册与触发。"""

    def __init__(self, orchestrator: TaskOrchestrator, config: ScheduleConfig):
        self._orchestrator = orchestrator
        self._config = config
        self._schedules: dict[str, dict] = {}  # schedule_id → schedule info

    async def start(self) -> None:
        """启动调度器，注册所有定时任务。"""
        ...

    async def stop(self) -> None:
        """停止调度器，取消所有定时任务。"""
        ...

    async def trigger_now(self, task_type: TaskType, connector_id: str) -> Task:
        """立即触发指定类型任务。"""
        ...
```

### 5.6 并发控制

```python
class ConcurrencyLimiter:
    """并发限制器 — 防止过多并行任务导致 API 限流。"""

    def __init__(self, max_concurrent: int = 5):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_count = 0

    async def acquire(self) -> None:
        await self._semaphore.acquire()
        self._active_count += 1

    def release(self) -> None:
        self._semaphore.release()
        self._active_count -= 1

    @property
    def active_count(self) -> int:
        return self._active_count
```

### 5.7 错误类型

```python
class TaskError(Exception):
    """任务层基础异常。"""
    pass

class TaskExecutionError(TaskError):
    """任务执行失败。"""
    pass

class TaskCancelledError(TaskError):
    """任务被取消。"""
    pass

class TaskTimeoutError(TaskError):
    """任务执行超时。"""
    pass

class ScheduleConflictError(TaskError):
    """调度冲突（同一连接器同类型任务正在执行）。"""
    pass
```

---

## 6. 层间协议与依赖关系

### 6.1 依赖图

```
┌────────────────┐
│  Task Layer    │
│                │
│  depends on:   │
│  - Auth Layer  │
│  - Data Layer  │
│  - Op Layer    │
└───────┬────────┘
        │
┌───────┼────────────────────────────┐
│       ▼                            │
│  ┌────────────────┐               │
│  │ Operation Layer │               │
│  │                 │               │
│  │  depends on:    │               │
│  │  - Auth Layer   │               │
│  └───────┬─────────┘               │
│          │                          │
│  ┌───────┼─────────┐               │
│  │       ▼         │               │
│  │  ┌──────────┐   │   ┌──────────┐│
│  │  │Auth Layer│   │   │Data Layer││
│  │  │          │   │   │          ││
│  │  │ no deps  │   │   │depends on││
│  │  └──────────┘   │   │Auth Layer││
│  │                  │   └──────────┘│
│  └──────────────────┘               │
└─────────────────────────────────────┘
```

### 6.2 层间通信协议

| 调用方 | 被调用方 | 通信方式 | 数据格式 |
|--------|---------|---------|---------|
| Task → Auth | 同步调用 | `await auth.verify_status()` | `AuthCredential` |
| Task → Data | 同步调用 | `await data.sync_full()` | `SyncResult` |
| Task → Operation | 同步调用 | `await ops.search()` | `SearchResult` |
| Operation → Auth | 同步调用 | `auth.get_env()` | `dict[str, str]` |
| Data → Auth | 同步调用 | `auth.get_env()` | `dict[str, str]` |
| Data → Operation | 同步任务内调用 | `materialize_snapshot` 前由 Task/Ops 提供远程结果 | `OperationResult` |

### 6.3 事件总线（跨层通知）

```python
class ConnectorEvent(Enum):
    AUTH_COMPLETED = "auth_completed"
    AUTH_EXPIRED = "auth_expired"
    SYNC_COMPLETED = "sync_completed"
    SYNC_FAILED = "sync_failed"
    SNAPSHOT_MATERIALIZED = "snapshot_materialized"
    SNAPSHOT_SUPERSEDED = "snapshot_superseded"
    PAGE_ACCESSED = "page_accessed"

@dataclass
class EventPayload:
    event: ConnectorEvent
    connector_id: str
    data: dict
    timestamp: str

class ConnectorEventBus:
    """连接器事件总线 — 解耦层间通知。"""

    def __init__(self):
        self._handlers: dict[ConnectorEvent, list[Callable]] = {}

    def subscribe(self, event: ConnectorEvent, handler: Callable) -> None:
        self._handlers.setdefault(event, []).append(handler)

    async def publish(self, payload: EventPayload) -> None:
        handlers = self._handlers.get(payload.event, [])
        for handler in handlers:
            await handler(payload)
```

---

## 7. 扩展点与多平台适配

### 7.1 多平台适配架构

```
┌──────────────────────────────────────────────────────────┐
│                 ConnectorFactory                           │
│                                                          │
│  create_connector(platform: str) → ConnectorBundle        │
│                                                          │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────┐  │
│  │ Notion Impl    │  │ GitHub Impl    │  │ GDrive   │  │
│  │                │  │ (future)       │  │ (future) │  │
│  │ NotionAuth     │  │ GitHubAuth     │  │ ...      │  │
│  │ NotionData     │  │ GitHubData     │  │          │  │
│  │ NotionOps      │  │ GitHubOps      │  │          │  │
│  │ NotionTasks    │  │ GitHubTasks    │  │          │  │
│  └────────────────┘  └────────────────┘  └──────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 7.2 ConnectorBundle 组装

```python
@dataclass
class ConnectorBundle:
    """连接器组件包 — 将四层实例打包。"""
    platform: str
    auth: AuthLayerProtocol
    data: DataLayerProtocol
    operations: OperationLayerProtocol
    tasks: TaskLayerProtocol
    event_bus: ConnectorEventBus

class ConnectorFactory:
    """连接器工厂 — 根据平台创建对应四层实例。"""

    _registry: dict[str, type] = {}

    @classmethod
    def register(cls, platform: str, builder: Callable[..., ConnectorBundle]):
        cls._registry[platform] = builder

    @classmethod
    def create(cls, platform: str, user_id: str, config: dict) -> ConnectorBundle:
        builder = cls._registry.get(platform)
        if not builder:
            raise ValueError(f"Unsupported platform: {platform}")
        return builder(user_id=user_id, config=config)
```

### 7.3 扩展清单

| 扩展点 | 新增平台需实现 | 说明 |
|--------|--------------|------|
| `AuthLayerProtocol` | 认证流程 | OAuth / API Key / Device Code |
| `DataLayerProtocol` | canonical snapshot 结构 | 虚拟索引目录名（如 `.github/`） |
| `OperationLayerProtocol` | API 映射 | 平台特定 CRUD |
| `TaskLayerProtocol` | 同步策略 | Webhook / Polling / Cursor |
| `RESOURCES` 映射表 | 虚拟路径 | PreToolUse 拦截规则 |

---

## 8. 实现文件索引

| 文件路径 | 层 | 职责 |
|---------|---|------|
| `backend/notion/auth.py` | Auth | 认证接口定义 + Notion 实现 |
| `backend/notion/data.py` | Data | 数据层接口 + canonical snapshot store |
| `backend/notion/operations.py` | Operation | 操作层接口 + ntn api 封装 |
| `backend/notion/tasks.py` | Task | 任务层接口 + 编排器 |
| `backend/notion/events.py` | Cross | 事件总线 + 事件类型 |
| `backend/notion/factory.py` | Cross | ConnectorFactory + Bundle |
| `backend/notion/errors.py` | Cross | 各层异常类型汇总 |
| `backend/libs/claude_agent_kit/server/notion_snapshot.py` | Data | snapshot 合同 + `.notion/` 虚拟路径解析 |

---
