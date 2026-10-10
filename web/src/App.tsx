import { Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/AppLayout'
import { AddTitlePage } from './pages/AddTitlePage'
import { LibraryPage } from './pages/LibraryPage'
import { ProcessPage } from './pages/ProcessPage'
import { ReviewPage } from './pages/ReviewPage'
import { WatchPage } from './pages/WatchPage'
import './App.css'

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<LibraryPage />} />
        <Route path="add" element={<AddTitlePage />} />
        <Route path="titles/:titleId/process" element={<ProcessPage />} />
        <Route path="titles/:titleId/review" element={<ReviewPage />} />
      </Route>
      {/* The player is full-screen, without the sidebar */}
      <Route path="titles/:titleId/watch" element={<WatchPage />} />
      <Route path="*" element={<AppLayout />}>
        <Route path="*" element={<p>That page doesn’t exist. Go back to the library.</p>} />
      </Route>
    </Routes>
  )
}
