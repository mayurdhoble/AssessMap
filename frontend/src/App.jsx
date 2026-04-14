import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import MonthlyTrends from './pages/MonthlyTrends'
import UsageInsights from './pages/UsageInsights'
import QBAnalytics from './pages/QBAnalytics'
import CompanyDrilldown from './pages/CompanyDrilldown'
import CompanyDetail from './pages/CompanyDetail'
import CategoryAnalysis from './pages/CategoryAnalysis'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/overview" replace />} />
        <Route path="overview" element={<Overview />} />
        <Route path="trends" element={<MonthlyTrends />} />
        <Route path="usage" element={<UsageInsights />} />
        <Route path="qb" element={<QBAnalytics />} />
        <Route path="company" element={<CompanyDrilldown />} />
        <Route path="company/:companyName" element={<CompanyDetail />} />
        <Route path="category" element={<CategoryAnalysis />} />
      </Route>
    </Routes>
  )
}
