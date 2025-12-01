import React, { useState, useRef, useEffect } from 'react';
import { DiffEditor } from '@monaco-editor/react';
import './ChatConsistencyMode.css';

export default function ChatConsistencyMode() {
  const [projectId, setProjectId] = useState('test202511241503');
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [modifications, setModifications] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [appliedFiles, setAppliedFiles] = useState(new Set());
  const [showThinkingProcess, setShowThinkingProcess] = useState(false);
  
  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);

  // 自动滚动到最新消息
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 添加消息
  const addMessage = (role, content, type = 'text') => {
    setMessages(prev => [...prev, { role, content, type, timestamp: Date.now() }]);
  };

  // 处理用户输入
  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isProcessing) return;

    const userRequest = inputMessage.trim();
    setInputMessage('');
    
    // 添加用户消息
    addMessage('user', userRequest);
    
    setIsProcessing(true);
    
    try {
      // AI思考中
      addMessage('assistant', '正在分析你的需求...', 'thinking');
      
      // 提取修改点（简单实现，可以用更智能的NLP）
      const modificationPoint = extractModificationPoint(userRequest);
      
      addMessage('assistant', `识别到修改点: "${modificationPoint}"`, 'info');
      addMessage('assistant', '正在RAG搜索相关文档...', 'thinking');
      
      // 调用一致性检查API
      const response = await fetch('/api/check-consistency', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          modification_point: modificationPoint,
          modification_request: userRequest,
          project_id: projectId,
          top_k: 15
        })
      });

      if (!response.ok) throw new Error('请求失败');

      const result = await response.json();
      
      // 显示搜索结果
      addMessage('assistant', 
        `找到 ${result.total_files} 个相关文档，共 ${result.total_chunks} 个相关片段`, 
        'success'
      );

      if (result.modifications && result.modifications.length > 0) {
        addMessage('assistant', 
          `AI已生成 ${result.modifications.length} 个文档的修改建议`, 
          'success'
        );
        
        // 保存修改建议
        setModifications(result.modifications);
        
        // 自动选择第一个文件
        if (result.modifications.length > 0) {
          setSelectedFile(result.modifications[0]);
        }
        
        // 添加修改卡片
        addMessage('assistant', result.modifications, 'modifications');
        
      } else {
        addMessage('assistant', 
          'AI分析后认为无需修改这些文档，或未找到相关内容', 
          'info'
        );
      }
      
    } catch (error) {
      addMessage('assistant', `出错了: ${error.message}`, 'error');
    } finally {
      setIsProcessing(false);
    }
  };

  // 简单的关键词提取（可以改进为更智能的NLP）
  const extractModificationPoint = (text) => {
    // 匹配 "把X换成Y" 或 "将X改为Y" 等模式
    const patterns = [
      /把(.+?)换成(.+)/,
      /将(.+?)改为(.+)/,
      /把(.+?)改成(.+)/,
      /替换(.+?)为(.+)/,
      /修改(.+)/,
    ];
    
    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match) {
        return match[1].trim();
      }
    }
    
    // 如果没匹配到，返回前10个字符作为关键词
    return text.slice(0, 20);
  };

  // 查看文件Diff
  const handleViewDiff = (mod) => {
    setSelectedFile(mod);
  };

  // 应用修改
  const handleApplyModification = (mod) => {
    setAppliedFiles(prev => new Set([...prev, mod.file_path]));
    addMessage('assistant', 
      `已应用修改: ${mod.file_path.split('/').pop()}`, 
      'success'
    );
    // TODO: 这里可以调用后端API实际保存修改
  };

  // 跳过修改
  const handleSkipModification = (mod) => {
    addMessage('assistant', 
      `已跳过: ${mod.file_path.split('/').pop()}`, 
      'info'
    );
  };

  // 全部应用
  const handleApplyAll = () => {
    modifications.forEach(mod => {
      setAppliedFiles(prev => new Set([...prev, mod.file_path]));
    });
    addMessage('assistant', `已应用全部 ${modifications.length} 个修改`, 'success');
  };

  // 渲染消息
  const renderMessage = (msg, index) => {
    const isUser = msg.role === 'user';
    
    if (msg.type === 'modifications') {
      return (
        <div key={index} className="message-modifications">
          {msg.content.map((mod, idx) => (
            <div key={idx} className={`mod-card ${appliedFiles.has(mod.file_path) ? 'applied' : ''}`}>
              <div className="mod-card-header">
                <span className="mod-number">#{idx + 1}</span>
                <span className="mod-filename">{mod.file_path.split('/').pop()}</span>
                {appliedFiles.has(mod.file_path) && <span className="applied-badge">已应用</span>}
              </div>
              <div className="mod-card-summary">{mod.diff_summary}</div>
              <div className="mod-card-stats">
                <span>{mod.original_length} → {mod.modified_length} 字符</span>
                <span className={`change ${mod.modified_length - mod.original_length >= 0 ? 'positive' : 'negative'}`}>
                  {mod.modified_length - mod.original_length >= 0 ? '+' : ''}
                  {mod.modified_length - mod.original_length}
                </span>
              </div>
              <div className="mod-card-actions">
                <button onClick={() => handleViewDiff(mod)} className="btn-view">
                  查看Diff
                </button>
                {!appliedFiles.has(mod.file_path) && (
                  <>
                    <button onClick={() => handleApplyModification(mod)} className="btn-apply">
                      应用
                    </button>
                    <button onClick={() => handleSkipModification(mod)} className="btn-skip">
                      跳过
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      );
    }
    
    return (
      <div key={index} className={`message ${isUser ? 'user' : 'assistant'} ${msg.type}`}>
        <div className="message-content">
          {msg.content}
        </div>
      </div>
    );
  };

  return (
    <div className="chat-consistency-container">
      {/* 左侧：Diff预览 + 文件列表 */}
      <div className="left-panel">
        {/* Diff编辑器 */}
        <div className="diff-preview">
          {selectedFile ? (
            <>
              <div className="diff-header">
                <h3>{selectedFile.file_path.split('/').pop()}</h3>
                <div className="diff-header-actions">
                  {appliedFiles.has(selectedFile.file_path) ? (
                    <span className="diff-summary applied">已应用修改</span>
                  ) : (
                    <span className="diff-summary">{selectedFile.diff_summary}</span>
                  )}
                  {selectedFile.react_thinking_process && selectedFile.react_thinking_process.length > 0 && (
                    <button 
                      className="btn-thinking" 
                      onClick={() => setShowThinkingProcess(!showThinkingProcess)}
                    >
                      {showThinkingProcess ? '隐藏' : '查看'} AI思考过程
                    </button>
                  )}
                </div>
              </div>
              {showThinkingProcess && selectedFile.react_thinking_process ? (
                <div className="thinking-process-panel">
                  <h4>ReactAgent 思考过程</h4>
                  
                  {selectedFile.react_thinking_process.map((thinking, idx) => (
                    <div key={idx} className="thinking-step">
                      <div className="thinking-step-header">
                        <span className="step-number">修改点 {thinking.modification_point}</span>
                        <span className="step-location">{thinking.location}</span>
                      </div>
                      
                      {thinking.thinking_steps && thinking.thinking_steps.length > 0 && (
                        <div className="thinking-steps">
                          <strong>迭代步骤:</strong>
                          {thinking.thinking_steps.map((step, stepIdx) => (
                            <div key={stepIdx} className="iteration-step">
                              <div className="iteration-header">
                                <span className="iteration-number">第 {step.iteration} 轮</span>
                              </div>
                              <div className="iteration-action">
                                <span className="action-type">{step.action.type === 'search' ? '搜索' : step.action.type === 'generate' ? '生成' : '完成'}</span>
                                {step.action.query && (
                                  <div className="action-detail">
                                    <strong>查询:</strong> {step.action.query.substring(0, 100)}...
                                  </div>
                                )}
                                {step.action.reason && (
                                  <div className="action-reason">
                                    <strong>原因:</strong> {step.action.reason}
                                  </div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                      
                      <div className="thinking-meta">
                        <span>生成内容长度: {thinking.generated_length} 字符</span>
                      </div>
                    </div>
                  ))}
                  
                  {selectedFile.react_search_history && selectedFile.react_search_history.length > 0 && (
                    <div className="search-history">
                      <h4>RAG搜索历史</h4>
                      {selectedFile.react_search_history.map((search, idx) => (
                        <div key={idx} className="search-item">
                          <span className="search-iteration">第 {search.iteration} 轮</span>
                          <span className={`search-status ${search.has_content ? 'success' : 'empty'}`}>
                            {search.has_content ? '找到资料' : '无结果'}
                          </span>
                          <span className="search-query">{search.query.substring(0, 80)}...</span>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  <div className="thinking-actions">
                    <button onClick={() => setShowThinkingProcess(false)} className="btn-close-thinking">
                      关闭思考过程
                    </button>
                  </div>
                </div>
              ) : (
                <DiffEditor
                  height="calc(100% - 60px)"
                  language="markdown"
                  original={appliedFiles.has(selectedFile.file_path) ? selectedFile.modified_content : selectedFile.original_content}
                  modified={selectedFile.modified_content}
                  theme="vs-dark"
                  options={{
                    readOnly: true,
                    minimap: { enabled: false },
                    fontSize: 13,
                    lineNumbers: 'on',
                    renderSideBySide: true,
                    scrollBeyondLastLine: false,
                  }}
                />
              )}
            </>
          ) : (
            <div className="diff-placeholder">
              <p>在右侧对话框输入需求，AI会自动生成修改建议</p>
              <p className="hint">例如："帮我把LSTM换成Transformer"</p>
            </div>
          )}
        </div>

        {/* 文件列表 */}
        {modifications.length > 0 && (
          <div className="file-list">
            <div className="file-list-header">
              <h4>待修改文件 ({modifications.length})</h4>
              <div className="file-list-actions">
                <button onClick={handleApplyAll} className="btn-apply-all">
                  全部应用
                </button>
              </div>
            </div>
            <div className="file-items">
              {modifications.map((mod, idx) => (
                <div
                  key={idx}
                  className={`file-item ${selectedFile?.file_path === mod.file_path ? 'selected' : ''} ${appliedFiles.has(mod.file_path) ? 'applied' : ''}`}
                  onClick={() => setSelectedFile(mod)}
                >
                  <input
                    type="checkbox"
                    checked={appliedFiles.has(mod.file_path)}
                    onChange={() => {}}
                    onClick={(e) => e.stopPropagation()}
                  />
                  <div className="file-item-info">
                    <span className="file-name">{mod.file_path.split('/').pop()}</span>
                    <span className="file-stats">
                      {mod.diff_summary}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 右侧：对话区 */}
      <div className="right-panel">
        <div className="chat-header">
          <h2>AI 一致性助手</h2>
          <div className="project-selector">
            <label>项目:</label>
            <input
              type="text"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              placeholder="输入项目ID"
            />
          </div>
        </div>

        <div className="chat-messages" ref={chatContainerRef}>
          {messages.length === 0 && (
            <div className="welcome-message">
              <h3>你好！我是你的文档一致性助手</h3>
              <p>告诉我你想要做什么修改，我会帮你找到所有相关文档并生成修改建议。</p>
              <div className="examples">
                <p><strong>示例:</strong></p>
                <ul>
                  <li>"帮我把LSTM换成Transformer"</li>
                  <li>"将早季分类改为产量预测"</li>
                  <li>"把所有ResNet替换成EfficientNet"</li>
                </ul>
              </div>
            </div>
          )}
          
          {messages.map((msg, idx) => renderMessage(msg, idx))}
          
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-area">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder="输入你的需求，例如：帮我把LSTM换成Transformer"
            disabled={isProcessing}
          />
          <button
            onClick={handleSendMessage}
            disabled={isProcessing || !inputMessage.trim()}
            className="btn-send"
          >
            {isProcessing ? '处理中...' : '发送'}
          </button>
        </div>
      </div>
    </div>
  );
}

