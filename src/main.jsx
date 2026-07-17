import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import GeneNetworkExplorer from './GeneNetworkExplorer.jsx'
import './styles/theme.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <GeneNetworkExplorer />
  </StrictMode>,
)
