import { useEffect, useMemo, useState } from 'react'
import { api } from './api.js'

function EditRecipe({ recipeId, onBack, onSaved }) {
  const [original, setOriginal] = useState(null)
  const [title, setTitle] = useState('')
  const [cuisine, setCuisine] = useState('')
  const [prepMin, setPrepMin] = useState('0')
  const [cookMin, setCookMin] = useState('0')
  const [tags, setTags] = useState([])
  const [tagInput, setTagInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    api
      .getRecipe(recipeId)
      .then((recipe) => {
        if (cancelled) return
        setOriginal(recipe)
        setTitle(recipe.title || '')
        setCuisine(recipe.cuisine || '')
        setPrepMin(String(recipe.prep_min ?? 0))
        setCookMin(String(recipe.cook_min ?? 0))
        setTags(recipe.tags || [])
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [recipeId])

  const changes = useMemo(() => {
    if (!original) return {}

    const next = {}
    const trimmedTitle = title.trim()
    const trimmedCuisine = cuisine.trim()
    const nextPrepMin = toWholeMinutes(prepMin)
    const nextCookMin = toWholeMinutes(cookMin)

    if (trimmedTitle !== (original.title || '')) next.title = trimmedTitle
    if (trimmedCuisine !== (original.cuisine || '')) next.cuisine = trimmedCuisine
    if (nextPrepMin !== (original.prep_min ?? 0)) next.prep_min = nextPrepMin
    if (nextCookMin !== (original.cook_min ?? 0)) next.cook_min = nextCookMin
    if (!sameTags(tags, original.tags || [])) next.tags = tags

    return next
  }, [cookMin, cuisine, original, prepMin, tags, title])

  const hasChanges = Object.keys(changes).length > 0

  function addTag() {
    const nextTag = tagInput.trim()
    if (!nextTag) return

    const alreadyExists = tags.some((tag) => tag.toLowerCase() === nextTag.toLowerCase())
    if (!alreadyExists) {
      setTags([...tags, nextTag])
    }
    setTagInput('')
  }

  function removeTagAt(indexToRemove) {
    setTags(tags.filter((_, index) => index !== indexToRemove))
  }

  function handleTagKeyDown(event) {
    if (event.key === 'Enter') {
      event.preventDefault()
      addTag()
    }
  }

  function handleCancel() {
    if (hasChanges && !window.confirm('Discard changes?')) return
    onBack()
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setMessage('')
    setError('')

    if (!hasChanges) {
      setMessage('No changes')
      return
    }

    if (!title.trim()) {
      setError('Title is required.')
      return
    }

    try {
      setSaving(true)
      const updatedRecipe = await api.updateRecipe(recipeId, changes)
      onSaved(updatedRecipe)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <p className="state-text">Loading...</p>
  }

  if (error && !original) {
    return (
      <div className="state-panel">
        <p>Something went wrong</p>
        <button className="button button-secondary" onClick={onBack}>
          Back
        </button>
      </div>
    )
  }

  return (
    <section className="page-section edit-layout">
      <header className="detail-actions">
        <button className="button button-secondary" onClick={handleCancel}>
          ← Back
        </button>
      </header>

      <div className="recipe-hero">
        <p className="eyebrow">Edit recipe</p>
        <h1>{original.title}</h1>
      </div>

      <form className="form-panel edit-form" onSubmit={handleSubmit}>
        <label>
          Title
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            required
          />
        </label>

        <label>
          Cuisine
          <input
            value={cuisine}
            onChange={(event) => setCuisine(event.target.value)}
          />
        </label>

        <div className="form-grid">
          <label>
            Prep time (min)
            <input
              min="0"
              step="1"
              type="number"
              value={prepMin}
              onChange={(event) => setPrepMin(event.target.value)}
            />
          </label>
          <label>
            Cook time (min)
            <input
              min="0"
              step="1"
              type="number"
              value={cookMin}
              onChange={(event) => setCookMin(event.target.value)}
            />
          </label>
        </div>

        <div className="field-group">
          <span className="field-label">Tags</span>
          <div className="tag-editor">
            {tags.map((tag, index) => (
              <span className="editable-tag" key={`${tag}-${index}`}>
                {tag}
                <button
                  type="button"
                  onClick={() => removeTagAt(index)}
                  aria-label={`Remove ${tag}`}
                >
                  ×
                </button>
              </span>
            ))}
            <div className="tag-input-row">
              <input
                value={tagInput}
                onChange={(event) => setTagInput(event.target.value)}
                onKeyDown={handleTagKeyDown}
                placeholder="Add tag"
              />
              <button className="button button-secondary" type="button" onClick={addTag}>
                Add
              </button>
            </div>
          </div>
        </div>

        {error && <p className="error-text">{error}</p>}
        {message && <p className="selected-file">{message}</p>}

        <div className="form-actions">
          <button className="button button-secondary" type="button" onClick={handleCancel}>
            Cancel
          </button>
          <button
            className={`button button-primary ${!hasChanges ? 'button-muted' : ''}`}
            type="submit"
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save changes'}
          </button>
        </div>
      </form>
    </section>
  )
}

function sameTags(left, right) {
  if (left.length !== right.length) return false
  return left.every((tag, index) => tag === right[index])
}

function toWholeMinutes(value) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return 0
  return Math.max(0, Math.trunc(parsed))
}

export default EditRecipe
