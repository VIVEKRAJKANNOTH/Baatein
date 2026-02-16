import { useState } from 'react';
import { useVoiceAgent } from './hooks/useVoiceAgent';
import { VoiceOrb } from './components/VoiceOrb';
import { StatusText } from './components/StatusText';
import { MicButton } from './components/MicButton';
import { TopBar } from './components/TopBar';
import { useStore } from './store/useStore';

function App() {
  const { connect, disconnect } = useVoiceAgent();
  const { isConnected } = useStore();
  const [hasStarted, setHasStarted] = useState(false);

  const handleMicClick = () => {
    if (!hasStarted) {
      setHasStarted(true);
      connect();
    } else {
      if (isConnected) {
        disconnect();
        setHasStarted(false);
      } else {
        connect();
      }
    }
  };

  return (
    <div className="min-h-screen bg-indigo-950 text-white overflow-hidden relative selection:bg-teal-500/30">

      {/* Background Ambience */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(42,157,143,0.1),transparent_50%)] animate-pulse duration-[10000ms]" />

      <TopBar />

      <main className="flex flex-col items-center justify-center min-h-screen relative z-10 p-6 gap-12 md:gap-20">

        {/* Main Orb Area */}
        <div className="flex-1 flex flex-col items-center justify-center w-full max-w-2xl mt-12 md:mt-0">
          <VoiceOrb />

          <div className="mt-12 md:mt-16 w-full px-4">
            <StatusText />
          </div>
        </div>

        {/* Controls */}
        <div className="pb-12 flex flex-col items-center gap-6">
          <MicButton onClick={handleMicClick} />

          <div className="text-xs text-white/40 font-medium tracking-widest uppercase">
            {isConnected ? 'Baatein AI Active' : 'Offline'}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
