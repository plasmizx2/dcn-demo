import { useEffect, useMemo, useRef, useState } from "react";
import { AdminLayout } from "../components/admin-layout";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useRequireAuth } from "../hooks/use-require-auth";

type ChatMsg = {
  seq: number;
  role: "system" | "user" | "assistant";
  content: string;
  created_at: string;
};

export function ChatPage() {
  const { ready } = useRequireAuth();
  const [jobId, setJobId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [afterSeq, setAfterSeq] = useState<number>(0);
  const [input, setInput] = useState("");
  const [starting, setStarting] = useState(false);
  const [sending, setSending] = useState(false);

  const bottomRef = useRef<HTMLDivElement | null>(null);
  const scrollToBottom = () => bottomRef.current?.scrollIntoView({ behavior: "smooth" });

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const lastSeq = useMemo(() => {
    if (!messages.length) return 0;
    return Math.max(...messages.map((m) => m.seq));
  }, [messages]);

  useEffect(() => {
    setAfterSeq(lastSeq);
  }, [lastSeq]);

  const startChat = async () => {
    setStarting(true);
    try {
      const res = await fetch("/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          title: "Private local LLM chat",
          description: "Streaming chat session powered by worker-local inference.",
          task_type: "local_llm_chat",
          input_payload: {
            model: "llama3.1",
            idle_timeout_seconds: 300,
            max_duration_seconds: 1800,
            system_prompt: "You are a helpful assistant. Keep answers concise.",
          },
          priority: 2,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail || "Failed to start chat");
      }
      const data = await res.json();
      const id = data.job_id || data.id;
      setJobId(id);
      setMessages([]);
      setAfterSeq(0);
      toast.success("Chat session started");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to start chat");
    } finally {
      setStarting(false);
    }
  };

  const sendMessage = async () => {
    if (!jobId) return;
    const content = input.trim();
    if (!content) return;
    setSending(true);
    try {
      const res = await fetch(`/chat/${jobId}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ content }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail || "Send failed");
      }
      setInput("");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Send failed");
    } finally {
      setSending(false);
    }
  };

  useEffect(() => {
    if (!ready || !jobId) return;
    let cancelled = false;

    const poll = async () => {
      try {
        const res = await fetch(`/chat/${jobId}/messages?after_seq=${afterSeq}`, {
          credentials: "include",
        });
        if (!res.ok) return;
        const data: ChatMsg[] = await res.json();
        if (cancelled || !data.length) return;

        // Merge by seq (assistant content may grow while streaming).
        setMessages((prev) => {
          const map = new Map<number, ChatMsg>();
          for (const m of prev) map.set(m.seq, m);
          for (const m of data) map.set(m.seq, m);
          return Array.from(map.values()).sort((a, b) => a.seq - b.seq);
        });
      } catch {
        // ignore
      }
    };

    const t = setInterval(poll, 900);
    poll();
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [ready, jobId, afterSeq]);

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
      <div className="container mx-auto px-6 py-10 max-w-4xl">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-white">Private local LLM chat</h1>
          <p className="text-slate-400 mt-2">
            Starts a long-running job. A worker runs local inference and streams tokens back into this page.
          </p>
        </div>

        {!jobId ? (
          <div className="rounded-2xl border border-white/10 bg-slate-900/50 backdrop-blur-xl p-6">
            <Button onClick={startChat} disabled={starting}>
              {starting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Starting…
                </>
              ) : (
                "Start chat session"
              )}
            </Button>
            <p className="text-xs text-slate-500 mt-3">
              Requires at least one worker running with Ollama on `localhost:11434`.
            </p>
          </div>
        ) : (
          <div className="rounded-2xl border border-white/10 bg-slate-900/50 backdrop-blur-xl p-4">
            <div className="text-xs text-slate-500 px-2 pb-3">
              Job: <span className="font-mono text-slate-300">{jobId}</span>
            </div>

            <div className="h-[55vh] overflow-y-auto px-2 pb-2 space-y-3">
              {messages.length === 0 ? (
                <div className="text-sm text-slate-400">No messages yet. Send the first message to begin.</div>
              ) : (
                messages.map((m) => (
                  <div
                    key={m.seq}
                    className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed border ${
                        m.role === "user"
                          ? "bg-purple-500/15 border-purple-500/30 text-slate-100"
                          : "bg-white/5 border-white/10 text-slate-200"
                      }`}
                    >
                      <div className="text-[10px] uppercase tracking-wider opacity-60 mb-1">
                        {m.role}
                      </div>
                      <div className="whitespace-pre-wrap">{m.content}</div>
                    </div>
                  </div>
                ))
              )}
              <div ref={bottomRef} />
            </div>

            <div className="pt-3 flex gap-2">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type a message…"
                disabled={sending}
                onKeyDown={(e) => {
                  if (e.key === "Enter") sendMessage();
                }}
              />
              <Button onClick={sendMessage} disabled={sending || !input.trim()}>
                {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : "Send"}
              </Button>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}

