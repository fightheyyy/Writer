import { useState } from 'react'
import './App.css'
import GenerateMode from './components/GenerateMode'
import EditMode from './components/EditMode'
import StarBackground from './components/StarBackground'

function App() {
  const [mode, setMode] = useState('generate')

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
      </div>

      <div className="content">
        {mode === 'generate' ? <GenerateMode /> : <EditMode />}
      </div>
    </div>
  )
}

export default App

