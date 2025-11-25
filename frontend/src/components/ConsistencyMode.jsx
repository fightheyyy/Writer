import { useState } from 'react'
import { DiffEditor, Editor } from '@monaco-editor/react'
import './ConsistencyMode.css'

function ConsistencyMode() {
  const [projectId, setProjectId] = useState('test202511241125')
  const [minioUrls, setMinioUrls] = useState([])
  const [newMinioUrl, setNewMinioUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState(null)
  
  // 修改设置
  const [modificationPoint, setModificationPoint] = useState('')
  const [modificationRequest, setModificationRequest] = useState('')
  const [topK, setTopK] = useState(15)
  
  // 一致性检查结果
  const [consistencyResult, setConsistencyResult] = useState(null)
  const [selectedDiff, setSelectedDiff] = useState(null)

  // 添加 MinIO URL
  const handleAddUrl = () => {
    if (newMinioUrl.trim()) {
      setMinioUrls([...minioUrls, newMinioUrl.trim()])
      setNewMinioUrl('')
    }
  }

  // 删除 URL
  const handleRemoveUrl = (index) => {
    setMinioUrls(minioUrls.filter((_, i) => i !== index))
  }

  // 上传到知识库
  const handleUploadToKB = async () => {
    if (minioUrls.length === 0) {
      alert('请先添加MinIO URL')
      return
    }

    setLoading(true)
    setUploadStatus(null)

    try {
      const response = await fetch('/api/batch-upload-to-kb', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          minio_urls: minioUrls,
          project_id: projectId,
          enable_vlm: false
        }),
      })

      const result = await response.json()
      setUploadStatus(result)
      
      if (result.success) {
        alert(`✓ 上传成功！\n${result.success_count}/${result.total} 个文件已添加到知识库\n\nProject ID: ${projectId}`)
      } else {
        alert(`⚠ 上传部分失败\n${result.success_count}/${result.total} 成功\n\n错误: ${result.message}`)
      }
    } catch (error) {
      alert('上传失败: ' + error.message)
      setUploadStatus({ success: false, error: error.message })
    } finally {
      setLoading(false)
    }
  }

  // 执行一致性检查（RAG模式）
  const handleConsistencyCheck = async () => {
    if (!projectId.trim()) {
      alert('请输入Project ID')
      return
    }

    if (!modificationPoint.trim() || !modificationRequest.trim()) {
      alert('请输入修改点和修改要求')
      return
    }

    setLoading(true)
    setConsistencyResult(null)

    try {
      const response = await fetch('/api/check-consistency', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          modification_point: modificationPoint,
          modification_request: modificationRequest,
          project_id: projectId,
          top_k: topK
        }),
      })

      const result = await response.json()
      setConsistencyResult(result)
      
      if (result.success) {
        if (result.total_files > 0) {
          alert(`✓ 一致性检查完成！\n\n找到 ${result.total_files} 个相关文档\n生成 ${result.modifications.length} 个修改建议`)
        } else {
          alert('未找到需要同步修改的文档')
        }
      } else {
        alert('一致性检查失败: ' + result.message)
      }
    } catch (error) {
      alert('一致性检查失败: ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  // 查看diff
  const handleViewDiff = (modification) => {
    setSelectedDiff(modification)
  }

  return (
    <div className="consistency-mode">
      <h1>📝 文档一致性检查系统</h1>
      <p className="subtitle">基于RAG的全局文档一致性分析与修改</p>
      
      {/* 步骤1：上传文档到知识库 */}
      <div className="section">
        <h2>步骤 1: 上传文档到知识库</h2>
        <p className="description">上传Markdown文档到知识库，系统会自动进行分块和向量化索引</p>
        
        <div className="project-id-input">
          <label>Project ID:</label>
          <input
            type="text"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            placeholder="项目ID（用于隔离不同项目的文档）"
            className="input-field"
          />
        </div>

        <div className="url-input-group">
          <input
            type="text"
            value={newMinioUrl}
            onChange={(e) => setNewMinioUrl(e.target.value)}
            placeholder="输入MinIO URL，例如: http://43.139.19.144:9000/gauz-documents/..."
            onKeyPress={(e) => e.key === 'Enter' && handleAddUrl()}
            className="url-input"
          />
          <button onClick={handleAddUrl} className="btn-add">添加</button>
        </div>

        {minioUrls.length > 0 && (
          <div className="url-list">
            <div className="url-list-header">
              待上传文档列表 ({minioUrls.length} 个)
            </div>
            {minioUrls.map((url, index) => (
              <div key={index} className="url-item">
                <span className="url-index">{index + 1}</span>
                <span className="url-text">{url}</span>
                <button onClick={() => handleRemoveUrl(index)} className="btn-remove">删除</button>
              </div>
            ))}
          </div>
        )}

        <button
          onClick={handleUploadToKB}
          disabled={loading || minioUrls.length === 0}
          className="btn-primary"
        >
          {loading ? '上传中...' : `📤 上传 ${minioUrls.length} 个文档到知识库`}
        </button>

        {uploadStatus && (
          <div className={`status-box ${uploadStatus.success ? 'success' : 'error'}`}>
            {uploadStatus.success 
              ? `✓ 上传成功: ${uploadStatus.success_count}/${uploadStatus.total} 个文件已添加到知识库`
              : `✗ 上传失败: ${uploadStatus.message || '部分失败'}`
            }
          </div>
        )}
      </div>

      <hr className="divider" />

      {/* 步骤2：设置一致性检查 */}
      <div className="section">
        <h2>步骤 2: 设置一致性检查</h2>
        <p className="description">输入修改要求，系统会通过RAG检索所有相关文档并生成一致性修改建议</p>

        <div className="form-group">
          <label className="form-label">
            修改点（关键词，用于RAG检索）
            <span className="hint">例如：LSTM模型、早季分类、2022年数据</span>
          </label>
          <input
            type="text"
            value={modificationPoint}
            onChange={(e) => setModificationPoint(e.target.value)}
            placeholder="输入关键词，系统会检索包含此内容的所有文档"
            className="input-field"
          />
        </div>

        <div className="form-group">
          <label className="form-label">
            修改要求（详细说明如何修改）
            <span className="hint">例如：将所有LSTM模型改为Transformer模型，包括模型描述、参数配置、实验结果</span>
          </label>
          <textarea
            value={modificationRequest}
            onChange={(e) => setModificationRequest(e.target.value)}
            placeholder="详细描述需要如何修改，AI会根据此要求生成一致性修改"
            rows={4}
            className="textarea-field"
          />
        </div>

        <div className="form-group">
          <label className="form-label">
            检索数量 (Top-K)
            <span className="hint">从知识库中召回多少个相关文档片段</span>
          </label>
          <input
            type="number"
            value={topK}
            onChange={(e) => setTopK(parseInt(e.target.value))}
            min="5"
            max="50"
            className="input-field-small"
          />
        </div>

        <button
          onClick={handleConsistencyCheck}
          disabled={loading || !projectId.trim()}
          className="btn-primary btn-large"
        >
          {loading ? '🔄 检查中...' : '🔍 开始一致性检查（RAG全局检索）'}
        </button>
      </div>

      <hr className="divider" />

      {/* 步骤3：查看一致性检查结果 */}
      {consistencyResult && consistencyResult.success && (
        <div className="section">
          <h2>步骤 3: 一致性检查结果</h2>
          
          <div className="analysis-summary">
            <h3>🤖 AI 分析结果</h3>
            <div className="analysis-card">
              <div className="analysis-item">
                <span className="label">修改类型:</span>
                <span className="value">{consistencyResult.consistency_analysis?.modification_type || '未知'}</span>
              </div>
              <div className="analysis-item">
                <span className="label">全局一致性:</span>
                <span className={`badge ${consistencyResult.consistency_analysis?.global_consistency_required ? 'badge-warning' : 'badge-info'}`}>
                  {consistencyResult.consistency_analysis?.global_consistency_required ? '需要全局同步' : '局部修改即可'}
                </span>
              </div>
              <div className="analysis-item full-width">
                <span className="label">分析说明:</span>
                <p className="analysis-text">{consistencyResult.consistency_analysis?.consistency_analysis || '无'}</p>
              </div>
            </div>
          </div>

          {consistencyResult.total_files > 0 && (
            <div className="related-files">
              <h3>📂 RAG检索到的相关文档 ({consistencyResult.total_files} 个)</h3>
              <p className="hint">系统在知识库中找到了以下与"{consistencyResult.modification_point}"相关的文档</p>
              <div className="file-grid">
                {Object.entries(consistencyResult.related_files || {}).map(([filePath, chunks], index) => (
                  <div key={index} className="file-card">
                    <div className="file-icon">📄</div>
                    <div className="file-info">
                      <div className="file-name" title={filePath}>{filePath.split('/').pop()}</div>
                      <div className="file-meta">
                        <span>召回 {chunks.length} 个相关片段</span>
                        {chunks[0]?.score && <span> | 相关度: {(chunks[0].score * 100).toFixed(1)}%</span>}
                      </div>
                      <div className="file-url">{filePath}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="modifications-section">
            <h3>✏️ AI生成的修改建议 ({consistencyResult.modifications?.length || 0} 个)</h3>
            
            {consistencyResult.modifications && consistencyResult.modifications.length > 0 ? (
              <>
                <p className="hint">AI根据"{consistencyResult.modification_point}"的修改要求，为以下文档生成了修改版本</p>
                <div className="modifications-list">
                  {consistencyResult.modifications.map((mod, index) => (
                  <div key={index} className={`modification-card ${mod.truncated ? 'truncated' : ''}`}>
                    <div className="mod-header">
                      <div className="mod-title">
                        <span className="mod-number">#{index + 1}</span>
                        <span className="mod-filename">{mod.file_path.split('/').pop()}</span>
                        {mod.truncated && <span className="truncated-badge">⚠️ 被截断</span>}
                      </div>
                      <button onClick={() => handleViewDiff(mod)} className="btn-view-diff">
                        查看 Diff
                      </button>
                    </div>
                    <div className="mod-summary">{mod.diff_summary}</div>
                    {mod.truncated && (
                      <div className="truncated-warning">
                        ⚠️ 此文档修改因超过AI输出限制被截断，建议：
                        <ul>
                          <li>将文档拆分为多个小文档</li>
                          <li>或缩小修改范围</li>
                          <li>或使用支持更长输出的模型</li>
                        </ul>
                      </div>
                    )}
                    <div className="mod-stats">
                      <span className="stat-item">原文: {mod.original_length} 字符</span>
                      <span className="stat-divider">→</span>
                      <span className="stat-item">修改后: {mod.modified_length} 字符</span>
                      <span className="stat-change">
                        {mod.modified_length - mod.original_length > 0 ? '+' : ''}
                        {mod.modified_length - mod.original_length} 字符
                      </span>
                    </div>
                  </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="empty-state">
                <p>📭 AI分析认为不需要生成修改建议</p>
                <p className="hint">
                  {consistencyResult.consistency_analysis?.consistency_analysis || 
                   '可能原因：找到的文档与修改点关联度较低，或修改不影响其他文档'}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Diff对比窗口 */}
      {selectedDiff && (
        <div className="diff-modal">
          <div className="diff-modal-content">
            <div className="diff-modal-header">
              <h3>📊 文档修改对比: {selectedDiff.file_path.split('/').pop()}</h3>
              <button onClick={() => setSelectedDiff(null)} className="btn-close">✕</button>
            </div>
            <div className="diff-info">
              <span>原文: {selectedDiff.original_length} 字符</span>
              <span>修改后: {selectedDiff.modified_length} 字符</span>
              <span>变化: {selectedDiff.modified_length - selectedDiff.original_length > 0 ? '+' : ''}{selectedDiff.modified_length - selectedDiff.original_length} 字符</span>
            </div>
            <DiffEditor
              height="calc(100vh - 200px)"
              language="markdown"
              original={selectedDiff.original_content}
              modified={selectedDiff.modified_content}
              theme="vs-dark"
              options={{
                readOnly: true,
                renderSideBySide: true,
                minimap: { enabled: true },
                fontSize: 14,
                wordWrap: 'on',
                scrollBeyondLastLine: false
              }}
            />
          </div>
        </div>
      )}
    </div>
  )
}

export default ConsistencyMode
