import { useRef, useEffect, useCallback } from 'react';
import { useStore } from '../store/useStore';

// VAD Constants
const VAD_SPEECH_THRESHOLD = 0.03;
const VAD_SILENCE_DURATION = 2000; // ms
const VAD_SPEECH_CONFIRM_MS = 300;
const VAD_BARGE_CONFIRM_MS = 500;

// Feature detect: MSE with audio/mpeg support (fails on iOS Safari)
const CAN_USE_MSE = typeof MediaSource !== 'undefined' &&
    MediaSource.isTypeSupported?.('audio/mpeg');

export const useVoiceAgent = () => {
    const {
        setStatus, setTranscript, setAiResponse, setAudioLevel,
        setConnected, resetChat
    } = useStore();

    const ws = useRef<WebSocket | null>(null);
    const audioContext = useRef<AudioContext | null>(null);
    const processor = useRef<ScriptProcessorNode | null>(null);
    const mediaStream = useRef<MediaStream | null>(null);
    const sourceNode = useRef<MediaStreamAudioSourceNode | null>(null);

    // VAD State Refs
    const vadState = useRef({
        isSpeaking: false,
        speechStart: 0,
        speechConfirmed: false,
        silenceStart: 0,
        silenceSent: false,
        aiIsPlaying: false,
    });

    // MSE State (desktop path)
    const mseState = useRef({
        mediaSource: null as MediaSource | null,
        sourceBuffer: null as SourceBuffer | null,
        queue: [] as ArrayBuffer[],
        isAppending: false,
        ttsDone: false,
    });

    // Fallback State (iOS path) - accumulate chunks, play as blob
    const fallbackState = useRef({
        chunks: [] as ArrayBuffer[],
        audioEl: null as HTMLAudioElement | null,
        ttsDone: false,
    });

    const audioPlayer = useRef<HTMLAudioElement | null>(null);

    // Initialize Audio Player
    useEffect(() => {
        audioPlayer.current = new Audio();
        return () => {
            audioPlayer.current = null;
        };
    }, []);

    // ─── Fallback (iOS): play accumulated chunks as a blob ───
    const fallbackPlayChunks = useCallback(() => {
        const state = fallbackState.current;
        if (state.chunks.length === 0) return;

        const blob = new Blob(state.chunks, { type: 'audio/mpeg' });
        const url = URL.createObjectURL(blob);
        state.chunks = [];

        const audio = new Audio();
        audio.src = url;
        state.audioEl = audio;

        audio.onended = () => {
            URL.revokeObjectURL(url);
            state.audioEl = null;
            if (state.ttsDone) {
                vadState.current.aiIsPlaying = false;
                setStatus('listening');
                setTranscript('');
            }
        };

        audio.play().catch(e => console.warn('iOS playback error:', e));
    }, [setStatus, setTranscript]);

    const stopAudioPlayback = useCallback(() => {
        vadState.current.aiIsPlaying = false;

        if (audioPlayer.current) {
            audioPlayer.current.pause();
            audioPlayer.current.src = '';
        }

        // Stop fallback audio
        if (fallbackState.current.audioEl) {
            fallbackState.current.audioEl.pause();
            fallbackState.current.audioEl.src = '';
            fallbackState.current.audioEl = null;
        }
        fallbackState.current.chunks = [];
        fallbackState.current.ttsDone = false;

        // Close MSE
        try {
            if (mseState.current.mediaSource?.readyState === 'open') {
                mseState.current.mediaSource.endOfStream();
            }
        } catch (e) { /* ignore */ }

        mseState.current = {
            mediaSource: null,
            sourceBuffer: null,
            queue: [],
            isAppending: false,
            ttsDone: false,
        };

        setStatus('listening');
    }, [setStatus]);

    const bargeIn = useCallback(() => {
        if (!vadState.current.aiIsPlaying) return;

        console.log("🛑 Barge-in triggered!");
        stopAudioPlayback();

        if (ws.current?.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify({ type: 'barge_in' }));
        }

        setAiResponse('');
        setStatus('listening');

        vadState.current.isSpeaking = true;
        vadState.current.speechConfirmed = true;
        vadState.current.speechStart = performance.now();
        vadState.current.silenceStart = 0;
        vadState.current.silenceSent = false;
    }, [stopAudioPlayback, setAiResponse, setStatus]);

    // ─── MSE Logic (desktop path, unchanged) ───
    const initMediaSource = useCallback(() => {
        mseState.current.queue = [];
        mseState.current.isAppending = false;
        mseState.current.ttsDone = false;

        const ms = new MediaSource();
        mseState.current.mediaSource = ms;

        if (audioPlayer.current) {
            audioPlayer.current.src = URL.createObjectURL(ms);
        }

        ms.addEventListener('sourceopen', () => {
            try {
                const sb = ms.addSourceBuffer('audio/mpeg');
                mseState.current.sourceBuffer = sb;

                sb.addEventListener('updateend', () => {
                    mseState.current.isAppending = false;
                    appendNextChunk();
                });
            } catch (e) {
                console.error('MSE SourceBuffer error:', e);
            }
        });
    }, []);

    const appendNextChunk = useCallback(() => {
        const state = mseState.current;
        if (!state.sourceBuffer || state.isAppending || state.queue.length === 0) {
            if (state.queue.length === 0 && state.ttsDone) {
                tryEndStream();
            }
            return;
        }

        state.isAppending = true;
        const chunk = state.queue.shift();

        try {
            if (chunk) {
                state.sourceBuffer.appendBuffer(chunk);
                if (audioPlayer.current?.paused) {
                    audioPlayer.current.play().catch(() => { });
                }
            }
        } catch (e) {
            console.warn('MSE append error:', e);
            state.isAppending = false;
        }
    }, []);

    const tryEndStream = useCallback(() => {
        const state = mseState.current;
        if (state.ttsDone && state.queue.length === 0 && !state.isAppending &&
            state.mediaSource?.readyState === 'open') {
            try {
                state.mediaSource.endOfStream();
            } catch (e) { /* ignore */ }

            if (audioPlayer.current) {
                audioPlayer.current.onended = () => {
                    vadState.current.aiIsPlaying = false;
                    setStatus('listening');
                    setTranscript('');
                };
            }
        }
    }, [setStatus, setTranscript]);

    // ─── Connect ───
    const connect = useCallback(() => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        ws.current = new WebSocket(wsUrl);

        ws.current.onopen = async () => {
            setConnected(true);
            setStatus('listening');

            // Start Mic
            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
                });
                mediaStream.current = stream;

                audioContext.current = new AudioContext({ sampleRate: 16000 });
                const source = audioContext.current.createMediaStreamSource(stream);
                sourceNode.current = source;
                processor.current = audioContext.current.createScriptProcessor(4096, 1, 1);

                processor.current.onaudioprocess = (e) => {
                    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) return;

                    const input = e.inputBuffer.getChannelData(0);

                    // 1. Calculate RMS for Visuals + VAD
                    let sumSq = 0;
                    for (let i = 0; i < input.length; i++) sumSq += input[i] * input[i];
                    const rms = Math.sqrt(sumSq / input.length);
                    setAudioLevel(rms);

                    // 2. VAD Logic
                    const now = performance.now();
                    const s = vadState.current;

                    if (rms > VAD_SPEECH_THRESHOLD) {
                        if (!s.speechStart) s.speechStart = now;

                        if (now - s.speechStart > VAD_SPEECH_CONFIRM_MS) {
                            s.speechConfirmed = true;
                            s.isSpeaking = true;
                            s.silenceStart = 0;
                            s.silenceSent = false;

                            if (s.aiIsPlaying && (now - s.speechStart > VAD_BARGE_CONFIRM_MS)) {
                                bargeIn();
                            }
                        }
                    } else {
                        s.speechStart = 0;
                        if (s.speechConfirmed) {
                            s.speechConfirmed = false;
                            s.isSpeaking = false;
                            s.silenceStart = now;
                        }

                        if (s.silenceStart && !s.silenceSent && !s.aiIsPlaying) {
                            if (now - s.silenceStart > VAD_SILENCE_DURATION) {
                                console.log("🎯 VAD Silence detected -> Sending trigger");
                                ws.current?.send(JSON.stringify({ type: 'user_stopped_speaking' }));
                                s.silenceSent = true;
                                setStatus('thinking');
                            }
                        }
                    }

                    // 3. Send Audio (Float32 -> Int16 -> Base64)
                    const pcmData = new Int16Array(input.length);
                    for (let i = 0; i < input.length; i++) {
                        const s = Math.max(-1, Math.min(1, input[i]));
                        pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                    }

                    let binary = '';
                    const bytes = new Uint8Array(pcmData.buffer);
                    const len = bytes.byteLength;
                    for (let i = 0; i < len; i++) binary += String.fromCharCode(bytes[i]);
                    const base64 = btoa(binary);

                    ws.current.send(JSON.stringify({ type: 'audio_chunk', data: base64 }));
                };

                source.connect(processor.current);
                processor.current.connect(audioContext.current.destination);

            } catch (err) {
                console.error('Mic Error:', err);
            }
        };

        ws.current.onmessage = (event) => {
            const msg = JSON.parse(event.data);

            switch (msg.type) {
                case 'transcript':
                    setTranscript(msg.text);
                    break;

                case 'final_transcript':
                    setTranscript('✅ ' + msg.text);
                    setStatus('thinking');
                    break;

                case 'llm_chunk':
                    useStore.getState().appendAiResponse(msg.text);
                    setStatus('thinking');
                    break;

                case 'tts_start':
                    vadState.current.aiIsPlaying = true;
                    if (CAN_USE_MSE) {
                        initMediaSource();
                    } else {
                        fallbackState.current.chunks = [];
                        fallbackState.current.ttsDone = false;
                    }
                    setStatus('speaking');
                    break;

                case 'audio_chunk': {
                    const bin = atob(msg.audio);
                    const bytes = new Uint8Array(bin.length);
                    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);

                    if (CAN_USE_MSE) {
                        mseState.current.queue.push(bytes.buffer);
                        appendNextChunk();
                    } else {
                        fallbackState.current.chunks.push(bytes.buffer);
                    }

                    if (msg.chunk_num === 1) setStatus('speaking');
                    break;
                }

                case 'search_start':
                    setStatus('thinking');
                    break;

                case 'search_audio_done':
                    if (CAN_USE_MSE) {
                        mseState.current.ttsDone = true;
                        tryEndStream();
                        setTimeout(() => {
                            if (vadState.current.aiIsPlaying) initMediaSource();
                        }, 500);
                    } else {
                        // Play accumulated search audio, then reset for next segment
                        fallbackPlayChunks();
                    }
                    break;

                case 'tts_done':
                    if (CAN_USE_MSE) {
                        mseState.current.ttsDone = true;
                        tryEndStream();
                    } else {
                        fallbackState.current.ttsDone = true;
                        fallbackPlayChunks();
                    }
                    break;

                case 'ping':
                    break;

                case 'stop_audio':
                    stopAudioPlayback();
                    resetChat();
                    setStatus('listening');
                    break;
            }
        };

        ws.current.onclose = () => {
            setConnected(false);
            setStatus('idle');
        };
    }, [bargeIn, appendNextChunk, tryEndStream, fallbackPlayChunks, setStatus, setTranscript, setAiResponse, setAudioLevel, setConnected, resetChat]);

    const disconnect = useCallback(() => {
        if (processor.current) {
            processor.current.disconnect();
            processor.current = null;
        }
        if (sourceNode.current) {
            sourceNode.current.disconnect();
            sourceNode.current = null;
        }
        if (audioContext.current) {
            audioContext.current.close();
            audioContext.current = null;
        }
        if (mediaStream.current) {
            mediaStream.current.getTracks().forEach(t => t.stop());
            mediaStream.current = null;
        }
        if (ws.current) {
            ws.current.close();
            ws.current = null;
        }

        setConnected(false);
        setStatus('idle');
    }, [setConnected, setStatus]);

    return { connect, disconnect };
};
