"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import * as api from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { useAsync } from "@/hooks/useApi";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { ChatHeader } from "@/components/chat/ChatHeader";
import { Composer } from "@/components/chat/Composer";
import { MessageThread, type ChatMessage } from "@/components/chat/MessageThread";
import { HistoryContent } from "@/components/chat/HistoryContent";
import { KnowledgeContent } from "@/components/chat/KnowledgeContent";
import { SkillsContent } from "@/components/chat/SkillsContent";
import { Drawer } from "@/components/layout/Drawer";
import { ErrorState, SkeletonLines } from "@/components/ui/States";

function ChatHome() {
  const { employeeId } = useAuth();

  const agentFetch = useCallback(() => {
    if (!employeeId) return Promise.reject(new Error("Not signed in"));
    return api.getAgentByEmployee(employeeId);
  }, [employeeId]);
  const agentState = useAsync(agentFetch, [employeeId]);

  const namespace = agentState.data?.memory_namespace ?? null;
  const conversationFetch = useCallback(() => {
    if (!namespace) return Promise.resolve([]);
    return api.getConversation(namespace, 200);
  }, [namespace]);
  const conversationState = useAsync(conversationFetch, [namespace]);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [seeded, setSeeded] = useState(false);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  const [historyOpen, setHistoryOpen] = useState(false);
  const [knowledgeOpen, setKnowledgeOpen] = useState(false);
  const [skillsOpen, setSkillsOpen] = useState(false);

  useEffect(() => {
    if (!seeded && conversationState.settled && !conversationState.error) {
      setMessages((conversationState.data ?? []) as ChatMessage[]);
      setSeeded(true);
    }
  }, [seeded, conversationState.settled, conversationState.error, conversationState.data]);

  async function handleSend() {
    const content = draft.trim();
    if (!content || sending) return;
    setSendError(null);
    setDraft("");

    const now = new Date().toISOString();
    const userMsg: ChatMessage = {
      id: `local-user-${Date.now()}`,
      memory_namespace: namespace ?? "",
      role: "user",
      content,
      created_at: now,
    };
    const pendingMsg: ChatMessage = {
      id: `local-assistant-${Date.now()}`,
      memory_namespace: namespace ?? "",
      role: "assistant",
      content: "",
      created_at: now,
      pending: true,
    };
    setMessages((prev) => [...prev, userMsg, pendingMsg]);
    setSending(true);

    try {
      const response = await api.sendChatMessage(content);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingMsg.id
            ? { ...m, content: response.reply, pending: false, created_at: new Date().toISOString() }
            : m
        )
      );
    } catch (err) {
      setSendError(apiErrorMessage(err, "Your agent didn't respond. Try sending that again."));
      setMessages((prev) =>
        prev.map((m) => (m.id === pendingMsg.id ? { ...m, pending: false, failed: true, content: "" } : m))
      );
    } finally {
      setSending(false);
    }
  }

  const initialLoading = agentState.loading || (conversationState.loading && !seeded);

  return (
    <div className="flex h-screen flex-col bg-bg">
      <ChatHeader
        agent={agentState.data}
        onOpenHistory={() => setHistoryOpen(true)}
        onOpenKnowledge={() => setKnowledgeOpen(true)}
        onOpenSkills={() => setSkillsOpen(true)}
      />

      <div className="thin-scroll flex-1 overflow-y-auto">
        {agentState.error && (
          <div className="mx-auto max-w-2xl px-4 py-6">
            <ErrorState
              title="Couldn't load your agent"
              message={agentState.error}
              onRetry={agentState.retry}
            />
          </div>
        )}
        {!agentState.error && initialLoading && (
          <div className="mx-auto max-w-2xl px-4 py-6">
            <SkeletonLines count={4} />
          </div>
        )}
        {!agentState.error && !initialLoading && conversationState.error && messages.length === 0 && (
          <div className="mx-auto max-w-2xl px-4 py-6">
            <ErrorState
              title="Couldn't load your conversation"
              message={conversationState.error}
              onRetry={conversationState.retry}
            />
          </div>
        )}
        {!agentState.error && !initialLoading && messages.length === 0 && !conversationState.error && (
          <div className="mx-auto flex max-w-2xl flex-col items-center gap-2 px-4 py-16 text-center">
            <h2 className="font-display text-2xl">
              Say hello to {agentState.data?.name ?? "your agent"}
            </h2>
            <p className="max-w-sm text-sm text-text-muted">
              {agentState.data?.personality ?? "This is the start of your conversation."}
            </p>
          </div>
        )}
        {!agentState.error && !initialLoading && messages.length > 0 && <MessageThread messages={messages} />}
      </div>

      <Composer value={draft} onChange={setDraft} onSend={handleSend} disabled={sending} error={sendError} />

      <Drawer open={historyOpen} onClose={() => setHistoryOpen(false)} title="Conversation history">
        <HistoryContent
          turns={messages}
          loading={conversationState.loading && !seeded}
          error={conversationState.error}
          onRetry={conversationState.retry}
        />
      </Drawer>
      <Drawer open={knowledgeOpen} onClose={() => setKnowledgeOpen(false)} title="Knowledge">
        <KnowledgeContent />
      </Drawer>
      <Drawer open={skillsOpen} onClose={() => setSkillsOpen(false)} title="Connected apps">
        <Suspense fallback={<SkeletonLines count={4} />}>
          <SkillsContent />
        </Suspense>
      </Drawer>
    </div>
  );
}

export default function Page() {
  return (
    <ProtectedRoute minRole="employee">
      <ErrorBoundary>
        <ChatHome />
      </ErrorBoundary>
    </ProtectedRoute>
  );
}
