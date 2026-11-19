import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'pnd-lib-react/styles.css'
import './index.css'
import './styles/app.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
