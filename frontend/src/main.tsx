import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import './index.css'
import StorySelector from './pages/StorySelector'
import RecommendationView from './pages/RecommendationView'
import LinkBobWork from './pages/LinkBobWork'
import OutcomeComparison from './pages/OutcomeComparison'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<StorySelector />} />
        <Route path="/stories/:id" element={<RecommendationView />} />
        <Route path="/stories/:id/bob-session" element={<LinkBobWork />} />
        <Route path="/stories/:id/outcome" element={<OutcomeComparison />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
