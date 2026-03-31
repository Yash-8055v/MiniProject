import { useState, useRef, useEffect } from 'react';
import { Mic, MicOff, Loader2 } from 'lucide-react';
import { transcribeAudio } from '../services/api';

interface VoiceInputProps {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}

type RecordState = 'idle' | 'recording' | 'processing';

const VoiceInput = ({ onTranscript, disabled = false }: VoiceInputProps) => {
  const [state, setState] = useState<RecordState>('idle');
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      mediaRecorderRef.current?.stop();
    };
  }, []);

  const startRecording = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        // Stop all tracks to release mic
        stream.getTracks().forEach((t) => t.stop());

        setState('processing');
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        try {
          const transcript = await transcribeAudio(blob);
          if (transcript) {
            onTranscript(transcript);
          } else {
            setError('No speech detected. Please try again.');
          }
        } catch {
          setError('Could not understand audio. Please try again.');
        } finally {
          setState('idle');
          setSeconds(0);
        }
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setState('recording');
      setSeconds(0);

      // Timer counter
      timerRef.current = setInterval(() => {
        setSeconds((s) => {
          // Auto-stop at 30 seconds
          if (s >= 30) {
            stopRecording();
            return 0;
          }
          return s + 1;
        });
      }, 1000);
    } catch {
      setError('Microphone access denied. Please allow mic permissions.');
      setState('idle');
    }
  };

  const stopRecording = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    mediaRecorderRef.current?.stop();
  };

  const handleClick = () => {
    if (state === 'recording') {
      stopRecording();
    } else if (state === 'idle') {
      startRecording();
    }
  };

  return (
    <div className="flex flex-col items-center">
      <button
        onClick={handleClick}
        disabled={disabled || state === 'processing'}
        title={state === 'recording' ? 'Stop recording' : 'Record voice claim'}
        className={`relative w-10 h-10 rounded-full flex items-center justify-center transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed ${
          state === 'recording'
            ? 'bg-red-500 hover:bg-red-600 shadow-lg shadow-red-500/40'
            : 'bg-secondary hover:bg-secondary/80 border border-border'
        }`}
      >
        {state === 'processing' ? (
          <Loader2 className="w-4 h-4 text-primary animate-spin" />
        ) : state === 'recording' ? (
          <>
            <MicOff className="w-4 h-4 text-white" />
            {/* Pulse ring */}
            <span className="absolute inset-0 rounded-full animate-ping bg-red-500 opacity-30" />
          </>
        ) : (
          <Mic className="w-4 h-4 text-muted-foreground" />
        )}
      </button>

      {state === 'recording' && (
        <span className="mt-1 text-xs text-red-400 tabular-nums">
          {String(Math.floor(seconds / 60)).padStart(2, '0')}:
          {String(seconds % 60).padStart(2, '0')}
        </span>
      )}

      {error && (
        <p className="mt-1 text-xs text-red-400 text-center max-w-[160px]">{error}</p>
      )}
    </div>
  );
};

export default VoiceInput;
