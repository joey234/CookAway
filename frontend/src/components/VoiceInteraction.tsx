import { useState, useEffect, useRef } from 'react'
import {
  Box,
  Button,
  Text,
  VStack,
  useToast,
  CircularProgress,
  Icon,
  Flex,
  Avatar,
  Divider,
  Spacer,
  HStack,
  Input,
  InputGroup,
  InputRightElement,
  IconButton,
} from '@chakra-ui/react'
import axios from 'axios'
import { FaMicrophone, FaMicrophoneSlash, FaPaperPlane } from 'react-icons/fa'

interface VoiceInteractionProps {
  recipeId: string
  onRecipeUpdate?: (newRecipeId: string) => void
}

type ConversationState = 
  | "initial_summary"
  | "asking_servings"
  | "asking_substitution"
  | "ready_to_cook"
  | "cooking"

interface SubstitutionOption {
  original: string
  substitute: string
  amount: string | number
  unit: string
  notes: string
  instructions: string
}

// Web Speech API type definitions
interface SpeechRecognitionEvent extends Event {
  results: {
    [key: number]: {
      [key: number]: {
        transcript: string;
      };
    };
  };
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: (event: SpeechRecognitionEvent) => void;
  onerror: (event: SpeechRecognitionErrorEvent) => void;
  onend: () => void;
}

interface SpeechRecognitionConstructor {
  new (): SpeechRecognition;
}

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

interface TimerData {
    duration: number;
    type: string;
    step: number;
    warning_time: number;
}

interface Message {
    id: string
    type: 'user' | 'assistant'
    content: string
    timestamp: Date
    state?: ConversationState
    timer?: TimerData
}

const VoiceInteraction: React.FC<VoiceInteractionProps> = ({ recipeId: initialRecipeId, onRecipeUpdate }) => {
  const [isListening, setIsListening] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentState, setCurrentState] = useState<ConversationState>("initial_summary")
  const [transcript, setTranscript] = useState("")
  const [currentRecipeId, setCurrentRecipeId] = useState(initialRecipeId)
  const [substitutionOptions, setSubstitutionOptions] = useState<SubstitutionOption[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [activeTimer, setActiveTimer] = useState<number | null>(null)
  const [timeRemaining, setTimeRemaining] = useState<number | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const recognitionRef = useRef<SpeechRecognition | null>(null)
  const isInitializedRef = useRef(false)
  const currentStateRef = useRef<ConversationState>("initial_summary")
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const toast = useToast()
  const [textInput, setTextInput] = useState("")

  // Scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Keep currentStateRef in sync with currentState
  useEffect(() => {
    currentStateRef.current = currentState
  }, [currentState])

  // Update currentRecipeId when initialRecipeId changes
  useEffect(() => {
    console.log('Recipe ID Effect:', {
      initialRecipeId,
      currentRecipeId,
      currentState,
      isInitialized: isInitializedRef.current
    })
    
    if (initialRecipeId !== currentRecipeId) {
      console.log('Updating recipe ID from', currentRecipeId, 'to', initialRecipeId)
      setCurrentRecipeId(initialRecipeId)
    }
  }, [initialRecipeId, currentRecipeId])

  useEffect(() => {
    console.log('Mount Effect:', {
      currentState,
      isInitialized: isInitializedRef.current,
      currentRecipeId
    })
    
    // Initialize Web Speech API
    if ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window) {
      const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition
      if (SpeechRecognitionAPI) {
        recognitionRef.current = new SpeechRecognitionAPI()
        recognitionRef.current.continuous = false
        recognitionRef.current.interimResults = false

        recognitionRef.current.onresult = (event) => {
          const transcript = event.results[0][0].transcript
          console.log('Speech Recognition Result:', { transcript, currentState: currentStateRef.current })
          setTranscript(transcript)
          handleVoiceInput(transcript)
        }

        recognitionRef.current.onerror = (event) => {
          console.error('Speech recognition error:', event.error)
          setIsListening(false)
          if (event.error === 'no-speech') {
            // Don't show error for no speech, just restart listening
            startListening()
          } else {
            toast({
              title: "Error",
              description: "Failed to recognize speech. Please try again.",
              status: "error",
              duration: 3000,
            })
          }
        }

        recognitionRef.current.onend = () => {
          setIsListening(false)
        }
      } else {
        toast({
          title: "Error",
          description: "Speech recognition is not supported in your browser.",
          status: "error",
          duration: 5000,
          isClosable: true,
        })
      }
    }

    // Create audio element
    const audio = new Audio()
    audioRef.current = audio
    
    const handleAudioEnd = () => {
      console.log('Audio ended, preserving state:', currentStateRef.current)
      setIsPlaying(false)
      // Only start listening if we're not in the initial state
      if (currentStateRef.current !== "initial_summary") {
        startListening()
      }
    }
    
    audio.addEventListener('ended', handleAudioEnd)

    // Only get initial summary on first mount
    if (!isInitializedRef.current) {
      console.log('Getting initial summary')
      isInitializedRef.current = true
      getRecipeSummary()
    }

    return () => {
      console.log('Cleanup Effect')
      if (recognitionRef.current) {
        recognitionRef.current.abort()
      }
      if (audioRef.current) {
        audioRef.current.removeEventListener('ended', handleAudioEnd)
        const url = audioRef.current.src
        audioRef.current.pause()
        if (url) {
          URL.revokeObjectURL(url)
        }
      }
    }
  }, []) // Keep empty dependency array

  // Add state change monitoring
  useEffect(() => {
    console.log('State changed:', {
      currentState,
      currentRecipeId,
      isInitialized: isInitializedRef.current
    })
  }, [currentState, currentRecipeId])

  // Handle timer updates
  useEffect(() => {
    if (timeRemaining !== null) {
        if (timeRemaining <= 0) {
            // Clear timer when it reaches 0 or is stopped
            setTimeRemaining(null);
            if (activeTimer) {
                window.clearInterval(activeTimer);
                setActiveTimer(null);
            }
            return;
        }

        const timer = window.setInterval(() => {
            setTimeRemaining(prev => {
                if (prev === null) return null;
                const newTime = prev - 1;
                
                // Play warning sound at 20 seconds remaining
                if (newTime === 20) {
                    const warningAudio = new Audio('/warning.mp3');
                    warningAudio.play();
                    toast({
                        title: "Timer Warning",
                        description: "20 seconds remaining!",
                        status: "warning",
                        duration: 5000,
                        isClosable: true,
                    });
                }
                
                // Timer complete
                if (newTime <= 0) {
                    const doneAudio = new Audio('/timer-done.mp3');
                    doneAudio.play();
                    toast({
                        title: "Timer Complete!",
                        description: "Your timer has finished.",
                        status: "success",
                        duration: null,
                        isClosable: true,
                    });
                    
                    // Automatically start listening for next command after timer ends
                    startListening();
                    return null;
                }
                
                return newTime;
            });
        }, 1000);
        
        setActiveTimer(timer);
        return () => window.clearInterval(timer);
    } else if (activeTimer) {
        window.clearInterval(activeTimer);
        setActiveTimer(null);
    }
  }, [timeRemaining]);

  const addMessage = (type: 'user' | 'assistant', content: string, state?: ConversationState, timer?: TimerData) => {
    setMessages(prev => [...prev, {
      id: Math.random().toString(36).substring(7),
      type,
      content,
      timestamp: new Date(),
      state,
      timer
    }])
  }

  const getRecipeSummary = async () => {
    const currentStateValue = currentStateRef.current
    console.log('Getting recipe summary:', {
      currentRecipeId,
      currentState: currentStateValue,
      isInitialized: isInitializedRef.current
    })
    
    try {
      const response = await axios.post(
        `http://localhost:8000/api/recipes/${currentRecipeId}/voice-interaction`,
        {
          recipe_id: currentRecipeId,
          transcript: "",
          current_state: currentStateValue
        },
        { 
          responseType: 'blob',
          headers: {
            'Accept': 'audio/mpeg, application/json',
          }
        }
      )

      const nextState = response.headers['x-next-state'] as ConversationState
      const encodedResponseText = response.headers['x-full-response']
      const isResponseTextEncoded = response.headers['x-response-text-encoded'] === 'true'
      
      // Decode response text if it's encoded
      const responseText = encodedResponseText && isResponseTextEncoded
        ? decodeBase64Text(encodedResponseText)
        : encodedResponseText
      
      if (nextState) {
        setCurrentState(nextState)
      }

      // Add initial assistant message with the response text
      if (responseText) {
        addMessage('assistant', responseText, nextState)
      }

      playAudioResponse(response.data)
    } catch (error) {
      console.error('Error getting recipe summary:', error)
      toast({
        title: "Error",
        description: "Failed to get recipe summary",
        status: "error",
        duration: 3000,
      })
    }
  }

  const startListening = () => {
    if (recognitionRef.current && !isListening) {
      try {
        recognitionRef.current.start()
        setIsListening(true)
      } catch (error) {
        console.error('Error starting speech recognition:', error)
      }
    }
  }

  const stopListening = () => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop()
      setIsListening(false)
    }
  }

  const playAudioResponse = (audioBlob: Blob) => {
    const url = URL.createObjectURL(audioBlob)
    if (audioRef.current) {
      audioRef.current.src = url
      audioRef.current.play()
      setIsPlaying(true)
    }
  }

  const handleVoiceInput = async (transcript: string) => {
    const currentStateValue = currentStateRef.current
    console.log('Handling voice input:', {
      transcript,
      currentState: currentStateValue,
      currentRecipeId
    })
    
    // Add user message
    addMessage('user', transcript)
    
    try {
      setIsPlaying(true)
      
      const response = await axios.post(
        `http://localhost:8000/api/recipes/${currentRecipeId}/voice-interaction`,
        {
          recipe_id: currentRecipeId,
          transcript,
          current_state: currentStateValue
        },
        { 
          responseType: 'blob',
          headers: {
            'Accept': 'audio/mpeg, application/json',
          }
        }
      )

      const nextState = response.headers['x-next-state'] as ConversationState
      const updatedRecipeId = response.headers['x-updated-recipe-id']
      const substitutionOptionsJson = response.headers['x-substitution-options']
      const encodedResponseText = response.headers['x-full-response']
      const isResponseTextEncoded = response.headers['x-response-text-encoded'] === 'true'
      const timerDataJson = response.headers['x-timer-data']
      
      // Decode response text if it's encoded
      const responseText = encodedResponseText && isResponseTextEncoded
        ? decodeBase64Text(encodedResponseText)
        : encodedResponseText
      
      if (updatedRecipeId) {
        setCurrentRecipeId(updatedRecipeId)
        if (onRecipeUpdate) {
          onRecipeUpdate(updatedRecipeId)
        }
      }
      
      // Handle timer data
      let timer: TimerData | undefined = undefined
      if (timerDataJson) {
        try {
          const timerData = JSON.parse(decodeBase64Text(timerDataJson))
          timer = {
            duration: parseInt(timerData.duration),
            type: String(timerData.type),
            step: parseInt(timerData.step),
            warning_time: parseInt(timerData.warning_time)
          }
          // Only set timeRemaining if it's not a stop signal
          if (timer.duration > 0) {
            setTimeRemaining(timer.duration)
          } else {
            setTimeRemaining(null)
          }
        } catch (e) {
          console.error('Error parsing timer data:', e)
        }
      }
      
      // Add assistant's audio response as a message
      if (responseText) {
        addMessage('assistant', responseText, nextState, timer)
      }
      
      if (substitutionOptionsJson) {
        try {
          const decodedOptionsJson = isResponseTextEncoded
            ? decodeBase64Text(substitutionOptionsJson)
            : substitutionOptionsJson
          const options = JSON.parse(decodedOptionsJson)
          setSubstitutionOptions(options)
          // Add substitution options as assistant message
          const optionsMessage = options.map((opt: SubstitutionOption, i: number) => 
            `Option ${i + 1}: ${opt.substitute} (${opt.amount} ${opt.unit})\n${opt.notes}`
          ).join('\n\n')
          addMessage('assistant', optionsMessage, nextState)
        } catch (e) {
          console.error('Error parsing substitution options:', e)
        }
      } else {
        setSubstitutionOptions([])
      }
      
      if (nextState && nextState !== currentStateValue) {
        setCurrentState(nextState)
      }

      playAudioResponse(response.data)
    } catch (error) {
      console.error('Error processing voice input:', error)
      toast({
        title: "Error",
        description: "Failed to process voice input. Please try again.",
        status: "error",
        duration: 3000,
      })
      setIsPlaying(false)
    }
  }

  const decodeBase64Text = (encodedText: string): string => {
    try {
      return atob(encodedText)
    } catch (e) {
      console.error('Error decoding base64 text:', e)
      return encodedText
    }
  }

  const formatTime = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  }

  const handleTextSubmit = async (e?: React.FormEvent) => {
    if (e) {
      e.preventDefault()
    }
    if (!textInput.trim()) return

    // Add user message
    addMessage('user', textInput)
    
    try {
      setIsPlaying(true)
      
      const response = await axios.post(
        `http://localhost:8000/api/recipes/${currentRecipeId}/voice-interaction`,
        {
          recipe_id: currentRecipeId,
          transcript: textInput,
          current_state: currentStateRef.current
        },
        { 
          responseType: 'blob',
          headers: {
            'Accept': 'audio/mpeg, application/json',
          }
        }
      )

      const nextState = response.headers['x-next-state'] as ConversationState
      const updatedRecipeId = response.headers['x-updated-recipe-id']
      const encodedResponseText = response.headers['x-full-response']
      const isResponseTextEncoded = response.headers['x-response-text-encoded'] === 'true'
      const timerDataJson = response.headers['x-timer-data']
      
      // Decode response text if it's encoded
      const responseText = encodedResponseText && isResponseTextEncoded
        ? decodeBase64Text(encodedResponseText)
        : encodedResponseText
      
      if (updatedRecipeId) {
        setCurrentRecipeId(updatedRecipeId)
        if (onRecipeUpdate) {
          onRecipeUpdate(updatedRecipeId)
        }
      }
      
      // Handle timer data
      let timer: TimerData | undefined = undefined
      if (timerDataJson) {
        try {
          const timerData = JSON.parse(decodeBase64Text(timerDataJson))
          timer = {
            duration: parseInt(timerData.duration),
            type: String(timerData.type),
            step: parseInt(timerData.step),
            warning_time: parseInt(timerData.warning_time)
          }
          // Only set timeRemaining if it's not a stop signal
          if (timer.duration > 0) {
            setTimeRemaining(timer.duration)
          } else {
            setTimeRemaining(null)
          }
        } catch (e) {
          console.error('Error parsing timer data:', e)
        }
      }
      
      // Add assistant's response as a message
      if (responseText) {
        addMessage('assistant', responseText, nextState, timer)
      }
      
      if (nextState && nextState !== currentStateRef.current) {
        setCurrentState(nextState)
      }

      playAudioResponse(response.data)
      setTextInput("") // Clear input after sending
    } catch (error) {
      console.error('Error processing text input:', error)
      toast({
        title: "Error",
        description: "Failed to process text input. Please try again.",
        status: "error",
        duration: 3000,
      })
      setIsPlaying(false)
    }
  }

  return (
    <HStack spacing={4} align="stretch" h="100vh" p={4}>
      {/* Left Column - Conversation */}
      <Box flex="2" h="100%">
        {/* Chat Messages */}
        <Box
          h="calc(100% - 120px)"  // Adjusted to leave space for input and button
          overflowY="auto"
          borderRadius="lg"
          borderWidth="1px"
          borderColor="gray.200"
          p={4}
          bg="gray.50"
          mb={4}
        >
          <VStack spacing={4} align="stretch">
            {messages.map((message) => (
              <Flex
                key={message.id}
                direction={message.type === 'user' ? 'row-reverse' : 'row'}
                align="start"
                gap={2}
              >
                <Avatar
                  size="sm"
                  name={message.type === 'user' ? 'User' : 'Assistant'}
                  bg={message.type === 'user' ? 'blue.500' : 'green.500'}
                />
                <Box
                  maxW="80%"
                  bg={message.type === 'user' ? 'blue.500' : 'white'}
                  color={message.type === 'user' ? 'white' : 'black'}
                  p={3}
                  borderRadius="lg"
                  boxShadow="sm"
                  position="relative"
                  _after={{
                    content: '""',
                    position: 'absolute',
                    top: '10px',
                    [message.type === 'user' ? 'right' : 'left']: '-8px',
                    border: '8px solid transparent',
                    borderRightColor: message.type === 'user' ? 'transparent' : 'white',
                    borderLeftColor: message.type === 'user' ? 'blue.500' : 'transparent',
                    transform: message.type === 'user' ? 'translateX(8px)' : 'translateX(-8px)'
                  }}
                >
                  <Text whiteSpace="pre-wrap">{message.content}</Text>
                  <Text fontSize="xs" color={message.type === 'user' ? 'whiteAlpha.700' : 'gray.500'} mt={1}>
                    {message.timestamp.toLocaleTimeString()}
                  </Text>
                  {message.timer && (
                    <Text fontSize="sm" color="blue.600" mt={1}>
                      Timer: {formatTime(message.timer.duration)}
                    </Text>
                  )}
                </Box>
              </Flex>
            ))}
            <div ref={messagesEndRef} />
          </VStack>
        </Box>

        {/* Input Section */}
        <VStack spacing={2}>
          <form onSubmit={handleTextSubmit} style={{ width: '100%' }}>
            <InputGroup size="lg">
              <Input
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder="Type your command or question..."
                pr="4.5rem"
                disabled={isPlaying}
              />
              <InputRightElement width="4.5rem">
                <IconButton
                  h="1.75rem"
                  size="sm"
                  icon={<Icon as={FaPaperPlane} />}
                  aria-label="Send message"
                  type="submit"
                  isDisabled={isPlaying || !textInput.trim()}
                  colorScheme="blue"
                />
              </InputRightElement>
            </InputGroup>
          </form>

          <Button
            colorScheme="blue"
            size="lg"
            width="full"
            onClick={isListening ? stopListening : startListening}
            isDisabled={isPlaying}
            leftIcon={isListening ? <Icon as={FaMicrophoneSlash} /> : <Icon as={FaMicrophone} />}
          >
            {isListening ? "Stop Listening" : "Start Listening"}
          </Button>
        </VStack>
      </Box>

      {/* Right Column - Status and Commands */}
      <Box flex="1" h="100%" position="sticky" top={4}>
        <VStack spacing={4} h="100%" align="stretch">
          {/* Status Box */}
          <Box p={4} bg="blue.50" borderRadius="lg" shadow="sm">
            <Text fontSize="lg" fontWeight="bold" mb={2}>
              Current State: {currentState.replace(/_/g, ' ').toUpperCase()}
            </Text>
            <Text fontSize="md" color="gray.600">
              {isListening ? "Listening..." : isPlaying ? "Playing audio response..." : "Ready for voice input"}
            </Text>
            {(isListening || isPlaying) && (
              <CircularProgress isIndeterminate size="40px" mt={2} color="blue.500" />
            )}
          </Box>

          {/* Timer Display */}
          {timeRemaining !== null && (
            <Box 
              p={4} 
              bg={timeRemaining <= 20 ? "red.50" : "blue.50"} 
              borderRadius="lg"
              border="2px"
              borderColor={timeRemaining <= 20 ? "red.500" : "blue.500"}
              shadow="sm"
            >
              <Text fontSize="3xl" fontWeight="bold" color={timeRemaining <= 20 ? "red.500" : "blue.500"}>
                {formatTime(timeRemaining)}
              </Text>
              {timeRemaining <= 20 && (
                <Text color="red.500" fontSize="lg" mt={2}>
                  Almost done! Get ready for the next step
                </Text>
              )}
            </Box>
          )}

          {/* Voice Command Guide */}
          <Box p={4} bg="gray.50" borderRadius="lg" border="1px" borderColor="gray.200" shadow="sm" flex="1" overflowY="auto">
            <Text fontWeight="bold" mb={4} color="blue.600">Available Commands:</Text>
            <VStack align="stretch" spacing={3}>
              {currentState === "initial_summary" && (
                <>
                  <Text fontSize="sm" fontWeight="medium">Change serving size:</Text>
                  <Text fontSize="sm">• "I want to make it for X people"</Text>
                  <Text fontSize="sm">• "No" to keep current serving size</Text>
                </>
              )}
              
              {currentState === "asking_servings" && (
                <>
                  <Text fontSize="sm" fontWeight="medium">Specify servings:</Text>
                  <Text fontSize="sm">• "4 servings"</Text>
                  <Text fontSize="sm">• "Make it for X people"</Text>
                </>
              )}
              
              {currentState === "asking_substitution" && (
                <>
                  <Text fontSize="sm" fontWeight="medium">Ingredient substitutions:</Text>
                  <Text fontSize="sm">• Name the ingredient to substitute</Text>
                  <Text fontSize="sm">• Choose option by number (1-3)</Text>
                  <Text fontSize="sm">• "No more substitutions"</Text>
                </>
              )}
              
              {currentState === "ready_to_cook" && (
                <>
                  <Text fontSize="sm" fontWeight="medium">Ready to begin?</Text>
                  <Text fontSize="sm">• "Ready" to start cooking</Text>
                  <Text fontSize="sm">• "Wait" if you need more time</Text>
                </>
              )}
              
              {currentState === "cooking" && (
                <>
                  <Text fontSize="sm" fontWeight="medium">Cooking commands:</Text>
                  <Text fontSize="sm">• "Start" - Begin first step</Text>
                  <Text fontSize="sm">• "Next" - Go to next step</Text>
                  <Text fontSize="sm">• "Repeat" - Hear current step</Text>
                  <Text fontSize="sm">• "Start timer" - Start step timer</Text>
                  <Text fontSize="sm">• "Stop timer" - Cancel timer</Text>
                  <Text fontSize="sm">• "Finish" - Complete recipe</Text>
                  <Divider my={2} />
                  <Text fontSize="sm" fontWeight="medium">Ask questions anytime:</Text>
                  <Text fontSize="sm">• "What temperature?"</Text>
                  <Text fontSize="sm">• "How do I know it's done?"</Text>
                  <Text fontSize="sm">• "Can I substitute X?"</Text>
                </>
              )}
            </VStack>
          </Box>
        </VStack>
      </Box>
    </HStack>
  )
}

export default VoiceInteraction 