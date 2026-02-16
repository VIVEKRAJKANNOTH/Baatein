import { create } from 'zustand';

interface Message {
    role: 'user' | 'assistant' | 'status';
    text: string;
}

interface VoiceState {
    status: 'idle' | 'listening' | 'thinking' | 'speaking';
    transcript: string;
    aiResponse: string;
    audioLevel: number;
    messages: Message[];
    isConnected: boolean;

    setStatus: (status: VoiceState['status']) => void;
    setTranscript: (text: string) => void;
    setAiResponse: (text: string) => void;
    setAudioLevel: (level: number) => void;
    addMessage: (msg: Message) => void;
    appendAiResponse: (text: string) => void;
    setConnected: (connected: boolean) => void;
    resetChat: () => void;
}

export const useStore = create<VoiceState>((set) => ({
    status: 'idle',
    transcript: '',
    aiResponse: '',
    audioLevel: 0,
    messages: [],
    isConnected: false,

    setStatus: (status) => set({ status }),
    setTranscript: (transcript) => set({ transcript }),
    setAiResponse: (aiResponse) => set({ aiResponse }),
    setAudioLevel: (audioLevel) => set({ audioLevel }),
    addMessage: (msg) => set((state) => ({ messages: [...state.messages, msg] })),
    appendAiResponse: (text) => set((state) => ({ aiResponse: state.aiResponse + text })),
    setConnected: (isConnected) => set({ isConnected }),
    resetChat: () => set({ transcript: '', aiResponse: '' }),
}));
