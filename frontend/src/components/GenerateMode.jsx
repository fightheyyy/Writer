import { useState } from 'react'
import Editor from '@monaco-editor/react'
import './GenerateMode.css'

function GenerateMode() {
  const [query, setQuery] = useState('')
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [searchHistory, setSearchHistory] = useState([])
  const [thinkingProcess, setThinkingProcess] = useState([])
  const [projectId, setProjectId] = useState('default')
  const [topK, setTopK] = useState(5)
  const [useRefine, setUseRefine] = useState(true)

  const handleGenerate = async () => {
    if (!query.trim()) return

    setLoading(true)
    try {
      const response = await fetch('/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query,
          mode: 'generate',
          max_iterations: 5,
          project_id: projectId,
          top_k: topK,
          use_refine: useRefine
        }),
      })

      const data = await response.json()
      setContent(data.content)
      setSearchHistory(data.search_history || [])
      setThinkingProcess(data.thinking_process || [])
    } catch (error) {
      alert('生成失败: ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="generate-mode">
      <div className="input-section">
        <h2>生成新文章</h2>
        
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
          className="query-input"
          placeholder="输入你想生成的文章主题，例如：人工智能在医疗领域的应用..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={4}
        />
        <button
          className="generate-btn"
          onClick={handleGenerate}
          disabled={loading || !query.trim()}
        >
          {loading ? '生成中...' : '生成文章'}
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
                  {item.action.type === 'generate' && item.action.instruction && (
                    <div className="generate-instruction">指导: {item.action.instruction}</div>
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

      {searchHistory.length > 0 && (
        <div className="search-history">
          <h3>搜索历史</h3>
          <div className="history-list">
            {searchHistory.map((item, index) => (
              <div key={index} className="history-item">
                <span className="iteration">第 {item.iteration} 次</span>
                <span className="query">{item.query}</span>
                <span className={`status ${item.success ? 'success' : 'failed'}`}>
                  {item.success ? '成功' : '失败'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="editor-section">
        <h3>生成结果</h3>
        <Editor
          height="500px"
          defaultLanguage="markdown"
          value={content}
          theme="vs-dark"
          options={{
            readOnly: false,
            minimap: { enabled: false },
            fontSize: 14,
            wordWrap: 'on',
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            padding: { top: 16, bottom: 16 },
            fontFamily: "'Fira Code', monospace",
            smoothScrolling: true,
            cursorBlinking: "smooth",
            cursorSmoothCaretAnimation: "on"
          }}
          onChange={(value) => setContent(value)}
        />
      </div>
    </div>
  )
}

export default GenerateMode

