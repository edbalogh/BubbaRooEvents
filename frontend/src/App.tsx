import { Routes, Route } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import Layout from './components/Layout'
import Home from './pages/Home'
import EventDetail from './pages/EventDetail'
import ForYou from './pages/ForYou'
import Settings from './pages/Settings'
import Login from './pages/Login'
import TripPlanner from './pages/TripPlanner'

export default function App() {
  return (
    <AuthProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/for-you" element={<ForYou />} />
          <Route path="/events/:id" element={<EventDetail />} />
          <Route path="/trip-planner" element={<TripPlanner />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/login" element={<Login />} />
        </Routes>
      </Layout>
    </AuthProvider>
  )
}
