import { lazy, Suspense } from 'react'
import { Link, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { EmptyState, LoadingState } from './components/ui'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Shipments = lazy(() => import('./pages/Shipments'))
const ShipmentDetail = lazy(() => import('./pages/ShipmentDetail'))
const ShipmentForm = lazy(() => import('./pages/ShipmentForm'))
const Carriers = lazy(() => import('./pages/Carriers'))
const RoutesPage = lazy(() => import('./pages/RoutesPage'))
const Alerts = lazy(() => import('./pages/Alerts'))

const page = (el) => <Suspense fallback={<LoadingState />}>{el}</Suspense>

function NotFound() {
  return (
    <EmptyState
      title="This page does not exist"
      action={
        <Link to="/" className="btn btn-primary">
          Go to the dashboard
        </Link>
      }
    >
      Check the address, or use the navigation to find what you need.
    </EmptyState>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={page(<Dashboard />)} />
        <Route path="shipments" element={page(<Shipments />)} />
        <Route path="shipments/new" element={page(<ShipmentForm />)} />
        <Route path="shipments/:id" element={page(<ShipmentDetail />)} />
        <Route path="shipments/:id/edit" element={page(<ShipmentForm />)} />
        <Route path="carriers" element={page(<Carriers />)} />
        <Route path="routes" element={page(<RoutesPage />)} />
        <Route path="alerts" element={page(<Alerts />)} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
