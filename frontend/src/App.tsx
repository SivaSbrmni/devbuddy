import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import ProjectsPage from './pages/ProjectsPage'
import ProjectDetailPage from './pages/ProjectDetailPage'
import WorkspacePage from './pages/WorkspacePage'
import KnowledgePage from './pages/KnowledgePage'
import SkillsPage from './pages/SkillsPage'
import MetricsPage from './pages/MetricsPage'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/projects/:id" element={<ProjectDetailPage />} />
        <Route path="/workspace" element={<WorkspacePage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/skills" element={<SkillsPage />} />
        <Route path="/metrics" element={<MetricsPage />} />
      </Routes>
    </Layout>
  )
}
