import { Mic, MicOff } from 'lucide-react';
import { useStore } from '../store/useStore';

interface MicButtonProps {
    onClick: () => void;
}

export const MicButton = ({ onClick }: MicButtonProps) => {
    const { status } = useStore();
    const isActive = status === 'listening' || status === 'speaking';

    return (
        <button
            onClick={onClick}
            className={`
        relative flex items-center justify-center
        w-16 h-16 md:w-20 md:h-20 rounded-full
        transition-all duration-300 transform
        ${isActive
                    ? 'bg-saffron-400 text-indigo-950 scale-110 shadow-[0_0_30px_rgba(244,162,97,0.5)]'
                    : 'bg-white/10 text-white hover:bg-white/20 hover:scale-105'
                }
      `}
        >
            {isActive && (
                <div className="absolute inset-0 rounded-full border-2 border-saffron-400 animate-ping opacity-20" />
            )}
            {isActive ? <Mic className="w-8 h-8 md:w-10 md:h-10" /> : <MicOff className="w-6 h-6 md:w-8 md:h-8" />}
        </button>
    );
};
