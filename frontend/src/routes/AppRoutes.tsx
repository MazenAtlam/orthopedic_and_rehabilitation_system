import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ProtectedRoute } from '../features/auth/ProtectedRoute';
import { LoginPage } from '../features/auth/LoginPage';
import { RegisterPage } from '../features/auth/RegisterPage';
import { AppShell } from '../components/layout/AppShell';
import { AnalyticsPage } from '../features/analytics/AnalyticsPage';
import { UsersPage } from '../features/users/UsersPage';
import { AppointmentsPage } from '../features/appointments/AppointmentsPage';
import { ClinicalEmrPage } from '../features/clinical/ClinicalEmrPage';
import { RehabPlansPage } from '../features/clinical/RehabPlansPage';
import { DicomViewerPage } from '../features/dicom-cdss/DicomViewerPage';
import { BillingPage } from '../features/billing/BillingPage';

export const AppRoutes: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route path="/dashboard" element={<AnalyticsPage />} />
            <Route path="/appointments" element={<AppointmentsPage />} />

            <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
              <Route path="/users" element={<UsersPage />} />
            </Route>

            <Route element={<ProtectedRoute allowedRoles={['staff', 'patient']} />}>
              <Route path="/clinical-emr" element={<ClinicalEmrPage />} />
              <Route path="/rehab-plans" element={<RehabPlansPage />} />
              <Route path="/dicom-viewer" element={<DicomViewerPage />} />
            </Route>

            <Route element={<ProtectedRoute allowedRoles={['admin', 'staff', 'patient']} />}>
              <Route path="/billing" element={<BillingPage />} />
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

