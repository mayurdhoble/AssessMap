import { useState, useRef } from 'react'
import { X, Upload, CheckCircle, AlertCircle } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import api from '../api/client'

export default function UploadModal({ onClose, onSuccess }) {
  const [dragging, setDragging] = useState(false)
  const [status, setStatus] = useState(null) // null | 'uploading' | 'success' | 'error'
  const [message, setMessage] = useState('')
  const [result, setResult] = useState(null)
  const fileRef = useRef(null)
  const qc = useQueryClient()

  const upload = async (file) => {
    const form = new FormData()
    form.append('file', file)
    setStatus('uploading')
    setMessage('')
    try {
      const { data } = await api.post('/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setStatus('success')
      setResult(data)
      // Use browser file.name as fallback in case backend filename is missing
      const displayName = data.filename || file.name || 'file'
      const displayRows = data.rows != null ? data.rows.toLocaleString() : '?'
      setMessage(`Loaded ${displayRows} rows from "${displayName}"`)
      qc.invalidateQueries()
    } catch (e) {
      setStatus('error')
      setMessage(e.response?.data?.detail || 'Upload failed. Check your file format.')
    }
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) upload(file)
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-gray-100">
          <h2 className="font-semibold text-gray-800">Upload Data File</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <X size={20} />
          </button>
        </div>

        <div className="p-5">
          {status === 'success' ? (
            <div className="text-center py-6">
              <CheckCircle size={48} className="text-green-500 mx-auto mb-3" />
              <p className="font-medium text-gray-800">{message}</p>
              {result?.date_range?.min && (
                <p className="text-sm text-gray-500 mt-1">
                  Date range: {result.date_range.min?.slice(0, 10)} → {result.date_range.max?.slice(0, 10)}
                </p>
              )}
              {!result?.has_date && (
                <p className="text-xs text-amber-600 bg-amber-50 rounded-lg px-3 py-2 mt-3">
                  No "Date" column detected — date filters will be unavailable.
                </p>
              )}
              <button
                onClick={onSuccess}
                className="mt-5 px-6 py-2.5 bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-medium transition-colors"
              >
                View Dashboard
              </button>
            </div>
          ) : (
            <>
              {/* Drop zone */}
              <div
                onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                onClick={() => fileRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors
                  ${dragging
                    ? 'border-orange-400 bg-orange-50'
                    : 'border-gray-200 hover:border-orange-300 hover:bg-gray-50'
                  }`}
              >
                <Upload
                  size={32}
                  className={`mx-auto mb-3 ${dragging ? 'text-orange-500' : 'text-gray-300'}`}
                />
                <p className="font-medium text-gray-600 mb-1">Drop CSV or Excel file here</p>
                <p className="text-sm text-gray-400">or click to browse</p>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
                />
              </div>

              {status === 'uploading' && (
                <div className="mt-4 text-center">
                  <div className="inline-block w-6 h-6 border-2 border-orange-500 border-t-transparent rounded-full animate-spin mb-2" />
                  <p className="text-sm text-gray-500">Parsing file…</p>
                </div>
              )}

              {status === 'error' && (
                <div className="mt-4 flex items-start gap-2 p-3 bg-red-50 rounded-lg text-red-600 text-sm">
                  <AlertCircle size={16} className="mt-0.5 shrink-0" />
                  {message}
                </div>
              )}

              <div className="mt-4 p-3 bg-gray-50 rounded-lg text-xs text-gray-500 space-y-1">
                <p className="font-medium text-gray-600">Required columns:</p>
                <p>Recruiter Email, Company Name, AccountTypeId, Test Name, QB Name, Library, Category, Reports Generated, NavigationType</p>
                <p className="font-medium text-gray-600 mt-1">Optional:</p>
                <p>Date (enables date range filters &amp; monthly trends)</p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
