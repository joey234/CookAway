import { useState } from 'react'
import {
  Box,
  Button,
  Container,
  FormControl,
  FormLabel,
  Heading,
  Radio,
  RadioGroup,
  Stack,
  Textarea,
  useToast,
  VStack,
  Input
} from '@chakra-ui/react'
import { useMutation } from '@tanstack/react-query'
import axios from 'axios'

interface Recipe {
  title: string
  metadata: {
    servings: number
    prepTime: string
    cookTime: string
    difficulty: string
  }
  ingredients: Array<{
    item: string
    amount: number
    unit: string
    notes?: string
  }>
  steps: Array<{
    step: number
    instruction: string
    timer?: {
      duration: number
      type: string
    }
    checkpoints?: string[]
  }>
  equipment: string[]
}

const RecipeImport = () => {
  const [inputType, setInputType] = useState<'text' | 'url'>('text')
  const [content, setContent] = useState('')
  const toast = useToast()

  const importRecipe = useMutation({
    mutationFn: async (data: { content: string; type: 'text' | 'url' }): Promise<Recipe> => {
      const response = await axios.post('http://localhost:8000/api/recipes/import', data)
      return response.data
    },
    onSuccess: (data) => {
      toast({
        title: 'Recipe imported successfully!',
        description: `Imported: ${data.title}`,
        status: 'success',
        duration: 5000,
        isClosable: true,
      })
      // TODO: Handle the parsed recipe data (e.g., store in state, navigate to next step)
    },
    onError: (error) => {
      toast({
        title: 'Failed to import recipe',
        description: error instanceof Error ? error.message : 'An error occurred',
        status: 'error',
        duration: 5000,
        isClosable: true,
      })
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!content.trim()) {
      toast({
        title: 'Error',
        description: 'Please enter a recipe or URL',
        status: 'error',
        duration: 3000,
        isClosable: true,
      })
      return
    }
    importRecipe.mutate({ content, type: inputType })
  }

  return (
    <Container maxW="container.md" py={10}>
      <VStack spacing={8} align="stretch">
        <Heading textAlign="center">Import Your Recipe</Heading>
        
        <form onSubmit={handleSubmit}>
          <VStack spacing={6}>
            <FormControl as="fieldset">
              <FormLabel as="legend">Import Method</FormLabel>
              <RadioGroup value={inputType} onChange={(value: 'text' | 'url') => setInputType(value)}>
                <Stack direction="row">
                  <Radio value="text">Paste Recipe Text</Radio>
                  <Radio value="url">Recipe URL</Radio>
                </Stack>
              </RadioGroup>
            </FormControl>

            <FormControl>
              {inputType === 'text' ? (
                <Textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="Paste your recipe here..."
                  size="lg"
                  minH="200px"
                />
              ) : (
                <Input
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="Enter recipe URL..."
                  size="lg"
                  type="url"
                />
              )}
            </FormControl>

            <Button
              type="submit"
              colorScheme="blue"
              size="lg"
              width="full"
              isLoading={importRecipe.isPending}
            >
              Import Recipe
            </Button>
          </VStack>
        </form>

        {importRecipe.isError && (
          <Box p={4} bg="red.100" color="red.700" borderRadius="md">
            Error: {importRecipe.error instanceof Error ? importRecipe.error.message : 'An error occurred'}
          </Box>
        )}
      </VStack>
    </Container>
  )
}

export default RecipeImport 