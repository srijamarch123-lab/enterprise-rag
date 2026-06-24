import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DocumentsPage from './pages/DocumentsPage'
import UploadPage from './pages/UploadPage'
import ProcessingPage from './pages/ProcessingPage'
import DrivePage from './pages/DrivePage'
import UsersPage from './pages/UsersPage'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  // cookie-backed auth; presence of cookie is checked implicitly by API calls.
  return <>{children}</>
}


export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <Layout />
          </PrivateRoute>
        }
      >
        <Route index element={<Navigate to="/documents" replace />} />
        <Route path="documents" element={<DocumentsPage />} />
        <Route path="upload" element={<UploadPage />} />
        <Route path="processing" element={<ProcessingPage />} />
        <Route path="drive" element={<DrivePage />} />
        <Route path="users" element={<UsersPage />} />
      </Route>
    </Routes>
  )
}
