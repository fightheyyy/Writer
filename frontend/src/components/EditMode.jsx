import { useState } from 'react'
import { DiffEditor } from '@monaco-editor/react'
import './EditMode.css'

function EditMode() {
  const [query, setQuery] = useState('')
  const [originalContent, setOriginalContent] = useState('')
  const [modifiedContent, setModifiedContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [showDiff, setShowDiff] = useState(false)
  const [thinkingProcess, setThinkingProcess] = useState([])
  const [projectId, setProjectId] = useState('default')
  const [topK, setTopK] = useState(5)
  const [useRefine, setUseRefine] = useState(true)

  const handleEdit = async () => {
    if (!query.trim() || !originalContent.trim()) {
      alert('请输入原始文章和修改要求')
      return
    }

    setLoading(true)
    try {
      const response = await fetch('/api/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query,
          original_content: originalContent,
          mode: 'edit',
          max_iterations: 3,
          project_id: projectId,
          top_k: topK,
          use_refine: useRefine
        }),
      })

      const data = await response.json()
      setModifiedContent(data.content)
      setThinkingProcess(data.thinking_process || [])
      setShowDiff(true)
    } catch (error) {
      alert('编辑失败: ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  const handleAccept = () => {
    setOriginalContent(modifiedContent)
    setModifiedContent('')
    setQuery('')
    setShowDiff(false)
  }

  const handleReject = () => {
    setModifiedContent('')
    setShowDiff(false)
  }

  return (
    <div className="edit-mode">
      <div className="input-section">
        <h2>编辑文章</h2>
        
        <div className="settings-row">
          <div className="setting-item">
            <label>Project ID</label>
            <input
              type="text"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              placeholder="项目ID"
            />
          </div>
          <div className="setting-item">
            <label>Top K</label>
            <input
              type="number"
              value={topK}
              onChange={(e) => setTopK(parseInt(e.target.value) || 5)}
              min="1"
              max="20"
            />
          </div>
          <div className="setting-item">
            <label>
              <input
                type="checkbox"
                checked={useRefine}
                onChange={(e) => setUseRefine(e.target.checked)}
              />
              Use Refine
            </label>
          </div>
        </div>

        <textarea
          className="original-input"
          placeholder="粘贴原始文章内容..."
          value={originalContent}
          onChange={(e) => setOriginalContent(e.target.value)}
          rows={8}
        />
        <textarea
          className="query-input"
          placeholder="输入修改要求（支持全文一致性修改）&#10;例如：&#10;- 把所有'人工智能'改为'AI技术'&#10;- 将论点从'支持'改成'反对'&#10;- 更新所有2022年数据到2024年&#10;- 调整全文语气为正式/轻松&#10;- 增加更多实例并保持论证一致"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={4}
        />
        <button
          className="edit-btn"
          onClick={handleEdit}
          disabled={loading || !query.trim() || !originalContent.trim()}
        >
          {loading ? '处理中...' : '生成修改'}
        </button>
      </div>

      {thinkingProcess.length > 0 && (
        <div className="thinking-process">
          <h3>思考过程</h3>
          <div className="process-list">
            {thinkingProcess.map((item, index) => (
              <div key={index} className="process-item">
                <div className="process-header">
                  <span className="iteration">第 {item.iteration} 轮</span>
                  <span className={`action-type ${item.action.type}`}>
                    {item.action.type === 'search' ? '搜索' : 
                     item.action.type === 'generate' ? '生成' : '完成'}
                  </span>
                </div>
                <div className="process-content">
                  {item.action.type === 'search' && (
                    <div className="search-query">查询: {item.action.query}</div>
                  )}
                  {item.action.reason && (
                    <div className="reason">原因: {item.action.reason}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {showDiff && (
        <div className="diff-section">
          <div className="diff-header">
            <h3>修改对比</h3>
            <div className="diff-actions">
              <button className="accept-btn" onClick={handleAccept}>
                接受修改
              </button>
              <button className="reject-btn" onClick={handleReject}>
                拒绝修改
              </button>
            </div>
          </div>
          <DiffEditor
            height="600px"
            language="markdown"
            original={originalContent}
            modified={modifiedContent}
            theme="vs-dark"
            options={{
              readOnly: false,
              renderSideBySide: true,
              minimap: { enabled: false },
              fontSize: 14,
              wordWrap: 'on',
              scrollBeyondLastLine: false,
              automaticLayout: true,
              padding: { top: 16, bottom: 16 },
              fontFamily: "'Fira Code', monospace",
              smoothScrolling: true,
              cursorBlinking: "smooth",
              cursorSmoothCaretAnimation: "on",
              diffWordWrap: "on"
            }}
            onMount={(editor) => {
              // 可以在这里添加编辑器挂载后的逻辑
            }}
          />
        </div>
      )}
    </div>
  )
}

export default EditMode

