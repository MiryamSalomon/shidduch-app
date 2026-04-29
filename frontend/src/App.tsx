import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import CandidatesPage from './pages/candidates/CandidatesPage'
import CandidateDetailPage from './pages/candidates/CandidateDetailPage'
import CandidateFormPage from './pages/candidates/CandidateFormPage'
import SuggestionsPage from './pages/suggestions/SuggestionsPage'
import SuggestionDetailPage from './pages/suggestions/SuggestionDetailPage'
import SuggestionCreatePage from './pages/suggestions/SuggestionCreatePage'
import MatchRunPage from './pages/MatchRunPage'
import MatchmakersPage from './pages/admin/MatchmakersPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/candidates" replace />} />

          {/* Candidates */}
          <Route path="/candidates" element={<CandidatesPage />} />
          <Route path="/candidates/new" element={<CandidateFormPage />} />
          <Route path="/candidates/:id" element={<CandidateDetailPage />} />
          <Route path="/candidates/:id/edit" element={<CandidateFormPage />} />

          {/* Suggestions */}
          <Route path="/suggestions" element={<SuggestionsPage />} />
          <Route path="/suggestions/new" element={<SuggestionCreatePage />} />
          <Route path="/suggestions/:id" element={<SuggestionDetailPage />} />

          {/* AI Match Run */}
          <Route path="/match-run" element={<MatchRunPage />} />

          {/* Admin */}
          <Route path="/admin/matchmakers" element={<MatchmakersPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

