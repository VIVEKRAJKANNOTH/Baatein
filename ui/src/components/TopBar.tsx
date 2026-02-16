import { Settings, Globe } from 'lucide-react';

export const TopBar = () => {
    return (
        <div className="fixed top-0 left-0 right-0 p-6 flex justify-between items-center z-50">
            <div className="flex items-center gap-2">
                <h1 className="text-2xl font-medium tracking-tight">Baatein</h1>
                <span className="px-2 py-0.5 rounded-full bg-teal-500/20 text-teal-300 text-xs font-medium border border-teal-500/30">
                    AI
                </span>
            </div>

            <div className="flex gap-4">
                <button className="p-2 rounded-full hover:bg-white/10 transition-colors">
                    <Globe className="w-5 h-5 opacity-80" />
                </button>
                <button className="p-2 rounded-full hover:bg-white/10 transition-colors">
                    <Settings className="w-5 h-5 opacity-80" />
                </button>
            </div>
        </div>
    );
};
