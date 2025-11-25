import { useState } from 'react'
import './App.css'
import GenerateMode from './components/GenerateMode'
import EditMode from './components/EditMode'
import ConsistencyMode from './components/ConsistencyMode'
import ChatConsistencyMode from './components/ChatConsistencyMode'
import StarBackground from './components/StarBackground'

function App() {
  const [mode, setMode] = useState('chat-consistency')

  return (
    <div className="app">
      <StarBackground />
      <header className="app-header">
        <h1>AI Writer</h1>
        <p>智能文章生成与编辑助手</p>
      </header>

      <div className="mode-selector">
        <button
          className={mode === 'generate' ? 'active' : ''}
          onClick={() => setMode('generate')}
        >
          生成模式
        </button>
        <button
          className={mode === 'edit' ? 'active' : ''}
          onClick={() => setMode('edit')}
        >
          编辑模式
        </button>
        <button
          className={mode === 'consistency' ? 'active' : ''}
          onClick={() => setMode('consistency')}
        >
          一致性检查
        </button>
        <button
          className={mode === 'chat-consistency' ? 'active' : ''}
          onClick={() => setMode('chat-consistency')}
        >
          💬 AI对话助手
        </button>
      </div>

      <div className="content">
        {mode === 'generate' && <GenerateMode />}
        {mode === 'edit' && <EditMode />}
        {mode === 'consistency' && <ConsistencyMode />}
        {mode === 'chat-consistency' && <ChatConsistencyMode />}
      </div>
    </div>
  )
}

export default App

