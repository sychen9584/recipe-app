import { useEffect, useState } from 'react'
import { api } from './api.js'

function RecipeList({ onSelect, onAdd }) {
  const [recipes, setRecipes] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    const timeout = setTimeout(() => {
      setLoading(true)
      setError('')

      api
        .getRecipes(search)
        .then((data) => {
          if (!cancelled) {
            setRecipes(data)
          }
        })
        .catch((err) => {
          if (!cancelled) {
            setError(err.message)
          }
        })
        .finally(() => {
          if (!cancelled) {
            setLoading(false)
          }
        })
    }, 300)

    return () => {
      cancelled = true
      clearTimeout(timeout)
    }
  }, [search, reloadKey])

  return (
    <section className="page-section">
      <header className="page-header">
        <div>
          <p className="eyebrow">Eating out is overrated</p>
          <h1>Sam's Recipe Collection</h1>
        </div>
        <button className="button button-primary" onClick={onAdd}>
          Add recipe
        </button>
      </header>

      <div className="toolbar">
        <label className="search-label" htmlFor="recipe-search">
          Search
        </label>
        <input
          id="recipe-search"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by title"
        />
      </div>

      {loading && <p className="state-text">Loading recipes...</p>}

      {!loading && error && (
        <div className="state-panel">
          <p>Something went wrong</p>
          <button
            className="button button-secondary"
            onClick={() => setReloadKey((key) => key + 1)}
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && recipes.length === 0 && (
        <div className="state-panel">
          <p>No recipes yet. Add your first one!</p>
          <button className="button button-primary" onClick={onAdd}>
            Add recipe
          </button>
        </div>
      )}

      {!loading && !error && recipes.length > 0 && (
        <div className="recipe-grid">
          {recipes.map((recipe) => (
            <button
              className="recipe-card"
              key={recipe.id}
              onClick={() => onSelect(recipe.id)}
            >
              <h2>{recipe.title}</h2>
              <p className="muted">
                {recipe.cuisine || 'Home kitchen'} · {totalTime(recipe)} min
              </p>
              <p>{recipe.servings || 0} servings</p>
              <TagList tags={recipe.tags} />
            </button>
          ))}
        </div>
      )}
    </section>
  )
}

function totalTime(recipe) {
  return (recipe.prep_min || 0) + (recipe.cook_min || 0)
}

function TagList({ tags = [] }) {
  if (!tags.length) {
    return null
  }

  return (
    <div className="tag-row">
      {tags.map((tag) => (
        <span className="tag" key={tag}>
          {tag}
        </span>
      ))}
    </div>
  )
}

export default RecipeList
