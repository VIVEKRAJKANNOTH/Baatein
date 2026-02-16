import { motion } from 'framer-motion';
import { useStore } from '../store/useStore';

export const VoiceOrb = () => {
    const { status, audioLevel } = useStore();

    // Map audio level 0-0.1 to scale 1-1.5
    const scale = 1 + Math.min(audioLevel * 5, 0.5);

    const variants = {
        idle: {
            scale: [1, 1.05, 1],
            transition: { duration: 4, repeat: Infinity, ease: "easeInOut" }
        },
        listening: {
            scale: scale,
            boxShadow: `0 0 ${20 + audioLevel * 200}px rgba(244, 162, 97, 0.6)`,
            transition: { type: "spring", stiffness: 300, damping: 20 }
        },
        thinking: {
            rotate: 360,
            scale: [1, 1.1, 1],
            transition: {
                rotate: { duration: 3, repeat: Infinity, ease: "linear" },
                scale: { duration: 1.5, repeat: Infinity }
            }
        },
        speaking: {
            scale: [1, 1.05, 1],
            boxShadow: [
                "0 0 20px rgba(42, 157, 143, 0.6)",
                "0 0 60px rgba(42, 157, 143, 0.8)",
                "0 0 20px rgba(42, 157, 143, 0.6)"
            ],
            transition: { duration: 2, repeat: Infinity }
        }
    } as any;

    return (
        <div className="relative flex items-center justify-center">
            <motion.div
                className="absolute w-48 h-48 rounded-full bg-gradient-to-br from-indigo-500/20 to-teal-500/20 blur-3xl"
                animate={{
                    scale: status === 'speaking' ? [1, 1.2, 1] : 1,
                    opacity: status === 'idle' ? 0.3 : 0.6
                }}
                transition={{ duration: 4, repeat: Infinity }}
            />

            <motion.div
                className="w-32 h-32 md:w-48 md:h-48 rounded-full bg-gradient-to-br from-indigo-600 via-teal-600 to-saffron-400 shadow-2xl relative z-10"
                variants={variants}
                animate={status}
            >
                <div className="absolute inset-0 rounded-full bg-gradient-to-t from-black/20 to-transparent pointer-events-none" />

                {status === 'thinking' && (
                    <motion.div
                        className="absolute inset-[-4px] rounded-full border-2 border-t-saffron-400 border-r-transparent border-b-teal-400 border-l-transparent"
                        animate={{ rotate: 360 }}
                        transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                    />
                )}
            </motion.div>
        </div>
    );
};
