# 📝 文档一致性检查系统（RAG版本）

## 🎯 核心功能

基于 RAG（检索增强生成）的全局文档一致性分析系统：

- ✅ 上传文档到知识库（自动分块、向量化）
- ✅ RAG全局检索（智能发现所有相关文档）
- ✅ AI一致性分析（判断是否需要同步修改）
- ✅ 自动生成修改（保持多文档间一致性）
- ✅ Monaco Diff展示（可视化对比修改）

## 🚀 快速开始

### 1. 启动服务

```bash
# 启动后端（Writer服务）
cd e:\项目代码\Writer\Writer
python run.py

# 服务运行在 http://localhost:8000
```

### 2. 访问前端

浏览器打开：**http://localhost:8000**

选择模式：**一致性检查**

### 3. 使用流程

#### 步骤1：上传文档到知识库

1. 输入 **Project ID**（例如：`test202511241125`）
2. 添加多个 **MinIO URL**（Markdown文件）
   ```
   http://43.139.19.144:9000/gauz-documents/documents/.../paper1.md
   http://43.139.19.144:9000/gauz-documents/documents/.../paper2.md
   http://43.139.19.144:9000/gauz-documents/documents/.../paper3.md
   ```
3. 点击 **"📤 上传 X 个文档到知识库"**
4. 等待上传完成（看到绿色提示）

#### 步骤2：设置一致性检查

1. **修改点**（关键词）
   ```
   LSTM模型
   ```

2. **修改要求**（详细说明）
   ```
   将所有LSTM模型改为Transformer模型，包括模型架构描述、参数配置、训练过程和实验结果
   ```

3. **Top-K**（召回数量，推荐 10-20）
   ```
   15
   ```

4. 点击 **"🔍 开始一致性检查（RAG全局检索）"**

#### 步骤3：查看结果

系统会自动：
1. 通过 RAG 检索所有相关文档（可能 15+ 个）
2. 从 MinIO 读取完整内容
3. AI 分析一致性需求
4. 生成每个文档的修改建议
5. 展示 Diff 对比

**点击"查看 Diff"**可查看详细修改：
- 左侧：原始内容
- 右侧：修改后内容
- 差异高亮

## 🌟 核心优势

### 与旧版本对比

| 特性 | 旧版本（本地模式） | 新版本（RAG模式） |
|---|---|---|
| 文档范围 | ❌ 仅前端加载的3个 | ✅ 整个项目（15+） |
| 检索方式 | ❌ 简单文本匹配 | ✅ 语义向量检索 |
| 发现能力 | ❌ 需手动选择 | ✅ 自动发现相关文档 |
| 适用场景 | ❌ 小项目 | ✅ 大项目效果更好 |
| RAG利用 | ❌ 没有利用 | ✅ 充分利用 |

### 工作原理

```
用户上传文档
    ↓
知识库建立索引（分块 + 向量化）
    ↓
用户输入修改要求
    ↓
RAG检索相关文档（语义搜索）
    ↓
从MinIO读取完整内容
    ↓
AI分析一致性
    ↓
生成修改建议
    ↓
Monaco Diff展示
```

## 📋 API接口

### 1. 批量上传到知识库

```http
POST /api/batch-upload-to-kb
Content-Type: application/json

{
  "minio_urls": ["http://...", "http://..."],
  "project_id": "test202511241125",
  "enable_vlm": false
}
```

### 2. RAG一致性检查

```http
POST /api/check-consistency
Content-Type: application/json

{
  "modification_point": "LSTM模型",
  "modification_request": "将所有LSTM模型改为Transformer模型...",
  "project_id": "test202511241125",
  "top_k": 15
}
```

## 🔧 依赖服务

### 必需服务

1. **知识库服务**（localhost:8001）
   - 负责文档处理、分块、向量化
   - API: `POST /api/v1/process_and_extract`

2. **RAG服务**（localhost:1234）
   - 负责向量检索
   - API: `POST /search`

3. **MinIO服务**
   - 文档存储
   - 需要公网可访问或内网可达

### 检查服务状态

```bash
# 检查知识库服务
curl http://localhost:8001

# 检查RAG服务
curl http://localhost:1234

# 检查MinIO
curl http://43.139.19.144:9000
```

## 📊 使用示例

### 示例1：统一模型架构

**场景**：项目有20篇论文，要把所有LSTM改成Transformer

1. 上传20个文档（Project ID: `nlp_papers`）
2. 修改点：`LSTM模型`
3. 修改要求：`将所有LSTM模型改为Transformer...`
4. Top-K：20
5. 系统自动召回15个相关文档并生成修改

### 示例2：更新实验数据

**场景**：将2022年数据更新为2023年

1. 修改点：`2022年数据`
2. 修改要求：`将所有2022年数据更新为2023年最新数据`
3. 系统召回所有提到2022年的文档
4. AI生成更新建议

### 示例3：术语统一

**场景**：统一术语（"深度学习" → "深度神经网络"）

1. 修改点：`深度学习`
2. 修改要求：`将"深度学习"统一改为"深度神经网络"`
3. 系统全局检索并修改

## ⚠️ 注意事项

### 1. Project ID 要一致
- 上传和检查必须使用同一个 Project ID
- 否则检索不到文档

### 2. Top-K 合理设置
- 太小（<5）：可能遗漏相关文档
- 太大（>30）：可能包含不相关文档
- **推荐：10-20**

### 3. MinIO URL 可访问性
- 确保URL可访问
- CORS配置正确
- 网络通畅

### 4. 文档大小限制
- 单个文档建议 <50KB
- 过大可能超出LLM上下文限制

### 5. 知识库服务必须运行
- 上传前确认 `localhost:8001` 可访问
- 查看后端日志排查错误

## 🐛 故障排除

### 问题1：上传失败

**症状**：点击上传后报错

**排查**：
```bash
# 检查知识库服务
curl http://localhost:8001

# 查看后端日志
tail -f logs/app_*.log
```

**解决**：启动知识库服务

---

### 问题2：检索不到文档

**症状**：一致性检查返回0个相关文档

**排查**：
- 确认 Project ID 正确
- 确认文档已成功上传
- 查看 RAG 服务日志

**解决**：
- 使用相同 Project ID
- 增大 Top-K
- 调整关键词

---

### 问题3：Diff显示空白

**症状**：点击"查看Diff"后空白

**排查**：
- 打开浏览器控制台
- 查看是否有JavaScript错误

**解决**：
- 刷新页面
- 清除浏览器缓存
- 确认 Monaco Editor 加载成功

---

## 📁 项目结构

```
Writer/
├── main.py                    # 后端主程序（FastAPI）
├── consistency_checker.py     # 一致性检查核心逻辑
├── knowledge_base.py          # 知识库管理
├── rag_tool.py               # RAG检索工具
├── config.py                 # 配置文件
├── run.py                    # 启动脚本
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ConsistencyMode.jsx   # 一致性检查组件
│   │   │   └── ConsistencyMode.css
│   │   └── App.jsx
│   └── dist/                 # 构建产物
└── logs/                     # 日志目录
```

## 🔮 未来计划

- [ ] 批量应用修改（一键更新所有文档）
- [ ] 修改历史记录
- [ ] 导出修改报告（PDF/Word）
- [ ] 支持更多格式（PDF、DOCX）
- [ ] 并发优化（并行生成修改）
- [ ] 修改预览（修改前预览效果）
- [ ] 回滚功能（撤销修改）

## 📞 技术支持

遇到问题？

1. 查看日志：`logs/app_*.log`
2. 查看完整文档：`新版使用说明.md`
3. 检查服务状态：`localhost:8000/api/health`

---

**享受智能文档一致性管理！** 🚀
