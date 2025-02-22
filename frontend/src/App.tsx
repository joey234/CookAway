import { ChakraProvider, CSSReset } from '@chakra-ui/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import RecipeImport from './components/RecipeImport'
import theme from './theme'

// Create a client
const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ChakraProvider theme={theme}>
        <CSSReset />
        <RecipeImport />
      </ChakraProvider>
    </QueryClientProvider>
  )
}

export default App
