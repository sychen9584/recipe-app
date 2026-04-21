import { useEffect, useState } from 'react'
import { api } from './api.js'

function RecipeList({ onSelect, onAdd }) {
  const [recipes, setRecipes] = useState([])
  const [search, setSearch] = useState('')
  const [activeTag, setActiveTag] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    const timeout = setTimeout(() => {
      setLoading(true)
      setError('')

      api
        .getRecipes(search, activeTag)
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
  }, [activeTag, search, reloadKey])

  function handleSearchChange(event) {
    setSearch(event.target.value)
    setActiveTag('')
  }

  function handleCardKeyDown(event, recipeId) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelect(recipeId)
    }
  }

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
          onChange={handleSearchChange}
          placeholder="Search by title or tag"
        />
      </div>

      {activeTag && (
        <div className="active-tag-banner">
          <span>
            Filtered by: <strong>{activeTag}</strong>
          </span>
          <button onClick={() => setActiveTag('')}>Clear ×</button>
        </div>
      )}

      {loading && <p className="state-text">Loading recipes... (may take up to 30s on first visit)</p>}

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
            <article
              className="recipe-card"
              key={recipe.id}
              role="button"
              tabIndex={0}
              onClick={() => onSelect(recipe.id)}
              onKeyDown={(event) => handleCardKeyDown(event, recipe.id)}
            >
              <h2>{recipe.title}</h2>
              <p className="muted">
                {recipe.cuisine || 'Home kitchen'} · {totalTime(recipe)} min
              </p>
              <p>{servingLabel(recipe.servings)}</p>
              <TagList
                activeTag={activeTag}
                tags={recipe.tags}
                onTagClick={setActiveTag}
              />
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

function totalTime(recipe) {
  return (recipe.prep_min || 0) + (recipe.cook_min || 0)
}

function servingLabel(servings) {
  if (!servings) return 'Servings unknown'
  return `${servings} ${servings === 1 ? 'serving' : 'servings'}`
}

function TagList({ tags = [], activeTag, onTagClick }) {
  const visibleTags = Array.isArray(tags) ? tags.filter(Boolean) : []

  if (!visibleTags.length) {
    return null
  }

  return (
    <div className="tag-row">
      {visibleTags.map((tag, index) => (
        <button
          className={`tag-pill ${activeTag === tag ? 'tag-pill--active' : ''}`}
          key={`${tag}-${index}`}
          onClick={(event) => {
            event.stopPropagation()
            onTagClick((previous) => (previous === tag ? '' : tag))
          }}
          onKeyDown={(event) => event.stopPropagation()}
        >
          {tag}
        </button>
      ))}
    </div>
  )
}

export default RecipeList
