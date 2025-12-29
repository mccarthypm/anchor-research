/**
 * API client for communicating with the stock-analysis-agent service
 */

export interface ChatRequest {
  ticker: string;
  question: string;
  model?: string;
  max_full_docs?: number;
}

export interface ChatResponse {
  ticker: string;
  company_name: string;
  response: string;
  session_summary: Record<string, unknown>;
}

/**
 * Send a chat message to the stock analysis agent
 * Uses Next.js API route to proxy requests (server-side can access Kubernetes services)
 */
export async function sendChatMessage(
  request: ChatRequest
): Promise<ChatResponse> {
  // Use Next.js API route which runs server-side and can access Kubernetes services
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP error! status: ${response.status}`);
  }

  return response.json();
}

