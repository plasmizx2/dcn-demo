import { AdminLayout } from '../components/admin-layout';
import { useRequireAuth } from '../hooks/use-require-auth';
import { useState, useEffect, useRef, FormEvent } from 'react';
import { Bot, User, CornerDownLeft, Loader2, Play, AlertCircle, StopCircle } from 'lucide-react';
import { toast } from 'sonner';
import { motion } from 'motion/react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { cn } from '../components/ui/utils';
import { useSearchParams } from 'react-router-dom';

type ChatMessage = {
  id: number;
  job_id: string;
  seq: number;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
};

// Simple hook to poll
function useInterval(callback: () => void, delay: number | null) {
  const savedCallback = useRef<() => void>();

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  useEffect(() => {
    function tick() {
      if (savedCallback.current) {
        savedCallback.current();
      }
    }
    if (delay !== null) {
      const id = setInterval(tick, delay);
      return () => clearInterval(id);
    }
  }, [delay]);
}


export function ChatPage() {
  const { ready } = useRequireAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [jobId, setJobId] = useState<string | null>(searchParams.get('job_id'));
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isTerminating, setIsTerminating] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(scrollToBottom, [messages]);

  // Fetch initial messages if Job ID is present
  useEffect(() => {
    if (jobId) {
      (async () => {
        try {
        const res = await fetch(`/chat/${jobId}/messages`, { credentials: 'include' });
         if (!res.ok) return;
         const data: ChatMessage[] = await res.json();
         setMessages(data.sort((a,b) => a.seq - b.seq));
        } catch {}
      })();
    }
  }, [jobId]);
  
  // Poll for messages
  useInterval(async () => {
    if (!jobId) return;
    try {
      const res = await fetch(`/chat/${jobId}/messages`, { credentials: 'include' });
      if (!res.ok) {
        if (res.status >= 500) {
           setError('Server error fetching messages.');
        }
        return;
      }
      const data: ChatMessage[] = await res.json();
      
      setMessages(currentMessages => {
        const messageMap = new Map(currentMessages.map(m => [m.id, m]));
        data.forEach(m => messageMap.set(m.id, m));
        return Array.from(messageMap.values()).sort((a, b) => a.seq - b.seq);
      });

      if (error) setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Network error');
    }
  }, jobId ? 1500 : null);

  const startChat = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          title: 'Local LLM Chat Session',
          description: `Started at ${new Date().toISOString()}`,
          task_type: 'local_llm_chat',
          input_payload: {},
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to start chat session');
      }
      const data = await res.json();
      const newJobId = data.job_id || data.id;
      setJobId(newJobId);
      setSearchParams({ job_id: newJobId });
      setMessages([]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to start chat';
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };
  
  const terminateChat = async () => {
    if (!jobId) return;
    setIsTerminating(true);
    try {
      await fetch(`/jobs/${jobId}/terminate`, { method: 'POST', credentials: 'include' });
      toast.success('Chat session terminated');
      setJobId(null);
      setMessages([]);
      setSearchParams({});
    } catch (e) {
      toast.error('Failed to terminate session');
    } finally {
      setIsTerminating(false);
    }
  };

  const handleSend = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !jobId || isSending) return;

    setIsSending(true);
    try {
      const res = await fetch(`/chat/${jobId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ content: input.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to send message');
      }
      // The message will appear after the next poll, so just clear the input
      setInput('');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to send message');
    } finally {
      setIsSending(false);
    }
  };

  if (!ready) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center min-h-[50vh]">
          <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className="container mx-auto px-6 py-12 max-w-4xl">
        <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }}>
          <div className="mb-8">
            <h1 className="text-4xl font-bold text-white">Local LLM Chat</h1>
            <p className="text-slate-400 text-lg">
              Chat with a private model running on the DCN worker network.
            </p>
          </div>

          {!jobId ? (
            <Card className="bg-slate-900/50 backdrop-blur-xl border-white/10">
              <CardContent className="p-8 text-center">
                <p className="text-slate-300 mb-6">Start a new secure chat session to begin.</p>
                <Button onClick={startChat} disabled={loading} size="lg">
                  {loading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="mr-2 h-4 w-4" />
                  )}
                  Start Chat Session
                </Button>
                {error && <p className="mt-4 text-sm text-red-400">{error}</p>}
              </CardContent>
            </Card>
          ) : (
            <Card className="bg-slate-900/50 backdrop-blur-xl border-white/10">
              <CardHeader className="flex flex-row items-center justify-between border-b border-white/10">
                <CardTitle className="text-white text-base font-mono">job:{jobId}</CardTitle>
                <Button onClick={terminateChat} disabled={isTerminating} variant="destructive" size="sm">
                  {isTerminating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <StopCircle className="mr-2 h-4 w-4" />}
                  End Session
                </Button>
              </CardHeader>
              <CardContent className="p-0">
                <div className="h-[60vh] overflow-y-auto p-6 space-y-6">
                  {messages.map((msg) => (
                    <motion.div
                      key={`${msg.id}-${msg.content.length}`}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={cn(
                        'flex items-start gap-4',
                        msg.role === 'user' ? 'justify-end' : 'justify-start'
                      )}
                    >
                      {msg.role === 'assistant' && (
                        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center">
