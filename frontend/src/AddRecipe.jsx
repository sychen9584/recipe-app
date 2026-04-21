import { useState } from 'react'
import { api } from './api.js'

function AddRecipe({ onBack, onSuccess }) {
  const [tab, setTab] = useState('url')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submitUrl(event) {
    event.preventDefault()
    if (!url.trim()) return

    setLoading(true)
    setError('')
    try {
      const recipe = await api.addByUrl(url.trim())
      onSuccess(recipe.id)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function submitUpload(event) {
    event.preventDefault()
    if (!file) return

    setLoading(true)
    setError('')
    try {
      const recipe = await api.addByUpload(file)
      onSuccess(recipe.id)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="page-section add-layout">
      <header className="detail-actions">
        <button className="button button-secondary" onClick={onBack}>
          ← Back
        </button>
      </header>

      <div className="recipe-hero">
        <p className="eyebrow">New recipe</p>
        <h1>Add a recipe</h1>
        <p className="muted">Import from a recipe page, photo, or PDF.</p>
      </div>

      <div className="tab-row">
        <button className={tab === 'url' ? 'active' : ''} onClick={() => setTab('url')}>
          From URL
        </button>
        <button className={tab === 'upload' ? 'active' : ''} onClick={() => setTab('upload')}>
          Upload file
        </button>
      </div>

      {tab === 'url' && (
        <form className="form-panel" onSubmit={submitUrl}>
          <label htmlFor="recipe-url">Recipe URL</label>
          <input
            id="recipe-url"
            type="url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://example.com/recipe"
          />
          <button className="button button-primary" type="submit" disabled={loading}>
            {loading ? <LoadingLabel text="Fetching recipe..." /> : 'Add from URL'}
          </button>
        </form>
      )}

      {tab === 'upload' && (
        <form className="form-panel" onSubmit={submitUpload}>
          <label htmlFor="recipe-file">Recipe file</label>
          <input
            id="recipe-file"
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
          {file && <p className="selected-file">{file.name}</p>}
          <button className="button button-primary" type="submit" disabled={loading || !file}>
            {loading ? <LoadingLabel text="Extracting recipe..." /> : 'Upload recipe'}
          </button>
        </form>
      )}

      {error && <p className="error-text">{error}</p>}
    </section>
  )
}

function LoadingLabel({ text }) {
  return (
    <span className="loading-label">
      <span className="spinner" />
      {text}
    </span>
  )
}

export default AddRecipe
