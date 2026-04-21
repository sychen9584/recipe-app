import { useEffect, useState } from 'react'
import * as Slider from '@radix-ui/react-slider'
import { api } from './api.js'

function RecipeDetail({ recipeId, initialRecipe, onBack, onEdit }) {
  const [recipe, setRecipe] = useState(initialRecipe || null)
  const [scaledRecipe, setScaledRecipe] = useState(initialRecipe || null)
  const [servings, setServings] = useState(initialRecipe?.servings || 1)
  const [unit, setUnit] = useState('imperial')
  const [loading, setLoading] = useState(!initialRecipe)
  const [scaling, setScaling] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    if (initialRecipe) {
      return () => {
        cancelled = true
      }
    }

    api
      .getRecipe(recipeId)
      .then((data) => {
        if (cancelled) return
        const initialServings = data.servings || 1
        setRecipe(data)
        setScaledRecipe(data)
        setServings(initialServings)
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
  }, [initialRecipe, recipeId])

  useEffect(() => {
    if (!recipe) return undefined

    let cancelled = false
    const timeout = setTimeout(() => {
      setScaling(true)
      api
        .scaleRecipe(recipeId, servings, unit)
        .then((data) => {
          if (!cancelled) setScaledRecipe(data)
        })
        .catch((err) => {
          if (!cancelled) setError(err.message)
        })
        .finally(() => {
          if (!cancelled) setScaling(false)
        })
    }, 200)

    return () => {
      cancelled = true
      clearTimeout(timeout)
    }
  }, [recipe, recipeId, servings, unit])

  async function handleDelete() {
    const confirmed = window.confirm('Delete this recipe?')
    if (!confirmed) return

    try {
      await api.deleteRecipe(recipeId)
      onBack()
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) {
    return <p className="state-text">Loading recipe...</p>
  }

  if (error && !recipe) {
    return (
      <div className="state-panel">
        <p>Something went wrong</p>
        <button className="button button-secondary" onClick={onBack}>
          Back
        </button>
      </div>
    )
  }

  if (!recipe || !scaledRecipe) {
    return null
  }

  return (
    <section className="page-section detail-layout">
      <header className="detail-actions">
        <button className="button button-secondary" onClick={onBack}>
          ← Back
        </button>
        <div className="action-row">
          <button className="button button-secondary" onClick={onEdit}>
            Edit
          </button>
          <button className="button button-danger" onClick={handleDelete}>
            Delete
          </button>
        </div>
      </header>

      <div className="recipe-hero">
        <p className="eyebrow">Recipe detail</p>
        <h1>{recipe.title}</h1>
        <p className="muted">
          {recipe.cuisine || 'Home kitchen'} · Prep {recipe.prep_min || 0} min · Cook{' '}
          {recipe.cook_min || 0} min
        </p>
        <SourceUrl value={recipe.source_url} />
        <TagList tags={recipe.tags} />
      </div>

      {error && <p className="error-text">{error}</p>}

      <div className="detail-columns">
        <section className="ingredient-panel">
          <div className="section-title-row">
            <h2>Ingredients</h2>
            {scaling && <span className="mini-status">Updating...</span>}
          </div>

          <div className="scaler-box">
            <div className="serving-row">
              <span>Servings</span>
              <strong>{servings}</strong>
            </div>
            {!recipe.servings && (
              <p className="mini-status">Original servings unknown; scaling defaults to 4 servings.</p>
            )}
            <Slider.Root
              className="slider-root"
              min={1}
              max={12}
              step={1}
              value={[servings]}
              onValueChange={([next]) => setServings(next)}
            >
              <Slider.Track className="slider-track">
                <Slider.Range className="slider-range" />
              </Slider.Track>
              <Slider.Thumb className="slider-thumb" aria-label="Servings" />
            </Slider.Root>

            <div className="unit-toggle" aria-label="Unit system">
              <button
                className={unit === 'imperial' ? 'active' : ''}
                onClick={() => setUnit('imperial')}
              >
                Imperial
              </button>
              <button
                className={unit === 'metric' ? 'active' : ''}
                onClick={() => setUnit('metric')}
              >
                Metric
              </button>
            </div>
          </div>

          <ul className="ingredient-list">
            {scaledRecipe.ingredients.map((ingredient) => (
              <li key={ingredient.id}>
                {formatIngredient(ingredient)}
              </li>
            ))}
          </ul>
        </section>

        <section className="steps-panel">
          <h2>Steps</h2>
          <ol className="steps-list">
            {recipe.steps.map((step) => (
              <li key={step.id}>
                <span>{step.step_number}</span>
                <p>{step.instruction}</p>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </section>
  )
}

function formatIngredient(ingredient) {
  const amount = [ingredient.display_quantity, ingredient.display_unit]
    .filter(Boolean)
    .join(' ')
  const prep = ingredient.preparation ? `, ${ingredient.preparation}` : ''
  return `${amount ? `${amount} ` : ''}${ingredient.name}${prep}`
}

function SourceUrl({ value }) {
  if (!value) return null

  if (value.startsWith('http://') || value.startsWith('https://')) {
    return (
      <a className="source-link" href={value} target="_blank" rel="noreferrer">
        {value}
      </a>
    )
  }

  return <p className="source-link muted">{value}</p>
}

function TagList({ tags = [] }) {
  if (!tags.length) return null

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

export default RecipeDetail
