import { useContext } from 'react'
import { AdminDataContext } from '../context/adminDataContextValue'

export function useAdminData() {
  const value = useContext(AdminDataContext)
  if (!value) {
    throw new Error('useAdminData must be used within AdminDataProvider')
  }
  return value
}
