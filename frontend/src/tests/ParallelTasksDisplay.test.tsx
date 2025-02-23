import React from 'react'
import { render, screen } from '@testing-library/react'
import { ChakraProvider } from '@chakra-ui/react'
import VoiceInteraction from '../components/VoiceInteraction'
import '@testing-library/jest-dom'

// Mock props required by VoiceInteraction
const mockProps = {
    recipeId: "test-recipe-id",
    onRecipeUpdate: jest.fn()
}

const mockTimer = {
    duration: 480,
    type: 'cooking',
    step: 3,
    warning_time: 20,
    parallel_tasks: [
        {
            step_number: 2,
            instruction: "Chop garlic and parsley",
            estimated_time: 120
        },
        {
            step_number: 4,
            instruction: "Heat olive oil in a pan",
            estimated_time: 60
        }
    ]
}

const mockTimerWithoutTasks = {
    duration: 300,
    type: 'cooking',
    step: 1,
    warning_time: 20,
    parallel_tasks: []
}

// Mock the messages state to include a timer
const mockMessages = [
    {
        id: '1',
        type: 'assistant',
        content: 'Timer started',
        timestamp: new Date(),
        timer: mockTimer
    }
]

describe('VoiceInteraction - Parallel Tasks', () => {
    beforeEach(() => {
        // Mock useState to return our mock messages
        jest.spyOn(React, 'useState').mockImplementation(() => [mockMessages, jest.fn()])
    })

    it('renders parallel tasks when available', () => {
        render(
            <ChakraProvider>
                <VoiceInteraction {...mockProps} />
            </ChakraProvider>
        )

        // Check if component renders
        expect(screen.getByText('Available Tasks')).toBeInTheDocument()

        // Check if tasks are displayed
        expect(screen.getByText('Step 2')).toBeInTheDocument()
        expect(screen.getByText('Chop garlic and parsley')).toBeInTheDocument()
        expect(screen.getByText('2m 0s')).toBeInTheDocument()

        expect(screen.getByText('Step 4')).toBeInTheDocument()
        expect(screen.getByText('Heat olive oil in a pan')).toBeInTheDocument()
        expect(screen.getByText('1m 0s')).toBeInTheDocument()

        // Check if instructions are displayed
        expect(screen.getByText(/Say the step number to start a task/)).toBeInTheDocument()
    })

    it('does not render parallel tasks when none are available', () => {
        // Mock messages with a timer that has no parallel tasks
        jest.spyOn(React, 'useState').mockImplementation(() => [[{
            id: '1',
            type: 'assistant',
            content: 'Timer started',
            timestamp: new Date(),
            timer: mockTimerWithoutTasks
        }], jest.fn()])

        render(
            <ChakraProvider>
                <VoiceInteraction {...mockProps} />
            </ChakraProvider>
        )

        // Component should not render parallel tasks section
        expect(screen.queryByText('Available Tasks')).not.toBeInTheDocument()
    })

    it('formats time display correctly', () => {
        render(
            <ChakraProvider>
                <VoiceInteraction {...mockProps} />
            </ChakraProvider>
        )

        // Check time formatting
        const twoMinutes = screen.getByText('2m 0s')
        const oneMinute = screen.getByText('1m 0s')

        expect(twoMinutes).toBeInTheDocument()
        expect(oneMinute).toBeInTheDocument()
    })
}) 