import { useState } from 'react'
import AddRecipe from './AddRecipe.jsx'
import EditRecipe from './EditRecipe.jsx'
import RecipeDetail from './RecipeDetail.jsx'
import RecipeList from './RecipeList.jsx'

function App() {
  const [view, setView] = useState('list')
  const [selectedId, setSelectedId] = useState(null)
  const [selectedRecipe, setSelectedRecipe] = useState(null)

  function showList() {
    setView('list')
    setSelectedId(null)
    setSelectedRecipe(null)
  }

  function showDetail(id) {
    setSelectedId(id)
    setSelectedRecipe(null)
    setView('detail')
  }

  function showSavedRecipe(recipe) {
    setSelectedId(recipe.id)
    setSelectedRecipe(recipe)
    setView('detail')
  }

  return (
    <main className="app-shell">
      {view === 'list' && (
        <RecipeList
          onSelect={showDetail}
          onAdd={() => setView('add')}
        />
      )}

      {view === 'detail' && selectedId && (
        <RecipeDetail
          key={selectedId}
          recipeId={selectedId}
          initialRecipe={selectedRecipe}
          onBack={showList}
          onEdit={() => setView('edit')}
        />
      )}

      {view === 'edit' && selectedId && (
        <EditRecipe
          recipeId={selectedId}
          onBack={() => setView('detail')}
          onSaved={showSavedRecipe}
        />
      )}

      {view === 'add' && (
        <AddRecipe
          onBack={showList}
          onSuccess={showDetail}
        />
      )}
    </main>
  )
}

export default App
