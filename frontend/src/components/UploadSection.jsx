import { useRef, useState } from 'react'

const MAX_SIZE = 50 * 1024 * 1024

function UploadSection({ onUpload, isUploading, uploadStatus, uploadProgress }) {
  const inputRef = useRef(null)
  const [dragOver, setDragOver] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [sizeError, setSizeError] = useState(null)

  const validateAndSelect = (file) => {
    setSizeError(null)
    if (file.size > MAX_SIZE) {
      setSizeError(`File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum is 50 MB.`)
      return
    }
    setSelectedFile(file)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file?.type === 'application/pdf') {
      validateAndSelect(file)
    }
  }

  const handleFileChange = (e) => {
    const file = e.target.files[0]
    if (file) validateAndSelect(file)
  }

  const handleUpload = async () => {
    if (!selectedFile) return
    await onUpload(selectedFile)
    setSelectedFile(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <section className="bg-white rounded-lg border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Upload Document</h2>

      <div
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          dragOver
            ? 'border-blue-400 bg-blue-50'
            : 'border-gray-300 hover:border-blue-400 hover:bg-blue-50'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileChange}
          className="hidden"
        />
        {selectedFile ? (
          <div>
            <p className="text-gray-900 font-medium">{selectedFile.name}</p>
            <p className="text-sm text-gray-500 mt-1">
              {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
            </p>
          </div>
        ) : (
          <div>
            <svg className="mx-auto h-12 w-12 text-gray-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 16v-8m0 0l-3 3m3-3l3 3M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
            </svg>
            <p className="text-gray-500">Drag & drop a PDF here, or click to select</p>
            <p className="text-sm text-gray-400 mt-1">PDF files only, max 50 MB</p>
          </div>
        )}
      </div>

      {sizeError && (
        <div className="mt-3 p-3 rounded-lg text-sm bg-red-50 text-red-700 border border-red-200">
          {sizeError}
        </div>
      )}

      {selectedFile && (
        <button
          onClick={handleUpload}
          disabled={isUploading}
          className="mt-4 w-full bg-blue-600 text-white py-2.5 px-4 rounded-lg hover:bg-blue-700 disabled:bg-blue-300 transition-colors font-medium flex items-center justify-center gap-2"
        >
          {isUploading && (
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          )}
          {isUploading ? 'Processing...' : 'Upload & Process'}
        </button>
      )}

      {isUploading && uploadProgress != null && (
        <div className="mt-3">
          <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
            <span>Uploading...</span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {uploadStatus && (
        <div className={`mt-4 p-3 rounded-lg text-sm ${
          uploadStatus.success
            ? 'bg-green-50 text-green-700 border border-green-200'
            : 'bg-red-50 text-red-700 border border-red-200'
        }`}>
          {uploadStatus.success ? '✓ ' : '✗ '}{uploadStatus.message}
        </div>
      )}
    </section>
  )
}

export default UploadSection
