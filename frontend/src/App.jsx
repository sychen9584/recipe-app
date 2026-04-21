import { useState } from 'react'
import AddRecipe from './AddRecipe.jsx'
import RecipeDetail from './RecipeDetail.jsx'
import RecipeList from './RecipeList.jsx'

function App() {
  const [view, setView] = useState('list')
  const [selectedId, setSelectedId] = useState(null)

  function showList() {
    setView('list')
    setSelectedId(null)
  }

  function showDetail(id) {
    setSelectedId(id)
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
          onBack={showList}
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
