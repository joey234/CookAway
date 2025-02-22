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
import VoiceInteraction from './VoiceInteraction'

interface Recipe {
  id: string
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
  const [importedRecipe, setImportedRecipe] = useState<Recipe | null>(null)
  const toast = useToast()

  const importRecipe = useMutation({
    mutationFn: async (data: { content: string; type: 'text' | 'url' }): Promise<Recipe> => {
      const response = await axios.post('http://localhost:8000/api/recipes/import', data)
      return response.data
    },
    onSuccess: (data) => {
      setImportedRecipe(data)
      toast({
        title: 'Recipe imported successfully!',
        description: `Imported: ${data.title}`,
        status: 'success',
        duration: 5000,
        isClosable: true,
      })
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

  const handleReset = () => {
    setContent('')
    setImportedRecipe(null)
  }

  return (
    <Container maxW="container.md" py={10}>
      <VStack spacing={8} align="stretch">
        <Heading textAlign="center">CookAway</Heading>
        
        {!importedRecipe ? (
          <form onSubmit={handleSubmit}>
            <VStack spacing={6}>
              <Button
                onClick={(e) => {
                  e.preventDefault();
                  axios.get('http://localhost:8000/api/test-recipe')
                    .then(response => {
                      const testRecipeId = response.data.id;
                      return axios.get(`http://localhost:8000/api/recipes/${testRecipeId}`);
                    })
                    .then(recipeResponse => {
                      setImportedRecipe(recipeResponse.data);
                      toast({
                        title: 'Test recipe loaded!',
                        description: `Loaded: ${recipeResponse.data.title}`,
                        status: 'success',
                        duration: 5000,
                        isClosable: true,
                      });
                    })
                    .catch(error => {
                      toast({
                        title: 'Failed to load test recipe',
                        description: error instanceof Error ? error.message : 'An error occurred',
                        status: 'error',
                        duration: 5000,
                        isClosable: true,
                      });
                    });
                }}
                colorScheme="green"
                size="lg"
                width="full"
                mb={4}
              >
                Load Test Recipe
              </Button>

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
        ) : (
          <VStack spacing={6}>
            <Heading size="md">{importedRecipe.title}</Heading>
            <VoiceInteraction 
              recipeId={importedRecipe.id} 
              onRecipeUpdate={(newRecipeId) => {
                setImportedRecipe(prev => prev ? { ...prev, id: newRecipeId } : null)
              }}
            />
            <Button onClick={handleReset} colorScheme="gray">
              Import Another Recipe
            </Button>
          </VStack>
        )}

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