import { useStore } from '../store/useStore';

export const StatusText = () => {
    const { status } = useStore();

    const getStatusText = () => {
        switch (status) {
            case 'idle':
                return 'Tap microphone to speak';
            case 'listening':
                return 'Listening...';
            case 'thinking':
                return 'Thinking...';
            case 'speaking':
                return 'Speaking...';
            default:
                return '';
        }
    };

    return (
        <div className="text-center space-y-2 min-h-[80px]">
            <p className="text-xl md:text-2xl font-light text-white/90 animate-pulse tracking-wide transition-all duration-300">
                {getStatusText()}
            </p>
        </div>
    );
};
