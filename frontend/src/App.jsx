/**
 * Main App Component
 * Root component with routing configuration
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import './styles/globals.css';

// Auth Pages
import StudentLogin from './pages/auth/StudentLogin';
import StudentRegister from './pages/auth/StudentRegister';
import OTPVerification from './pages/auth/OTPVerification';
import FacultyLogin from './pages/auth/FacultyLogin';
import FacultyRegister from './pages/auth/FacultyRegister';
import FacultyOTPVerify from './pages/auth/FacultyOTPVerify';

// Student Pages
import StudentDashboard from './pages/student/Dashboard';
import ChatSupport from './pages/student/ChatSupport';
import Emails from './pages/student/Emails';
import RaiseTicket from './pages/student/RaiseTicket';
import TicketHistory from './pages/student/TicketHistory';
import ContactFaculty from './pages/student/ContactFaculty';
import EmailHistory from './pages/student/EmailHistory';
import StudentProfile from './pages/student/Profile';

// Layouts
import StudentLayout from './layouts/StudentLayout';

// Faculty Pages
import FacultyDashboard from './pages/faculty/Dashboard';
import ViewTickets from './pages/faculty/ViewTickets';
import EmailInbox from './pages/faculty/EmailInbox';
import FacultyProfile from './pages/faculty/Profile';

// Components
import ProtectedRoute from './components/common/ProtectedRoute';
import { isAuthenticated, getDefaultRoute } from './utils/auth';

function App() {
  return (
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

        {/* Auth Routes */}
        <Route path="/login" element={<StudentLogin />} />
        <Route path="/register" element={<StudentRegister />} />
        <Route path="/verify-otp" element={<OTPVerification />} />
        <Route path="/faculty/login" element={<FacultyLogin />} />
        <Route path="/faculty/register" element={<FacultyRegister />} />
        <Route path="/faculty/verify-otp" element={<FacultyOTPVerify />} />

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

        {/* Faculty Routes */}
        <Route
          path="/faculty/dashboard"
          element={
            <ProtectedRoute allowedRoles={['faculty']}>
              <FacultyDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/faculty/tickets"
          element={
            <ProtectedRoute allowedRoles={['faculty']}>
              <ViewTickets />
            </ProtectedRoute>
          }
        />
        <Route
          path="/faculty/inbox"
          element={
            <ProtectedRoute allowedRoles={['faculty']}>
              <EmailInbox />
            </ProtectedRoute>
          }
        />
        <Route
          path="/faculty/profile"
          element={
            <ProtectedRoute allowedRoles={['faculty']}>
              <FacultyProfile />
            </ProtectedRoute>
          }
        />

        {/* 404 - Not Found */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
