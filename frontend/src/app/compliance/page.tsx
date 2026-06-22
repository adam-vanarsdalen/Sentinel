'use client'
import { PackageBuilder } from '@/components/compliance/PackageBuilder'

export default function CompliancePage() {
  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-200 mb-4">Compliance Evidence Packages</h2>
      <PackageBuilder />
    </div>
  )
}
