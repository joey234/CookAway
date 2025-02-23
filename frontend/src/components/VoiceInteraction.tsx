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
  Badge,
  List,
  ListItem,
  ListIcon,
  Progress,
  Heading,
  Grid,
} from '@chakra-ui/react'
import axios from 'axios'
import { FaMicrophone, FaMicrophoneSlash, FaPaperPlane, FaCheckCircle, FaClock, FaListUl, FaArrowRight, FaCircle } from 'react-icons/fa'

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
    parallel_tasks?: Array<{
        step_number: number;
        instruction: string;
        estimated_time: number;
    }>;
}

interface Message {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: Date
  state?: ConversationState
    timer?: TimerData
}

interface Step {
  step: number;
  instruction: string;
  timer?: {
    duration: number;
    type: string;
  };
  parallel_with?: number[];
  estimated_time?: number;
  checkpoints?: string[];
  warnings?: string[];
  notes?: string[];
}

interface StepsDashboardProps {
  steps: Step[];
  currentStep: number;
  timeRemaining: number | null;
  completedSteps: number[];
  activeParallelSteps: number[];
}

interface ParallelTask {
  step_number: number;
  instruction: string;
  estimated_time: number;
}

interface ParallelTasksDisplayProps {
  tasks?: ParallelTask[];
}

interface TimerDisplayProps {
  duration: number;
  step: number;
  warningTime: number;
}

const TimerDisplay: React.FC<TimerDisplayProps> = ({ duration, step, warningTime }) => {
  const minutes = Math.floor(duration / 60);
  const seconds = duration % 60;
  const isWarning = duration <= warningTime;

  // Calculate progress percentage based on the original duration
  const originalDuration = step === 1 ? 300 : step === 3 ? 480 : step === 7 ? 60 : duration;
  const progress = ((originalDuration - duration) / originalDuration) * 100;

  return (
    <Box
      p={3}
      bg={isWarning ? "red.50" : "blue.50"}
      borderRadius="md"
      border="1px solid"
      borderColor={isWarning ? "red.200" : "blue.200"}
    >
      <VStack spacing={2} align="stretch">
        <Text fontSize="lg" fontWeight="bold" color={isWarning ? "red.600" : "blue.600"}>
          {minutes}:{seconds.toString().padStart(2, '0')}
        </Text>
        <Progress
          value={progress}
          size="sm"
          colorScheme={isWarning ? "red" : "blue"}
          borderRadius="full"
          hasStripe
          isAnimated
        />
        {isWarning && (
          <Text fontSize="sm" color="red.600">
            Almost done! Get ready for the next step
          </Text>
        )}
      </VStack>
    </Box>
  );
};

const ParallelTasksDisplay: React.FC<ParallelTasksDisplayProps> = ({ tasks }) => {
  if (!tasks || tasks.length === 0) return null;

  // Get the first task as the recommended one
  const recommendedTask = tasks[0];
  const estTime = recommendedTask.estimated_time;
  const estMinutes = Math.floor(estTime / 60);
  const estSeconds = estTime % 60;
  const estTimeStr = estMinutes > 0 ? `${estMinutes}m ${estSeconds}s` : `${estSeconds}s`;

  return (
    <Box mt={4} p={4} borderRadius="md" bg="blue.50" border="2px solid" borderColor="blue.200">
      <Heading size="md" color="blue.700" mb={4}>
        Available Tasks While Timer is Running
      </Heading>
      <Box p={4} bg="white" borderRadius="md" boxShadow="sm" border="1px solid" borderColor="blue.100">
        <VStack spacing={3} align="stretch">
          <Box>
            <Text fontSize="sm" fontWeight="bold" color="blue.600" mb={1}>
              Recommended Task:
            </Text>
            <Box bg="blue.50" p={3} borderRadius="md">
              <Text fontSize="lg" fontWeight="medium" color="blue.800">
                Step {recommendedTask.step_number}: {recommendedTask.instruction}
              </Text>
              <Text fontSize="sm" color="gray.600" mt={1}>
                Estimated time: {estTimeStr}
              </Text>
              <Text fontSize="sm" color="blue.600" mt={2} fontWeight="medium">
                Say "start step {recommendedTask.step_number}" to begin this task
              </Text>
            </Box>
          </Box>
          
          {tasks.length > 1 && (
            <Box>
              <Text fontSize="sm" fontWeight="bold" color="blue.600" mb={2}>
                Other Available Tasks:
              </Text>
              <VStack spacing={2} align="stretch">
                {tasks.slice(1).map(task => {
                  const taskTime = task.estimated_time;
                  const taskMinutes = Math.floor(taskTime / 60);
                  const taskSeconds = taskTime % 60;
                  const taskTimeStr = taskMinutes > 0 ? `${taskMinutes}m ${taskSeconds}s` : `${taskSeconds}s`;
                  
                  return (
                    <Box 
                      key={task.step_number} 
                      p={3} 
                      bg="gray.50" 
                      borderRadius="md" 
                      border="1px solid"
                      borderColor="gray.200"
                    >
                      <Text fontSize="md" color="gray.700">
                        Step {task.step_number}: {task.instruction}
                      </Text>
                      <Text fontSize="sm" color="gray.500" mt={1}>
                        Estimated time: {taskTimeStr}
                      </Text>
                    </Box>
                  );
                })}
              </VStack>
            </Box>
          )}
        </VStack>
      </Box>
      
      <Text fontSize="sm" color="blue.600" mt={4} textAlign="center" fontWeight="medium">
        Say "done with step X" when you've completed any task
      </Text>
    </Box>
  );
};

const StepsDashboard: React.FC<StepsDashboardProps> = ({
  steps,
  currentStep,
  timeRemaining,
  completedSteps,
  activeParallelSteps
}) => {
  return (
    <Box
      bg="white"
      borderTop="1px solid"
      borderColor="gray.200"
      boxShadow="0 -4px 6px -1px rgba(0, 0, 0, 0.1)"
      p={4}
      minHeight="300px"
      maxHeight="40vh"
      overflowY="auto"
    >
      <Box maxW="1400px" mx="auto" w="100%">
        <Text fontSize="lg" fontWeight="bold" mb={4}>
          Recipe Progress
        </Text>
        <VStack spacing={4} align="stretch">
          {steps.map((step) => {
            const isCurrentStep = step.step === currentStep;
            const hasTimer = step.timer && timeRemaining !== null && isCurrentStep;
            const timerProgress = hasTimer
              ? ((step.timer!.duration - timeRemaining!) / step.timer!.duration) * 100
              : 0;
            const isWarning = hasTimer && timeRemaining! <= 20;

            return (
              <Box
                key={step.step}
                p={4}
                borderRadius="md"
                bg={
                  completedSteps.includes(step.step)
                    ? "green.100"
                    : isCurrentStep
                    ? "blue.100"
                    : "white"
                }
                border="1px solid"
                borderColor={
                  completedSteps.includes(step.step)
                    ? "green.200"
                    : isCurrentStep
                    ? "blue.200"
                    : "gray.200"
                }
                boxShadow="sm"
                position="relative"
                opacity={completedSteps.includes(step.step) ? 0.7 : 1}
              >
                {/* Status indicator */}
                <Box
                  position="absolute"
                  left={-2}
                  top="50%"
                  transform="translateY(-50%)"
                  w={1}
                  h="80%"
                  bg={
                    completedSteps.includes(step.step)
                      ? "green.500"
                      : isCurrentStep
                      ? "blue.500"
                      : "gray.200"
                  }
                  borderRadius="full"
                />

                <HStack spacing={4} align="flex-start">
                  {/* Step number */}
                  <Box
                    minW="40px"
                    h="40px"
                    borderRadius="full"
                    bg={
                      completedSteps.includes(step.step)
                        ? "green.500"
                        : isCurrentStep
                        ? "blue.500"
                        : "gray.200"
                    }
                    color="white"
                    display="flex"
                    alignItems="center"
                    justifyContent="center"
                    fontSize="lg"
                    fontWeight="bold"
                  >
                    {step.step}
                  </Box>

                  <VStack spacing={2} align="stretch" flex={1}>
                    {/* Step instruction */}
                    <Text
                      fontSize="md"
                      color={completedSteps.includes(step.step) ? "gray.600" : "gray.800"}
                    >
                      {step.instruction}
                    </Text>

                    {/* Timer display */}
                    {hasTimer && (
                      <Box>
                        <HStack spacing={2} mb={1}>
                          <Icon as={FaClock} color={isWarning ? "red.500" : "blue.500"} />
                          <Text color={isWarning ? "red.600" : "blue.600"} fontWeight="bold">
                            {Math.floor(timeRemaining! / 60)}:
                            {(timeRemaining! % 60).toString().padStart(2, "0")}
                          </Text>
                        </HStack>
                        <Progress
                          value={timerProgress}
                          size="sm"
                          colorScheme={isWarning ? "red" : "blue"}
                          borderRadius="full"
                          hasStripe
                          isAnimated
                        />
                      </Box>
                    )}

                    {/* Estimated time */}
                    {step.estimated_time && !hasTimer && (
                      <Text fontSize="sm" color="gray.500">
                        Est: {Math.floor(step.estimated_time / 60)}m {step.estimated_time % 60}s
                      </Text>
                    )}
                  </VStack>

                  {/* Completion indicator */}
                  {completedSteps.includes(step.step) && (
                    <Icon as={FaCheckCircle} color="green.500" boxSize={6} />
                  )}
                </HStack>
              </Box>
            );
          })}
        </VStack>
      </Box>
    </Box>
  );
};

const voiceCommands = [
  "next - Next step",
  "repeat - Repeat step",
  "start - Start cooking",
  "start timer - Start timer",
  "stop timer - Stop timer",
  "step X - Start task",
  "done with step X - Complete",
  "help - Get help",
  "what's next - Preview next"
];

const MessageBubble: React.FC<{message: Message}> = ({message}) => {
  const isUser = message.type === 'user';
  
  // Function to format text with bullet points
  const formatText = (text: string) => {
    return text.split('\n').map((line, i) => {
      if (line.trim().startsWith('-') || line.trim().startsWith('•')) {
        return (
          <Box key={i} pl={4} my={1}>
            <Text>
              <Icon as={FaCircle} boxSize={2} mr={2} color={isUser ? "blue.500" : "gray.500"} />
              {line.trim().substring(1).trim()}
            </Text>
          </Box>
        );
      }
      return line.trim() && <Text key={i} my={1}>{line}</Text>;
    });
  };

  return (
    <Flex justify={isUser ? "flex-end" : "flex-start"} w="100%" align="start">
      {!isUser && (
        <Avatar
          size="sm"
          name="Assistant"
          src="/assistant-avatar.png"
          bg="blue.500"
          color="white"
          mr={2}
        />
      )}
      <Box
        maxW="80%"
        bg={isUser ? "blue.50" : "gray.50"}
        color={isUser ? "blue.800" : "gray.800"}
        p={4}
        rounded="lg"
        boxShadow="sm"
        borderWidth={1}
        borderColor={isUser ? "blue.200" : "gray.200"}
      >
        <VStack align="stretch" spacing={3}>
          {formatText(message.content)}
          {message.timer && (
            <Box mt={2}>
              <TimerDisplay
                duration={message.timer.duration}
                step={message.timer.step}
                warningTime={message.timer.warning_time}
              />
              {message.timer.parallel_tasks && message.timer.parallel_tasks.length > 0 && (
                <Box mt={4}>
                  <ParallelTasksDisplay tasks={message.timer.parallel_tasks} />
                </Box>
              )}
            </Box>
          )}
        </VStack>
      </Box>
      {isUser && (
        <Avatar
          size="sm"
          name="User"
          src="/user-avatar.png"
          bg="blue.500"
          color="white"
          ml={2}
        />
      )}
    </Flex>
  );
};

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
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [activeParallelSteps, setActiveParallelSteps] = useState<number[]>([]);
  const [recipeSteps, setRecipeSteps] = useState<Step[]>([]);
  const [currentStepNumber, setCurrentStepNumber] = useState<number>(0);

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
      // Only start listening if we're not in the initial state and not in a timer period
      if (currentStateRef.current !== "initial_summary" && !timeRemaining) {
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

  // Update active parallel steps when timer starts
  useEffect(() => {
    if (messages.length > 0) {
      const lastMessage = messages[messages.length - 1];
      console.log('Checking last message for parallel tasks:', {
        hasTimer: !!lastMessage?.timer,
        parallelTasks: lastMessage?.timer?.parallel_tasks
      });
      
      if (lastMessage?.timer?.parallel_tasks) {
        const parallelSteps = lastMessage.timer.parallel_tasks.map(task => task.step_number);
        console.log('Setting active parallel steps:', parallelSteps);
        setActiveParallelSteps(parallelSteps);
      } else if (!timeRemaining) {
        console.log('Clearing active parallel steps');
        setActiveParallelSteps([]);
      }
    }
  }, [messages, timeRemaining]);

  // Handle timer updates
  useEffect(() => {
    if (timeRemaining !== null) {
      console.log('Timer update:', {
        timeRemaining,
        activeParallelSteps,
        currentStep: currentStepNumber
      });
      
      if (timeRemaining <= 0) {
        console.log('Timer completed');
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
            console.log('Timer warning at 20 seconds');
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
            console.log('Timer completed');
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
      console.log('Clearing active timer');
      window.clearInterval(activeTimer);
      setActiveTimer(null);
    }
  }, [timeRemaining]);

  // Update completed steps when a step is done
  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    if (lastMessage?.content.toLowerCase().includes("completed")) {
      const stepMatch = lastMessage.content.match(/step (\d+)/i);
      if (stepMatch) {
        const completedStep = parseInt(stepMatch[1]);
        setCompletedSteps(prev => [...prev, completedStep]);
      }
    }
  }, [messages]);

  // Get recipe steps when recipe ID changes
  useEffect(() => {
    const getRecipeSteps = async () => {
      try {
        console.log('Fetching recipe steps for ID:', currentRecipeId);
        const response = await axios.get(`http://localhost:8000/api/recipes/${currentRecipeId}`);
        const steps = response.data.steps;
        
        // Process steps to ensure parallel_with arrays are properly set
        const processedSteps = steps.map((step: Step) => {
          if (step.parallel_with) {
            console.log(`Step ${step.step} has parallel_with:`, step.parallel_with);
            return step;
          }
          // Check if this step can be done in parallel with any other step
          const parallelWith = steps
            .filter((s: Step) => s.parallel_with?.includes(step.step))
            .map((s: Step) => s.step);
          
          if (parallelWith.length > 0) {
            console.log(`Step ${step.step} can be done in parallel with:`, parallelWith);
          }
          
          return {
            ...step,
            parallel_with: parallelWith.length > 0 ? parallelWith : undefined
          };
        });
        
        console.log('Processed steps:', processedSteps);
        setRecipeSteps(processedSteps);
        
        // Initialize parallel tasks with the recipe steps
        console.log('Initializing parallel tasks...');
        const initResponse = await axios.post(
          `http://localhost:8000/api/recipes/${currentRecipeId}/voice-interaction`,
          {
            recipe_id: currentRecipeId,
            transcript: "initialize parallel tasks",
            current_state: currentStateRef.current
          },
          { 
            responseType: 'blob',
            headers: {
              'Accept': 'audio/mpeg, application/json',
            }
          }
        );
        console.log('Parallel tasks initialized');
      } catch (error) {
        console.error('Error fetching recipe steps:', error);
      }
    };
    
    if (currentRecipeId) {
      getRecipeSteps();
    }
  }, [currentRecipeId]);

  // Update current step when receiving a response
  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    if (lastMessage?.type === 'assistant') {
      const stepMatch = lastMessage.content.match(/Step (\d+):/);
      if (stepMatch) {
        setCurrentStepNumber(parseInt(stepMatch[1]));
      }
    }
  }, [messages]);

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
    if (recognitionRef.current && !isListening && !isPlaying) {
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
      // Stop listening before playing audio
      if (isListening) {
        stopListening()
      }
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
      currentRecipeId,
        isTimerRunning: timeRemaining !== null
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
      const encodedResponseText = response.headers['x-full-response']
      const isResponseTextEncoded = response.headers['x-response-text-encoded'] === 'true'
      const timerDataJson = response.headers['x-timer-data']
        
        console.log('Response headers:', {
            nextState,
            updatedRecipeId,
            hasTimerData: !!timerDataJson
        })
      
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
                console.log('Received timer data:', timerData)
                
                timer = {
                    duration: parseInt(timerData.duration),
                    type: String(timerData.type),
                    step: parseInt(timerData.step),
                    warning_time: parseInt(timerData.warning_time),
                    parallel_tasks: timerData.parallel_tasks
                }
                
                // Only set timeRemaining if it's not a stop signal
                if (timer.duration > 0) {
                    console.log('Starting timer with parallel tasks:', {
                        duration: timer.duration,
                        parallelTasks: timer.parallel_tasks
                    })
                    setTimeRemaining(timer.duration)
                } else {
                    console.log('Stopping timer')
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
            console.log('State transition:', {
                from: currentStateRef.current,
                to: nextState
            })
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
    <Grid
      h="100vh"
      templateColumns="120px 1fr"
      templateRows="1fr auto auto"
    >
      {/* Voice Commands Sidebar */}
      <Box
          bg="gray.50"
        p={4}
        borderRight="1px"
        borderColor="gray.200"
        overflowY="auto"
        gridRow="1 / -1"
      >
        <VStack spacing={4} align="start">
          <Text fontSize="sm" fontWeight="bold" color="gray.600">
            Voice Commands
          </Text>
          <VStack spacing={2} align="start" w="100%">
            {voiceCommands.map((command, index) => (
              <Text
                key={index}
                fontSize="xs"
                color="gray.600"
                noOfLines={2}
              >
                {command}
                  </Text>
            ))}
          </VStack>
        </VStack>
                </Box>

      {/* Main Content Area */}
      <Box overflowY="auto" p={8} bg="white">
        <Box maxW="1400px" mx="auto">
          <VStack spacing={6} align="stretch" w="100%">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            <div ref={messagesEndRef} />
          </VStack>
        </Box>
        </Box>

      {/* Input Controls */}
      <Box
        bg="white"
        borderTop="1px"
        borderColor="gray.200"
        p={4}
        gridColumn="2"
      >
        <Box maxW="1400px" mx="auto">
          <form onSubmit={handleTextSubmit}>
            <HStack spacing={4}>
              <Input
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder="Type your message..."
                size="lg"
              />
          <Button
            colorScheme="blue"
            size="lg"
                type="submit"
          >
                Send
          </Button>
              <IconButton
                aria-label="Toggle microphone"
                icon={isListening ? <FaMicrophoneSlash /> : <FaMicrophone />}
                onClick={isListening ? stopListening : startListening}
                colorScheme={isListening ? "red" : "blue"}
                size="lg"
              />
            </HStack>
          </form>
      </Box>
          </Box>

      {/* Steps Dashboard */}
      <Box gridColumn="2">
        <StepsDashboard
          steps={recipeSteps}
          currentStep={currentStepNumber}
          timeRemaining={timeRemaining}
          completedSteps={completedSteps}
          activeParallelSteps={activeParallelSteps}
        />
      </Box>
    </Grid>
  )
}

export default VoiceInteraction 