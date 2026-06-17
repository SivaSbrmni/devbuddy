var __defProp = Object.defineProperty;
var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
var __publicField = (obj, key, value) => __defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);
import { j as jsxRuntimeExports, M as Markdown, r as remarkGfm } from "./markdown-CZmKipT5.js";
import { b as reactExports, g as getDefaultExportFromCjs } from "./vendor-CPzzSAOr.js";
import { I as Icon, u as useAuth } from "./index-DIoWrWjG.js";
import { r as requireJszip_min } from "./utils-Cm2wexb8.js";
const BACKEND$2 = "";
const API$4 = `${BACKEND$2}/api/v1`;
const Ctx = reactExports.createContext({});
function GitHubProvider({ children, token }) {
  const [connected, setConnected] = reactExports.useState(false);
  const [githubLogin, setGithubLogin] = reactExports.useState(null);
  const [loading, setLoading] = reactExports.useState(true);
  const [repos, setRepos] = reactExports.useState([]);
  const [reposLoading, setReposLoading] = reactExports.useState(false);
  const [activeRepo, setActiveRepoState] = reactExports.useState(() => {
    try {
      return JSON.parse(localStorage.getItem("devbuddy_active_repo") || "null");
    } catch {
      return null;
    }
  });
  const setActiveRepo = reactExports.useCallback((r) => {
    setActiveRepoState(r);
    if (r) localStorage.setItem("devbuddy_active_repo", JSON.stringify(r));
    else localStorage.removeItem("devbuddy_active_repo");
  }, []);
  reactExports.useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    fetch(`${API$4}/github/status?token=${encodeURIComponent(token)}`).then((r) => r.ok ? r.json() : { connected: false }).then((d) => {
      setConnected(d.connected);
      setGithubLogin(d.login || null);
    }).catch(() => {
      setConnected(false);
    }).finally(() => setLoading(false));
  }, [token]);
  const connect = reactExports.useCallback(() => {
    window.location.href = `${API$4}/github/login?token=${encodeURIComponent(token)}`;
  }, [token]);
  const disconnect = reactExports.useCallback(() => {
    setConnected(false);
    setGithubLogin(null);
    setRepos([]);
    setActiveRepo(null);
  }, [setActiveRepo]);
  const fetchRepos = reactExports.useCallback(async () => {
    if (!connected) return;
    setReposLoading(true);
    try {
      const r = await fetch(`${API$4}/github/repos?token=${encodeURIComponent(token)}&per_page=50&sort=pushed`);
      if (r.ok) setRepos(await r.json());
    } finally {
      setReposLoading(false);
    }
  }, [connected, token]);
  const searchRepos = reactExports.useCallback(async (q) => {
    if (!q.trim()) return repos;
    const r = await fetch(`${API$4}/github/repos/search?token=${encodeURIComponent(token)}&q=${encodeURIComponent(q)}`);
    if (r.ok) return r.json();
    return [];
  }, [token, repos]);
  reactExports.useEffect(() => {
    if (connected) fetchRepos();
  }, [connected]);
  return /* @__PURE__ */ jsxRuntimeExports.jsx(Ctx.Provider, { value: { connected, githubLogin, loading, connect, disconnect, repos, reposLoading, fetchRepos, searchRepos, activeRepo, setActiveRepo }, children });
}
const useGitHub = () => reactExports.useContext(Ctx);
const API$3 = `${""}/api/v1`;
function getToken$1() {
  return localStorage.getItem("devbuddy_token") || "";
}
async function fetchWithAuth$1(url, options = {}) {
  const token = getToken$1();
  if (!token) {
    throw new Error("Not authenticated");
  }
  const separator = url.includes("?") ? "&" : "?";
  const authedUrl = `${url}${separator}token=${encodeURIComponent(token)}`;
  return fetch(authedUrl, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers
    }
  });
}
async function listConversations(options = {}) {
  const params = new URLSearchParams();
  if (options.status) params.set("status", options.status);
  if (options.repo_url) params.set("repo_url", options.repo_url);
  if (options.limit) params.set("limit", String(options.limit));
  if (options.offset) params.set("offset", String(options.offset));
  const response = await fetchWithAuth$1(`${API$3}/conversations?${params}`);
  if (!response.ok) {
    throw new Error(`Failed to list conversations: ${response.status}`);
  }
  return response.json();
}
async function createConversation(req) {
  const response = await fetchWithAuth$1(`${API$3}/conversations`, {
    method: "POST",
    body: JSON.stringify(req)
  });
  if (!response.ok) {
    throw new Error(`Failed to create conversation: ${response.status}`);
  }
  return response.json();
}
async function updateConversation(id, updates) {
  const response = await fetchWithAuth$1(`${API$3}/conversations/${id}`, {
    method: "PATCH",
    body: JSON.stringify(updates)
  });
  if (!response.ok) {
    throw new Error(`Failed to update conversation: ${response.status}`);
  }
  return response.json();
}
async function deleteConversation(id) {
  const response = await fetchWithAuth$1(`${API$3}/conversations/${id}`, {
    method: "DELETE"
  });
  if (!response.ok) {
    throw new Error(`Failed to delete conversation: ${response.status}`);
  }
}
async function listMessages(conversationId, options = {}) {
  const params = new URLSearchParams();
  if (options.limit) params.set("limit", String(options.limit));
  if (options.offset) params.set("offset", String(options.offset));
  const response = await fetchWithAuth$1(`${API$3}/conversations/${conversationId}/messages?${params}`);
  if (!response.ok) {
    throw new Error(`Failed to list messages: ${response.status}`);
  }
  return response.json();
}
async function createMessage$1(conversationId, req) {
  const response = await fetchWithAuth$1(`${API$3}/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify(req)
  });
  if (!response.ok) {
    throw new Error(`Failed to create message: ${response.status}`);
  }
  return response.json();
}
async function syncConversations(req) {
  const response = await fetchWithAuth$1(`${API$3}/conversations/sync`, {
    method: "POST",
    body: JSON.stringify(req)
  });
  if (!response.ok) {
    throw new Error(`Failed to sync: ${response.status}`);
  }
  return response.json();
}
class ConversationWebSocket {
  constructor() {
    __publicField(this, "ws", null);
    __publicField(this, "reconnectAttempts", 0);
    __publicField(this, "maxReconnectAttempts", 5);
    __publicField(this, "reconnectDelay", 1e3);
    __publicField(this, "listeners", []);
    __publicField(this, "onConnectCallbacks", []);
    __publicField(this, "onDisconnectCallbacks", []);
  }
  connect() {
    const token = getToken$1();
    if (!token) {
      console.error("Cannot connect WebSocket: no token");
      return;
    }
    const wsUrl = `${API$3.replace(/^http/, "ws")}/conversations/ws?token=${encodeURIComponent(token)}`;
    this.ws = new WebSocket(wsUrl);
    this.ws.onopen = () => {
      console.log("WebSocket connected");
      this.reconnectAttempts = 0;
      this.onConnectCallbacks.forEach((cb) => cb());
    };
    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        this.listeners.forEach((cb) => cb(msg));
      } catch (e) {
        console.error("Failed to parse WebSocket message:", e);
      }
    };
    this.ws.onclose = () => {
      console.log("WebSocket disconnected");
      this.onDisconnectCallbacks.forEach((cb) => cb());
      this.attemptReconnect();
    };
    this.ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };
  }
  attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error("Max WebSocket reconnect attempts reached");
      return;
    }
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    console.log(`Reconnecting in ${delay}ms... (attempt ${this.reconnectAttempts})`);
    setTimeout(() => this.connect(), delay);
  }
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
  send(msg) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }
  ping() {
    this.send({ type: "ping" });
  }
  onMessage(callback) {
    this.listeners.push(callback);
    return () => {
      const index = this.listeners.indexOf(callback);
      if (index > -1) {
        this.listeners.splice(index, 1);
      }
    };
  }
  onConnect(callback) {
    this.onConnectCallbacks.push(callback);
    return () => {
      const index = this.onConnectCallbacks.indexOf(callback);
      if (index > -1) {
        this.onConnectCallbacks.splice(index, 1);
      }
    };
  }
  onDisconnect(callback) {
    this.onDisconnectCallbacks.push(callback);
    return () => {
      const index = this.onDisconnectCallbacks.indexOf(callback);
      if (index > -1) {
        this.onDisconnectCallbacks.splice(index, 1);
      }
    };
  }
  get isConnected() {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
}
const conversationWS = new ConversationWebSocket();
function useServerConversations(options = {}) {
  const { autoSync = true, syncInterval = 3e4 } = options;
  const [conversations, setConversations] = reactExports.useState([]);
  const [activeConversationId, setActiveConversationId] = reactExports.useState(null);
  const [messages, setMessages2] = reactExports.useState([]);
  const [loading, setLoading] = reactExports.useState(false);
  const [error, setError] = reactExports.useState(null);
  const [syncStatus, setSyncStatus] = reactExports.useState("idle");
  const [lastSyncedAt, setLastSyncedAt] = reactExports.useState(null);
  const [isWebSocketConnected, setIsWebSocketConnected] = reactExports.useState(false);
  const syncTimeoutRef = reactExports.useRef(null);
  const abortControllerRef = reactExports.useRef(null);
  const isMountedRef = reactExports.useRef(true);
  const activeConversation = conversations.find((c) => c.id === activeConversationId) || null;
  const loadConversations = reactExports.useCallback(async () => {
    if (!isMountedRef.current) return;
    setLoading(true);
    setError(null);
    try {
      const data = await listConversations({ limit: 100 });
      if (isMountedRef.current) {
        setConversations(data);
        setLastSyncedAt((/* @__PURE__ */ new Date()).toISOString());
        setSyncStatus("idle");
      }
    } catch (e) {
      if (isMountedRef.current) {
        setError(e instanceof Error ? e.message : "Failed to load conversations");
        setSyncStatus("error");
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, []);
  reactExports.useEffect(() => {
    loadConversations();
    return () => {
      isMountedRef.current = false;
      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [loadConversations]);
  reactExports.useEffect(() => {
    conversationWS.connect();
    const unsubscribeMessage = conversationWS.onMessage((msg) => {
      switch (msg.type) {
        case "conversation_updated":
          setConversations((prev) => {
            const exists = prev.find((c) => c.id === msg.conversation.id);
            if (exists) {
              return prev.map((c) => c.id === msg.conversation.id ? msg.conversation : c);
            }
            return [msg.conversation, ...prev];
          });
          break;
        case "message_created":
          if (msg.conversation_id === activeConversationId) {
            setMessages2((prev) => [...prev, msg.message]);
          }
          setConversations(
            (prev) => prev.map(
              (c) => c.id === msg.conversation_id ? { ...c, last_message_at: msg.message.created_at, message_count: c.message_count + 1 } : c
            )
          );
          break;
        case "sync_required":
          sync();
          break;
      }
    });
    const unsubscribeConnect = conversationWS.onConnect(() => {
      setIsWebSocketConnected(true);
      setSyncStatus("idle");
    });
    const unsubscribeDisconnect = conversationWS.onDisconnect(() => {
      setIsWebSocketConnected(false);
      setSyncStatus("offline");
    });
    const pingInterval = setInterval(() => {
      if (conversationWS.isConnected) {
        conversationWS.ping();
      }
    }, 3e4);
    return () => {
      unsubscribeMessage();
      unsubscribeConnect();
      unsubscribeDisconnect();
      clearInterval(pingInterval);
      conversationWS.disconnect();
    };
  }, [activeConversationId]);
  const sync = reactExports.useCallback(async () => {
    if (!isMountedRef.current) return;
    setSyncStatus("syncing");
    try {
      const req = {
        last_sync_at: lastSyncedAt || void 0,
        client_conversations: conversations.map((c) => ({
          id: c.id,
          updated_at: c.updated_at,
          version: 0
          // TODO: Add version field
        }))
      };
      const response = await syncConversations(req);
      if (!isMountedRef.current) return;
      if (response.updated_conversations.length > 0) {
        setConversations((prev) => {
          const updatedIds = new Set(response.updated_conversations.map((c) => c.id));
          const unchanged = prev.filter((c) => !updatedIds.has(c.id));
          return [...response.updated_conversations, ...unchanged].sort(
            (a, b) => new Date(b.last_message_at || b.created_at).getTime() - new Date(a.last_message_at || a.created_at).getTime()
          );
        });
      }
      if (response.deleted_ids.length > 0) {
        setConversations((prev) => prev.filter((c) => !response.deleted_ids.includes(c.id)));
      }
      setLastSyncedAt(response.server_timestamp);
      setSyncStatus("idle");
    } catch (e) {
      if (isMountedRef.current) {
        setSyncStatus("error");
      }
    }
  }, [conversations, lastSyncedAt]);
  reactExports.useEffect(() => {
    if (!autoSync) return;
    const scheduleSync = () => {
      syncTimeoutRef.current = setTimeout(() => {
        sync();
        scheduleSync();
      }, syncInterval);
    };
    scheduleSync();
    return () => {
      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }
    };
  }, [autoSync, syncInterval, sync]);
  const setActiveConversation = reactExports.useCallback(async (id) => {
    setActiveConversationId(id);
    setMessages2([]);
    if (id) {
      try {
        const msgs = await listMessages(id, { limit: 100 });
        if (isMountedRef.current) {
          setMessages2(msgs);
        }
      } catch (e) {
        console.error("Failed to load messages:", e);
      }
    }
  }, []);
  const createConversation$1 = reactExports.useCallback(async (req) => {
    const conversation = await createConversation(req);
    if (isMountedRef.current) {
      setConversations((prev) => [conversation, ...prev]);
      setActiveConversationId(conversation.id);
    }
    return conversation;
  }, []);
  const updateConversation$1 = reactExports.useCallback(async (id, updates) => {
    setConversations(
      (prev) => prev.map((c) => c.id === id ? { ...c, ...updates, updated_at: (/* @__PURE__ */ new Date()).toISOString() } : c)
    );
    try {
      await updateConversation(id, updates);
    } catch (e) {
      loadConversations();
      throw e;
    }
  }, [loadConversations]);
  const deleteConversation$1 = reactExports.useCallback(async (id) => {
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeConversationId === id) {
      setActiveConversationId(null);
      setMessages2([]);
    }
    try {
      await deleteConversation(id);
    } catch (e) {
      loadConversations();
      throw e;
    }
  }, [activeConversationId, loadConversations]);
  const createMessage2 = reactExports.useCallback(async (conversationId, req) => {
    const optimisticMessage = {
      id: `temp-${Date.now()}`,
      conversation_id: conversationId,
      role: req.role,
      content: req.content,
      metadata: req.metadata || {},
      is_complete: true,
      created_at: (/* @__PURE__ */ new Date()).toISOString()
    };
    if (conversationId === activeConversationId) {
      setMessages2((prev) => [...prev, optimisticMessage]);
    }
    try {
      const message = await createMessage$1(conversationId, req);
      if (isMountedRef.current) {
        if (conversationId === activeConversationId) {
          setMessages2((prev) => prev.map((m) => m.id === optimisticMessage.id ? message : m));
        }
        setConversations(
          (prev) => prev.map(
            (c) => c.id === conversationId ? { ...c, last_message_at: message.created_at, message_count: c.message_count + 1 } : c
          )
        );
      }
      return message;
    } catch (e) {
      if (conversationId === activeConversationId) {
        setMessages2((prev) => prev.filter((m) => m.id !== optimisticMessage.id));
      }
      throw e;
    }
  }, [activeConversationId]);
  const refreshMessages = reactExports.useCallback(async (conversationId) => {
    const msgs = await listMessages(conversationId, { limit: 100 });
    if (isMountedRef.current && conversationId === activeConversationId) {
      setMessages2(msgs);
    }
  }, [activeConversationId]);
  const forceRefresh = reactExports.useCallback(async () => {
    await loadConversations();
    if (activeConversationId) {
      await refreshMessages(activeConversationId);
    }
  }, [loadConversations, activeConversationId, refreshMessages]);
  return {
    conversations,
    activeConversation,
    messages,
    loading,
    error,
    syncStatus,
    lastSyncedAt,
    isWebSocketConnected,
    setActiveConversation,
    createConversation: createConversation$1,
    updateConversation: updateConversation$1,
    deleteConversation: deleteConversation$1,
    createMessage: createMessage2,
    refreshMessages,
    sync,
    forceRefresh
  };
}
const API$2 = `${""}/api/v1`;
function getToken() {
  return localStorage.getItem("devbuddy_token") || "";
}
async function fetchWithAuth(url, options = {}) {
  const token = getToken();
  if (!token) {
    throw new Error("Not authenticated");
  }
  const separator = url.includes("?") ? "&" : "?";
  const authedUrl = `${url}${separator}token=${encodeURIComponent(token)}`;
  return fetch(authedUrl, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers
    }
  });
}
async function listProviders() {
  const response = await fetchWithAuth(`${API$2}/llm-providers`);
  if (!response.ok) {
    throw new Error(`Failed to list providers: ${response.status}`);
  }
  return response.json();
}
async function createProvider(req) {
  const response = await fetchWithAuth(`${API$2}/llm-providers`, {
    method: "POST",
    body: JSON.stringify(req)
  });
  if (!response.ok) {
    throw new Error(`Failed to create provider: ${response.status}`);
  }
  return response.json();
}
async function updateProvider(id, req) {
  const response = await fetchWithAuth(`${API$2}/llm-providers/${id}`, {
    method: "PATCH",
    body: JSON.stringify(req)
  });
  if (!response.ok) {
    throw new Error(`Failed to update provider: ${response.status}`);
  }
  return response.json();
}
async function deleteProvider(id) {
  const response = await fetchWithAuth(`${API$2}/llm-providers/${id}`, {
    method: "DELETE"
  });
  if (!response.ok) {
    throw new Error(`Failed to delete provider: ${response.status}`);
  }
}
async function testConnection(req) {
  const response = await fetchWithAuth(`${API$2}/llm-providers/test`, {
    method: "POST",
    body: JSON.stringify(req)
  });
  if (!response.ok) {
    throw new Error(`Failed to test connection: ${response.status}`);
  }
  return response.json();
}
async function testSavedProvider(id) {
  const response = await fetchWithAuth(`${API$2}/llm-providers/${id}/test`, {
    method: "POST"
  });
  if (!response.ok) {
    throw new Error(`Failed to test provider: ${response.status}`);
  }
  return response.json();
}
async function getAvailableModels() {
  const response = await fetchWithAuth(`${API$2}/llm-providers/models/available`);
  if (!response.ok) {
    throw new Error(`Failed to get models: ${response.status}`);
  }
  return response.json();
}
const PROVIDER_PRESETS = {
  ollama: {
    provider_type: "ollama",
    base_url: "http://localhost:11434",
    default_model: "qwen3-coder:480b",
    supports_streaming: true,
    supports_tools: true,
    context_size: 32768,
    cost_per_1k_input: 0,
    cost_per_1k_output: 0
  },
  openrouter: {
    provider_type: "openai-compatible",
    base_url: "https://openrouter.ai/api/v1",
    default_model: "anthropic/claude-3.5-sonnet",
    supports_streaming: true,
    supports_tools: true,
    supports_vision: true,
    context_size: 2e5,
    cost_per_1k_input: 3e-3,
    cost_per_1k_output: 0.015
  },
  openai: {
    provider_type: "openai-compatible",
    base_url: "https://api.openai.com/v1",
    default_model: "gpt-4o-mini",
    supports_streaming: true,
    supports_tools: true,
    supports_vision: true,
    context_size: 128e3,
    cost_per_1k_input: 0.15,
    cost_per_1k_output: 0.6
  },
  anthropic: {
    provider_type: "anthropic",
    base_url: "https://api.anthropic.com/v1",
    default_model: "claude-3-5-sonnet-20241022",
    supports_streaming: true,
    supports_tools: true,
    supports_vision: true,
    context_size: 2e5,
    cost_per_1k_input: 3e-3,
    cost_per_1k_output: 0.015
  },
  azure: {
    provider_type: "azure",
    base_url: "https://your-resource.openai.azure.com/openai/deployments/your-deployment",
    default_model: "gpt-4",
    supports_streaming: true,
    supports_tools: true,
    context_size: 128e3,
    cost_per_1k_input: 0.03,
    cost_per_1k_output: 0.06
  },
  lmstudio: {
    provider_type: "openai-compatible",
    base_url: "http://localhost:1234/v1",
    default_model: "local-model",
    supports_streaming: true,
    supports_tools: false,
    context_size: 8192,
    cost_per_1k_input: 0,
    cost_per_1k_output: 0
  }
};
function useLLMProviders() {
  const [providers, setProviders] = reactExports.useState([]);
  const [availableModels, setAvailableModels] = reactExports.useState([]);
  const [loading, setLoading] = reactExports.useState(false);
  const [testing, setTesting] = reactExports.useState(false);
  const [error, setError] = reactExports.useState(null);
  const [testResult, setTestResult] = reactExports.useState(null);
  const refresh = reactExports.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [providersData, modelsData] = await Promise.all([
        listProviders(),
        getAvailableModels()
      ]);
      setProviders(providersData);
      setAvailableModels(modelsData.models);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load providers");
    } finally {
      setLoading(false);
    }
  }, []);
  reactExports.useEffect(() => {
    refresh();
  }, [refresh]);
  const defaultProvider = providers.find((p) => p.is_default) || providers[0] || null;
  const addProvider = reactExports.useCallback(async (req) => {
    setLoading(true);
    setError(null);
    try {
      const provider = await createProvider(req);
      setProviders((prev) => [...prev, provider]);
      return provider;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create provider");
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);
  const editProvider = reactExports.useCallback(async (id, req) => {
    setLoading(true);
    setError(null);
    try {
      const provider = await updateProvider(id, req);
      setProviders((prev) => prev.map((p) => p.id === id ? provider : p));
      return provider;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update provider");
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);
  const removeProvider = reactExports.useCallback(async (id) => {
    setLoading(true);
    setError(null);
    try {
      await deleteProvider(id);
      setProviders((prev) => prev.filter((p) => p.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete provider");
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);
  const testNewConnection = reactExports.useCallback(async (req) => {
    setTesting(true);
    setTestResult(null);
    setError(null);
    try {
      const result = await testConnection(req);
      setTestResult(result);
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to test connection");
      throw e;
    } finally {
      setTesting(false);
    }
  }, []);
  const testExistingProvider = reactExports.useCallback(async (id) => {
    setTesting(true);
    setTestResult(null);
    setError(null);
    try {
      const result = await testSavedProvider(id);
      setTestResult(result);
      await refresh();
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to test provider");
      throw e;
    } finally {
      setTesting(false);
    }
  }, [refresh]);
  const setDefaultProvider = reactExports.useCallback(async (id) => {
    setLoading(true);
    try {
      await updateProvider(id, { is_default: true });
      setProviders((prev) => prev.map((p) => ({
        ...p,
        is_default: p.id === id
      })));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to set default");
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);
  return {
    providers,
    defaultProvider,
    availableModels,
    loading,
    testing,
    error,
    testResult,
    refresh,
    addProvider,
    editProvider,
    removeProvider,
    testNewConnection,
    testExistingProvider,
    setDefaultProvider
  };
}
function LLMProviderSettings({ isOpen, onClose }) {
  const {
    providers,
    loading,
    testing,
    error,
    testResult,
    addProvider,
    editProvider,
    removeProvider,
    testNewConnection,
    testExistingProvider
  } = useLLMProviders();
  const [activeTab, setActiveTab] = reactExports.useState("providers");
  const [editingProvider, setEditingProvider] = reactExports.useState(null);
  const [deletingId, setDeletingId] = reactExports.useState(null);
  const [formData, setFormData] = reactExports.useState({
    name: "",
    provider_type: "openai-compatible",
    base_url: "",
    api_key: "",
    default_model: "",
    supports_streaming: true,
    supports_tools: true,
    supports_vision: false,
    context_size: 8192,
    max_tokens: 4096,
    cost_per_1k_input: 0,
    cost_per_1k_output: 0,
    priority: 100,
    is_default: false
  });
  const applyPreset = (presetKey) => {
    const preset = PROVIDER_PRESETS[presetKey];
    if (preset) {
      setFormData((prev) => ({
        ...prev,
        ...preset,
        name: presetKey.charAt(0).toUpperCase() + presetKey.slice(1)
      }));
    }
  };
  const handleTest = async () => {
    if (!formData.base_url || !formData.default_model) return;
    await testNewConnection({
      base_url: formData.base_url,
      api_key: formData.api_key || "",
      provider_type: formData.provider_type,
      model: formData.default_model
    });
  };
  const handleSave = async () => {
    try {
      await addProvider(formData);
      setActiveTab("providers");
      setFormData({
        name: "",
        provider_type: "openai-compatible",
        base_url: "",
        api_key: "",
        default_model: "",
        supports_streaming: true,
        supports_tools: true,
        supports_vision: false,
        context_size: 8192,
        max_tokens: 4096,
        cost_per_1k_input: 0,
        cost_per_1k_output: 0,
        priority: 100,
        is_default: false
      });
    } catch {
    }
  };
  const handleUpdate = async () => {
    if (!editingProvider) return;
    try {
      await editProvider(editingProvider.id, {
        name: formData.name,
        base_url: formData.base_url,
        api_key: formData.api_key,
        default_model: formData.default_model,
        supports_streaming: formData.supports_streaming,
        supports_tools: formData.supports_tools,
        supports_vision: formData.supports_vision,
        context_size: formData.context_size,
        max_tokens: formData.max_tokens,
        cost_per_1k_input: formData.cost_per_1k_input,
        cost_per_1k_output: formData.cost_per_1k_output,
        priority: formData.priority
      });
      setActiveTab("providers");
      setEditingProvider(null);
    } catch {
    }
  };
  const startEdit = (provider) => {
    setEditingProvider(provider);
    setFormData({
      name: provider.name,
      provider_type: provider.provider_type,
      base_url: provider.base_url,
      api_key: "",
      // Don't show masked key, user enters new one if changing
      default_model: provider.default_model,
      supports_streaming: provider.supports_streaming,
      supports_tools: provider.supports_tools,
      supports_vision: provider.supports_vision,
      context_size: provider.context_size,
      max_tokens: provider.max_tokens,
      cost_per_1k_input: provider.cost_per_1k_input,
      cost_per_1k_output: provider.cost_per_1k_output,
      priority: provider.priority,
      is_default: provider.is_default
    });
    setActiveTab("edit");
  };
  const confirmDelete = (id) => {
    setDeletingId(id);
  };
  const handleDelete = async () => {
    if (!deletingId) return;
    try {
      await removeProvider(deletingId);
      setDeletingId(null);
    } catch {
    }
  };
  if (!isOpen) return null;
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: "rgba(0,0,0,0.7)",
    backdropFilter: "blur(4px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1e3
  }, children: [
    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
      background: "var(--bg-card)",
      border: "1px solid var(--border)",
      borderRadius: 12,
      width: 600,
      maxWidth: "90vw",
      maxHeight: "90vh",
      overflow: "auto",
      display: "flex",
      flexDirection: "column"
    }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
        padding: "16px 20px",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between"
      }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx("h2", { style: { margin: 0, fontSize: 18, fontWeight: 600 }, children: "LLM Providers" }),
        /* @__PURE__ */ jsxRuntimeExports.jsx(
          "button",
          {
            onClick: onClose,
            className: "db-btn",
            style: { width: 32, height: 32 },
            children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "close", size: 16 })
          }
        )
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
        display: "flex",
        gap: 4,
        padding: "12px 20px 0",
        borderBottom: "1px solid var(--border)"
      }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx(
          "button",
          {
            onClick: () => setActiveTab("providers"),
            style: {
              padding: "8px 16px",
              border: "none",
              background: activeTab === "providers" ? "var(--accent)" : "transparent",
              color: activeTab === "providers" ? "white" : "var(--text)",
              borderRadius: "6px 6px 0 0",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 500
            },
            children: "My Providers"
          }
        ),
        /* @__PURE__ */ jsxRuntimeExports.jsx(
          "button",
          {
            onClick: () => {
              setActiveTab("add");
              setEditingProvider(null);
              setFormData({
                name: "",
                provider_type: "openai-compatible",
                base_url: "",
                api_key: "",
                default_model: "",
                supports_streaming: true,
                supports_tools: true,
                supports_vision: false,
                context_size: 8192,
                max_tokens: 4096,
                cost_per_1k_input: 0,
                cost_per_1k_output: 0,
                priority: 100,
                is_default: false
              });
            },
            style: {
              padding: "8px 16px",
              border: "none",
              background: activeTab === "add" || activeTab === "edit" ? "var(--accent)" : "transparent",
              color: activeTab === "add" || activeTab === "edit" ? "white" : "var(--text)",
              borderRadius: "6px 6px 0 0",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 500
            },
            children: activeTab === "edit" ? "Edit Provider" : "Add Provider"
          }
        )
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: 20 }, children: [
        loading && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { textAlign: "center", padding: 40 }, children: "Loading..." }),
        error && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
          padding: 12,
          background: "rgba(239,68,68,0.1)",
          border: "1px solid rgba(239,68,68,0.3)",
          borderRadius: 8,
          color: "#ef4444",
          marginBottom: 16,
          fontSize: 13
        }, children: error }),
        activeTab === "providers" && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { children: providers.length === 0 ? /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
          textAlign: "center",
          padding: 40,
          color: "var(--text-muted)"
        }, children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "bot", size: 48, style: { marginBottom: 16, opacity: 0.5 } }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("p", { children: "No LLM providers configured" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx(
            "button",
            {
              onClick: () => setActiveTab("add"),
              className: "db-btn",
              style: { marginTop: 16 },
              children: "Add your first provider"
            }
          )
        ] }) : /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { display: "flex", flexDirection: "column", gap: 12 }, children: providers.map((provider) => /* @__PURE__ */ jsxRuntimeExports.jsx(
          "div",
          {
            style: {
              padding: 16,
              background: "var(--bg-hover)",
              borderRadius: 8,
              border: provider.is_default ? "2px solid var(--accent)" : "1px solid var(--border)"
            },
            children: /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "flex-start" }, children: [
              /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { children: [
                /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 8 }, children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontWeight: 600 }, children: provider.name }),
                  provider.is_default && /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: {
                    fontSize: 11,
                    padding: "2px 8px",
                    background: "var(--accent)",
                    color: "white",
                    borderRadius: 4
                  }, children: "Default" }),
                  /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: {
                    fontSize: 11,
                    padding: "2px 8px",
                    background: provider.health_status === "healthy" ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)",
                    color: provider.health_status === "healthy" ? "#22c55e" : "#ef4444",
                    borderRadius: 4
                  }, children: provider.health_status })
                ] }),
                /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 12, color: "var(--text-muted)", marginTop: 4 }, children: provider.base_url }),
                /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { fontSize: 12, color: "var(--text-muted)" }, children: [
                  "Model: ",
                  provider.default_model,
                  provider.latency_ms && ` • ${provider.latency_ms}ms`
                ] })
              ] }),
              /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", gap: 8 }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx(
                  "button",
                  {
                    onClick: () => testExistingProvider(provider.id),
                    disabled: testing,
                    className: "db-btn",
                    style: { width: 32, height: 32 },
                    title: "Test connection",
                    children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "refresh", size: 14 })
                  }
                ),
                /* @__PURE__ */ jsxRuntimeExports.jsx(
                  "button",
                  {
                    onClick: () => startEdit(provider),
                    className: "db-btn",
                    style: { width: 32, height: 32 },
                    title: "Edit",
                    children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "edit", size: 14 })
                  }
                ),
                /* @__PURE__ */ jsxRuntimeExports.jsx(
                  "button",
                  {
                    onClick: () => confirmDelete(provider.id),
                    className: "db-btn",
                    style: { width: 32, height: 32 },
                    title: "Delete",
                    children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "trash", size: 14 })
                  }
                )
              ] })
            ] })
          },
          provider.id
        )) }) }),
        (activeTab === "add" || activeTab === "edit") && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", flexDirection: "column", gap: 16 }, children: [
          activeTab === "add" && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx("label", { style: { fontSize: 12, fontWeight: 600, marginBottom: 8, display: "block" }, children: "Quick Setup (optional)" }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { display: "flex", flexWrap: "wrap", gap: 8 }, children: Object.keys(PROVIDER_PRESETS).map((preset) => /* @__PURE__ */ jsxRuntimeExports.jsx(
              "button",
              {
                onClick: () => applyPreset(preset),
                style: {
                  padding: "6px 12px",
                  border: "1px solid var(--border)",
                  background: "var(--bg-hover)",
                  borderRadius: 6,
                  cursor: "pointer",
                  fontSize: 12,
                  textTransform: "capitalize"
                },
                children: preset
              },
              preset
            )) })
          ] }),
          /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx("label", { style: { fontSize: 12, fontWeight: 600, marginBottom: 4, display: "block" }, children: "Name *" }),
            /* @__PURE__ */ jsxRuntimeExports.jsx(
              "input",
              {
                type: "text",
                value: formData.name,
                onChange: (e) => setFormData({ ...formData, name: e.target.value }),
                placeholder: "My Ollama Server",
                style: {
                  width: "100%",
                  padding: "8px 12px",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  background: "var(--bg-input)",
                  color: "var(--text)",
                  fontSize: 14
                }
              }
            )
          ] }),
          /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx("label", { style: { fontSize: 12, fontWeight: 600, marginBottom: 4, display: "block" }, children: "Base URL *" }),
            /* @__PURE__ */ jsxRuntimeExports.jsx(
              "input",
              {
                type: "text",
                value: formData.base_url,
                onChange: (e) => setFormData({ ...formData, base_url: e.target.value }),
                placeholder: "http://localhost:11434 or https://api.openai.com/v1",
                style: {
                  width: "100%",
                  padding: "8px 12px",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  background: "var(--bg-input)",
                  color: "var(--text)",
                  fontSize: 14,
                  fontFamily: "monospace"
                }
              }
            )
          ] }),
          /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { children: [
            /* @__PURE__ */ jsxRuntimeExports.jsxs("label", { style: { fontSize: 12, fontWeight: 600, marginBottom: 4, display: "block" }, children: [
              "API Key ",
              editingProvider && "(leave blank to keep current)"
            ] }),
            /* @__PURE__ */ jsxRuntimeExports.jsx(
              "input",
              {
                type: "password",
                value: formData.api_key,
                onChange: (e) => setFormData({ ...formData, api_key: e.target.value }),
                placeholder: "sk-... or leave blank for no auth",
                style: {
                  width: "100%",
                  padding: "8px 12px",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  background: "var(--bg-input)",
                  color: "var(--text)",
                  fontSize: 14,
                  fontFamily: "monospace"
                }
              }
            )
          ] }),
          /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx("label", { style: { fontSize: 12, fontWeight: 600, marginBottom: 4, display: "block" }, children: "Default Model *" }),
            /* @__PURE__ */ jsxRuntimeExports.jsx(
              "input",
              {
                type: "text",
                value: formData.default_model,
                onChange: (e) => setFormData({ ...formData, default_model: e.target.value }),
                placeholder: "qwen3-coder:480b or gpt-4o",
                style: {
                  width: "100%",
                  padding: "8px 12px",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  background: "var(--bg-input)",
                  color: "var(--text)",
                  fontSize: 14
                }
              }
            )
          ] }),
          testResult && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
            padding: 12,
            background: testResult.success ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)",
            border: `1px solid ${testResult.success ? "#22c55e" : "#ef4444"}`,
            borderRadius: 8,
            fontSize: 13
          }, children: [
            /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 8 }, children: [
              /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: testResult.success ? "check" : "error", size: 16 }),
              /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontWeight: 600 }, children: testResult.success ? "Connected!" : "Connection failed" }),
              /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { color: "var(--text-muted)" }, children: [
                "(",
                testResult.latency_ms,
                "ms)"
              ] })
            ] }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { marginTop: 4 }, children: testResult.message }),
            testResult.models_available && testResult.models_available.length > 0 && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { marginTop: 8, fontSize: 11 }, children: [
              "Available models: ",
              testResult.models_available.slice(0, 5).join(", "),
              testResult.models_available.length > 5 && ` +${testResult.models_available.length - 5} more`
            ] })
          ] }),
          /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", gap: 12, justifyContent: "flex-end", marginTop: 8 }, children: [
            /* @__PURE__ */ jsxRuntimeExports.jsxs(
              "button",
              {
                onClick: handleTest,
                disabled: testing || !formData.base_url || !formData.default_model,
                className: "db-btn",
                style: {
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  opacity: testing || !formData.base_url || !formData.default_model ? 0.5 : 1
                },
                children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: testing ? "loading" : "refresh", size: 14 }),
                  testing ? "Testing..." : "Test Connection"
                ]
              }
            ),
            /* @__PURE__ */ jsxRuntimeExports.jsx(
              "button",
              {
                onClick: activeTab === "edit" ? handleUpdate : handleSave,
                disabled: !formData.name || !formData.base_url || !formData.default_model,
                className: "db-btn",
                style: {
                  background: "var(--accent)",
                  color: "white",
                  opacity: !formData.name || !formData.base_url || !formData.default_model ? 0.5 : 1
                },
                children: activeTab === "edit" ? "Update Provider" : "Save Provider"
              }
            )
          ] })
        ] })
      ] })
    ] }),
    deletingId && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
      position: "fixed",
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: "rgba(0,0,0,0.5)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 1100
    }, children: /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
      background: "var(--bg-card)",
      border: "1px solid var(--border)",
      borderRadius: 12,
      padding: 24,
      width: 400
    }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsx("h3", { style: { margin: "0 0 16px" }, children: "Delete Provider?" }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("p", { style: { color: "var(--text-muted)", marginBottom: 24 }, children: "This will permanently remove this LLM provider. This action cannot be undone." }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", gap: 12, justifyContent: "flex-end" }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx(
          "button",
          {
            onClick: () => setDeletingId(null),
            className: "db-btn",
            children: "Cancel"
          }
        ),
        /* @__PURE__ */ jsxRuntimeExports.jsx(
          "button",
          {
            onClick: handleDelete,
            className: "db-btn",
            style: { background: "#ef4444", color: "white" },
            children: "Delete"
          }
        )
      ] })
    ] }) })
  ] });
}
const BACKEND$1 = "";
const API$1 = `${BACKEND$1}/api/v1`;
const LANG_COLORS = {
  TypeScript: "#3178c6",
  JavaScript: "#f7df1e",
  Python: "#3572A5",
  Go: "#00ADD8",
  Rust: "#dea584",
  Java: "#b07219",
  "C++": "#f34b7d",
  Ruby: "#701516",
  Swift: "#F05138",
  Kotlin: "#A97BFF",
  default: "#6e7681"
};
function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const m = Math.floor(diff / 6e4);
  if (m < 2) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d}d ago`;
  return new Date(dateStr).toLocaleDateString();
}
function GitHubPanel({ token, isOpen, onClose, onSelectRepo }) {
  const { connected, githubLogin, loading, connect, repos, reposLoading, fetchRepos, searchRepos, activeRepo, setActiveRepo } = useGitHub();
  const [view, setView] = reactExports.useState("selector");
  const [search, setSearch] = reactExports.useState("");
  const [searchResults, setSearchResults] = reactExports.useState(null);
  const [searchLoading, setSearchLoading] = reactExports.useState(false);
  const [filterPrivate, setFilterPrivate] = reactExports.useState("all");
  const [sortBy, setSortBy] = reactExports.useState("pushed");
  const [dashRepo, setDashRepo] = reactExports.useState(null);
  const [branches, setBranches] = reactExports.useState([]);
  const [issues, setIssues] = reactExports.useState([]);
  const [prs, setPrs] = reactExports.useState([]);
  const [languages, setLanguages] = reactExports.useState({});
  const [dashLoading, setDashLoading] = reactExports.useState(false);
  const searchTimer = reactExports.useRef(null);
  const [createName, setCreateName] = reactExports.useState("");
  const [createDesc, setCreateDesc] = reactExports.useState("");
  const [createPrivate, setCreatePrivate] = reactExports.useState(true);
  const [createInit, setCreateInit] = reactExports.useState(true);
  const [createTemplate, setCreateTemplate] = reactExports.useState("");
  const [creating, setCreating] = reactExports.useState(false);
  const [createError, setCreateError] = reactExports.useState("");
  reactExports.useEffect(() => {
    if (!isOpen) return;
    if (activeRepo) {
      openDashboard(activeRepo);
      return;
    }
    setView("selector");
  }, [isOpen]);
  reactExports.useEffect(() => {
    if (!search.trim()) {
      setSearchResults(null);
      return;
    }
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(async () => {
      setSearchLoading(true);
      const r = await searchRepos(search);
      setSearchResults(r);
      setSearchLoading(false);
    }, 350);
  }, [search]);
  const openDashboard = async (repo) => {
    setDashRepo(repo);
    setView("dashboard");
    setDashLoading(true);
    try {
      const [b, i, p, l] = await Promise.all([
        fetch(`${API$1}/github/repos/${repo.owner}/${repo.name}/branches?token=${encodeURIComponent(token)}`).then((r) => r.ok ? r.json() : []),
        fetch(`${API$1}/github/repos/${repo.owner}/${repo.name}/issues?token=${encodeURIComponent(token)}`).then((r) => r.ok ? r.json() : []),
        fetch(`${API$1}/github/repos/${repo.owner}/${repo.name}/pulls?token=${encodeURIComponent(token)}`).then((r) => r.ok ? r.json() : []),
        fetch(`${API$1}/github/repos/${repo.owner}/${repo.name}/languages?token=${encodeURIComponent(token)}`).then((r) => r.ok ? r.json() : {})
      ]);
      setBranches(b);
      setIssues(i);
      setPrs(p);
      setLanguages(l);
    } finally {
      setDashLoading(false);
    }
  };
  const handleSelectRepo = (repo) => {
    setActiveRepo(repo);
    onSelectRepo(repo);
    onClose();
  };
  const handleCreateRepo = async () => {
    if (!createName.trim()) {
      setCreateError("Repository name is required");
      return;
    }
    setCreating(true);
    setCreateError("");
    try {
      const resp = await fetch(`${API$1}/github/repos?token=${encodeURIComponent(token)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: createName.trim(), description: createDesc, private: createPrivate, auto_init: createInit, gitignore_template: createTemplate })
      });
      if (!resp.ok) {
        const e = await resp.text();
        setCreateError(e);
        return;
      }
      const repo = await resp.json();
      await fetchRepos();
      openDashboard(repo);
    } catch (e) {
      setCreateError(e.message);
    } finally {
      setCreating(false);
    }
  };
  const displayRepos = searchResults ?? repos;
  const filteredRepos = displayRepos.filter((r) => filterPrivate === "all" ? true : filterPrivate === "private" ? r.private : !r.private).sort((a, b) => {
    if (sortBy === "stars") return b.stargazers_count - a.stargazers_count;
    if (sortBy === "name") return a.name.localeCompare(b.name);
    return new Date(b.pushed_at).getTime() - new Date(a.pushed_at).getTime();
  });
  const totalLangBytes = Object.values(languages).reduce((s, v) => s + v, 0);
  if (!isOpen) return null;
  return /* @__PURE__ */ jsxRuntimeExports.jsx(
    "div",
    {
      onClick: onClose,
      style: { position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", backdropFilter: "blur(8px)", zIndex: 300, display: "flex", alignItems: "center", justifyContent: "center", padding: 20, animation: "fadeIn 0.15s ease" },
      children: /* @__PURE__ */ jsxRuntimeExports.jsxs(
        "div",
        {
          onClick: (e) => e.stopPropagation(),
          style: { width: "100%", maxWidth: 720, maxHeight: "90vh", background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", boxShadow: "0 32px 80px rgba(0,0,0,0.6)", display: "flex", flexDirection: "column", overflow: "hidden", animation: "modalContent 0.2s ease" },
          children: [
            /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: "16px 20px", borderBottom: "1px solid var(--border-subtle)", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }, children: [
              /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 10 }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { width: 32, height: 32, borderRadius: 8, background: "linear-gradient(135deg, #24292e, #444d56)", display: "flex", alignItems: "center", justifyContent: "center" }, children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "git", size: 18, style: { color: "white" } }) }),
                /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 14, fontWeight: 700, color: "var(--text)" }, children: "GitHub" }),
                  connected && githubLogin && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { fontSize: 11, color: "var(--text-faint)" }, children: [
                    "@",
                    githubLogin
                  ] })
                ] })
              ] }),
              /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 8 }, children: [
                connected && view === "selector" && /* @__PURE__ */ jsxRuntimeExports.jsxs("button", { onClick: () => setView("create"), style: { fontSize: 12, color: "var(--accent-hover)", background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.25)", borderRadius: "var(--radius-md)", padding: "5px 12px", cursor: "pointer", fontWeight: 600, display: "flex", alignItems: "center", gap: 5 }, children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "plus", size: 12 }),
                  " New repo"
                ] }),
                connected && /* @__PURE__ */ jsxRuntimeExports.jsxs(
                  "button",
                  {
                    onClick: connect,
                    title: "Re-authorize to grant workflow permissions",
                    style: { fontSize: 12, color: "var(--text-muted)", background: "transparent", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: "5px 10px", cursor: "pointer", display: "flex", alignItems: "center", gap: 5 },
                    children: [
                      /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "refresh", size: 12 }),
                      " Reconnect"
                    ]
                  }
                ),
                view !== "selector" && /* @__PURE__ */ jsxRuntimeExports.jsx("button", { onClick: () => setView("selector"), style: { fontSize: 12, color: "var(--text-muted)", background: "transparent", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: "5px 10px", cursor: "pointer" }, children: "← Back" }),
                /* @__PURE__ */ jsxRuntimeExports.jsx("button", { onClick: onClose, style: { background: "none", border: "none", color: "var(--text-faint)", cursor: "pointer", padding: "4px 6px", borderRadius: "var(--radius-sm)", display: "flex" }, onMouseEnter: (e) => {
                  e.currentTarget.style.color = "var(--text)";
                  e.currentTarget.style.background = "rgba(255,255,255,0.06)";
                }, onMouseLeave: (e) => {
                  e.currentTarget.style.color = "var(--text-faint)";
                  e.currentTarget.style.background = "none";
                }, children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "close", size: 16 }) })
              ] })
            ] }),
            /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { flex: 1, minHeight: 0, overflowY: "auto" }, children: [
              !loading && !connected && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "60px 40px", gap: 24, textAlign: "center" }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { width: 64, height: 64, borderRadius: 16, background: "linear-gradient(135deg, #24292e, #444d56)", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 8px 24px rgba(0,0,0,0.4)" }, children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "git", size: 32, style: { color: "white" } }) }),
                /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 20, fontWeight: 700, color: "var(--text)", marginBottom: 8 }, children: "Connect GitHub" }),
                  /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 14, color: "var(--text-dim)", lineHeight: 1.6, maxWidth: 360 }, children: "Let DevBuddy work directly inside your repositories. Read code, create branches, open pull requests — automatically." })
                ] }),
                /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { display: "flex", gap: 12, flexWrap: "wrap", justifyContent: "center" }, children: ["Read repos", "Create branches", "Open PRs", "Manage issues"].map((f) => /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 12, color: "var(--text-faint)", background: "rgba(255,255,255,0.04)", border: "1px solid var(--border-subtle)", borderRadius: 20, padding: "4px 12px" }, children: f }, f)) }),
                /* @__PURE__ */ jsxRuntimeExports.jsxs(
                  "button",
                  {
                    onClick: connect,
                    style: { background: "#24292e", color: "white", border: "none", borderRadius: "var(--radius-md)", padding: "12px 28px", fontSize: 14, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 10, boxShadow: "0 4px 16px rgba(0,0,0,0.4)", transition: "all 0.15s ease" },
                    onMouseEnter: (e) => e.currentTarget.style.background = "#444d56",
                    onMouseLeave: (e) => e.currentTarget.style.background = "#24292e",
                    children: [
                      /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "git", size: 18 }),
                      " Continue with GitHub"
                    ]
                  }
                )
              ] }),
              loading && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", justifyContent: "center", padding: 60, gap: 12, color: "var(--text-faint)", fontSize: 13 }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "loader", size: 16 }),
                " Checking GitHub connection..."
              ] }),
              !loading && connected && view === "selector" && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", flexDirection: "column", gap: 0 }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: "12px 16px", borderBottom: "1px solid var(--border-subtle)", display: "flex", gap: 8, flexWrap: "wrap" }, children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { flex: 1, minWidth: 180, position: "relative" }, children: [
                    /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "command", size: 14, style: { position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-faint)" } }),
                    /* @__PURE__ */ jsxRuntimeExports.jsx(
                      "input",
                      {
                        value: search,
                        onChange: (e) => setSearch(e.target.value),
                        placeholder: "Search repositories...",
                        style: { width: "100%", paddingLeft: 32, paddingRight: 12, paddingTop: 7, paddingBottom: 7, background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", color: "var(--text)", fontSize: 13, outline: "none", boxSizing: "border-box" }
                      }
                    )
                  ] }),
                  /* @__PURE__ */ jsxRuntimeExports.jsxs("select", { value: filterPrivate, onChange: (e) => setFilterPrivate(e.target.value), style: { background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", color: "var(--text)", fontSize: 12, padding: "6px 8px", cursor: "pointer" }, children: [
                    /* @__PURE__ */ jsxRuntimeExports.jsx("option", { value: "all", children: "All" }),
                    /* @__PURE__ */ jsxRuntimeExports.jsx("option", { value: "public", children: "Public" }),
                    /* @__PURE__ */ jsxRuntimeExports.jsx("option", { value: "private", children: "Private" })
                  ] }),
                  /* @__PURE__ */ jsxRuntimeExports.jsxs("select", { value: sortBy, onChange: (e) => setSortBy(e.target.value), style: { background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", color: "var(--text)", fontSize: 12, padding: "6px 8px", cursor: "pointer" }, children: [
                    /* @__PURE__ */ jsxRuntimeExports.jsx("option", { value: "pushed", children: "Recent" }),
                    /* @__PURE__ */ jsxRuntimeExports.jsx("option", { value: "stars", children: "Stars" }),
                    /* @__PURE__ */ jsxRuntimeExports.jsx("option", { value: "name", children: "Name" })
                  ] }),
                  /* @__PURE__ */ jsxRuntimeExports.jsx("button", { onClick: fetchRepos, title: "Refresh", style: { background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", color: "var(--text-muted)", padding: "6px 10px", cursor: "pointer", display: "flex", alignItems: "center" }, children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "loader", size: 13 }) })
                ] }),
                reposLoading || searchLoading ? /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: 32, textAlign: "center", color: "var(--text-faint)", fontSize: 13, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }, children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "loader", size: 14 }),
                  " Loading repositories..."
                ] }) : filteredRepos.length === 0 ? /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { padding: 40, textAlign: "center", color: "var(--text-faint)", fontSize: 13 }, children: search ? "No repositories found" : "No repositories yet" }) : /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { display: "flex", flexDirection: "column" }, children: filteredRepos.map((repo) => /* @__PURE__ */ jsxRuntimeExports.jsx(RepoCard, { repo, onOpen: () => openDashboard(repo), onSelect: () => handleSelectRepo(repo), isActive: (activeRepo == null ? void 0 : activeRepo.id) === repo.id }, repo.id)) })
              ] }),
              connected && view === "create" && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: "24px 28px", display: "flex", flexDirection: "column", gap: 20 }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 16, fontWeight: 700, color: "var(--text)", marginBottom: 6 }, children: "Create a new repository" }),
                  /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 13, color: "var(--text-dim)" }, children: "DevBuddy will initialize it and start working immediately." })
                ] }),
                /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", flexDirection: "column", gap: 14 }, children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsx(Field, { label: "Repository name *", children: /* @__PURE__ */ jsxRuntimeExports.jsx("input", { value: createName, onChange: (e) => setCreateName(e.target.value), placeholder: "my-awesome-project", style: inputStyle }) }),
                  /* @__PURE__ */ jsxRuntimeExports.jsx(Field, { label: "Description", children: /* @__PURE__ */ jsxRuntimeExports.jsx("input", { value: createDesc, onChange: (e) => setCreateDesc(e.target.value), placeholder: "What does this project do?", style: inputStyle }) }),
                  /* @__PURE__ */ jsxRuntimeExports.jsx(Field, { label: ".gitignore template", children: /* @__PURE__ */ jsxRuntimeExports.jsxs("select", { value: createTemplate, onChange: (e) => setCreateTemplate(e.target.value), style: { ...inputStyle, cursor: "pointer" }, children: [
                    /* @__PURE__ */ jsxRuntimeExports.jsx("option", { value: "", children: "None" }),
                    /* @__PURE__ */ jsxRuntimeExports.jsx("option", { value: "Node", children: "Node" }),
                    /* @__PURE__ */ jsxRuntimeExports.jsx("option", { value: "Python", children: "Python" }),
                    /* @__PURE__ */ jsxRuntimeExports.jsx("option", { value: "Go", children: "Go" }),
                    /* @__PURE__ */ jsxRuntimeExports.jsx("option", { value: "Rust", children: "Rust" }),
                    /* @__PURE__ */ jsxRuntimeExports.jsx("option", { value: "Java", children: "Java" })
                  ] }) }),
                  /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", gap: 16 }, children: [
                    /* @__PURE__ */ jsxRuntimeExports.jsxs("label", { style: { display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, color: "var(--text-muted)" }, children: [
                      /* @__PURE__ */ jsxRuntimeExports.jsx("input", { type: "checkbox", checked: createPrivate, onChange: (e) => setCreatePrivate(e.target.checked) }),
                      " Private"
                    ] }),
                    /* @__PURE__ */ jsxRuntimeExports.jsxs("label", { style: { display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, color: "var(--text-muted)" }, children: [
                      /* @__PURE__ */ jsxRuntimeExports.jsx("input", { type: "checkbox", checked: createInit, onChange: (e) => setCreateInit(e.target.checked) }),
                      " Initialize with README"
                    ] })
                  ] }),
                  createError && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 12, color: "var(--error)", background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: "var(--radius-md)", padding: "8px 12px" }, children: createError }),
                  /* @__PURE__ */ jsxRuntimeExports.jsx(
                    "button",
                    {
                      onClick: handleCreateRepo,
                      disabled: creating || !createName.trim(),
                      style: { background: creating || !createName.trim() ? "var(--border)" : "linear-gradient(135deg, var(--accent), var(--accent-hover))", color: creating || !createName.trim() ? "var(--text-faint)" : "white", border: "none", borderRadius: "var(--radius-md)", padding: "11px 24px", fontSize: 13, fontWeight: 600, cursor: creating || !createName.trim() ? "not-allowed" : "pointer", marginTop: 4, display: "flex", alignItems: "center", gap: 8, justifyContent: "center" },
                      children: creating ? /* @__PURE__ */ jsxRuntimeExports.jsxs(jsxRuntimeExports.Fragment, { children: [
                        /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "loader", size: 14 }),
                        " Creating..."
                      ] }) : /* @__PURE__ */ jsxRuntimeExports.jsxs(jsxRuntimeExports.Fragment, { children: [
                        /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "plus", size: 14 }),
                        " Create Repository"
                      ] })
                    }
                  )
                ] })
              ] }),
              connected && view === "dashboard" && dashRepo && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: "20px 24px", display: "flex", flexDirection: "column", gap: 20 }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }, children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { flex: 1, minWidth: 0 }, children: [
                    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 8, marginBottom: 4, flexWrap: "wrap" }, children: [
                      /* @__PURE__ */ jsxRuntimeExports.jsx("img", { src: dashRepo.owner_avatar, alt: "", style: { width: 20, height: 20, borderRadius: "50%" } }),
                      /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { fontSize: 13, color: "var(--text-faint)" }, children: [
                        dashRepo.owner,
                        " /"
                      ] }),
                      /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 14, fontWeight: 700, color: "var(--text)" }, children: dashRepo.name }),
                      /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 10, color: dashRepo.private ? "var(--text-faint)" : "var(--success)", background: dashRepo.private ? "rgba(255,255,255,0.06)" : "rgba(16,185,129,0.1)", border: `1px solid ${dashRepo.private ? "var(--border)" : "rgba(16,185,129,0.2)"}`, borderRadius: 10, padding: "1px 7px", fontWeight: 600 }, children: dashRepo.private ? "Private" : "Public" })
                    ] }),
                    dashRepo.description && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 13, color: "var(--text-dim)", lineHeight: 1.5 }, children: dashRepo.description })
                  ] }),
                  /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", gap: 6, flexShrink: 0 }, children: [
                    /* @__PURE__ */ jsxRuntimeExports.jsxs("a", { href: dashRepo.html_url, target: "_blank", rel: "noopener noreferrer", style: { fontSize: 11, color: "var(--text-muted)", background: "rgba(255,255,255,0.05)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "4px 10px", textDecoration: "none", display: "flex", alignItems: "center", gap: 4 }, children: [
                      /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "folder", size: 11 }),
                      " GitHub ↗"
                    ] }),
                    /* @__PURE__ */ jsxRuntimeExports.jsx(
                      "button",
                      {
                        onClick: () => handleSelectRepo(dashRepo),
                        style: { fontSize: 12, color: "white", background: "linear-gradient(135deg, var(--accent), var(--accent-hover))", border: "none", borderRadius: "var(--radius-md)", padding: "5px 14px", cursor: "pointer", fontWeight: 600 },
                        children: "Work here →"
                      }
                    )
                  ] })
                ] }),
                /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { display: "flex", gap: 16, flexWrap: "wrap" }, children: [
                  { icon: "git", label: "Branch", value: dashRepo.default_branch },
                  { icon: "zap", label: "Stars", value: dashRepo.stargazers_count.toLocaleString() },
                  { icon: "folder", label: "Forks", value: dashRepo.forks_count.toLocaleString() },
                  { icon: "info", label: "Issues", value: dashRepo.open_issues_count.toLocaleString() },
                  { icon: "file", label: "Size", value: dashRepo.size > 1024 ? `${(dashRepo.size / 1024).toFixed(1)}MB` : `${dashRepo.size}KB` }
                ].map((s) => /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", flexDirection: "column", gap: 2, padding: "10px 14px", background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", minWidth: 80 }, children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 10, color: "var(--text-faint)", textTransform: "uppercase", letterSpacing: "0.4px" }, children: s.label }),
                  /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 13, fontWeight: 700, color: "var(--text)" }, children: s.value })
                ] }, s.label)) }),
                dashLoading ? /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: 24, textAlign: "center", color: "var(--text-faint)", fontSize: 13, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }, children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "loader", size: 14 }),
                  " Loading repository details..."
                ] }) : /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }, children: [
                  Object.keys(languages).length > 0 && /* @__PURE__ */ jsxRuntimeExports.jsx(DashCard, { title: "Languages", icon: "file", children: /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { display: "flex", flexDirection: "column", gap: 6 }, children: Object.entries(languages).slice(0, 5).map(([lang, bytes]) => {
                    const pct = Math.round(bytes / totalLangBytes * 100);
                    return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 8 }, children: [
                      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { width: 8, height: 8, borderRadius: "50%", background: LANG_COLORS[lang] || LANG_COLORS.default, flexShrink: 0 } }),
                      /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 12, color: "var(--text-muted)", flex: 1 }, children: lang }),
                      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { width: 60, height: 4, background: "var(--bg-elevated)", borderRadius: 2, overflow: "hidden" }, children: /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { width: `${pct}%`, height: "100%", background: LANG_COLORS[lang] || LANG_COLORS.default } }) }),
                      /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { fontSize: 11, color: "var(--text-faint)", width: 28, textAlign: "right" }, children: [
                        pct,
                        "%"
                      ] })
                    ] }, lang);
                  }) }) }),
                  /* @__PURE__ */ jsxRuntimeExports.jsx(DashCard, { title: `Branches (${branches.length})`, icon: "git", children: branches.length === 0 ? /* @__PURE__ */ jsxRuntimeExports.jsx(Empty, {}) : /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", flexDirection: "column", gap: 4 }, children: [
                    branches.slice(0, 6).map((b) => /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 6, fontSize: 12 }, children: [
                      /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "git", size: 11, style: { color: "var(--text-faint)" } }),
                      /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { color: b.name === dashRepo.default_branch ? "var(--accent-hover)" : "var(--text-muted)", fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }, children: b.name }),
                      b.protected && /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 9, color: "var(--warning)", background: "rgba(245,158,11,0.1)", border: "1px solid rgba(245,158,11,0.2)", borderRadius: 8, padding: "1px 5px" }, children: "protected" }),
                      b.name === dashRepo.default_branch && /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 9, color: "var(--accent-hover)", background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.2)", borderRadius: 8, padding: "1px 5px" }, children: "default" })
                    ] }, b.name)),
                    branches.length > 6 && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { fontSize: 11, color: "var(--text-faint)", marginTop: 2 }, children: [
                      "+",
                      branches.length - 6,
                      " more"
                    ] })
                  ] }) }),
                  /* @__PURE__ */ jsxRuntimeExports.jsx(DashCard, { title: `Open Issues (${issues.length})`, icon: "info", children: issues.length === 0 ? /* @__PURE__ */ jsxRuntimeExports.jsx(Empty, { text: "No open issues" }) : /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", flexDirection: "column", gap: 6 }, children: [
                    issues.slice(0, 4).map((issue) => /* @__PURE__ */ jsxRuntimeExports.jsxs("a", { href: issue.html_url, target: "_blank", rel: "noopener noreferrer", style: { textDecoration: "none", display: "flex", alignItems: "flex-start", gap: 6 }, children: [
                      /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { fontSize: 11, color: "var(--text-faint)", fontFamily: "monospace", flexShrink: 0, marginTop: 1 }, children: [
                        "#",
                        issue.number
                      ] }),
                      /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 12, color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }, children: issue.title })
                    ] }, issue.number)),
                    issues.length > 4 && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { fontSize: 11, color: "var(--text-faint)", marginTop: 2 }, children: [
                      "+",
                      issues.length - 4,
                      " more open"
                    ] })
                  ] }) }),
                  /* @__PURE__ */ jsxRuntimeExports.jsx(DashCard, { title: `Pull Requests (${prs.length})`, icon: "send", children: prs.length === 0 ? /* @__PURE__ */ jsxRuntimeExports.jsx(Empty, { text: "No open PRs" }) : /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", flexDirection: "column", gap: 6 }, children: [
                    prs.slice(0, 4).map((pr) => /* @__PURE__ */ jsxRuntimeExports.jsxs("a", { href: pr.html_url, target: "_blank", rel: "noopener noreferrer", style: { textDecoration: "none", display: "flex", alignItems: "flex-start", gap: 6 }, children: [
                      /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { fontSize: 11, color: "var(--accent-hover)", fontFamily: "monospace", flexShrink: 0, marginTop: 1 }, children: [
                        "#",
                        pr.number
                      ] }),
                      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { flex: 1, minWidth: 0 }, children: [
                        /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 12, color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }, children: pr.title }),
                        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { fontSize: 10, color: "var(--text-faint)" }, children: [
                          pr.head,
                          " → ",
                          pr.base,
                          " ",
                          pr.draft && "· Draft"
                        ] })
                      ] })
                    ] }, pr.number)),
                    prs.length > 4 && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { fontSize: 11, color: "var(--text-faint)", marginTop: 2 }, children: [
                      "+",
                      prs.length - 4,
                      " more open"
                    ] })
                  ] }) })
                ] })
              ] })
            ] })
          ]
        }
      )
    }
  );
}
function RepoCard({ repo, onOpen, onSelect, isActive }) {
  const langColor = LANG_COLORS[repo.language] || LANG_COLORS.default;
  return /* @__PURE__ */ jsxRuntimeExports.jsxs(
    "div",
    {
      onClick: onOpen,
      style: { padding: "12px 16px", borderBottom: "1px solid var(--border-subtle)", cursor: "pointer", display: "flex", alignItems: "center", gap: 12, transition: "background 0.1s", background: isActive ? "rgba(99,102,241,0.06)" : "transparent" },
      onMouseEnter: (e) => {
        if (!isActive) e.currentTarget.style.background = "rgba(255,255,255,0.03)";
      },
      onMouseLeave: (e) => {
        if (!isActive) e.currentTarget.style.background = "transparent";
      },
      children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx("img", { src: repo.owner_avatar, alt: "", style: { width: 28, height: 28, borderRadius: "50%", flexShrink: 0 } }),
        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { flex: 1, minWidth: 0 }, children: [
          /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 6, marginBottom: 2, flexWrap: "wrap" }, children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 13, fontWeight: 600, color: isActive ? "var(--accent-hover)" : "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }, children: repo.name }),
            repo.private && /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 9, color: "var(--text-faint)", background: "rgba(255,255,255,0.06)", border: "1px solid var(--border-subtle)", borderRadius: 8, padding: "1px 6px", flexShrink: 0 }, children: "Private" }),
            repo.fork && /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 9, color: "var(--text-faint)", background: "rgba(255,255,255,0.04)", border: "1px solid var(--border-subtle)", borderRadius: 8, padding: "1px 6px", flexShrink: 0 }, children: "Fork" }),
            repo.archived && /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 9, color: "var(--warning)", background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.2)", borderRadius: 8, padding: "1px 6px", flexShrink: 0 }, children: "Archived" })
          ] }),
          repo.description && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 12, color: "var(--text-faint)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginBottom: 4 }, children: repo.description }),
          /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 10 }, children: [
            repo.language && /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "var(--text-faint)" }, children: [
              /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { width: 8, height: 8, borderRadius: "50%", background: langColor } }),
              repo.language
            ] }),
            repo.stargazers_count > 0 && /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { fontSize: 11, color: "var(--text-faint)" }, children: [
              "★ ",
              repo.stargazers_count
            ] }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 11, color: "var(--text-faint)" }, children: timeAgo(repo.pushed_at) })
          ] })
        ] }),
        /* @__PURE__ */ jsxRuntimeExports.jsx(
          "button",
          {
            onClick: (e) => {
              e.stopPropagation();
              onSelect();
            },
            style: { fontSize: 11, color: "var(--accent-hover)", background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.25)", borderRadius: "var(--radius-sm)", padding: "4px 10px", cursor: "pointer", fontWeight: 600, flexShrink: 0, whiteSpace: "nowrap" },
            children: "Use"
          }
        )
      ]
    }
  );
}
function DashCard({ title, icon, children }) {
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "14px 16px" }, children: [
    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { fontSize: 11, fontWeight: 600, color: "var(--text-faint)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 12, display: "flex", alignItems: "center", gap: 5 }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: icon, size: 11 }),
      " ",
      title
    ] }),
    children
  ] });
}
function Empty({ text = "Nothing here yet" }) {
  return /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 12, color: "var(--text-faint)", textAlign: "center", padding: "8px 0" }, children: text });
}
function Field({ label, children }) {
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", flexDirection: "column", gap: 6 }, children: [
    /* @__PURE__ */ jsxRuntimeExports.jsx("label", { style: { fontSize: 12, fontWeight: 500, color: "var(--text-faint)" }, children: label }),
    children
  ] });
}
const inputStyle = {
  width: "100%",
  background: "var(--bg-card)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-md)",
  padding: "8px 12px",
  color: "var(--text)",
  fontSize: 13,
  outline: "none",
  boxSizing: "border-box"
};
const PHASE_ORDER$1 = ["plan", "read", "execute", "deliver"];
const PHASE_META = {
  plan: { label: "Planning", icon: "brain" },
  read: { label: "Understanding", icon: "book" },
  execute: { label: "Implementing", icon: "code" },
  deliver: { label: "Delivering", icon: "git-pull" }
};
function eventPhase(category) {
  switch (category) {
    case "plan":
    case "think":
    case "analyze":
      return "plan";
    case "context":
    case "search":
    case "read":
    case "observe":
      return "read";
    case "execute":
    case "tool":
    case "test":
    case "reflect":
      return "execute";
    case "branch":
    case "commit":
    case "push":
    case "pr":
    case "done":
      return "deliver";
    case "warn":
    case "error":
    case "step":
    default:
      return "execute";
  }
}
function groupEvents(events) {
  const groups = /* @__PURE__ */ new Map();
  for (const evt of events) {
    const phase = eventPhase(evt.category);
    if (!groups.has(phase)) groups.set(phase, []);
    groups.get(phase).push(evt);
  }
  return PHASE_ORDER$1.map((type) => {
    const evts = groups.get(type) ?? [];
    const hasError = evts.some((e) => e.status === "error");
    const hasRunning = evts.some((e) => e.status === "running");
    const hasDone = evts.some((e) => e.status === "done");
    const status = hasError ? "error" : hasRunning ? "active" : hasDone ? "done" : "pending";
    return { type, ...PHASE_META[type], events: evts, status };
  }).filter((g) => g.events.length > 0);
}
function liveElapsed(startedAt) {
  const ms = Date.now() - startedAt;
  if (ms < 6e4) return `${Math.floor(ms / 1e3)}s`;
  return `${Math.floor(ms / 6e4)}m ${Math.round(ms % 6e4 / 1e3)}s`;
}
function PhaseRow({ group, isLast }) {
  const { label, status, events } = group;
  const isActive = status === "active";
  const isDone = status === "done";
  const isError = status === "error";
  const [expanded, setExpanded] = reactExports.useState(false);
  const canExpand = events.length > 1 && (isDone || isError);
  const latestEvent = events[events.length - 1];
  const summary = isActive && latestEvent ? latestEvent.title : isDone ? `${events.length} steps completed` : isError ? "Issue encountered" : "Waiting...";
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { children: [
    /* @__PURE__ */ jsxRuntimeExports.jsxs(
      "div",
      {
        onClick: () => canExpand && setExpanded((x) => !x),
        style: {
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "6px 0",
          opacity: status === "pending" ? 0.5 : 1,
          transition: "opacity 0.3s ease",
          cursor: canExpand ? "pointer" : "default"
        },
        children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
            width: 8,
            height: 8,
            borderRadius: "50%",
            flexShrink: 0,
            background: isError ? "#ef4444" : isActive ? "#6366f1" : isDone ? "#22c55e" : "var(--border)",
            boxShadow: isActive ? "0 0 8px rgba(99,102,241,0.5)" : "none",
            animation: isActive ? "pulse 2s ease-in-out infinite" : "none"
          } }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { flex: 1, minWidth: 0 }, children: /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
            fontSize: 12.5,
            fontWeight: isActive ? 500 : 400,
            color: isError ? "#ef4444" : isActive ? "var(--text)" : isDone ? "var(--text-muted)" : "var(--text-faint)",
            lineHeight: 1.4
          }, children: [
            label,
            /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: {
              color: isActive ? "var(--text-dim)" : "var(--text-faint)",
              fontWeight: 400,
              marginLeft: 6
            }, children: [
              "— ",
              summary
            ] })
          ] }) }),
          canExpand && /* @__PURE__ */ jsxRuntimeExports.jsx(
            Icon,
            {
              name: "chevron-down",
              size: 11,
              style: {
                color: "var(--text-faint)",
                flexShrink: 0,
                transition: "transform 0.15s ease",
                transform: expanded ? "rotate(180deg)" : "rotate(0deg)"
              }
            }
          ),
          isActive && /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "loader", size: 11, style: { color: "#6366f1", flexShrink: 0 } }),
          isDone && !canExpand && /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "check", size: 11, style: { color: "#22c55e", flexShrink: 0, opacity: 0.7 } })
        ]
      }
    ),
    expanded && canExpand && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
      marginLeft: 18,
      paddingLeft: 12,
      borderLeft: "1px solid var(--border-subtle)",
      display: "flex",
      flexDirection: "column",
      gap: 4,
      animation: "fadeIn 0.15s ease"
    }, children: events.map((evt, i) => /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
      fontSize: 12,
      color: evt.status === "error" ? "#ef4444" : "var(--text-dim)",
      lineHeight: 1.4,
      padding: "2px 0"
    }, children: evt.title }, i)) })
  ] });
}
function ProgressBar({ progress, status }) {
  return /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { height: 2, background: "rgba(255,255,255,0.06)", borderRadius: 1, overflow: "hidden" }, children: /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
    height: "100%",
    width: `${Math.max(2, progress)}%`,
    background: status === "error" ? "#ef4444" : status === "done" ? "#22c55e" : "#6366f1",
    transition: "width 0.4s ease",
    borderRadius: 1
  } }) });
}
function TaskCard$1({ card, userAvatar, userName, isStreaming, onRetry }) {
  const [elapsed2, setElapsed2] = reactExports.useState(() => liveElapsed(card.startedAt));
  const [showAnswer, setShowAnswer] = reactExports.useState(false);
  const eventsEndRef = reactExports.useRef(null);
  reactExports.useEffect(() => {
    if (card.status !== "running") return;
    const t = setInterval(() => setElapsed2(liveElapsed(card.startedAt)), 1e3);
    return () => clearInterval(t);
  }, [card.status, card.startedAt]);
  reactExports.useEffect(() => {
    var _a;
    if (card.status === "running") {
      (_a = eventsEndRef.current) == null ? void 0 : _a.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [card.events.length]);
  reactExports.useEffect(() => {
    if (card.status === "done" && card.answer) {
      const t = setTimeout(() => setShowAnswer(true), 300);
      return () => clearTimeout(t);
    }
  }, [card.status, card.answer]);
  const isRunning = card.status === "running";
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { marginBottom: 32, animation: "messageIn 0.25s ease" }, children: [
    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", gap: 12, marginBottom: 12, justifyContent: "flex-end" }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
        maxWidth: "72%",
        background: "rgba(99,102,241,0.1)",
        border: "1px solid rgba(99,102,241,0.2)",
        borderRadius: "16px 16px 4px 16px",
        padding: "12px 16px"
      }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 14, color: "#e2e8f0", lineHeight: 1.5, whiteSpace: "pre-wrap" }, children: card.task }),
        (card.repo || card.branch) && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }, children: [
          card.repo && /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { fontSize: 11, color: "#818cf8", background: "rgba(99,102,241,0.12)", padding: "2px 8px", borderRadius: 10, display: "flex", alignItems: "center", gap: 4 }, children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "git", size: 10, style: { color: "#818cf8" } }),
            " ",
            card.repo
          ] }),
          card.branch && /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { fontSize: 11, color: "#4ade80", background: "rgba(52,211,153,0.1)", padding: "2px 8px", borderRadius: 10, display: "flex", alignItems: "center", gap: 4 }, children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "branch", size: 10, style: { color: "#4ade80" } }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontFamily: "monospace" }, children: card.branch.replace("devbuddy/", "") })
          ] })
        ] })
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { width: 32, height: 32, borderRadius: "50%", flexShrink: 0, overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(99,102,241,0.2)", border: "2px solid rgba(99,102,241,0.15)" }, children: userAvatar ? /* @__PURE__ */ jsxRuntimeExports.jsx("img", { src: userAvatar, alt: userName || "User", style: { width: "100%", height: "100%", objectFit: "cover" } }) : /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "user", size: 15, style: { color: "#818cf8" } }) })
    ] }),
    (card.events.length > 0 || isRunning) && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", gap: 12 }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
        width: 32,
        height: 32,
        borderRadius: "50%",
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: isRunning ? "linear-gradient(135deg, #6366f1, #818cf8)" : card.status === "error" ? "rgba(239,68,68,0.2)" : "rgba(52,211,153,0.15)",
        border: `2px solid ${isRunning ? "rgba(99,102,241,0.4)" : card.status === "error" ? "rgba(239,68,68,0.3)" : "rgba(52,211,153,0.2)"}`,
        boxShadow: isRunning ? "0 0 12px rgba(99,102,241,0.3)" : "none",
        transition: "all 0.3s"
      }, children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: isRunning ? "loader" : card.status === "error" ? "error" : "check", size: 14, style: { color: isRunning ? "white" : card.status === "error" ? "#ef4444" : "#34d399" } }) }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
        flex: 1,
        minWidth: 0,
        background: "var(--bg-card)",
        border: `1px solid ${isRunning ? "rgba(99,102,241,0.2)" : card.status === "error" ? "rgba(239,68,68,0.2)" : "rgba(52,211,153,0.12)"}`,
        borderRadius: "4px 16px 16px 16px",
        overflow: "hidden",
        transition: "border-color 0.3s",
        boxShadow: isRunning ? "0 4px 20px rgba(99,102,241,0.08)" : "0 2px 12px rgba(0,0,0,0.12)"
      }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: "12px 14px", borderBottom: "1px solid rgba(255,255,255,0.04)" }, children: [
          /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }, children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 12, fontWeight: 600, color: isRunning ? "var(--accent-light)" : card.status === "error" ? "var(--error)" : "var(--success)", flexShrink: 0 }, children: isRunning ? "Working" : card.status === "error" ? "Failed" : "Complete" }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 11, color: "var(--text-faint)" }, children: isRunning ? elapsed2 : card.modifiedFiles && card.modifiedFiles.length > 0 ? `${card.modifiedFiles.length} file${card.modifiedFiles.length !== 1 ? "s" : ""}` : "" })
          ] }),
          (isRunning || card.status === "done" || card.status === "error") && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { marginTop: 10 }, children: /* @__PURE__ */ jsxRuntimeExports.jsx(ProgressBar, { progress: card.progress, status: card.status }) })
        ] }),
        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: "8px 14px", maxHeight: isRunning ? 280 : 220, overflowY: "auto" }, children: [
          (() => {
            const phases = groupEvents(card.events);
            if (phases.length === 0 && isRunning) {
              return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 8, padding: "4px 0" }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { width: 8, height: 8, borderRadius: "50%", background: "#6366f1", animation: "pulse 2s ease-in-out infinite" } }),
                /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 12.5, color: "var(--text-muted)" }, children: "Starting up..." })
              ] });
            }
            return phases.map((g, i) => /* @__PURE__ */ jsxRuntimeExports.jsx(PhaseRow, { group: g, isLast: i === phases.length - 1 }, g.type));
          })(),
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { ref: eventsEndRef })
        ] }),
        card.status === "done" && (card.prUrl || card.commitHash || card.modifiedFiles && card.modifiedFiles.length > 0) && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: "10px 14px", borderTop: "1px solid var(--border-subtle)", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }, children: [
          card.modifiedFiles && card.modifiedFiles.length > 0 && /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { fontSize: 12, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 4 }, children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "file", size: 12 }),
            " ",
            card.modifiedFiles.length,
            " file",
            card.modifiedFiles.length !== 1 ? "s" : ""
          ] }),
          card.prUrl && /* @__PURE__ */ jsxRuntimeExports.jsxs(
            "a",
            {
              href: card.prUrl,
              target: "_blank",
              rel: "noopener noreferrer",
              style: { fontSize: 12, fontWeight: 600, color: "var(--accent-light)", textDecoration: "none", display: "flex", alignItems: "center", gap: 4 },
              children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "git-pull", size: 12 }),
                " Review PR ",
                card.prNumber ? `#${card.prNumber}` : ""
              ]
            }
          ),
          card.commitHash && /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 11, color: "var(--text-dim)", fontFamily: "monospace" }, children: card.commitHash.slice(0, 7) })
        ] }),
        card.status === "error" && onRetry && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { padding: "10px 14px", borderTop: "1px solid rgba(239,68,68,0.15)", display: "flex", alignItems: "center", gap: 8 }, children: /* @__PURE__ */ jsxRuntimeExports.jsxs("button", { onClick: onRetry, className: "db-btn db-focus", style: { fontSize: 12, color: "var(--error)", background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: "var(--radius-md)", padding: "5px 12px", cursor: "pointer" }, children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "refresh", size: 11 }),
          " Retry"
        ] }) })
      ] })
    ] }),
    card.answer && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", gap: 12, marginTop: 12, animation: showAnswer ? "messageIn 0.25s ease" : "none", opacity: showAnswer ? 1 : 0, transition: "opacity 0.3s" }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { width: 32, height: 32, borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(52,211,153,0.15)", border: "2px solid rgba(52,211,153,0.2)" }, children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "bot", size: 15, style: { color: "#34d399" } }) }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { flex: 1, minWidth: 0, background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "4px 16px 16px 16px", padding: "14px 18px" }, children: /* @__PURE__ */ jsxRuntimeExports.jsx(
        Markdown,
        {
          remarkPlugins: [remarkGfm],
          components: {
            code: ({ node, className, children, ...props }) => {
              const inline = !className;
              if (inline) return /* @__PURE__ */ jsxRuntimeExports.jsx("code", { style: { background: "rgba(99,102,241,0.12)", padding: "1px 5px", borderRadius: 4, fontSize: "0.88em", fontFamily: "monospace", color: "#c4b5fd" }, children });
              return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { background: "#0d1117", border: "1px solid #21262d", borderRadius: 8, margin: "10px 0", overflow: "auto" }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { padding: "6px 12px", borderBottom: "1px solid #21262d", fontSize: 11, color: "#6e7681", fontFamily: "monospace" }, children: (className == null ? void 0 : className.replace("language-", "")) || "code" }),
                /* @__PURE__ */ jsxRuntimeExports.jsx("pre", { style: { margin: 0, padding: "12px", fontSize: 13, fontFamily: "monospace", overflowX: "auto", color: "#e6edf3", lineHeight: 1.6 }, children: /* @__PURE__ */ jsxRuntimeExports.jsx("code", { children }) })
              ] });
            },
            pre: ({ children }) => /* @__PURE__ */ jsxRuntimeExports.jsx(jsxRuntimeExports.Fragment, { children }),
            p: ({ children }) => /* @__PURE__ */ jsxRuntimeExports.jsx("p", { style: { fontSize: 14, lineHeight: 1.7, color: "var(--text)", marginBottom: 8, marginTop: 0 }, children }),
            ul: ({ children }) => /* @__PURE__ */ jsxRuntimeExports.jsx("ul", { style: { fontSize: 14, lineHeight: 1.7, color: "var(--text)", paddingLeft: 20, marginBottom: 8 }, children }),
            ol: ({ children }) => /* @__PURE__ */ jsxRuntimeExports.jsx("ol", { style: { fontSize: 14, lineHeight: 1.7, color: "var(--text)", paddingLeft: 20, marginBottom: 8 }, children }),
            li: ({ children }) => /* @__PURE__ */ jsxRuntimeExports.jsx("li", { style: { marginBottom: 4 }, children }),
            strong: ({ children }) => /* @__PURE__ */ jsxRuntimeExports.jsx("strong", { style: { color: "var(--accent-hover)", fontWeight: 600 }, children }),
            a: ({ children, href }) => /* @__PURE__ */ jsxRuntimeExports.jsx("a", { href, style: { color: "var(--accent-hover)", textDecoration: "underline" }, target: "_blank", rel: "noopener noreferrer", children }),
            h1: ({ children }) => /* @__PURE__ */ jsxRuntimeExports.jsx("h1", { style: { fontSize: 18, fontWeight: 700, color: "var(--text)", margin: "12px 0 6px" }, children }),
            h2: ({ children }) => /* @__PURE__ */ jsxRuntimeExports.jsx("h2", { style: { fontSize: 16, fontWeight: 700, color: "var(--text)", margin: "10px 0 4px" }, children }),
            h3: ({ children }) => /* @__PURE__ */ jsxRuntimeExports.jsx("h3", { style: { fontSize: 14, fontWeight: 600, color: "var(--text)", margin: "8px 0 4px" }, children })
          },
          children: card.answer
        }
      ) })
    ] })
  ] });
}
function sseToTaskEvent(type, payload) {
  var _a, _b, _c, _d, _e, _f;
  const id = Math.random().toString(36).slice(2, 9);
  const ts = Date.now();
  switch (type) {
    case "timeline":
      return {
        id,
        ts,
        category: payload.step ?? "step",
        title: payload.message || payload.step,
        status: payload.status === "done" ? "done" : payload.status === "error" ? "error" : payload.status === "warn" ? "warn" : "running",
        durationMs: void 0
      };
    case "thinking":
      return {
        id,
        ts,
        category: "think",
        title: ((_a = payload.thought) == null ? void 0 : _a.slice(0, 100)) ?? "Reasoning…",
        status: "done",
        expandable: ((_b = payload.thought) == null ? void 0 : _b.length) > 100,
        children: payload.thought ? [payload.thought] : void 0
      };
    case "plan":
      return {
        id,
        ts,
        category: "plan",
        title: `Execution plan · ${((_c = payload.steps) == null ? void 0 : _c.length) ?? 0} steps`,
        status: "done",
        expandable: true,
        children: payload.steps ?? []
      };
    case "tool_call":
      return {
        id,
        ts,
        category: "tool",
        title: `${toolLabel(payload.tool)} ${firstParam(payload.params)}`,
        status: "running",
        expandable: false
      };
    case "observation": {
      return {
        id,
        ts,
        category: "observe",
        title: `${toolLabel(payload.tool)} → ${((_d = payload.output) == null ? void 0 : _d.slice(0, 60)) ?? ""}`,
        status: "done",
        expandable: (((_e = payload.output) == null ? void 0 : _e.length) ?? 0) > 60,
        children: payload.output ? [payload.output] : void 0
      };
    }
    case "file_change":
      return {
        id,
        ts,
        category: "execute",
        title: `${payload.action === "create_file" ? "Created" : payload.action === "edit_file" ? "Edited" : "Modified"} ${payload.path}`,
        status: "done"
      };
    case "analysis":
      return {
        id,
        ts,
        category: "analyze",
        title: `Analyzed ${payload.file_count ?? "?"} files`,
        status: "done",
        expandable: !!payload.tree_preview,
        children: payload.tree_preview ? payload.tree_preview.split("\n").slice(0, 20) : void 0
      };
    case "branch":
      return {
        id,
        ts,
        category: "branch",
        title: `Branch ready: ${((_f = payload.name) == null ? void 0 : _f.replace("devbuddy/", "")) ?? ""}`,
        status: "done"
      };
    case "pr":
      return {
        id,
        ts,
        category: "pr",
        title: `Pull Request #${payload.number} opened`,
        status: "done",
        expandable: !!payload.url,
        children: payload.url ? [payload.url] : void 0
      };
    case "runner":
      return {
        id,
        ts,
        category: "step",
        title: payload.message ?? payload.state ?? "Runner",
        status: payload.state === "completed" || payload.state === "destroyed" ? "done" : payload.state === "queued" ? "skip" : "running",
        detail: payload.run_url
      };
    case "quality_gates":
      return null;
    // handled separately on the card data
    case "log":
      return {
        id,
        ts,
        category: "observe",
        title: payload.message ?? "",
        status: "done",
        expandable: false
      };
    case "step":
      return {
        id,
        ts,
        category: "step",
        title: payload.message ?? payload.agent ?? "Step",
        status: "running"
      };
    case "error":
      return {
        id,
        ts,
        category: "error",
        title: payload.message ?? "Error",
        status: "error"
      };
    case "done":
      return {
        id,
        ts,
        category: "done",
        title: payload.summary ?? "Task complete",
        status: "done"
      };
    default:
      return null;
  }
}
function toolLabel(tool) {
  const map = {
    read_file: "Reading",
    write_file: "Writing",
    edit_file: "Editing",
    create_file: "Creating",
    list_files: "Listing",
    search_code: "Searching",
    run_command: "Running",
    delete_file: "Deleting"
  };
  return map[tool] ?? tool.replace("_", " ");
}
function firstParam(params = {}) {
  const v = Object.values(params)[0] ?? "";
  return v.length > 40 ? v.slice(0, 40) + "…" : v;
}
const PHASE_ORDER = [
  "understanding",
  "planning",
  "implementing",
  "validating",
  "delivering",
  "completed"
];
const THINKING_MESSAGES = {
  understanding: [
    "Analyzing project structure...",
    "Reviewing existing implementation...",
    "Understanding requirements...",
    "Identifying affected components..."
  ],
  planning: [
    "Comparing implementation patterns...",
    "Planning minimal change set...",
    "Designing test strategy...",
    "Evaluating edge cases..."
  ],
  implementing: [
    "Preparing isolated workspace...",
    "Updating configuration...",
    "Implementing core logic...",
    "Adding error handling..."
  ],
  validating: [
    "Running test suite...",
    "Checking code coverage...",
    "Validating edge cases...",
    "Verifying no regressions..."
  ],
  delivering: [
    "Preparing commit message...",
    "Creating pull request...",
    "Adding PR description...",
    "Requesting review..."
  ],
  completed: [
    "Task completed successfully"
  ]
};
function formatDuration(seconds) {
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}
function formatTimeAgo(dateStr) {
  const date = new Date(dateStr);
  const now = /* @__PURE__ */ new Date();
  const diff = Math.floor((now.getTime() - date.getTime()) / 1e3);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
  return `${Math.floor(diff / 86400)} days ago`;
}
function PhaseStepper({
  phases,
  currentPhase,
  expandedPhase,
  onPhaseClick
}) {
  const currentIndex = PHASE_ORDER.indexOf(currentPhase);
  return /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
    display: "flex",
    alignItems: "center",
    gap: 4,
    padding: "10px 0"
  }, children: PHASE_ORDER.map((phaseId, index) => {
    phases.find((p) => p.id === phaseId);
    const isCompleted = index < currentIndex;
    const isActive = phaseId === currentPhase;
    return /* @__PURE__ */ jsxRuntimeExports.jsx(
      "div",
      {
        onClick: () => onPhaseClick(phaseId),
        style: {
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          cursor: "pointer",
          flex: 1
        },
        children: /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
          width: 10,
          height: 10,
          borderRadius: "50%",
          background: isCompleted ? "#22c55e" : isActive ? "#6366f1" : "var(--border)",
          border: isActive ? "2px solid #6366f1" : "none",
          transition: "all 200ms ease-in-out",
          boxShadow: isActive ? "0 0 8px rgba(99, 102, 241, 0.4)" : "none"
        } })
      },
      phaseId
    );
  }) });
}
function LiveThinking({ phase }) {
  var _a, _b;
  if (phase.status !== "active") return null;
  const message = ((_a = phase.thinking) == null ? void 0 : _a[phase.thinking.length - 1]) || ((_b = THINKING_MESSAGES[phase.id]) == null ? void 0 : _b[0]) || "Working...";
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "6px 0",
    fontSize: 13,
    color: "var(--accent-light)"
  }, children: [
    /* @__PURE__ */ jsxRuntimeExports.jsx(
      "div",
      {
        className: "pulse",
        style: {
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: "var(--accent)"
        }
      }
    ),
    /* @__PURE__ */ jsxRuntimeExports.jsx("span", { children: message })
  ] });
}
function PhaseDetails({ phase }) {
  if (!phase.files || phase.files.length === 0) {
    return /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
      padding: 16,
      color: "var(--text-muted)",
      fontSize: 13,
      textAlign: "center"
    }, children: phase.status === "active" ? /* @__PURE__ */ jsxRuntimeExports.jsx(LiveThinking, { phase }) : phase.status === "pending" ? "Waiting to start..." : "No details available" });
  }
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: 12 }, children: [
    phase.status === "active" && phase.currentFile && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
      marginBottom: 16,
      padding: 12,
      background: "rgba(99, 102, 241, 0.05)",
      borderRadius: 8,
      border: "1px solid rgba(99, 102, 241, 0.2)"
    }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
        fontSize: 11,
        textTransform: "uppercase",
        color: "#6366f1",
        fontWeight: 600,
        marginBottom: 4
      }, children: "Currently Working" }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
        fontSize: 14,
        fontFamily: "monospace",
        color: "var(--text)"
      }, children: phase.currentFile }),
      /* @__PURE__ */ jsxRuntimeExports.jsx(LiveThinking, { phase })
    ] }),
    /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
      display: "flex",
      flexDirection: "column",
      gap: 4
    }, children: phase.files.map((file, i) => /* @__PURE__ */ jsxRuntimeExports.jsxs(
      "div",
      {
        style: {
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "6px 10px",
          borderRadius: 6,
          background: "var(--bg-hover)",
          fontSize: 13,
          fontFamily: "monospace"
        },
        children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: {
            color: file.status === "created" ? "#22c55e" : file.status === "deleted" ? "#ef4444" : "#6366f1",
            fontWeight: 600,
            fontSize: 11,
            textTransform: "uppercase"
          }, children: file.status === "created" ? "+" : file.status === "deleted" ? "−" : "•" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: {
            flex: 1,
            color: "var(--text)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap"
          }, children: file.path }),
          (file.additions || file.deletions) && /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: {
            fontSize: 11,
            color: "var(--text-muted)"
          }, children: [
            /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { color: "#22c55e" }, children: [
              "+",
              file.additions || 0
            ] }),
            " ",
            /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { color: "#ef4444" }, children: [
              "-",
              file.deletions || 0
            ] })
          ] })
        ]
      },
      i
    )) }),
    phase.stats && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
      marginTop: 12,
      paddingTop: 12,
      borderTop: "1px solid var(--border)",
      display: "flex",
      gap: 16,
      fontSize: 12,
      color: "var(--text-muted)"
    }, children: [
      phase.stats.filesChanged !== void 0 && /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { children: [
        phase.stats.filesChanged,
        " files"
      ] }),
      phase.stats.duration !== void 0 && /* @__PURE__ */ jsxRuntimeExports.jsx("span", { children: formatDuration(phase.stats.duration) })
    ] })
  ] });
}
function TaskCard({ task, expandedPhase, onPhaseClick }) {
  const isCompleted = task.status === "completed";
  const isError = task.status === "error";
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
    background: "var(--bg-card)",
    border: `1px solid ${isError ? "#ef4444" : isCompleted ? "#22c55e" : "var(--border)"}`,
    borderRadius: 12,
    overflow: "hidden",
    transition: "all 200ms ease-in-out",
    boxShadow: isError ? "0 0 0 1px rgba(239, 68, 68, 0.2)" : isCompleted ? "0 0 0 1px rgba(34, 197, 94, 0.2)" : "none"
  }, children: [
    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
      padding: "16px 20px",
      borderBottom: "1px solid var(--border)"
    }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        marginBottom: 8
      }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx("h3", { style: {
          margin: 0,
          fontSize: 16,
          fontWeight: 600,
          color: "var(--text)",
          lineHeight: 1.4
        }, children: task.title }),
        /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: {
          padding: "4px 10px",
          borderRadius: 20,
          fontSize: 11,
          fontWeight: 600,
          textTransform: "uppercase",
          background: isError ? "rgba(239, 68, 68, 0.1)" : isCompleted ? "rgba(34, 197, 94, 0.1)" : "rgba(99, 102, 241, 0.1)",
          color: isError ? "#ef4444" : isCompleted ? "#22c55e" : "#6366f1"
        }, children: isError ? "Error" : isCompleted ? "Completed" : "Working" })
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
        display: "flex",
        alignItems: "center",
        gap: 12,
        fontSize: 13,
        color: "var(--text-muted)"
      }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { display: "flex", alignItems: "center", gap: 4 }, children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "repo", size: 14 }),
          task.repository.name
        ] }),
        /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { display: "flex", alignItems: "center", gap: 4 }, children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "git-branch", size: 14 }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("code", { style: {
            fontFamily: "monospace",
            background: "var(--bg-hover)",
            padding: "2px 6px",
            borderRadius: 4,
            fontSize: 12
          }, children: task.branch.replace("devbuddy/", "") })
        ] }),
        /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { children: [
          "Started ",
          formatTimeAgo(task.startedAt)
        ] })
      ] })
    ] }),
    /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { padding: "0 20px" }, children: /* @__PURE__ */ jsxRuntimeExports.jsx(
      PhaseStepper,
      {
        phases: task.phases,
        currentPhase: task.currentPhase,
        expandedPhase,
        onPhaseClick
      }
    ) }),
    expandedPhase && /* @__PURE__ */ jsxRuntimeExports.jsx(
      "div",
      {
        className: "expand-animation",
        style: {
          borderTop: "1px solid var(--border)",
          background: "rgba(0, 0, 0, 0.02)"
        },
        children: /* @__PURE__ */ jsxRuntimeExports.jsx(
          PhaseDetails,
          {
            phase: task.phases.find((p) => p.id === expandedPhase)
          }
        )
      }
    ),
    isCompleted && task.summary && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
      padding: "16px 20px",
      borderTop: "1px solid var(--border)",
      background: "rgba(34, 197, 94, 0.03)"
    }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
        display: "flex",
        gap: 24,
        fontSize: 13
      }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 6 }, children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "file", size: 14, color: "#22c55e" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontWeight: 600 }, children: task.summary.filesChanged }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { color: "var(--text-muted)" }, children: "files" })
        ] }),
        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 6 }, children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "check", size: 14, color: "#22c55e" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontWeight: 600 }, children: task.summary.testsPassed }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { color: "var(--text-muted)" }, children: "tests" })
        ] }),
        task.summary.prNumber && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 6 }, children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "git-pull", size: 14, color: "#6366f1" }),
          /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { fontWeight: 600 }, children: [
            "#",
            task.summary.prNumber
          ] })
        ] })
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
        display: "flex",
        gap: 12,
        marginTop: 16
      }, children: [
        task.summary.prUrl && /* @__PURE__ */ jsxRuntimeExports.jsx(
          "a",
          {
            href: task.summary.prUrl,
            target: "_blank",
            rel: "noopener noreferrer",
            className: "db-btn",
            style: {
              padding: "8px 16px",
              background: "#6366f1",
              color: "#fff",
              textDecoration: "none",
              fontSize: 13,
              fontWeight: 500
            },
            children: "Review PR →"
          }
        ),
        /* @__PURE__ */ jsxRuntimeExports.jsx(
          "button",
          {
            className: "db-btn",
            style: {
              padding: "8px 16px",
              fontSize: 13
            },
            children: "Continue Working →"
          }
        )
      ] })
    ] })
  ] });
}
function EngineeringTimeline({ tasks }) {
  const [expandedPhase, setExpandedPhase] = reactExports.useState(null);
  const handlePhaseClick = (phase) => {
    setExpandedPhase(expandedPhase === phase ? null : phase);
  };
  if (tasks.length === 0) {
    return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
      padding: 40,
      textAlign: "center",
      color: "var(--text-muted)"
    }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "clock", size: 48, style: { marginBottom: 16, opacity: 0.5 } }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("p", { children: "No active engineering tasks" }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("p", { style: { fontSize: 13, marginTop: 8 }, children: "Start a conversation to begin engineering work" })
    ] });
  }
  return /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
    display: "flex",
    flexDirection: "column",
    gap: 16,
    padding: 16
  }, children: tasks.map((task) => /* @__PURE__ */ jsxRuntimeExports.jsx(
    TaskCard,
    {
      task,
      expandedPhase,
      onPhaseClick: handlePhaseClick
    },
    task.id
  )) });
}
var jszip_minExports = requireJszip_min();
const JSZip = /* @__PURE__ */ getDefaultExportFromCjs(jszip_minExports);
let toastListeners = [];
function toast(message, type = "info") {
  const t = { id: crypto.randomUUID(), message, type };
  toastListeners.forEach((l) => l(t));
}
function ToastContainer() {
  const [toasts, setToasts] = reactExports.useState([]);
  reactExports.useEffect(() => {
    const handler = (t) => {
      setToasts((prev) => [...prev, t]);
      const duration = t.type === "error" ? 6e3 : t.type === "success" ? 4e3 : 3e3;
      setTimeout(() => {
        setToasts((prev) => prev.filter((x) => x.id !== t.id));
      }, duration);
    };
    toastListeners.push(handler);
    return () => {
      toastListeners = toastListeners.filter((l) => l !== handler);
    };
  }, []);
  const dismiss = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };
  if (toasts.length === 0) return null;
  return /* @__PURE__ */ jsxRuntimeExports.jsxs(
    "div",
    {
      role: "status",
      "aria-live": "polite",
      "aria-atomic": "true",
      style: {
        position: "fixed",
        top: 20,
        right: 20,
        zIndex: 200,
        display: "flex",
        flexDirection: "column",
        gap: 8
      },
      children: [
        toasts.map((t) => /* @__PURE__ */ jsxRuntimeExports.jsxs(
          "div",
          {
            role: "alert",
            style: {
              background: t.type === "error" ? "rgba(239,68,68,0.9)" : t.type === "success" ? "rgba(16,185,129,0.9)" : "rgba(99,102,241,0.9)",
              backdropFilter: "blur(8px)",
              color: "white",
              padding: "10px 14px",
              borderRadius: 10,
              fontSize: 13,
              fontWeight: 500,
              boxShadow: "0 4px 16px rgba(0,0,0,0.3)",
              animation: "toastIn 0.3s ease",
              maxWidth: 340,
              display: "flex",
              alignItems: "flex-start",
              gap: 10
            },
            children: [
              /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { flex: 1, lineHeight: 1.4 }, children: t.message }),
              /* @__PURE__ */ jsxRuntimeExports.jsx(
                "button",
                {
                  onClick: () => dismiss(t.id),
                  "aria-label": "Dismiss notification",
                  style: {
                    background: "none",
                    border: "none",
                    color: "rgba(255,255,255,0.7)",
                    cursor: "pointer",
                    padding: 2,
                    fontSize: 12,
                    flexShrink: 0,
                    marginTop: 1
                  },
                  children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "close", size: 12 })
                }
              )
            ]
          },
          t.id
        )),
        /* @__PURE__ */ jsxRuntimeExports.jsx("style", { children: `
        @keyframes toastIn {
          from { opacity: 0; transform: translateX(30px); }
          to { opacity: 1; transform: translateX(0); }
        }
      ` })
      ]
    }
  );
}
function TypingIndicator() {
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
    display: "flex",
    gap: 12,
    marginBottom: 24,
    animation: "fadeIn 0.3s ease"
  }, children: [
    /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
      width: 28,
      height: 28,
      borderRadius: "50%",
      background: "linear-gradient(135deg, #6366f1, #818cf8)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0
    }, children: /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 12 }, children: "🤖" }) }),
    /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
      background: "var(--db-bg-card)",
      border: "1px solid var(--db-border)",
      borderRadius: "var(--radius-lg)",
      padding: "14px 18px",
      display: "flex",
      alignItems: "center",
      gap: 6
    }, children: [0, 1, 2].map((i) => /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
      width: 7,
      height: 7,
      borderRadius: "50%",
      background: "var(--db-text-faint)",
      animation: `typing-dot 1.4s ease-in-out ${i * 0.16}s infinite`
    } }, i)) })
  ] });
}
function CommandPalette({ isOpen, onClose, commands, conversations = [], onSelectConversation }) {
  const [query, setQuery] = reactExports.useState("");
  const [selectedIndex, setSelectedIndex] = reactExports.useState(0);
  const inputRef = reactExports.useRef(null);
  const listRef = reactExports.useRef(null);
  const q = query.trim().toLowerCase();
  const filteredCommands = reactExports.useMemo(
    () => q ? commands.filter((c) => c.label.toLowerCase().includes(q)) : commands,
    [commands, q]
  );
  const filteredConversations = reactExports.useMemo(
    () => q ? conversations.filter((c) => c.title.toLowerCase().includes(q)) : conversations.slice(0, 5),
    [conversations, q]
  );
  const items = reactExports.useMemo(() => {
    const list = [];
    filteredCommands.forEach((c, i) => list.push({ type: "command", index: i, data: c }));
    filteredConversations.forEach((c, i) => list.push({ type: "conversation", index: i, data: c }));
    return list;
  }, [filteredCommands, filteredConversations]);
  reactExports.useEffect(() => {
    setSelectedIndex(0);
  }, [query]);
  reactExports.useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => {
        var _a;
        return (_a = inputRef.current) == null ? void 0 : _a.focus();
      }, 50);
    }
  }, [isOpen]);
  reactExports.useEffect(() => {
    if (listRef.current) {
      const selectedEl = listRef.current.querySelector('[data-selected="true"]');
      if (selectedEl) {
        selectedEl.scrollIntoView({ block: "nearest" });
      }
    }
  }, [selectedIndex]);
  const handleKeyDown = reactExports.useCallback((e) => {
    if (e.key === "Escape") {
      onClose();
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => (i + 1) % items.length);
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => (i - 1 + items.length) % items.length);
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      const item = items[selectedIndex];
      if (!item) return;
      if (item.type === "command") {
        item.data.action();
      } else {
        onSelectConversation == null ? void 0 : onSelectConversation(item.data.id);
      }
      onClose();
      return;
    }
  }, [items, selectedIndex, onClose, onSelectConversation]);
  if (!isOpen) return null;
  const renderSectionHeader = (label, icon) => /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: "6px 12px 4px", fontSize: 10, color: "var(--text-faint)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: 700, display: "flex", alignItems: "center", gap: 6 }, children: [
    /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: icon, size: 10 }),
    " ",
    label
  ] });
  const selectedId = items[selectedIndex] ? `cmd-item-${items[selectedIndex].type}-${items[selectedIndex].index}` : void 0;
  return /* @__PURE__ */ jsxRuntimeExports.jsx("div", { role: "dialog", "aria-modal": "true", "aria-label": "Command palette", style: { position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.5)", backdropFilter: "blur(6px)", zIndex: 200, display: "flex", alignItems: "flex-start", justifyContent: "center", paddingTop: "12vh", animation: "fadeIn 0.15s ease" }, onClick: onClose, children: /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { width: "100%", maxWidth: 560, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", boxShadow: "0 24px 64px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04)", overflow: "hidden", animation: "modalContent 0.2s ease" }, onClick: (e) => e.stopPropagation(), children: [
    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: "14px 18px", borderBottom: "1px solid var(--border-subtle)", display: "flex", alignItems: "center", gap: 12 }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "search", size: 18, style: { color: "var(--text-faint)" } }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("input", { ref: inputRef, value: query, onChange: (e) => setQuery(e.target.value), onKeyDown: handleKeyDown, placeholder: "Search commands, conversations, files...", "aria-label": "Search commands and conversations", "aria-autocomplete": "list", "aria-controls": "cmd-results", "aria-activedescendant": selectedId, style: { flex: 1, background: "none", border: "none", outline: "none", color: "var(--text)", fontSize: 16, fontFamily: "inherit" } }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 11, color: "var(--text-faint)", background: "var(--bg-card)", padding: "3px 8px", borderRadius: "var(--radius-sm)", fontFamily: "monospace" }, children: "ESC" })
    ] }),
    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { ref: listRef, id: "cmd-results", role: "listbox", "aria-label": "Results", style: { maxHeight: 380, overflowY: "auto", padding: "6px" }, children: [
      items.length === 0 && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { role: "status", "aria-live": "polite", style: { padding: "32px", textAlign: "center" }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "search", size: 32, style: { color: "var(--border)", marginBottom: 12 } }),
        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { color: "var(--text-faint)", fontSize: 14 }, children: [
          'No results for "',
          query,
          '"'
        ] })
      ] }),
      filteredCommands.length > 0 && /* @__PURE__ */ jsxRuntimeExports.jsxs(jsxRuntimeExports.Fragment, { children: [
        renderSectionHeader("Actions", "zap"),
        filteredCommands.map((cmd, i) => {
          const globalIndex = items.findIndex((it) => it.type === "command" && it.index === i);
          const isSelected = globalIndex === selectedIndex;
          return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { id: `cmd-item-command-${i}`, role: "option", "aria-selected": isSelected, tabIndex: -1, "data-selected": isSelected, onClick: () => {
            cmd.action();
            onClose();
          }, onMouseEnter: () => setSelectedIndex(globalIndex), style: { display: "flex", alignItems: "center", gap: 12, padding: "10px 12px", borderRadius: "var(--radius-md)", cursor: "pointer", background: isSelected ? "rgba(99,102,241,0.12)" : "transparent", border: isSelected ? "1px solid rgba(99,102,241,0.2)" : "1px solid transparent", transition: "all 0.08s ease" }, children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: cmd.icon, size: 18, style: { color: isSelected ? "var(--accent-hover)" : "var(--text-dim)" } }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { flex: 1, fontSize: 14, color: "var(--text)" }, children: cmd.label }),
            cmd.shortcut && /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 11, color: "var(--text-faint)", background: "var(--bg-card)", padding: "2px 8px", borderRadius: "var(--radius-sm)", fontFamily: "monospace" }, children: cmd.shortcut })
          ] }, cmd.id);
        })
      ] }),
      filteredConversations.length > 0 && /* @__PURE__ */ jsxRuntimeExports.jsxs(jsxRuntimeExports.Fragment, { children: [
        renderSectionHeader("Conversations", "chat"),
        filteredConversations.map((conv, i) => {
          const globalIndex = items.findIndex((it) => it.type === "conversation" && it.index === i);
          const isSelected = globalIndex === selectedIndex;
          return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { id: `cmd-item-conversation-${i}`, role: "option", "aria-selected": isSelected, tabIndex: -1, "data-selected": isSelected, onClick: () => {
            onSelectConversation == null ? void 0 : onSelectConversation(conv.id);
            onClose();
          }, onMouseEnter: () => setSelectedIndex(globalIndex), style: { display: "flex", alignItems: "center", gap: 12, padding: "10px 12px", borderRadius: "var(--radius-md)", cursor: "pointer", background: isSelected ? "rgba(99,102,241,0.12)" : "transparent", border: isSelected ? "1px solid rgba(99,102,241,0.2)" : "1px solid transparent", transition: "all 0.08s ease" }, children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { width: 28, height: 28, borderRadius: "50%", background: isSelected ? `hsl(${conv.title.split("").reduce((a, ch) => a + ch.charCodeAt(0), 0) % 360}, 70%, 55%)` : `hsl(${conv.title.split("").reduce((a, ch) => a + ch.charCodeAt(0), 0) % 360}, 50%, 20%)`, border: isSelected ? "none" : "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, color: "white", flexShrink: 0 }, children: conv.title.charAt(0).toUpperCase() }),
            /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { flex: 1, minWidth: 0 }, children: [
              /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 14, color: "var(--text)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }, children: conv.title }),
              /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { fontSize: 11, color: "var(--text-faint)" }, children: [
                conv.messageCount,
                " message",
                conv.messageCount !== 1 ? "s" : ""
              ] })
            ] }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { color: isSelected ? "var(--accent-hover)" : "var(--text-faint)", opacity: isSelected ? 1 : 0, fontSize: 14 }, children: "→" })
          ] }, conv.id);
        })
      ] })
    ] }),
    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: "8px 16px", borderTop: "1px solid var(--border-subtle)", display: "flex", alignItems: "center", gap: 16, fontSize: 11, color: "var(--text-faint)" }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx("kbd", { style: { background: "var(--bg-card)", padding: "1px 5px", borderRadius: "var(--radius-sm)", fontFamily: "monospace", border: "1px solid var(--border)" }, children: "↑↓" }),
        " Navigate"
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx("kbd", { style: { background: "var(--bg-card)", padding: "1px 5px", borderRadius: "var(--radius-sm)", fontFamily: "monospace", border: "1px solid var(--border)" }, children: "↵" }),
        " Select"
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx("kbd", { style: { background: "var(--bg-card)", padding: "1px 5px", borderRadius: "var(--radius-sm)", fontFamily: "monospace", border: "1px solid var(--border)" }, children: "esc" }),
        " Close"
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { flex: 1 } }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { children: [
        items.length,
        " results"
      ] })
    ] })
  ] }) });
}
function WorkspacePanel({ files, onDownload, onDownloadOne, isOpen, onToggle }) {
  const [selectedFile, setSelectedFile] = reactExports.useState(null);
  const [expanded, setExpanded] = reactExports.useState(true);
  const selected = files.find((f) => f.name === selectedFile);
  if (!isOpen) {
    return /* @__PURE__ */ jsxRuntimeExports.jsxs(
      "button",
      {
        onClick: onToggle,
        className: "db-btn",
        title: "Workspace",
        style: {
          position: "fixed",
          right: 16,
          top: "50%",
          transform: "translateY(-50%)",
          width: 36,
          height: 36,
          borderRadius: "50%",
          background: files.length > 0 ? "rgba(99,102,241,0.15)" : "rgba(255,255,255,0.04)",
          border: files.length > 0 ? "1px solid rgba(99,102,241,0.3)" : "1px solid #2a2d3a",
          color: files.length > 0 ? "#818cf8" : "#6b7280",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 16,
          zIndex: 30,
          transition: "all var(--transition-base)"
        },
        onMouseEnter: (e) => {
          e.currentTarget.style.background = "rgba(99,102,241,0.2)";
          e.currentTarget.style.transform = "translateY(-50%) scale(1.1)";
        },
        onMouseLeave: (e) => {
          e.currentTarget.style.background = files.length > 0 ? "rgba(99,102,241,0.15)" : "rgba(255,255,255,0.04)";
          e.currentTarget.style.transform = "translateY(-50%) scale(1)";
        },
        children: [
          "📁",
          files.length > 0 && /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: {
            position: "absolute",
            top: -4,
            right: -4,
            width: 16,
            height: 16,
            borderRadius: "50%",
            background: "#6366f1",
            color: "white",
            fontSize: 10,
            fontWeight: 700,
            display: "flex",
            alignItems: "center",
            justifyContent: "center"
          }, children: files.length })
        ]
      }
    );
  }
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
    width: 340,
    background: "#111318",
    borderLeft: "1px solid #1e2130",
    display: "flex",
    flexDirection: "column",
    flexShrink: 0,
    animation: "slideInRight 0.25s ease"
  }, children: [
    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: "14px 16px", borderBottom: "1px solid #1e2130", display: "flex", alignItems: "center", justifyContent: "space-between" }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { fontSize: 13, fontWeight: 700, color: "#e4e6eb", display: "flex", alignItems: "center", gap: 8 }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx("span", { children: "📁" }),
        " Workspace",
        files.length > 0 && /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { fontSize: 11, color: "#6b7280", fontWeight: 400 }, children: [
          "(",
          files.length,
          ")"
        ] })
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("button", { onClick: onToggle, className: "db-btn", style: { background: "none", border: "none", color: "#4b4f63", cursor: "pointer", fontSize: 16, padding: "2px 6px", borderRadius: "var(--radius-sm)" }, children: "×" })
    ] }),
    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { flex: 1, overflowY: "auto", padding: "8px" }, children: [
      files.length === 0 && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: 24, textAlign: "center" }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 32, marginBottom: 8 }, children: "📂" }),
        /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 13, color: "#6b7280" }, children: "No files yet" }),
        /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 12, color: "#4b4f63", marginTop: 4 }, children: "Ask DevBuddy to build something" })
      ] }),
      files.map((file) => /* @__PURE__ */ jsxRuntimeExports.jsxs(
        "div",
        {
          onClick: () => {
            setSelectedFile(file.name);
            setExpanded(true);
          },
          className: "db-btn",
          style: {
            padding: "8px 10px",
            borderRadius: "var(--radius-md)",
            cursor: "pointer",
            marginBottom: 2,
            background: selectedFile === file.name ? "rgba(99,102,241,0.1)" : "transparent",
            border: selectedFile === file.name ? "1px solid rgba(99,102,241,0.2)" : "1px solid transparent",
            display: "flex",
            alignItems: "center",
            gap: 8,
            transition: "all var(--transition-fast)"
          },
          children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 14 }, children: "📄" }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { flex: 1, fontSize: 12, color: selectedFile === file.name ? "#c7d2fe" : "#9ca3af", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }, children: file.name }),
            /* @__PURE__ */ jsxRuntimeExports.jsx(
              "button",
              {
                onClick: (e) => {
                  e.stopPropagation();
                  onDownloadOne(file);
                },
                className: "db-btn",
                title: "Download",
                style: { background: "none", border: "none", color: "#4b4f63", cursor: "pointer", fontSize: 12, padding: "2px 6px", borderRadius: "var(--radius-sm)", transition: "all var(--transition-fast)" },
                onMouseEnter: (e) => {
                  e.currentTarget.style.color = "#818cf8";
                },
                onMouseLeave: (e) => {
                  e.currentTarget.style.color = "#4b4f63";
                },
                children: "↓"
              }
            )
          ]
        },
        file.name
      ))
    ] }),
    selected && expanded && selected.content && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
      borderTop: "1px solid #1e2130",
      maxHeight: 300,
      display: "flex",
      flexDirection: "column",
      animation: "fadeIn 0.2s ease"
    }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: "8px 12px", borderBottom: "1px solid #1e2130", display: "flex", alignItems: "center", justifyContent: "space-between" }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 11, color: "#6b7280", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }, children: selected.name }),
        /* @__PURE__ */ jsxRuntimeExports.jsx("button", { onClick: () => setExpanded(false), className: "db-btn", style: { background: "none", border: "none", color: "#4b4f63", cursor: "pointer", fontSize: 12 }, children: "−" })
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("pre", { style: {
        flex: 1,
        overflow: "auto",
        padding: 12,
        margin: 0,
        fontSize: 12,
        lineHeight: 1.5,
        color: "#9ca3af",
        background: "#0d0f14",
        fontFamily: "monospace"
      }, children: [
        selected.content.slice(0, 2e3),
        selected.content.length > 2e3 ? "\n\n... (truncated)" : ""
      ] })
    ] }),
    files.length > 0 && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { padding: "10px 12px", borderTop: "1px solid #1e2130", display: "flex", gap: 8 }, children: /* @__PURE__ */ jsxRuntimeExports.jsx(
      "button",
      {
        onClick: () => onDownload(files),
        className: "db-btn db-focus",
        style: {
          flex: 1,
          padding: "6px 10px",
          background: "rgba(99,102,241,0.12)",
          border: "1px solid rgba(99,102,241,0.3)",
          borderRadius: "var(--radius-md)",
          color: "#818cf8",
          fontSize: 12,
          fontWeight: 600,
          cursor: "pointer",
          textAlign: "center",
          transition: "all var(--transition-base)"
        },
        onMouseEnter: (e) => {
          e.currentTarget.style.background = "rgba(99,102,241,0.2)";
        },
        onMouseLeave: (e) => {
          e.currentTarget.style.background = "rgba(99,102,241,0.12)";
        },
        children: "📦 Download All"
      }
    ) })
  ] });
}
const statusColors = {
  modified: "#fbbf24",
  new: "#34d399",
  error: "#ef4444",
  clean: "#6b7280"
};
function ContextBar({ project, branch, files, lastTopic, onFileClick }) {
  return /* @__PURE__ */ jsxRuntimeExports.jsxs(
    "div",
    {
      style: {
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: "6px 16px",
        background: "var(--bg-card)",
        borderBottom: "1px solid var(--border-subtle)",
        fontSize: 12,
        color: "var(--text-dim)",
        flexShrink: 0,
        overflow: "hidden"
      },
      children: [
        project && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }, children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "folder", size: 12, style: { color: "var(--accent-hover)" } }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { color: "var(--text)", fontWeight: 600 }, children: project }),
          branch && /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { background: "var(--bg-elevated)", padding: "1px 6px", borderRadius: "var(--radius-sm)", fontSize: 11, color: "var(--text-muted)" }, children: branch })
        ] }),
        /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { width: 1, height: 16, background: "var(--border-subtle)", flexShrink: 0 } }),
        files && files.length > 0 && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 8, flexShrink: 0, overflow: "hidden" }, children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 11, textTransform: "uppercase", letterSpacing: "0.5px", color: "var(--text-faint)" }, children: "Files" }),
          /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", gap: 6, overflow: "hidden" }, children: [
            files.slice(0, 4).map((f) => /* @__PURE__ */ jsxRuntimeExports.jsxs(
              "button",
              {
                onClick: () => onFileClick == null ? void 0 : onFileClick(f.path),
                className: "db-btn",
                title: f.path,
                style: {
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-sm)",
                  padding: "2px 8px",
                  fontSize: 11,
                  color: "var(--text-muted)",
                  cursor: "pointer",
                  transition: "all var(--transition-fast)",
                  flexShrink: 0
                },
                onMouseEnter: (e) => {
                  e.currentTarget.style.borderColor = "var(--accent)";
                  e.currentTarget.style.color = "var(--text)";
                },
                onMouseLeave: (e) => {
                  e.currentTarget.style.borderColor = "var(--border)";
                  e.currentTarget.style.color = "var(--text-muted)";
                },
                children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { width: 6, height: 6, borderRadius: "50%", background: statusColors[f.status] } }),
                  f.path.split("/").pop()
                ]
              },
              f.path
            )),
            files.length > 4 && /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { fontSize: 11, color: "var(--text-faint)" }, children: [
              "+",
              files.length - 4
            ] })
          ] })
        ] }),
        lastTopic && /* @__PURE__ */ jsxRuntimeExports.jsxs(jsxRuntimeExports.Fragment, { children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { width: 1, height: 16, background: "var(--border-subtle)", flexShrink: 0 } }),
          /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 6, flexShrink: 0, overflow: "hidden" }, children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "brain", size: 12, style: { color: "var(--text-faint)" } }),
            /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 200 }, children: [
              "Last: ",
              lastTopic
            ] })
          ] })
        ] }),
        /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { flex: 1 } }),
        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 4, color: "var(--text-faint)", fontSize: 11, flexShrink: 0 }, children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "command", size: 10 }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("span", { children: "Type @ to reference files" })
        ] })
      ]
    }
  );
}
function Dropdown({ value, options, onChange, disabled, placeholder, searchable = true }) {
  const [open, setOpen] = reactExports.useState(false);
  const [query, setQuery] = reactExports.useState("");
  const ref = reactExports.useRef(null);
  const inputRef = reactExports.useRef(null);
  const selected = options.find((o) => o.value === value);
  const filteredOptions = searchable && query ? options.filter((o) => o.label.toLowerCase().includes(query.toLowerCase()) || o.description && o.description.toLowerCase().includes(query.toLowerCase())) : options;
  reactExports.useEffect(() => {
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
        setQuery("");
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);
  reactExports.useEffect(() => {
    if (open && searchable && inputRef.current) {
      inputRef.current.focus();
    }
  }, [open, searchable]);
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { ref, style: { position: "relative" }, children: [
    /* @__PURE__ */ jsxRuntimeExports.jsxs(
      "button",
      {
        onClick: () => {
          if (!disabled) {
            setOpen(!open);
            if (!open) setQuery("");
          }
        },
        disabled,
        className: "db-btn db-focus",
        style: {
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "5px 10px",
          background: "var(--bg-elevated)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-md)",
          color: "var(--text-muted)",
          fontSize: 11,
          cursor: disabled ? "not-allowed" : "pointer",
          opacity: disabled ? 0.5 : 1,
          transition: "all var(--transition-base)"
        },
        onMouseEnter: (e) => {
          if (!disabled) e.currentTarget.style.borderColor = "var(--text-faint)";
        },
        onMouseLeave: (e) => {
          if (!disabled) e.currentTarget.style.borderColor = "var(--border)";
        },
        children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("span", { children: (selected == null ? void 0 : selected.label) || placeholder || "Select..." }),
          /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "chevron-down", size: 12, style: { transition: "transform var(--transition-fast)", transform: open ? "rotate(180deg)" : "rotate(0deg)" } })
        ]
      }
    ),
    open && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
      position: "absolute",
      bottom: "calc(100% + 6px)",
      right: 0,
      minWidth: 220,
      maxHeight: 320,
      overflow: "auto",
      background: "var(--bg-elevated)",
      border: "1px solid var(--border)",
      borderRadius: "var(--radius-lg)",
      padding: searchable ? "6px 6px 0 6px" : "6px",
      zIndex: 100,
      boxShadow: "var(--shadow-lg)",
      animation: "dropdownIn 0.15s ease"
    }, children: [
      searchable && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { padding: "0 4px 6px 4px", borderBottom: "1px solid var(--border-subtle)" }, children: /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 6 }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "search", size: 12, style: { color: "var(--text-faint)", flexShrink: 0 } }),
        /* @__PURE__ */ jsxRuntimeExports.jsx(
          "input",
          {
            ref: inputRef,
            type: "text",
            value: query,
            onChange: (e) => setQuery(e.target.value),
            placeholder: "Search models...",
            style: {
              flex: 1,
              background: "transparent",
              border: "none",
              outline: "none",
              color: "var(--text)",
              fontSize: 12,
              padding: "4px 0"
            },
            onKeyDown: (e) => {
              if (e.key === "Escape") {
                setOpen(false);
                setQuery("");
              }
              e.stopPropagation();
            }
          }
        ),
        query && /* @__PURE__ */ jsxRuntimeExports.jsx(
          "button",
          {
            onClick: () => setQuery(""),
            style: {
              background: "none",
              border: "none",
              color: "var(--text-faint)",
              cursor: "pointer",
              fontSize: 10,
              padding: 0
            },
            children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "close", size: 10 })
          }
        )
      ] }) }),
      filteredOptions.length === 0 && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { padding: "12px", textAlign: "center", color: "var(--text-faint)", fontSize: 11 }, children: "No models found" }),
      filteredOptions.map((opt) => /* @__PURE__ */ jsxRuntimeExports.jsxs(
        "button",
        {
          onClick: () => {
            onChange(opt.value);
            setOpen(false);
          },
          className: "db-btn",
          style: {
            width: "100%",
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-start",
            gap: 2,
            padding: "8px 10px",
            borderRadius: "var(--radius-sm)",
            background: opt.value === value ? "rgba(99,102,241,0.1)" : "transparent",
            border: "none",
            color: opt.value === value ? "var(--accent-hover)" : "var(--text-muted)",
            fontSize: 12,
            cursor: "pointer",
            textAlign: "left",
            transition: "all var(--transition-fast)"
          },
          onMouseEnter: (e) => {
            if (opt.value !== value) {
              e.currentTarget.style.background = "rgba(255,255,255,0.04)";
              e.currentTarget.style.color = "var(--text)";
            }
          },
          onMouseLeave: (e) => {
            if (opt.value !== value) {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "var(--text-muted)";
            }
          },
          children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontWeight: opt.value === value ? 600 : 500 }, children: opt.label }),
            opt.description && /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 10, color: "var(--text-faint)" }, children: opt.description })
          ]
        },
        opt.value
      ))
    ] })
  ] });
}
const BACKEND = "";
const API = `${BACKEND}/api/v1`;
function capitalizeFirst(s) {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}
const FALLBACK_MODELS = [
  { id: "claude-sonnet-4-20250514", label: "Claude Sonnet 4", provider: "anthropic", family: "anthropic" },
  { id: "llama-4-scout-17b-16e-instruct", label: "Llama 4 Scout", provider: "llama", family: "llama" },
  { id: "qwen3-coder:480b", label: "Qwen 3 Coder", provider: "ollama", family: "ollama" },
  { id: "llama3.3:latest", label: "Llama 3.3", provider: "ollama", family: "ollama" },
  { id: "deepseek-coder:latest", label: "DeepSeek Coder", provider: "ollama", family: "ollama" }
];
function Workspace() {
  const { user, logout } = useAuth();
  const {
    conversations,
    activeConversation,
    messages: serverMessages,
    loading: conversationsLoading,
    syncStatus,
    setActiveConversation,
    createConversation: createConversation2,
    updateConversation: updateConversation2,
    deleteConversation: deleteConversation2,
    createMessage: createServerMessage
  } = useServerConversations({ autoSync: true, syncInterval: 3e4 });
  const [activeRepo, setActiveRepoLocal] = reactExports.useState(() => {
    try {
      return JSON.parse(localStorage.getItem("devbuddy_active_repo") || "null");
    } catch {
      return null;
    }
  });
  reactExports.useEffect(() => {
    if (activeRepo) {
      localStorage.setItem("devbuddy_active_repo", JSON.stringify(activeRepo));
    } else {
      localStorage.removeItem("devbuddy_active_repo");
    }
  }, [activeRepo]);
  const convs = reactExports.useMemo(() => conversations.map((c) => ({
    ...c,
    messages: c.id === (activeConversation == null ? void 0 : activeConversation.id) ? serverMessages : [],
    ts: new Date(c.created_at).getTime()
  })), [conversations, activeConversation == null ? void 0 : activeConversation.id, serverMessages]);
  const active = reactExports.useMemo(() => activeConversation ? {
    ...activeConversation,
    messages: serverMessages,
    ts: new Date(activeConversation.created_at).getTime()
  } : null, [activeConversation, serverMessages]);
  const activeId = (activeConversation == null ? void 0 : activeConversation.id) || "";
  const createNew = reactExports.useCallback(() => {
    const tempId = crypto.randomUUID();
    const optimisticConv = {
      id: tempId,
      user_id: (user == null ? void 0 : user.id) || "",
      title: "New conversation",
      repository_url: (activeRepo == null ? void 0 : activeRepo.html_url) || null,
      repository_name: (activeRepo == null ? void 0 : activeRepo.name) || null,
      repository_owner: (activeRepo == null ? void 0 : activeRepo.owner) || null,
      branch: null,
      summary: "",
      current_goal: "",
      completed_tasks: [],
      open_tasks: [],
      modified_files: [],
      important_decisions: [],
      status: "active",
      last_message_at: null,
      message_count: 0,
      created_at: (/* @__PURE__ */ new Date()).toISOString(),
      updated_at: (/* @__PURE__ */ new Date()).toISOString(),
      messages: [],
      ts: Date.now()
    };
    setActiveConversation(tempId);
    createConversation2({
      title: "New conversation",
      repository_url: activeRepo == null ? void 0 : activeRepo.html_url,
      repository_name: activeRepo == null ? void 0 : activeRepo.name,
      repository_owner: activeRepo == null ? void 0 : activeRepo.owner
    }).then((serverConv) => {
      setActiveConversation(serverConv.id);
    }).catch((err) => {
      console.error("Failed to create conversation:", err);
    });
    return optimisticConv;
  }, [user == null ? void 0 : user.id, activeRepo, createConversation2, setActiveConversation]);
  const SyncIndicator = () => {
    if (!syncStatus || syncStatus === "idle") return null;
    const statusConfig = {
      syncing: { icon: "refresh", color: "#6366f1", text: "Syncing..." },
      error: { icon: "error", color: "#ef4444", text: "Sync failed" },
      offline: { icon: "offline", color: "#9ca3af", text: "Offline" }
    };
    const config = statusConfig[syncStatus];
    if (!config) return null;
    return /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: {
      fontSize: 10,
      color: config.color,
      display: "flex",
      alignItems: "center",
      gap: 4,
      marginLeft: 8
    }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: config.icon, size: 10 }),
      config.text
    ] });
  };
  const updateActive = reactExports.useCallback((msgs, title, forceId) => {
    const targetId = forceId || activeId;
    if (!targetId) return;
    const nextMsgs = typeof msgs === "function" ? msgs(serverMessages) : msgs;
    nextMsgs.forEach(async (msg) => {
      if (!msg.id.startsWith("temp-")) {
        await createServerMessage(targetId, {
          role: msg.role,
          content: msg.content,
          metadata: msg.taskCard ? { task_card: msg.taskCard } : {}
        });
      }
    });
    if (title && targetId) {
      updateConversation2(targetId, { title });
    }
  }, [activeId, serverMessages, setMessages, createMessage, updateConversation2]);
  const selectConv = reactExports.useCallback((id) => {
    setActiveConversation(id);
  }, [setActiveConversation]);
  const deleteConv = reactExports.useCallback(async (id) => {
    await deleteConversation2(id);
  }, [deleteConversation2]);
  const restoreConv = reactExports.useCallback((conv) => {
    setActiveConversation(conv.id);
  }, [setActiveConversation]);
  const [userMenuOpen, setUserMenuOpen] = reactExports.useState(false);
  const [githubPanelOpen, setGithubPanelOpen] = reactExports.useState(false);
  const [agentRun, setAgentRun] = reactExports.useState(null);
  const [agentTimelineOpen, setAgentTimelineOpen] = reactExports.useState(false);
  const [engineeringTasks, setEngineeringTasks] = reactExports.useState([]);
  const [models, setModels] = reactExports.useState(FALLBACK_MODELS);
  const [modelsLoading, setModelsLoading] = reactExports.useState(true);
  const [model, setModel] = reactExports.useState(FALLBACK_MODELS[0].id);
  const [input, setInput] = reactExports.useState("");
  const [loading, setLoading] = reactExports.useState(false);
  const [sidebarOpen, setSidebarOpen] = reactExports.useState(false);
  const [paletteOpen, setPaletteOpen] = reactExports.useState(false);
  const [workspaceOpen, setWorkspaceOpen] = reactExports.useState(false);
  const [agentMode, setAgentMode] = reactExports.useState(true);
  const [workspaceId, setWorkspaceId] = reactExports.useState(null);
  const [workspaceFiles, setWorkspaceFiles] = reactExports.useState([]);
  const [settingsOpen, setSettingsOpen] = reactExports.useState(false);
  const [llmProviderSettingsOpen, setLlmProviderSettingsOpen] = reactExports.useState(false);
  const [mentionOpen, setMentionOpen] = reactExports.useState(false);
  const [mentionQuery, setMentionQuery] = reactExports.useState("");
  const [mentionIndex, setMentionIndex] = reactExports.useState(0);
  const [aiThinking, setAiThinking] = reactExports.useState(false);
  const [aiReasoning, setAiReasoning] = reactExports.useState(null);
  const [providerKeys, setProviderKeys] = reactExports.useState({
    anthropic: { key: "", base_url: "" },
    ollama: { key: "", base_url: "" },
    llama: { key: "", base_url: "" }
  });
  const [showKey, setShowKey] = reactExports.useState({});
  const [savingKeys, setSavingKeys] = reactExports.useState(false);
  const [isMobile, setIsMobile] = reactExports.useState(() => window.innerWidth < 768);
  const [modKey] = reactExports.useState(() => {
    var _a;
    return ((_a = navigator.platform) == null ? void 0 : _a.includes("Mac")) ? "⌘" : "Ctrl";
  });
  const [lastDeleted, setLastDeleted] = reactExports.useState(null);
  const abortControllerRef = reactExports.useRef(null);
  const bottomRef = reactExports.useRef(null);
  const textareaRef = reactExports.useRef(null);
  reactExports.useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  const messages = (active == null ? void 0 : active.messages) || [];
  reactExports.useEffect(() => {
    var _a;
    (_a = bottomRef.current) == null ? void 0 : _a.scrollIntoView({ behavior: "smooth" });
  }, [messages]);
  reactExports.useEffect(() => {
    if (workspaceFiles.length > 0 && !workspaceOpen) {
      const timer = setTimeout(() => setWorkspaceOpen(true), 300);
      return () => clearTimeout(timer);
    }
  }, [workspaceFiles.length]);
  reactExports.useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") {
        if (settingsOpen) setSettingsOpen(false);
        if (llmProviderSettingsOpen) setLlmProviderSettingsOpen(false);
        if (paletteOpen) setPaletteOpen(false);
        if (githubPanelOpen) setGithubPanelOpen(false);
        if (agentTimelineOpen) setAgentTimelineOpen(false);
        if (sidebarOpen && isMobile) setSidebarOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [settingsOpen, llmProviderSettingsOpen, paletteOpen, githubPanelOpen, agentTimelineOpen, sidebarOpen, isMobile]);
  reactExports.useEffect(() => {
    if (!activeId && !loading) createNew();
  }, []);
  reactExports.useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const newToken = params.get("token");
    const ghConnected = params.get("github_connected");
    if (newToken && ghConnected) {
      localStorage.setItem("devbuddy_token", newToken);
      window.history.replaceState({}, "", window.location.pathname);
      window.location.reload();
    }
  }, []);
  reactExports.useEffect(() => {
    const token = localStorage.getItem("devbuddy_token") || "";
    const fetchModels = async () => {
      try {
        setModelsLoading(true);
        const resp = await fetch(`${API}/models?token=${encodeURIComponent(token)}`);
        if (resp.ok) {
          const data = await resp.json();
          setModels(data.length > 0 ? data : []);
          if (data.length > 0) {
            setModel((prev) => data.find((m) => m.id === prev) ? prev : data[0].id);
          }
        }
      } catch (e) {
        console.error("Failed to fetch models:", e);
      } finally {
        setModelsLoading(false);
      }
    };
    const fetchSettings = async () => {
      var _a, _b, _c, _d, _e, _f;
      try {
        const resp = await fetch(`${API}/settings?token=${encodeURIComponent(token)}`);
        if (resp.ok) {
          const data = await resp.json();
          const p = data.providers || {};
          setProviderKeys({
            anthropic: { key: ((_a = p.anthropic) == null ? void 0 : _a.configured) ? "••••••••" : "", base_url: ((_b = p.anthropic) == null ? void 0 : _b.base_url) || "" },
            ollama: { key: ((_c = p.ollama) == null ? void 0 : _c.configured) ? "••••••••" : "", base_url: ((_d = p.ollama) == null ? void 0 : _d.base_url) || "" },
            llama: { key: ((_e = p.llama) == null ? void 0 : _e.configured) ? "••••••••" : "", base_url: ((_f = p.llama) == null ? void 0 : _f.base_url) || "" }
          });
        }
      } catch (e) {
        console.error("Failed to fetch settings:", e);
      }
    };
    fetchModels();
    fetchSettings();
  }, []);
  reactExports.useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setPaletteOpen((prev) => !prev);
      }
      if (e.key === "Escape") {
        setPaletteOpen(false);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);
  const saveProviderKeys = async () => {
    const token = localStorage.getItem("devbuddy_token") || "";
    setSavingKeys(true);
    try {
      const payload = {};
      for (const id of ["anthropic", "ollama", "llama"]) {
        const { key, base_url } = providerKeys[id];
        const hasNewKey = key && key !== "••••••••";
        const hasUrl = base_url.trim() !== "";
        if (hasNewKey || hasUrl) {
          payload[id] = {
            ...hasNewKey ? { key } : {},
            base_url
          };
        }
      }
      const resp = await fetch(`${API}/settings?token=${encodeURIComponent(token)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (resp.ok) {
        toast("API keys saved successfully", "success");
        const modelsResp = await fetch(`${API}/models?token=${encodeURIComponent(token)}`);
        if (modelsResp.ok) {
          const data = await modelsResp.json();
          setModels(data);
          if (data.length > 0) setModel(data[0].id);
        }
        setSettingsOpen(false);
      } else {
        toast("Failed to save API keys", "error");
      }
    } catch (e) {
      console.error("Failed to save keys:", e);
      toast("Failed to save API keys", "error");
    } finally {
      setSavingKeys(false);
    }
  };
  reactExports.useCallback(async (task, msgId, conversationAtStart) => {
    var _a, _b, _c, _d;
    if (!activeRepo) return false;
    const token = localStorage.getItem("devbuddy_token") || "";
    const owner = activeRepo.owner || ((_a = activeRepo.full_name) == null ? void 0 : _a.split("/")[0]) || "";
    const repo = activeRepo.name;
    const intentResp = await fetch(`${API}/follow-up/create-task?token=${encodeURIComponent(token)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: activeId,
        message: task,
        force_new_task: false
      })
    });
    let intentType = "implement";
    let noCodeWorkNeeded = false;
    if (intentResp.ok) {
      const intentData = await intentResp.json();
      intentType = intentData.intent_type || "implement";
      noCodeWorkNeeded = intentData.no_code_work_needed || false;
      if (noCodeWorkNeeded || ["analyze", "question", "chat"].includes(intentType)) {
        const analysisTask = {
          id: msgId,
          title: task.slice(0, 100),
          repository: {
            name: repo,
            owner,
            fullName: `${owner}/${repo}`
          },
          branch: "",
          // No branch for analysis
          baseBranch: "main",
          status: "working",
          startedAt: (/* @__PURE__ */ new Date()).toISOString(),
          currentPhase: "understanding",
          phases: [
            {
              id: "understanding",
              label: "Understanding",
              status: "active",
              startedAt: (/* @__PURE__ */ new Date()).toISOString(),
              currentFile: "Analyzing repository structure...",
              thinking: [
                "Analyzing project structure...",
                "Reviewing repository layout...",
                "Identifying key components..."
              ],
              stats: { duration: 0 }
            },
            {
              id: "planning",
              label: "Planning",
              status: "pending",
              files: []
            },
            {
              id: "implementing",
              label: "Implementation",
              status: "pending",
              files: []
            },
            {
              id: "validating",
              label: "Validation",
              status: "pending",
              files: []
            },
            {
              id: "delivering",
              label: "Delivery",
              status: "pending",
              files: []
            },
            {
              id: "completed",
              label: "Completed",
              status: "pending",
              files: []
            }
          ]
        };
        setEngineeringTasks((prev) => [...prev, analysisTask]);
        const analysisMsg = {
          id: msgId,
          role: "assistant",
          content: "",
          ts: Date.now(),
          engineeringTask: analysisTask,
          intentType
        };
        const convTitle2 = conversationAtStart.length === 1 ? capitalizeFirst(task.slice(0, 50)) : (active == null ? void 0 : active.title) || capitalizeFirst(task.slice(0, 50));
        updateActive([...conversationAtStart, analysisMsg], convTitle2);
        try {
          const chatResp = await fetch(`${API}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              messages: conversationAtStart.map((m) => ({
                role: m.role,
                content: m.content
              })),
              model,
              stream: true
            })
          });
          if (chatResp.ok && chatResp.body) {
            const reader = chatResp.body.getReader();
            const decoder = new TextDecoder();
            let content = "";
            setEngineeringTasks((prev) => prev.map(
              (t) => t.id === msgId ? { ...t, currentPhase: "delivering", phases: t.phases.map(
                (p) => p.id === "understanding" ? { ...p, status: "completed", completedAt: (/* @__PURE__ */ new Date()).toISOString() } : p.id === "planning" ? { ...p, status: "completed" } : p.id === "delivering" ? { ...p, status: "active", startedAt: (/* @__PURE__ */ new Date()).toISOString() } : p
              ) } : t
            ));
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;
              content += decoder.decode(value, { stream: true });
              updateActive((prev) => prev.map(
                (m) => m.id === msgId ? { ...m, content } : m
              ), convTitle2);
            }
            setEngineeringTasks((prev) => prev.map(
              (t) => t.id === msgId ? {
                ...t,
                status: "completed",
                currentPhase: "completed",
                completedAt: (/* @__PURE__ */ new Date()).toISOString(),
                phases: t.phases.map(
                  (p) => p.status === "active" || p.status === "pending" ? { ...p, status: "completed", completedAt: (/* @__PURE__ */ new Date()).toISOString() } : p
                ),
                summary: {
                  filesChanged: 0,
                  testsPassed: 0,
                  testsTotal: 0
                }
              } : t
            ));
            updateActive((prev) => prev.map(
              (m) => m.id === msgId ? { ...m, content, engineeringTask: { ...m.engineeringTask, status: "completed" } } : m
            ), convTitle2);
          }
        } catch (err) {
          console.error("Analysis request failed:", err);
        }
        return true;
      }
    }
    const cardId = msgId;
    const initialCard = {
      id: cardId,
      task,
      repo: `${owner}/${repo}`,
      branch: "",
      startedAt: Date.now(),
      status: "running",
      progress: 2,
      currentTool: "Connecting to repository…",
      events: [],
      isGitHubTask: true
    };
    const agentMsg = {
      id: cardId,
      role: "assistant",
      content: "",
      ts: Date.now(),
      taskCard: initialCard,
      intentType
    };
    const convTitle = conversationAtStart.length === 1 ? capitalizeFirst(task.slice(0, 50)) : (active == null ? void 0 : active.title) || capitalizeFirst(task.slice(0, 50));
    updateActive([...conversationAtStart, agentMsg], convTitle);
    const patchCard = (fn) => {
      updateActive((prev) => prev.map(
        (m) => m.id === cardId && m.taskCard ? { ...m, taskCard: fn(m.taskCard) } : m
      ), convTitle);
    };
    const PROGRESS = {
      init: 8,
      workspace: 18,
      branch: 28,
      analysis: 38,
      planning: 48,
      execution: 62,
      commit: 82,
      push: 90,
      pr: 96
    };
    try {
      const resp = await fetch(`${API}/github-agent/run?token=${encodeURIComponent(token)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task, owner, repo, conversation_id: activeId })
      });
      if (!resp.ok) {
        const err = await resp.text();
        patchCard((c) => ({
          ...c,
          status: "error",
          currentTool: void 0,
          events: [...c.events, { id: "err", ts: Date.now(), category: "error", title: err.slice(0, 120), status: "error" }]
        }));
        return true;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            const { type, payload } = evt;
            const taskEvt = sseToTaskEvent(type, payload);
            patchCard((c) => {
              var _a2, _b2;
              const next = { ...c };
              if (type === "observation") {
                next.events = next.events.map(
                  (e) => e.category === "tool" && e.status === "running" ? { ...e, status: "done" } : e
                );
              }
              if (type === "timeline" && payload.status === "done") {
                next.events = next.events.map(
                  (e) => e.category === payload.step && e.status === "running" ? { ...e, status: "done", title: payload.message } : e
                );
              }
              if (taskEvt) next.events = [...next.events, taskEvt];
              if (type === "timeline" && PROGRESS[payload.step]) {
                next.progress = Math.max(next.progress, PROGRESS[payload.step]);
              }
              if (type === "tool_call") next.currentTool = `${payload.tool.replace("_", " ")} ${((_a2 = Object.values(payload.params || {})[0]) == null ? void 0 : _a2.toString().slice(0, 30)) ?? ""}`;
              if (type === "timeline" && payload.status === "running") next.currentTool = payload.message;
              if (type === "branch") next.branch = payload.name || "";
              if (type === "pr") {
                next.prUrl = payload.url || "";
                next.prNumber = payload.number || "";
              }
              if (type === "file_change" && payload.path) {
                const mf = next.modifiedFiles || [];
                if (!mf.includes(payload.path)) next.modifiedFiles = [...mf, payload.path];
              }
              if (type === "done") {
                next.status = "done";
                next.progress = 100;
                next.currentTool = void 0;
                next.prUrl = payload.pr_url || next.prUrl;
                next.commitHash = payload.commit_hash || "";
                if ((_b2 = payload.modified_files) == null ? void 0 : _b2.length) next.modifiedFiles = payload.modified_files;
              }
              if (type === "error") {
                next.status = "error";
                next.currentTool = void 0;
              }
              return next;
            });
          } catch (_) {
          }
        }
      }
    } catch (e) {
      const isNetworkError = e.name === "AbortError" || ((_b = e.message) == null ? void 0 : _b.includes("network")) || ((_c = e.message) == null ? void 0 : _c.includes("fetch")) || ((_d = e.message) == null ? void 0 : _d.includes("Failed"));
      const errorTitle = isNetworkError ? "Connection lost — the task may still be running on the server. Check your repository for updates." : e.message || "Task failed";
      patchCard((c) => ({
        ...c,
        status: "error",
        currentTool: void 0,
        events: [...c.events, { id: "err", ts: Date.now(), category: "error", title: errorTitle, status: "error" }]
      }));
    }
    return true;
  }, [activeRepo, activeId, active == null ? void 0 : active.title]);
  const runCloudAgent = reactExports.useCallback(async (task, msgId, conversationAtStart, convId, signal) => {
    var _a, _b, _c, _d;
    if (!activeRepo) return false;
    const token = localStorage.getItem("devbuddy_token") || "";
    const owner = activeRepo.owner || ((_a = activeRepo.full_name) == null ? void 0 : _a.split("/")[0]) || "";
    const repo = activeRepo.name;
    const cardId = msgId;
    const initialCard = {
      id: cardId,
      task,
      repo: `${owner}/${repo}`,
      branch: "",
      startedAt: Date.now(),
      status: "running",
      progress: 2,
      currentTool: "Dispatching GitHub Actions runner…",
      events: [],
      isGitHubTask: true,
      isCloudJob: true,
      runnerState: "queued"
    };
    const agentMsg = {
      id: cardId,
      role: "assistant",
      content: "",
      ts: Date.now(),
      taskCard: initialCard
    };
    const convTitle = conversationAtStart.length === 1 ? capitalizeFirst(task.slice(0, 50)) : (active == null ? void 0 : active.title) || capitalizeFirst(task.slice(0, 50));
    updateActive([...conversationAtStart, agentMsg], convTitle, convId);
    const patchCard = (fn) => {
      updateActive((prev) => prev.map(
        (m) => m.id === cardId && m.taskCard ? { ...m, taskCard: fn(m.taskCard) } : m
      ), convTitle, convId);
    };
    const PROGRESS = {
      queued: 4,
      provisioning: 12,
      initializing: 20,
      connecting: 30,
      analyzing: 40,
      executing: 55,
      validating: 72,
      reflecting: 80,
      pushing: 88,
      creating_pr: 94,
      uploading: 97,
      completed: 100
    };
    try {
      const resp = await fetch(`${API}/cloud-agent/run?token=${encodeURIComponent(token)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task, owner, repo, conversation_id: activeId }),
        signal
      });
      if (!resp.ok) {
        const err = await resp.text();
        patchCard((c) => ({
          ...c,
          status: "error",
          currentTool: void 0,
          events: [...c.events, { id: "err", ts: Date.now(), category: "error", title: err.slice(0, 160), status: "error" }]
        }));
        return true;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            const { type, payload } = evt;
            const taskEvt = sseToTaskEvent(type, payload);
            patchCard((c) => {
              var _a2;
              const next = { ...c };
              if (type === "observation") {
                next.events = next.events.map(
                  (e) => e.category === "tool" && e.status === "running" ? { ...e, status: "done" } : e
                );
              }
              if (taskEvt && type !== "runner") next.events = [...next.events, taskEvt];
              if (type === "runner") {
                const state = payload.state;
                next.runnerState = state;
                next.runUrl = payload.run_url || next.runUrl;
                next.runId = payload.run_id || next.runId;
                if (PROGRESS[state]) next.progress = Math.max(next.progress, PROGRESS[state]);
                next.currentTool = payload.message || state;
                const evt2 = sseToTaskEvent(type, payload);
                if (evt2) next.events = [...next.events, evt2];
              }
              if (type === "quality_gates") {
                next.qualityGates = { ...next.qualityGates || {}, ...payload.gates };
              }
              if (type === "timeline" && PROGRESS[payload.step]) {
                next.progress = Math.max(next.progress, PROGRESS[payload.step] || 0);
              }
              if (type === "branch") next.branch = payload.name || "";
              if (type === "pr") {
                next.prUrl = payload.url || "";
                next.prNumber = payload.number || "";
              }
              if (type === "file_change" && payload.path) {
                const mf = next.modifiedFiles || [];
                if (!mf.includes(payload.path)) next.modifiedFiles = [...mf, payload.path];
              }
              if (type === "done") {
                next.status = "done";
                next.progress = 100;
                next.currentTool = void 0;
                next.prUrl = payload.pr_url || next.prUrl;
                next.commitHash = payload.commit_hash || "";
                next.runUrl = payload.run_url || next.runUrl;
                next.qualityGates = payload.quality_gates ? { ...next.qualityGates || {}, ...payload.quality_gates } : next.qualityGates;
                if ((_a2 = payload.modified_files) == null ? void 0 : _a2.length) next.modifiedFiles = payload.modified_files;
              }
              if (type === "error") {
                next.status = "error";
                next.currentTool = void 0;
              }
              return next;
            });
          } catch (_) {
          }
        }
      }
    } catch (e) {
      const isNetworkError = e.name === "AbortError" || ((_b = e.message) == null ? void 0 : _b.includes("network")) || ((_c = e.message) == null ? void 0 : _c.includes("fetch")) || ((_d = e.message) == null ? void 0 : _d.includes("Failed"));
      const errorTitle = isNetworkError ? "Connection lost — the task may still be running on the server. Check your repository for updates." : e.message || "Task failed";
      patchCard((c) => ({
        ...c,
        status: "error",
        currentTool: void 0,
        events: [...c.events, { id: "err", ts: Date.now(), category: "error", title: errorTitle, status: "error" }]
      }));
    }
    return true;
  }, [activeRepo, activeId, active == null ? void 0 : active.title]);
  const autoResize = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  };
  const processSSEStream = async (reader, onChunk) => {
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const line of lines) onChunk(line);
    }
    if (buf) onChunk(buf);
  };
  const sendChat = async (newMsgs, assistantMsg, title) => {
    var _a;
    const resp = await fetch(`${API}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: newMsgs.map((m) => ({ role: m.role, content: m.content })),
        model
      }),
      signal: abortControllerRef.current.signal
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const reader = (_a = resp.body) == null ? void 0 : _a.getReader();
    if (!reader) return;
    let fullContent = "";
    await processSSEStream(reader, (line) => {
      if (!line.startsWith("data: ")) return;
      const data = line.slice(6);
      if (data === "[DONE]") return;
      if (data.startsWith("[ERROR]")) throw new Error(data.slice(7));
      if (data.startsWith("[STEP]")) {
        assistantMsg.steps = [...assistantMsg.steps || [], data.slice(7)];
        updateActive([...newMsgs, { ...assistantMsg }], title);
      } else if (data.startsWith("[FILE]")) {
        try {
          const fileData = JSON.parse(data.slice(6));
          assistantMsg.files = [...assistantMsg.files || [], fileData];
          updateActive([...newMsgs, { ...assistantMsg }], title);
        } catch {
        }
      } else {
        fullContent += data;
        updateActive([...newMsgs, { ...assistantMsg, content: fullContent }], title);
      }
    });
  };
  const sendAgent = async (text, newMsgs, assistantMsg, title) => {
    var _a;
    const resp = await fetch(`${API}/agent/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: text, model }),
      signal: abortControllerRef.current.signal
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const reader = (_a = resp.body) == null ? void 0 : _a.getReader();
    if (!reader) return;
    let summaryContent = "";
    await processSSEStream(reader, (line) => {
      var _a2, _b, _c, _d, _e, _f, _g;
      if (!line.startsWith("data: ")) return;
      let raw = line.slice(6).trim();
      if (!raw || raw === "[DONE]") return;
      try {
        const event = JSON.parse(raw);
        assistantMsg.agentEvents = [...assistantMsg.agentEvents || [], event];
        if (event.type === "step") {
          assistantMsg.steps = [...assistantMsg.steps || [], ((_a2 = event.payload) == null ? void 0 : _a2.message) || ((_b = event.payload) == null ? void 0 : _b.agent) || ""];
        } else if (event.type === "file") {
          const f = event.payload;
          if ((f == null ? void 0 : f.path) && (f == null ? void 0 : f.content) !== void 0) {
            assistantMsg.files = [...assistantMsg.files || [], { name: f.path, content: f.content }];
            setWorkspaceFiles((prev) => prev.includes(f.path) ? prev : [...prev, f.path]);
          }
        } else if (event.type === "workspace") {
          if ((_c = event.payload) == null ? void 0 : _c.workspace_id) setWorkspaceId(event.payload.workspace_id);
          if ((_d = event.payload) == null ? void 0 : _d.files) setWorkspaceFiles(event.payload.files);
        } else if (event.type === "done") {
          summaryContent = ((_e = event.payload) == null ? void 0 : _e.summary) || ((_f = event.payload) == null ? void 0 : _f.message) || "Agent completed.";
          assistantMsg.content = summaryContent;
        } else if (event.type === "error") {
          assistantMsg.content = `Agent error: ${((_g = event.payload) == null ? void 0 : _g.message) || "Unknown error"}`;
        }
        updateActive([...newMsgs, { ...assistantMsg }], title);
      } catch {
      }
    });
    if (!assistantMsg.content) assistantMsg.content = summaryContent || "Agent run complete.";
    updateActive([...newMsgs, { ...assistantMsg }], title);
  };
  const detectMode = (text) => {
    const agentKeywords = ["build", "create", "setup", "deploy", "generate", "make", "scaffold", "implement", "write", "develop"];
    const chatKeywords = ["explain", "why", "how does", "what is", "compare", "debug", "fix", "review", "check"];
    const lower = text.toLowerCase();
    const agentScore = agentKeywords.filter((k) => lower.includes(k)).length;
    const chatScore = chatKeywords.filter((k) => lower.includes(k)).length;
    if (agentScore > chatScore) return true;
    if (chatScore > agentScore) return false;
    return agentMode;
  };
  const routeModel = (text) => {
    const lower = text.toLowerCase();
    const claudeKeywords = ["build", "create", "implement", "write", "code", "api", "function", "component", "script", "fastapi", "react", "vue", "angular"];
    const gptKeywords = ["explain", "analyze", "compare", "why", "how", "review", "debug", "optimize", "refactor"];
    const claudeScore = claudeKeywords.filter((k) => lower.includes(k)).length;
    const gptScore = gptKeywords.filter((k) => lower.includes(k)).length;
    if (claudeScore > gptScore) {
      const claude = models.find((m) => m.family === "claude");
      if (claude) return claude.id;
    }
    if (gptScore > claudeScore) {
      const gpt = models.find((m) => m.family === "gpt");
      if (gpt) return gpt.id;
    }
    return model;
  };
  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;
    const timeoutId = setTimeout(() => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        toast("Request timed out — please try again", "error");
      }
    }, 12e4);
    const cleanup = () => {
      clearTimeout(timeoutId);
      abortControllerRef.current = null;
      setLoading(false);
      setAiThinking(false);
      setAiReasoning(null);
    };
    if (activeRepo && agentMode) {
      setInput("");
      if (textareaRef.current) textareaRef.current.style.height = "auto";
      let conv2 = active;
      let convId = activeId;
      if (!conv2) {
        conv2 = createNew();
        convId = conv2.id;
      }
      const userMsg2 = { id: crypto.randomUUID(), role: "user", content: text, ts: Date.now() };
      const agentMsgId = crypto.randomUUID();
      const msgsWithUser = [...conv2.messages, userMsg2];
      updateActive(msgsWithUser, capitalizeFirst(text.slice(0, 50)), convId);
      try {
        await runCloudAgent(text, agentMsgId, msgsWithUser, convId, signal);
      } catch (e) {
        const errorMsg = (e == null ? void 0 : e.name) === "AbortError" ? "Request cancelled" : `Error: ${(e == null ? void 0 : e.message) || "Connection failed. The task may still be running on the server."}`;
        updateActive([...msgsWithUser, { id: crypto.randomUUID(), role: "assistant", content: errorMsg, ts: Date.now() }], conv2.title, convId);
      } finally {
        cleanup();
      }
      return;
    }
    const shouldUseAgent = detectMode(text);
    if (shouldUseAgent !== agentMode) {
      setAgentMode(shouldUseAgent);
      toast(`Switched to ${shouldUseAgent ? "Agent" : "Chat"} mode`, "info");
    }
    const bestModel = routeModel(text);
    if (bestModel !== model) {
      setModel(bestModel);
      const m = models.find((x) => x.id === bestModel);
      if (m) toast(`Using ${m.label}`, "info");
    }
    let conv = active;
    if (!conv) conv = createNew();
    const userMsg = { id: crypto.randomUUID(), role: "user", content: text, ts: Date.now() };
    const title = conv.messages.length === 0 ? capitalizeFirst(text.slice(0, 50)) : conv.title;
    const newMsgs = [...conv.messages, userMsg];
    updateActive(newMsgs, title);
    setInput("");
    setLoading(true);
    setAiThinking(true);
    setAiReasoning(agentMode ? "Planning autonomous pipeline..." : "Analyzing your question...");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    const assistantMsg = { id: crypto.randomUUID(), role: "assistant", content: "", ts: Date.now(), steps: [], files: [], agentEvents: [] };
    updateActive([...newMsgs, assistantMsg], title);
    try {
      if (agentMode) {
        await sendAgent(text, newMsgs, assistantMsg, title);
      } else {
        await sendChat(newMsgs, assistantMsg, title);
      }
    } catch (e) {
      const errorMsg = e instanceof Error && e.name === "AbortError" ? "Request cancelled" : `Error: ${e instanceof Error ? e.message : "Failed to connect"}`;
      updateActive([...newMsgs, { ...assistantMsg, content: errorMsg }], title);
    } finally {
      cleanup();
      if (active && active.messages.length > 2) {
        try {
          await fetch(`${API}/knowledge/extract`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              conversation_id: active.id,
              messages: active.messages.map((m) => ({ role: m.role, content: m.content }))
            })
          });
        } catch (e) {
          console.error("Failed to extract knowledge:", e);
        }
      }
    }
  };
  const cancelRequest = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setLoading(false);
    setAiThinking(false);
    setAiReasoning(null);
    toast("Request cancelled", "info");
  };
  const projectFiles = [
    "frontend/src/App.tsx",
    "frontend/src/pages/Workspace.tsx",
    "frontend/src/components/ContextBar.tsx",
    "frontend/src/components/Icon.tsx",
    "backend/app/main.py",
    "backend/app/api/routes/agent.py",
    "README.md",
    "package.json"
  ];
  const filteredMentions = mentionQuery ? projectFiles.filter((f) => f.toLowerCase().includes(mentionQuery.toLowerCase())) : projectFiles;
  const onKeyDown = (e) => {
    if (mentionOpen) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setMentionIndex((i) => Math.min(i + 1, filteredMentions.length - 1));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setMentionIndex((i) => Math.max(i - 1, 0));
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        const file = filteredMentions[mentionIndex];
        if (file) {
          const lastAt = input.lastIndexOf("@");
          if (lastAt >= 0) {
            const before = input.slice(0, lastAt);
            const after = input.slice(lastAt + 1 + mentionQuery.length);
            setInput(before + "@" + file + " " + after);
            setMentionOpen(false);
            setMentionQuery("");
          }
        }
        return;
      }
      if (e.key === "Escape") {
        setMentionOpen(false);
        setMentionQuery("");
        return;
      }
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };
  const handleInputChange = (e) => {
    const val = e.target.value;
    setInput(val);
    autoResize();
    const lastAt = val.lastIndexOf("@");
    if (lastAt >= 0) {
      const afterAt = val.slice(lastAt + 1);
      const endIdx = afterAt.search(/[\s\n]/);
      const query = endIdx >= 0 ? afterAt.slice(0, endIdx) : afterAt;
      if (!afterAt.includes(" ") && !afterAt.includes("\n")) {
        setMentionQuery(query);
        setMentionOpen(true);
        setMentionIndex(0);
      } else {
        setMentionOpen(false);
      }
    } else {
      setMentionOpen(false);
    }
  };
  const downloadFiles = async (files) => {
    const zip = new JSZip();
    files.forEach((file) => {
      zip.file(file.name, file.content);
    });
    const blob = await zip.generateAsync({ type: "blob" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `devbuddy-${Date.now()}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };
  const CodeBlock = ({ children, className, ...props }) => {
    const match = /language-(\w+)/.exec(className || "");
    const language = match ? match[1] : "text";
    const [copied, setCopied] = reactExports.useState(false);
    const codeText = typeof children === "string" ? children : "";
    const copyCode = () => {
      navigator.clipboard.writeText(codeText).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2e3);
      });
    };
    return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { position: "relative", marginTop: 10, marginBottom: 10 }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: "var(--border-subtle)",
        border: "1px solid var(--border)",
        borderBottom: "none",
        borderRadius: "var(--radius-md) var(--radius-md) 0 0",
        padding: "6px 12px"
      }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 11, color: "var(--text-dim)", fontFamily: "monospace", textTransform: "uppercase", letterSpacing: "0.5px" }, children: language }),
        /* @__PURE__ */ jsxRuntimeExports.jsx("button", { onClick: copyCode, className: "db-btn db-focus", style: { background: "none", border: "none", color: copied ? "var(--success)" : "var(--text-dim)", fontSize: 11, cursor: "pointer", padding: "2px 8px", borderRadius: "var(--radius-sm)", transition: "all var(--transition-fast)", display: "flex", alignItems: "center", gap: 4 }, onMouseEnter: (e) => {
          if (!copied) e.currentTarget.style.color = "var(--accent-hover)";
        }, onMouseLeave: (e) => {
          if (!copied) e.currentTarget.style.color = "var(--text-dim)";
        }, children: copied ? "✓ Copied" : "⎘ Copy" })
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("pre", { style: {
        background: "var(--bg)",
        border: "1px solid var(--border)",
        borderTop: "none",
        borderRadius: "0 0 var(--radius-md) var(--radius-md)",
        padding: "14px",
        overflowX: "auto",
        fontSize: 13,
        lineHeight: 1.6,
        color: "var(--text-muted)",
        margin: 0
      }, children: /* @__PURE__ */ jsxRuntimeExports.jsx("code", { className, ...props, children }) })
    ] });
  };
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", height: "100vh", background: "var(--bg)", color: "var(--text)", fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' }, children: [
    userMenuOpen && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { onClick: () => setUserMenuOpen(false), style: { position: "fixed", inset: 0, zIndex: 99 } }),
    sidebarOpen && isMobile && /* @__PURE__ */ jsxRuntimeExports.jsx(
      "div",
      {
        onClick: () => setSidebarOpen(false),
        style: {
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(0,0,0,0.6)",
          backdropFilter: "blur(4px)",
          zIndex: 40,
          animation: "fadeIn 0.2s ease"
        }
      }
    ),
    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
      width: 240,
      height: "100vh",
      background: "var(--bg-elevated)",
      borderRight: "1px solid var(--border-subtle)",
      display: "flex",
      flexDirection: "column",
      flexShrink: 0,
      alignItems: "stretch",
      padding: "12px 0",
      gap: 0,
      position: isMobile ? "fixed" : "relative",
      left: isMobile ? sidebarOpen ? 0 : -240 : 0,
      top: 0,
      bottom: 0,
      zIndex: 50,
      transition: "left 0.3s ease",
      boxSizing: "border-box"
    }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: "10px 12px", display: "flex", alignItems: "center", justifyContent: "space-between" }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 6 }, children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 13, fontWeight: 700, color: "var(--text)", letterSpacing: "-0.2px" }, children: "DevBuddy" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx(SyncIndicator, {})
        ] }),
        /* @__PURE__ */ jsxRuntimeExports.jsx(
          "button",
          {
            onClick: createNew,
            title: "New conversation (Ctrl+N)",
            className: "db-btn db-focus",
            style: {
              width: 28,
              height: 28,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "var(--radius-md)",
              background: "transparent",
              border: "1px solid var(--border-subtle)",
              color: "var(--text-dim)",
              cursor: "pointer",
              transition: "all var(--transition-fast)"
            },
            onMouseEnter: (e) => {
              e.currentTarget.style.background = "rgba(99,102,241,0.1)";
              e.currentTarget.style.borderColor = "rgba(99,102,241,0.3)";
              e.currentTarget.style.color = "var(--accent-hover)";
            },
            onMouseLeave: (e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.borderColor = "var(--border-subtle)";
              e.currentTarget.style.color = "var(--text-dim)";
            },
            children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "plus", size: 14 })
          }
        )
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", flexDirection: "column", gap: 2, alignItems: "stretch", flex: 1, minHeight: 0, overflowY: "auto", overflowX: "hidden", padding: "4px 12px", width: "100%" }, children: [
        conversationsLoading && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { display: "flex", flexDirection: "column", gap: 8, padding: "8px 12px" }, children: Array.from({ length: 4 }).map((_, i) => /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 8, padding: "8px 10px" }, children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "db-skeleton", style: { width: 24, height: 24, borderRadius: "50%", flexShrink: 0 } }),
          /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { flex: 1, display: "flex", flexDirection: "column", gap: 4 }, children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "db-skeleton", style: { width: "70%", height: 12, borderRadius: 4 } }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "db-skeleton", style: { width: "50%", height: 10, borderRadius: 4 } })
          ] })
        ] }, i)) }),
        !conversationsLoading && convs.length === 0 && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { role: "status", "aria-live": "polite", style: { padding: "32px 12px", textAlign: "center", color: "var(--text-faint)", fontSize: 13 }, children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 24, marginBottom: 8, opacity: 0.5 }, children: "💬" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontWeight: 500, color: "var(--text-muted)", marginBottom: 4 }, children: "No conversations yet" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 12 }, children: "Click + to start your first chat" })
        ] }),
        convs.map((c) => {
          var _a;
          const hue = c.title.split("").reduce((acc, ch) => acc + ch.charCodeAt(0), 0) % 360;
          const isActive = c.id === activeId;
          const firstUserMessage = ((_a = c.messages.find((m) => m.role === "user")) == null ? void 0 : _a.content) || "";
          const description = firstUserMessage.substring(0, 40) + (firstUserMessage.length > 40 ? "..." : "") || "New conversation";
          return /* @__PURE__ */ jsxRuntimeExports.jsxs(
            "div",
            {
              role: "button",
              tabIndex: 0,
              onClick: () => selectConv(c.id),
              onKeyDown: (e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  selectConv(c.id);
                }
              },
              title: c.title,
              className: "db-btn db-focus conv-item",
              style: {
                width: "100%",
                padding: "8px 10px",
                borderRadius: "var(--radius-md)",
                background: isActive ? `hsla(${hue}, 70%, 55%, 0.15)` : "transparent",
                border: isActive ? `1px solid hsla(${hue}, 70%, 55%, 0.3)` : "1px solid transparent",
                color: isActive ? `hsl(${hue}, 70%, 65%)` : "var(--text)",
                cursor: "pointer",
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                gap: 3,
                fontSize: 12,
                fontWeight: isActive ? 600 : 500,
                transition: "all var(--transition-fast)",
                flexShrink: 0,
                textAlign: "left",
                overflow: "hidden",
                position: "relative",
                boxSizing: "border-box"
              },
              onMouseEnter: (e) => {
                if (!isActive) e.currentTarget.style.background = "rgba(255,255,255,0.04)";
                const btn = e.currentTarget.querySelector(".conv-del-btn");
                if (btn) btn.style.opacity = "1";
              },
              onMouseLeave: (e) => {
                if (!isActive) e.currentTarget.style.background = "transparent";
                const btn = e.currentTarget.querySelector(".conv-del-btn");
                if (btn) btn.style.opacity = "0";
              },
              children: [
                /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 8, width: "100%", minWidth: 0 }, children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: {
                    width: 24,
                    height: 24,
                    borderRadius: "50%",
                    background: isActive ? `hsl(${hue}, 70%, 55%)` : `hsl(${hue}, 50%, 30%)`,
                    color: "white",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 10,
                    fontWeight: 700,
                    flexShrink: 0
                  }, children: c.title.charAt(0).toUpperCase() }),
                  /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1, minWidth: 0, fontSize: 13 }, children: c.title }),
                  c.messages.length > 0 && /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 10, color: "var(--text-faint)", flexShrink: 0, background: "rgba(255,255,255,0.06)", padding: "1px 5px", borderRadius: "var(--radius-sm)", minWidth: 16, textAlign: "center" }, children: c.messages.length }),
                  /* @__PURE__ */ jsxRuntimeExports.jsx(
                    "button",
                    {
                      className: "conv-del-btn db-focus",
                      onClick: (e) => {
                        e.stopPropagation();
                        setLastDeleted(c);
                        deleteConv(c.id);
                        setTimeout(() => setLastDeleted(null), 5e3);
                      },
                      title: "Delete conversation",
                      style: {
                        background: "none",
                        border: "none",
                        color: "var(--text-faint)",
                        cursor: "pointer",
                        padding: "2px 4px",
                        borderRadius: "var(--radius-sm)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                        opacity: 0,
                        transition: "all var(--transition-fast)",
                        lineHeight: 1
                      },
                      onMouseEnter: (e) => {
                        e.currentTarget.style.color = "var(--error)";
                        e.currentTarget.style.background = "rgba(239,68,68,0.12)";
                      },
                      onMouseLeave: (e) => {
                        e.currentTarget.style.color = "var(--text-faint)";
                        e.currentTarget.style.background = "none";
                      },
                      children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "trash", size: 12 })
                    }
                  )
                ] }),
                /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 11, color: "var(--text-faint)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", width: "100%", paddingLeft: 32 }, children: description })
              ]
            },
            c.id
          );
        })
      ] }),
      lastDeleted && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { margin: "4px 12px", padding: "8px 12px", background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: "var(--radius-md)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, animation: "fadeIn 0.15s ease", flexShrink: 0 }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { style: { fontSize: 11, color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1, minWidth: 0 }, children: [
          "Deleted ",
          /* @__PURE__ */ jsxRuntimeExports.jsx("strong", { style: { color: "var(--text)" }, children: lastDeleted.title })
        ] }),
        /* @__PURE__ */ jsxRuntimeExports.jsx(
          "button",
          {
            onClick: () => {
              restoreConv(lastDeleted);
              setLastDeleted(null);
            },
            style: { fontSize: 11, color: "var(--accent-hover)", background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.25)", borderRadius: "var(--radius-sm)", padding: "3px 10px", cursor: "pointer", fontWeight: 600, flexShrink: 0, whiteSpace: "nowrap" },
            children: "Undo"
          }
        )
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: "8px 12px", borderTop: "1px solid var(--border-subtle)", position: "relative" }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsxs(
          "div",
          {
            role: "button",
            tabIndex: 0,
            onClick: () => setUserMenuOpen((v) => !v),
            onKeyDown: (e) => {
              if (e.key === "Enter" || e.key === " ") setUserMenuOpen((v) => !v);
            },
            className: "db-btn",
            style: { display: "flex", alignItems: "center", gap: 8, padding: "6px 8px", borderRadius: "var(--radius-md)", cursor: "pointer", transition: "background var(--transition-fast)", width: "100%" },
            onMouseEnter: (e) => e.currentTarget.style.background = "rgba(255,255,255,0.05)",
            onMouseLeave: (e) => e.currentTarget.style.background = "transparent",
            children: [
              (user == null ? void 0 : user.picture) ? /* @__PURE__ */ jsxRuntimeExports.jsx("img", { src: user.picture, alt: (user == null ? void 0 : user.name) || "User", style: { width: 28, height: 28, borderRadius: "50%", objectFit: "cover", border: "2px solid var(--border)", flexShrink: 0 } }) : /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { width: 28, height: 28, borderRadius: "50%", background: "var(--bg-card)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }, children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "user", size: 14, style: { color: "var(--text-dim)" } }) }),
              /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { flex: 1, minWidth: 0 }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 12, fontWeight: 600, color: "var(--text)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }, children: (user == null ? void 0 : user.name) || "User" }),
                /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 10, color: "var(--text-faint)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }, children: user == null ? void 0 : user.email })
              ] }),
              /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "chevron-down", size: 12, style: { color: "var(--text-faint)", flexShrink: 0, transition: "transform var(--transition-fast)", transform: userMenuOpen ? "rotate(180deg)" : "rotate(0deg)" } })
            ]
          }
        ),
        userMenuOpen && /* @__PURE__ */ jsxRuntimeExports.jsxs(
          "div",
          {
            style: { position: "absolute", bottom: "100%", left: 12, right: 12, marginBottom: 4, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", boxShadow: "0 8px 24px rgba(0,0,0,0.4)", overflow: "hidden", animation: "fadeIn 0.12s ease", zIndex: 100 },
            children: [
              /* @__PURE__ */ jsxRuntimeExports.jsxs("button", { onClick: () => {
                setPaletteOpen(true);
                setUserMenuOpen(false);
              }, className: "db-btn db-focus", style: { width: "100%", padding: "10px 14px", background: "none", border: "none", color: "var(--text-muted)", fontSize: 13, cursor: "pointer", display: "flex", alignItems: "center", gap: 8, textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }, onMouseEnter: (e) => {
                e.currentTarget.style.background = "rgba(255,255,255,0.04)";
                e.currentTarget.style.color = "var(--text)";
              }, onMouseLeave: (e) => {
                e.currentTarget.style.background = "none";
                e.currentTarget.style.color = "var(--text-muted)";
              }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "command", size: 14 }),
                " Command Palette",
                /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { marginLeft: "auto", fontSize: 10, color: "var(--text-faint)", background: "var(--bg-card)", padding: "1px 5px", borderRadius: 4, fontFamily: "monospace" }, children: "⌘K" })
              ] }),
              /* @__PURE__ */ jsxRuntimeExports.jsxs("button", { onClick: () => {
                setSettingsOpen(true);
                setUserMenuOpen(false);
              }, className: "db-btn db-focus", style: { width: "100%", padding: "10px 14px", background: "none", border: "none", color: "var(--text-muted)", fontSize: 13, cursor: "pointer", display: "flex", alignItems: "center", gap: 8, textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }, onMouseEnter: (e) => {
                e.currentTarget.style.background = "rgba(255,255,255,0.04)";
                e.currentTarget.style.color = "var(--text)";
              }, onMouseLeave: (e) => {
                e.currentTarget.style.background = "none";
                e.currentTarget.style.color = "var(--text-muted)";
              }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "settings", size: 14 }),
                " Settings"
              ] }),
              /* @__PURE__ */ jsxRuntimeExports.jsxs("button", { onClick: () => {
                logout();
                setUserMenuOpen(false);
              }, className: "db-btn db-focus", style: { width: "100%", padding: "10px 14px", background: "none", border: "none", color: "var(--error)", fontSize: 13, cursor: "pointer", display: "flex", alignItems: "center", gap: 8, textAlign: "left" }, onMouseEnter: (e) => {
                e.currentTarget.style.background = "rgba(239,68,68,0.06)";
              }, onMouseLeave: (e) => {
                e.currentTarget.style.background = "none";
              }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "logout", size: 14 }),
                " Sign out"
              ] })
            ]
          }
        )
      ] })
    ] }),
    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { flex: 1, minWidth: 0, minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden" }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: "8px 16px", borderBottom: "1px solid var(--border-subtle)", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 12 }, children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx(
            "button",
            {
              onClick: () => setSidebarOpen(!sidebarOpen),
              className: "db-btn db-focus",
              "aria-label": "Open sidebar",
              style: {
                display: isMobile ? "flex" : "none",
                background: "none",
                border: "none",
                color: "var(--text-muted)",
                cursor: "pointer",
                width: 44,
                height: 44,
                alignItems: "center",
                justifyContent: "center",
                borderRadius: "var(--radius-md)",
                marginLeft: -6
              },
              children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "menu", size: 20 })
            }
          ),
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 13, fontWeight: 600, color: "var(--text)", maxWidth: 400, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }, children: (active == null ? void 0 : active.title) || "New conversation" }),
          aiThinking && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
            display: "flex",
            alignItems: "center",
            gap: 6,
            animation: "fadeIn 0.3s ease"
          }, children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx("span", { className: "pulse", style: { width: 6, height: 6, borderRadius: "50%", background: "var(--accent)" } }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 11, color: "var(--accent-hover)", fontWeight: 500 }, children: aiReasoning })
          ] })
        ] }),
        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 6 }, children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx(GitHubRepoButton, { activeRepo, onClick: () => setGithubPanelOpen(true) }),
          /* @__PURE__ */ jsxRuntimeExports.jsxs(
            "button",
            {
              onClick: () => setPaletteOpen(true),
              className: "db-btn db-focus",
              style: {
                background: "var(--bg-elevated)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                color: "var(--text-faint)",
                fontSize: 12,
                padding: "4px 10px",
                cursor: "pointer",
                display: isMobile ? "none" : "flex",
                alignItems: "center",
                gap: 6,
                minWidth: 140,
                justifyContent: "flex-start"
              },
              children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "command", size: 12 }),
                /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 12 }, children: "Search..." }),
                /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { marginLeft: "auto", fontSize: 10, color: "var(--text-faint)", background: "var(--bg-card)", padding: "1px 5px", borderRadius: "var(--radius-sm)" }, children: "⌘K" })
              ]
            }
          ),
          /* @__PURE__ */ jsxRuntimeExports.jsxs(
            "button",
            {
              onClick: () => setWorkspaceOpen(!workspaceOpen),
              className: "db-btn db-focus",
              title: "Toggle workspace",
              style: {
                background: workspaceOpen ? "rgba(99,102,241,0.08)" : "transparent",
                border: workspaceOpen ? "1px solid rgba(99,102,241,0.2)" : "1px solid transparent",
                borderRadius: "var(--radius-md)",
                color: workspaceOpen ? "var(--accent-hover)" : "var(--text-dim)",
                fontSize: 12,
                padding: "5px 8px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 4
              },
              children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "folder", size: 14 }),
                workspaceFiles.length > 0 && /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 10, background: "var(--accent)", color: "white", padding: "1px 5px", borderRadius: "var(--radius-full)", fontWeight: 700 }, children: workspaceFiles.length })
              ]
            }
          ),
          /* @__PURE__ */ jsxRuntimeExports.jsx(
            "button",
            {
              onClick: () => setSettingsOpen(!settingsOpen),
              title: "Settings",
              className: "db-btn db-focus",
              style: {
                background: settingsOpen ? "rgba(99,102,241,0.08)" : "transparent",
                border: settingsOpen ? "1px solid rgba(99,102,241,0.2)" : "1px solid transparent",
                borderRadius: "var(--radius-md)",
                color: settingsOpen ? "var(--accent-hover)" : "var(--text-dim)",
                fontSize: 12,
                padding: "5px 8px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 4
              },
              children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "settings", size: 14 })
            }
          )
        ] })
      ] }),
      activeRepo && /* @__PURE__ */ jsxRuntimeExports.jsx(
        ContextBar,
        {
          project: activeRepo.name,
          branch: activeRepo.default_branch || "main",
          lastTopic: (active == null ? void 0 : active.title) && active.title !== "New conversation" ? active.title : void 0
        }
      ),
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { flex: 1, minHeight: 0, overflow: "hidden", display: "flex", flexDirection: "column" }, children: /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { flex: 1, minHeight: 0, overflowY: "auto", padding: "24px 0" }, children: messages.length === 0 ? /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: 28, padding: "40px 24px" }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { textAlign: "center", maxWidth: 520, padding: isMobile ? "0 8px" : 0 }, children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
            fontSize: isMobile ? 22 : 28,
            fontWeight: 700,
            color: "var(--text)",
            letterSpacing: "-0.5px",
            marginBottom: 10
          }, children: (() => {
            const hasVisited = localStorage.getItem("devbuddy_visited");
            if (!hasVisited) {
              localStorage.setItem("devbuddy_visited", "true");
              return (user == null ? void 0 : user.name) ? `Welcome, ${user.name.split(" ")[0]}` : "Welcome to DevBuddy";
            }
            return (user == null ? void 0 : user.name) ? `Welcome back, ${user.name.split(" ")[0]}` : "Welcome to DevBuddy";
          })() }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("p", { style: { color: "var(--text-muted)", fontSize: isMobile ? 14 : 15, lineHeight: 1.6, margin: 0 }, children: activeRepo ? `Working in ${activeRepo.name}. Describe what you want to build — DevBuddy will write code, run tests, and open a pull request.` : "Describe what you want to build. DevBuddy will design the architecture, write the code, run tests, and deploy it." })
        ] }),
        !activeRepo && /* @__PURE__ */ jsxRuntimeExports.jsxs(
          "button",
          {
            onClick: () => setGithubPanelOpen(true),
            className: "db-btn db-focus",
            style: {
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: isMobile ? "10px 14px" : "12px 20px",
              background: "var(--bg-card)",
              border: "1px dashed var(--accent)",
              borderRadius: "var(--radius-lg)",
              color: "var(--accent-light)",
              fontSize: isMobile ? 13 : 14,
              fontWeight: 500,
              cursor: "pointer",
              transition: "all 0.2s ease",
              textAlign: "left",
              lineHeight: 1.4
            },
            onMouseEnter: (e) => {
              e.currentTarget.style.background = "rgba(99,102,241,0.08)";
            },
            onMouseLeave: (e) => {
              e.currentTarget.style.background = "var(--bg-card)";
            },
            children: [
              /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "git", size: 16 }),
              /* @__PURE__ */ jsxRuntimeExports.jsx("span", { children: "Connect a GitHub repository to start coding" }),
              /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 12, color: "var(--text-faint)", marginLeft: 4, flexShrink: 0 }, children: "(optional)" })
            ]
          }
        ),
        /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(2, 1fr)", gap: 12, maxWidth: 520, width: "100%" }, children: [
          { label: "Build a REST API", icon: "zap", desc: "FastAPI + PostgreSQL + tests" },
          { label: "React Dashboard", icon: "brain", desc: "Charts, auth, and deployment" },
          { label: "CI/CD Pipeline", icon: "rocket", desc: "GitHub Actions workflow" },
          { label: "Debug Python", icon: "wrench", desc: "Trace, fix, and verify" }
        ].map((s) => /* @__PURE__ */ jsxRuntimeExports.jsxs(
          "button",
          {
            onClick: () => {
              setInput(s.label);
              setTimeout(() => {
                if (!loading) send();
              }, 0);
            },
            className: "db-btn db-focus",
            style: {
              background: "var(--bg-card)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              padding: isMobile ? "14px 16px" : "20px",
              textAlign: "left",
              cursor: "pointer",
              transition: "all 0.2s ease",
              display: "flex",
              flexDirection: "column",
              gap: isMobile ? 6 : 8
            },
            onMouseEnter: (e) => {
              e.currentTarget.style.borderColor = "rgba(99,102,241,0.35)";
              e.currentTarget.style.background = "rgba(99,102,241,0.05)";
            },
            onMouseLeave: (e) => {
              e.currentTarget.style.borderColor = "var(--border)";
              e.currentTarget.style.background = "var(--bg-card)";
            },
            children: [
              /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 10 }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
                  width: isMobile ? 28 : 32,
                  height: isMobile ? 28 : 32,
                  borderRadius: "var(--radius-md)",
                  background: "rgba(99,102,241,0.1)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0
                }, children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: s.icon, size: isMobile ? 14 : 16, style: { color: "var(--accent-hover)" } }) }),
                /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { color: "var(--text)", fontSize: isMobile ? 13 : 14, fontWeight: 600 }, children: s.label })
              ] }),
              /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { color: "var(--text-dim)", fontSize: isMobile ? 12 : 13, lineHeight: 1.5, paddingLeft: isMobile ? 38 : 42 }, children: s.desc })
            ]
          },
          s.label
        )) })
      ] }) : /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { maxWidth: 780, margin: "0 auto", padding: "0 20px" }, children: [
        (() => {
          const pairs = [];
          let i = 0;
          const msgs = messages;
          while (i < msgs.length) {
            const m = msgs[i];
            if (m.role === "user") {
              const next = msgs[i + 1];
              if (next && next.role === "assistant" && next.taskCard) {
                pairs.push({ user: m, agent: next });
                i += 2;
              } else if (next && next.role === "assistant" && !next.taskCard) {
                pairs.push({ user: m, agent: next });
                i += 2;
              } else {
                pairs.push({ user: m, agent: null });
                i += 1;
              }
            } else {
              pairs.push({ user: { id: "_", role: "user", content: "", ts: 0 }, agent: m });
              i += 1;
            }
          }
          return pairs.map(({ user: uMsg, agent: aMsg }) => {
            if ((aMsg == null ? void 0 : aMsg.engineeringTask) || (aMsg == null ? void 0 : aMsg.intentType) && ["analyze", "question"].includes(aMsg.intentType)) {
              const task = (aMsg == null ? void 0 : aMsg.engineeringTask) || engineeringTasks.find((t) => t.id === (aMsg == null ? void 0 : aMsg.id));
              if (task) {
                return /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { marginBottom: 24 }, children: /* @__PURE__ */ jsxRuntimeExports.jsx(EngineeringTimeline, { tasks: [task] }) }, aMsg.id);
              }
            }
            if (aMsg == null ? void 0 : aMsg.taskCard) {
              return /* @__PURE__ */ jsxRuntimeExports.jsx(
                TaskCard$1,
                {
                  card: aMsg.taskCard,
                  userAvatar: user == null ? void 0 : user.picture,
                  userName: user == null ? void 0 : user.name,
                  isStreaming: aMsg.taskCard.status === "running"
                },
                aMsg.id
              );
            }
            return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { marginBottom: 24 }, children: [
              uMsg.content && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", gap: 12, flexDirection: "row-reverse", marginBottom: 12 }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { width: 32, height: 32, borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(99,102,241,0.2)", border: "2px solid rgba(99,102,241,0.15)", overflow: "hidden" }, children: (user == null ? void 0 : user.picture) ? /* @__PURE__ */ jsxRuntimeExports.jsx("img", { src: user.picture, alt: user.name || "User", style: { width: 32, height: 32, borderRadius: "50%" } }) : /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "user", size: 16, style: { color: "#818cf8" } }) }),
                /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "message-enter", style: { maxWidth: "78%", background: "rgba(99,102,241,0.09)", border: "1px solid rgba(99,102,241,0.18)", borderRadius: "16px 16px 4px 16px", padding: "12px 16px" }, children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 14, lineHeight: 1.6, color: "var(--text)", whiteSpace: "pre-wrap" }, children: uMsg.content }),
                  /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 10, color: "var(--text-faint)", marginTop: 4, textAlign: "right" }, children: new Date(uMsg.ts).toLocaleTimeString() })
                ] })
              ] }),
              aMsg && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", gap: 12 }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { width: 32, height: 32, borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(52,211,153,0.15)", border: "2px solid rgba(52,211,153,0.2)" }, children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "bot", size: 15, style: { color: "#34d399" } }) }),
                /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "message-enter", style: { maxWidth: "78%", background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "4px 16px 16px 16px", padding: "14px 18px", boxShadow: "0 2px 12px rgba(0,0,0,0.1)" }, children: [
                  aMsg.steps && aMsg.steps.length > 0 && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { marginBottom: 10, paddingBottom: 10, borderBottom: "1px solid var(--border-subtle)" }, children: aMsg.steps.filter(Boolean).map((step, si) => /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { fontSize: 12, color: "var(--text-muted)", marginBottom: 3, display: "flex", alignItems: "center", gap: 6 }, children: [
                    /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { color: "var(--accent)" }, children: "→" }),
                    " ",
                    step
                  ] }, si)) }),
                  /* @__PURE__ */ jsxRuntimeExports.jsx(
                    Markdown,
                    {
                      remarkPlugins: [remarkGfm],
                      components: {
                        code: CodeBlock,
                        pre: ({ children }) => /* @__PURE__ */ jsxRuntimeExports.jsx(jsxRuntimeExports.Fragment, { children }),
                        p: ({ children }) => /* @__PURE__ */ jsxRuntimeExports.jsx("p", { style: { fontSize: 14, lineHeight: 1.7, color: "var(--text)", marginBottom: 8, marginTop: 0 }, children }),
                        ul: ({ children }) => /* @__PURE__ */ jsxRuntimeExports.jsx("ul", { style: { fontSize: 14, lineHeight: 1.7, color: "var(--text)", paddingLeft: 20, marginBottom: 8 }, children }),
                        ol: ({ children }) => /* @__PURE__ */ jsxRuntimeExports.jsx("ol", { style: { fontSize: 14, lineHeight: 1.7, color: "var(--text)", paddingLeft: 20, marginBottom: 8 }, children }),
                        li: ({ children }) => /* @__PURE__ */ jsxRuntimeExports.jsx("li", { style: { marginBottom: 4 }, children }),
                        strong: ({ children }) => /* @__PURE__ */ jsxRuntimeExports.jsx("strong", { style: { color: "var(--accent-hover)", fontWeight: 600 }, children }),
                        em: ({ children }) => /* @__PURE__ */ jsxRuntimeExports.jsx("em", { style: { color: "var(--accent-hover)" }, children }),
                        a: ({ children, href }) => /* @__PURE__ */ jsxRuntimeExports.jsx("a", { href, style: { color: "var(--accent-hover)", textDecoration: "underline" }, target: "_blank", rel: "noopener noreferrer", children })
                      },
                      children: aMsg.content
                    }
                  ),
                  aMsg.files && aMsg.files.length > 0 && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--border)" }, children: /* @__PURE__ */ jsxRuntimeExports.jsxs("button", { onClick: () => downloadFiles(aMsg.files), style: { background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.3)", borderRadius: "var(--radius-sm)", color: "var(--accent-hover)", fontSize: 12, fontWeight: 600, cursor: "pointer", padding: "6px 12px", display: "flex", alignItems: "center", gap: 6 }, children: [
                    /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "download", size: 12 }),
                    " Download ",
                    aMsg.files.length,
                    " file",
                    aMsg.files.length > 1 ? "s" : "",
                    " as ZIP"
                  ] }) }),
                  /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { fontSize: 10, color: "var(--text-faint)", marginTop: 6 }, children: new Date(aMsg.ts).toLocaleTimeString() })
                ] })
              ] })
            ] }, uMsg.id + ((aMsg == null ? void 0 : aMsg.id) ?? ""));
          });
        })(),
        loading && /* @__PURE__ */ jsxRuntimeExports.jsx(TypingIndicator, {}),
        /* @__PURE__ */ jsxRuntimeExports.jsx("div", { ref: bottomRef })
      ] }) }) }),
      settingsOpen && /* @__PURE__ */ jsxRuntimeExports.jsx(
        "div",
        {
          onClick: () => setSettingsOpen(false),
          style: { position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)", backdropFilter: "blur(6px)", zIndex: 200, display: "flex", alignItems: isMobile ? "flex-end" : "center", justifyContent: "center", padding: isMobile ? 0 : 20, animation: "fadeIn 0.15s ease" },
          children: /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { onClick: (e) => e.stopPropagation(), className: isMobile ? "mobile-sheet" : "", style: {
            width: "100%",
            maxWidth: isMobile ? "100%" : 440,
            maxHeight: isMobile ? "90vh" : "85vh",
            background: "var(--bg-elevated)",
            border: "1px solid var(--border)",
            borderRadius: isMobile ? "var(--radius-xl) var(--radius-xl) 0 0" : "var(--radius-xl)",
            boxShadow: "0 24px 64px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04)",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            animation: isMobile ? void 0 : "modalContent 0.2s ease"
          }, children: [
            /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: "16px 20px", borderBottom: "1px solid var(--border-subtle)", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }, children: [
              /* @__PURE__ */ jsxRuntimeExports.jsxs("h2", { style: { margin: 0, fontSize: 15, color: "var(--text)", fontWeight: 700, display: "flex", alignItems: "center", gap: 8 }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "settings", size: 16 }),
                " Settings"
              ] }),
              /* @__PURE__ */ jsxRuntimeExports.jsx("button", { onClick: () => setSettingsOpen(false), className: "db-btn db-focus", "aria-label": "Close settings", style: { background: "none", border: "none", color: "var(--text-faint)", cursor: "pointer", width: 36, height: 36, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: "var(--radius-sm)", transition: "all var(--transition-fast)" }, onMouseEnter: (e) => {
                e.currentTarget.style.color = "var(--text)";
                e.currentTarget.style.background = "rgba(255,255,255,0.06)";
              }, onMouseLeave: (e) => {
                e.currentTarget.style.color = "var(--text-faint)";
                e.currentTarget.style.background = "none";
              }, children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "close", size: 18 }) })
            ] }),
            /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { flex: 1, overflowY: "auto", padding: "20px" }, children: [
              /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { marginBottom: 20, padding: 16, background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.2)", borderRadius: "var(--radius-lg)" }, children: /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between" }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsx("h3", { style: { margin: "0 0 4px", fontSize: 14, fontWeight: 600 }, children: "Universal LLM Providers" }),
                  /* @__PURE__ */ jsxRuntimeExports.jsx("p", { style: { margin: 0, fontSize: 12, color: "var(--text-dim)" }, children: "Add any OpenAI-compatible endpoint (Ollama, OpenRouter, Azure, etc.)" })
                ] }),
                /* @__PURE__ */ jsxRuntimeExports.jsx(
                  "button",
                  {
                    onClick: () => {
                      setSettingsOpen(false);
                      setLlmProviderSettingsOpen(true);
                    },
                    className: "db-btn",
                    style: {
                      padding: "8px 16px",
                      background: "var(--accent)",
                      color: "white",
                      border: "none",
                      borderRadius: "var(--radius-md)",
                      fontSize: 13,
                      fontWeight: 500,
                      cursor: "pointer"
                    },
                    children: "Configure"
                  }
                )
              ] }) }),
              /* @__PURE__ */ jsxRuntimeExports.jsx("p", { style: { margin: "0 0 20px", fontSize: 13, color: "var(--text-dim)", lineHeight: 1.5 }, children: "Or add individual API keys below. Keys are encrypted at rest." }),
              [
                { id: "anthropic", name: "Anthropic", icon: "brain", placeholder: "sk-ant-api03-...", defaultUrl: "https://api.anthropic.com" },
                { id: "ollama", name: "Ollama", icon: "bot", placeholder: "Ollama API key (if required)", defaultUrl: "https://ollama.com" },
                { id: "llama", name: "Llama API", icon: "zap", placeholder: "Bearer token...", defaultUrl: "https://api.llama.com/v1" }
              ].map((provider) => /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { marginBottom: 20, padding: 16, background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)" }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }, children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: provider.icon, size: 18, style: { color: "var(--accent-hover)" } }),
                  /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 14, fontWeight: 600, color: "var(--accent-hover)" }, children: provider.name }),
                  providerKeys[provider.id].key === "••••••••" && /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { fontSize: 11, color: "var(--success)", background: "rgba(16,185,129,0.1)", padding: "2px 8px", borderRadius: "var(--radius-sm)" }, children: "Configured" })
                ] }),
                /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", flexDirection: "column", gap: 10 }, children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { children: [
                    /* @__PURE__ */ jsxRuntimeExports.jsx("label", { style: { fontSize: 11, color: "var(--text-faint)", marginBottom: 4, display: "block" }, children: "API Key" }),
                    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { position: "relative", display: "flex", alignItems: "center" }, children: [
                      /* @__PURE__ */ jsxRuntimeExports.jsx(
                        "input",
                        {
                          type: showKey[provider.id] ? "text" : "password",
                          value: providerKeys[provider.id].key,
                          onChange: (e) => setProviderKeys((prev) => ({ ...prev, [provider.id]: { ...prev[provider.id], key: e.target.value } })),
                          placeholder: provider.placeholder,
                          className: "db-input",
                          style: {
                            width: "100%",
                            background: "var(--bg-elevated)",
                            border: "1px solid var(--border)",
                            borderRadius: "var(--radius-md)",
                            padding: "8px 36px 8px 12px",
                            color: "var(--text)",
                            fontSize: 13,
                            outline: "none",
                            fontFamily: "monospace"
                          }
                        }
                      ),
                      /* @__PURE__ */ jsxRuntimeExports.jsx(
                        "button",
                        {
                          onClick: () => setShowKey((prev) => ({ ...prev, [provider.id]: !prev[provider.id] })),
                          type: "button",
                          className: "db-btn",
                          "aria-label": showKey[provider.id] ? "Hide API key" : "Show API key",
                          style: {
                            position: "absolute",
                            right: 8,
                            top: "50%",
                            transform: "translateY(-50%)",
                            background: "none",
                            border: "none",
                            color: "var(--text-faint)",
                            cursor: "pointer",
                            padding: 4,
                            fontSize: 12
                          },
                          children: showKey[provider.id] ? "Hide" : "Show"
                        }
                      )
                    ] })
                  ] }),
                  /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { children: [
                    /* @__PURE__ */ jsxRuntimeExports.jsx("label", { style: { fontSize: 11, color: "var(--text-faint)", marginBottom: 4, display: "block" }, children: "Base URL (optional)" }),
                    /* @__PURE__ */ jsxRuntimeExports.jsx(
                      "input",
                      {
                        type: "text",
                        value: providerKeys[provider.id].base_url,
                        onChange: (e) => setProviderKeys((prev) => ({ ...prev, [provider.id]: { ...prev[provider.id], base_url: e.target.value } })),
                        placeholder: provider.defaultUrl,
                        className: "db-input",
                        style: {
                          width: "100%",
                          background: "var(--bg-elevated)",
                          border: "1px solid var(--border)",
                          borderRadius: "var(--radius-md)",
                          padding: "8px 12px",
                          color: "var(--text)",
                          fontSize: 13,
                          outline: "none",
                          fontFamily: "monospace"
                        }
                      }
                    )
                  ] })
                ] })
              ] }, provider.id)),
              /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 8, paddingTop: 4 }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx(
                  "button",
                  {
                    onClick: () => setSettingsOpen(false),
                    className: "db-btn db-focus",
                    style: {
                      padding: "8px 16px",
                      background: "transparent",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius-md)",
                      color: "var(--text-muted)",
                      fontSize: 13,
                      cursor: "pointer",
                      transition: "all var(--transition-base)"
                    },
                    onMouseEnter: (e) => {
                      e.currentTarget.style.borderColor = "var(--text-faint)";
                      e.currentTarget.style.color = "var(--accent-hover)";
                    },
                    onMouseLeave: (e) => {
                      e.currentTarget.style.borderColor = "var(--border)";
                      e.currentTarget.style.color = "var(--text-muted)";
                    },
                    children: "Cancel"
                  }
                ),
                /* @__PURE__ */ jsxRuntimeExports.jsx(
                  "button",
                  {
                    onClick: saveProviderKeys,
                    disabled: savingKeys,
                    className: "db-btn db-focus",
                    style: {
                      padding: "8px 20px",
                      background: "linear-gradient(135deg, var(--accent), var(--accent-hover))",
                      border: "none",
                      borderRadius: "var(--radius-md)",
                      color: "white",
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: savingKeys ? "not-allowed" : "pointer",
                      opacity: savingKeys ? 0.7 : 1,
                      transition: "all var(--transition-base)",
                      boxShadow: "0 2px 12px rgba(99,102,241,0.3)"
                    },
                    onMouseEnter: (e) => {
                      if (!savingKeys) {
                        e.currentTarget.style.boxShadow = "0 4px 16px rgba(99,102,241,0.4)";
                        e.currentTarget.style.transform = "translateY(-1px)";
                      }
                    },
                    onMouseLeave: (e) => {
                      e.currentTarget.style.boxShadow = "0 2px 12px rgba(99,102,241,0.3)";
                      e.currentTarget.style.transform = "translateY(0)";
                    },
                    children: savingKeys ? "Saving..." : "Save Keys"
                  }
                )
              ] })
            ] })
          ] })
        }
      ),
      /* @__PURE__ */ jsxRuntimeExports.jsx(
        LLMProviderSettings,
        {
          isOpen: llmProviderSettingsOpen,
          onClose: () => setLlmProviderSettingsOpen(false)
        }
      ),
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { padding: isMobile ? "12px 16px max(16px, env(safe-area-inset-bottom))" : "16px 20px 20px", borderTop: "1px solid var(--border-subtle)", flexShrink: 0 }, children: /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { maxWidth: 760, margin: "0 auto" }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsxs(
          "div",
          {
            style: { position: "relative", background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "12px 14px", display: "flex", flexDirection: "column", gap: 8, boxShadow: "0 4px 24px rgba(0,0,0,0.2)", transition: "border-color var(--transition-base), box-shadow var(--transition-base)" },
            className: "db-input-container",
            id: "chat-input-container",
            onDragOver: (e) => {
              e.preventDefault();
              const el = document.getElementById("chat-input-container");
              if (el) el.style.borderColor = "var(--accent)";
            },
            onDragLeave: (e) => {
              e.preventDefault();
              const el = document.getElementById("chat-input-container");
              if (el) el.style.borderColor = "var(--border)";
            },
            onDrop: (e) => {
              e.preventDefault();
              const el = document.getElementById("chat-input-container");
              if (el) el.style.borderColor = "var(--border)";
              const files = Array.from(e.dataTransfer.files);
              if (files.length > 0) {
                const fileNames = files.map((f) => f.name).join(", ");
                setInput((prev) => prev + (prev ? "\n\n" : "") + `[Attached: ${fileNames}]`);
              }
            },
            children: [
              /* @__PURE__ */ jsxRuntimeExports.jsx("label", { htmlFor: "chat-textarea", style: { position: "absolute", width: 1, height: 1, padding: 0, margin: -1, overflow: "hidden", clip: "rect(0,0,0,0)", whiteSpace: "nowrap", border: 0 }, children: "Message" }),
              /* @__PURE__ */ jsxRuntimeExports.jsx(
                "textarea",
                {
                  id: "chat-textarea",
                  ref: textareaRef,
                  value: input,
                  onChange: handleInputChange,
                  onKeyDown,
                  placeholder: activeRepo && agentMode ? `Describe a task for ${activeRepo.name}… (runs in isolated GitHub Actions runner)` : "Describe what you want to build, or type @ to reference files...",
                  rows: 1,
                  className: "db-input",
                  "aria-label": activeRepo && agentMode ? `Describe a task for ${activeRepo.name}` : "Describe what you want to build",
                  style: { width: "100%", background: "none", border: "none", outline: "none", color: "var(--text)", fontSize: 14, lineHeight: 1.5, resize: "none", maxHeight: 200, fontFamily: "inherit", overflowY: "auto", padding: "0 4px" },
                  onFocus: (e) => {
                    const container = document.getElementById("chat-input-container");
                    if (container) {
                      container.style.borderColor = "rgba(99,102,241,0.4)";
                      container.style.boxShadow = "0 4px 24px rgba(0,0,0,0.2), 0 0 0 3px rgba(99,102,241,0.1)";
                    }
                  },
                  onBlur: (e) => {
                    setTimeout(() => setMentionOpen(false), 200);
                    const container = document.getElementById("chat-input-container");
                    if (container) {
                      container.style.borderColor = "var(--border)";
                      container.style.boxShadow = "0 4px 24px rgba(0,0,0,0.2)";
                    }
                  }
                }
              ),
              mentionOpen && filteredMentions.length > 0 && /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { role: "listbox", "aria-label": "Project files", style: {
                position: "absolute",
                bottom: "100%",
                left: 0,
                right: 0,
                marginBottom: 8,
                background: "var(--bg-elevated)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-lg)",
                boxShadow: "var(--shadow-lg), 0 0 0 1px rgba(99,102,241,0.1)",
                maxHeight: 200,
                overflowY: "auto",
                zIndex: 50,
                animation: "dropdownIn 0.15s ease"
              }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { padding: "8px 12px", fontSize: 11, color: "var(--text-faint)", textTransform: "uppercase", letterSpacing: "0.5px", borderBottom: "1px solid var(--border-subtle)" }, children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "folder", size: 10 }),
                  " Project Files"
                ] }),
                filteredMentions.map((f, i) => /* @__PURE__ */ jsxRuntimeExports.jsxs(
                  "button",
                  {
                    role: "option",
                    "aria-selected": i === mentionIndex,
                    onMouseDown: (e) => {
                      e.preventDefault();
                      const lastAt = input.lastIndexOf("@");
                      if (lastAt >= 0) {
                        const before = input.slice(0, lastAt);
                        const after = input.slice(lastAt + 1 + mentionQuery.length);
                        setInput(before + "@" + f + " " + after);
                        setMentionOpen(false);
                        setMentionQuery("");
                      }
                    },
                    className: "db-btn db-focus",
                    style: {
                      width: "100%",
                      padding: "8px 12px",
                      textAlign: "left",
                      background: i === mentionIndex ? "rgba(99,102,241,0.1)" : "transparent",
                      border: "none",
                      borderBottom: "1px solid var(--border-subtle)",
                      color: i === mentionIndex ? "var(--accent-hover)" : "var(--text-muted)",
                      fontSize: 13,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      transition: "all var(--transition-fast)"
                    },
                    onMouseEnter: (e) => {
                      setMentionIndex(i);
                      e.currentTarget.style.background = "rgba(99,102,241,0.1)";
                      e.currentTarget.style.color = "var(--accent-hover)";
                    },
                    onMouseLeave: (e) => {
                      e.currentTarget.style.background = i === mentionIndex ? "rgba(99,102,241,0.1)" : "transparent";
                      e.currentTarget.style.color = i === mentionIndex ? "var(--accent-hover)" : "var(--text-muted)";
                    },
                    children: [
                      /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "file", size: 14, style: { color: "var(--text-faint)" } }),
                      /* @__PURE__ */ jsxRuntimeExports.jsx("span", { children: f })
                    ]
                  },
                  f
                ))
              ] }),
              /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }, children: [
                /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { display: "flex", alignItems: "center", gap: 6 }, children: /* @__PURE__ */ jsxRuntimeExports.jsxs(
                  "button",
                  {
                    onClick: () => setAgentMode(!agentMode),
                    title: agentMode ? "Agent Mode — full autonomous pipeline" : "Chat Mode — raw LLM",
                    className: "db-btn db-focus",
                    style: {
                      background: agentMode ? "rgba(16,185,129,0.1)" : "transparent",
                      border: agentMode ? "1px solid rgba(16,185,129,0.2)" : "1px solid transparent",
                      borderRadius: "var(--radius-full)",
                      color: agentMode ? "var(--success)" : "var(--text-dim)",
                      fontSize: 11,
                      fontWeight: 600,
                      padding: "4px 10px",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                      transition: "all var(--transition-base)"
                    },
                    children: [
                      /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: agentMode ? "agent" : "chat", size: 12 }),
                      agentMode ? "Agent" : "Chat"
                    ]
                  }
                ) }),
                /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { display: "flex", alignItems: "center", gap: 8 }, children: [
                  /* @__PURE__ */ jsxRuntimeExports.jsx(
                    Dropdown,
                    {
                      value: model,
                      options: models.map((m) => {
                        const guidance = {
                          anthropic: "Best for complex engineering tasks",
                          llama: "Fast, good for drafts and exploration",
                          ollama: "Run locally, great for privacy"
                        };
                        return {
                          value: m.id,
                          label: m.label,
                          description: guidance[m.provider] || m.provider
                        };
                      }),
                      onChange: setModel,
                      disabled: modelsLoading
                    }
                  ),
                  /* @__PURE__ */ jsxRuntimeExports.jsx(
                    "button",
                    {
                      onClick: loading ? cancelRequest : send,
                      disabled: !input.trim() && !loading,
                      title: loading ? "Cancel" : "Send",
                      className: "db-btn db-focus",
                      "aria-label": loading ? "Cancel request" : "Send message",
                      style: {
                        width: 44,
                        height: 44,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        background: loading ? "rgba(239,68,68,0.15)" : input.trim() ? "linear-gradient(135deg, var(--accent), var(--accent-hover))" : "var(--border)",
                        border: loading ? "1px solid rgba(239,68,68,0.3)" : "none",
                        borderRadius: "50%",
                        color: loading ? "var(--error)" : input.trim() ? "white" : "var(--text-faint)",
                        fontSize: 16,
                        fontWeight: 600,
                        cursor: input.trim() || loading ? "pointer" : "not-allowed",
                        flexShrink: 0,
                        transition: "all var(--transition-base)",
                        boxShadow: input.trim() && !loading ? "0 2px 12px rgba(99,102,241,0.3)" : "none"
                      },
                      onMouseEnter: (e) => {
                        if (input.trim() && !loading) {
                          e.currentTarget.style.boxShadow = "0 4px 16px rgba(99,102,241,0.4)";
                          e.currentTarget.style.transform = "translateY(-1px) scale(1.05)";
                        }
                      },
                      onMouseLeave: (e) => {
                        if (input.trim() && !loading) {
                          e.currentTarget.style.boxShadow = "0 2px 12px rgba(99,102,241,0.3)";
                          e.currentTarget.style.transform = "translateY(0) scale(1)";
                        }
                      },
                      children: loading ? /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "close", size: 16 }) : /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "send", size: 16 })
                    }
                  )
                ] })
              ] })
            ]
          }
        ),
        !isMobile && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { marginTop: 6, display: "flex", alignItems: "center", justifyContent: "center", gap: 12, fontSize: 11, color: "var(--text-faint)", opacity: 0.7 }, children: /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { children: [
          "↵ send · ⇧↵ newline · ",
          modKey,
          "K commands"
        ] }) })
      ] }) })
    ] }),
    /* @__PURE__ */ jsxRuntimeExports.jsx(
      GitHubPanelWrapper,
      {
        token: localStorage.getItem("devbuddy_token") || "",
        isOpen: githubPanelOpen,
        onClose: () => setGithubPanelOpen(false),
        onSelectRepo: (repo) => {
          if (activeRepo && activeRepo.full_name !== repo.full_name && messages.length > 0) {
            toast(`Switched to ${repo.full_name}. New conversations will use this repository.`, "info");
          } else {
            toast(`Working in ${repo.full_name}`, "success");
          }
          setActiveRepoLocal(repo);
        }
      }
    ),
    workspaceOpen && /* @__PURE__ */ jsxRuntimeExports.jsx(
      WorkspacePanel,
      {
        files: workspaceFiles.map((path) => {
          const fileData = messages.flatMap((m) => m.files || []).find((f) => f.name === path);
          return { name: path, content: fileData == null ? void 0 : fileData.content };
        }),
        onDownload: (files) => downloadFiles(files.filter((f) => f.content).map((f) => ({ name: f.name, content: f.content }))),
        onDownloadOne: (file) => file.content && downloadFiles([{ name: file.name, content: file.content }]),
        isOpen: workspaceOpen,
        onToggle: () => setWorkspaceOpen(!workspaceOpen)
      }
    ),
    /* @__PURE__ */ jsxRuntimeExports.jsx(
      CommandPalette,
      {
        isOpen: paletteOpen,
        onClose: () => setPaletteOpen(false),
        commands: [
          { id: "new-chat", label: "New conversation", shortcut: "Ctrl+N", icon: "sparkles", action: () => {
            createNew();
            setWorkspaceOpen(false);
          } },
          { id: "workspace", label: "Toggle workspace panel", shortcut: "Ctrl+Shift+F", icon: "folder", action: () => setWorkspaceOpen(!workspaceOpen) },
          { id: "settings", label: "Open settings", shortcut: "", icon: "settings", action: () => setSettingsOpen(true) },
          { id: "llm-providers", label: "Configure LLM providers", shortcut: "", icon: "bot", action: () => setLlmProviderSettingsOpen(true) },
          { id: "agent-mode", label: agentMode ? "Switch to Chat mode" : "Switch to Agent mode", shortcut: "", icon: agentMode ? "chat" : "agent", action: () => setAgentMode(!agentMode) },
          { id: "logout", label: "Sign out", shortcut: "", icon: "logout", action: () => logout() }
        ],
        conversations: convs.map((c) => ({ id: c.id, title: c.title, messageCount: c.messages.length })),
        onSelectConversation: (id) => {
          selectConv(id);
          setPaletteOpen(false);
        }
      }
    ),
    /* @__PURE__ */ jsxRuntimeExports.jsx(ToastContainer, {})
  ] });
}
function GitHubRepoButton({ activeRepo, onClick }) {
  if (activeRepo) {
    return /* @__PURE__ */ jsxRuntimeExports.jsxs(
      "button",
      {
        onClick,
        className: "db-btn db-focus",
        title: "Change repository",
        style: { background: "rgba(36,41,46,0.6)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "var(--radius-md)", color: "var(--text-muted)", fontSize: 12, padding: "4px 10px", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, maxWidth: 180 },
        children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "git", size: 12 }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("span", { style: { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }, children: activeRepo.name })
        ]
      }
    );
  }
  return /* @__PURE__ */ jsxRuntimeExports.jsxs(
    "button",
    {
      onClick,
      className: "db-btn db-focus",
      title: "Connect GitHub repository",
      style: { background: "transparent", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", color: "var(--text-dim)", fontSize: 12, padding: "4px 10px", cursor: "pointer", display: "flex", alignItems: "center", gap: 6 },
      onMouseEnter: (e) => {
        e.currentTarget.style.borderColor = "rgba(255,255,255,0.2)";
        e.currentTarget.style.color = "var(--text-muted)";
      },
      onMouseLeave: (e) => {
        e.currentTarget.style.borderColor = "var(--border)";
        e.currentTarget.style.color = "var(--text-dim)";
      },
      children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "git", size: 12 }),
        " GitHub"
      ]
    }
  );
}
function GitHubPanelWrapper(props) {
  return /* @__PURE__ */ jsxRuntimeExports.jsx(GitHubProvider, { token: props.token, children: /* @__PURE__ */ jsxRuntimeExports.jsx(GitHubPanel, { ...props }) });
}
export {
  Workspace as default
};
