/**
 * Main App Component
 * Root component with routing configuration
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import './styles/globals.css';

// Auth Pages (Unified — handle both Student and Faculty)
import Login from './pages/auth/StudentLogin';
import Register from './pages/auth/StudentRegister';
import OTPVerification from './pages/auth/OTPVerification';

// Student Pages
import StudentDashboard from './pages/student/Dashboard';
import ChatSupport from './pages/student/ChatSupport';
import Emails from './pages/student/Emails';
import RaiseTicket from './pages/student/RaiseTicket';
import TicketHistory from './pages/student/TicketHistory';
import ContactFaculty from './pages/student/ContactFaculty';
import EmailHistory from './pages/student/EmailHistory';
import StudentProfile from './pages/student/Profile';

// Layouts (shared for student & faculty — sidebar is role-aware)
import StudentLayout from './layouts/StudentLayout';

// Faculty Pages
import FacultyDashboard from './pages/faculty/Dashboard';
import ViewTickets from './pages/faculty/ViewTickets';
import EmailInbox from './pages/faculty/EmailInbox';
import FacultyProfile from './pages/faculty/Profile';
import FacultyAssistant from './pages/faculty/ChatAssistant';

// Admin Pages
import AdminDashboard from './pages/admin/Dashboard';
import UserManagement from './pages/admin/UserManagement';
import TicketOversight from './pages/admin/TicketOversight';
import Announcements from './pages/admin/Announcements';
import Reports from './pages/admin/Reports';

// Components
import ProtectedRoute from './components/common/ProtectedRoute';
import { isAuthenticated, getDefaultRoute } from './utils/auth';

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          {/* Root - Redirect based on auth status */}
          <Route
            path="/"
            element={
              isAuthenticated() ?
                <Navigate to={getDefaultRoute()} replace /> :
                <Navigate to="/login" replace />
            }
          />

          {/* Auth Routes (Unified) */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/verify-otp" element={<OTPVerification />} />

          {/* Student Routes - Wrapped in Layout with Sidebar */}
          <Route
            path="/student"
            element={
              <ProtectedRoute allowedRoles={['student']}>
                <StudentLayout />
              </ProtectedRoute>
            }
          >
            <Route path="dashboard" element={<StudentDashboard />} />
            <Route path="chat" element={<ChatSupport />} />
            <Route path="emails" element={<Emails />} />
            <Route path="tickets/new" element={<RaiseTicket />} />
            <Route path="tickets" element={<TicketHistory />} />
            <Route path="contact-faculty" element={<ContactFaculty />} />
            <Route path="email-history" element={<EmailHistory />} />
            <Route path="profile" element={<StudentProfile />} />
          </Route>

          {/* Faculty Routes - Wrapped in Layout with Sidebar (role-aware) */}
          <Route
            path="/faculty"
            element={
              <ProtectedRoute allowedRoles={['faculty']}>
                <StudentLayout />
              </ProtectedRoute>
            }
          >
            <Route path="dashboard" element={<FacultyDashboard />} />
            <Route path="tickets" element={<ViewTickets />} />
            <Route path="inbox" element={<EmailInbox />} />
            <Route path="profile" element={<FacultyProfile />} />
            <Route path="calendar" element={<ViewTickets />} />
            <Route path="assistant" element={<FacultyAssistant />} />
          </Route>

          {/* Admin Routes - Wrapped in Layout with Sidebar (role-aware) */}
          <Route
            path="/admin"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <StudentLayout />
              </ProtectedRoute>
            }
          >
            <Route path="dashboard" element={<AdminDashboard />} />
            <Route path="users" element={<UserManagement />} />
            <Route path="tickets" element={<TicketOversight />} />
            <Route path="announcements" element={<Announcements />} />
            <Route path="reports" element={<Reports />} />
          </Route>

          {/* 404 - Not Found */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
