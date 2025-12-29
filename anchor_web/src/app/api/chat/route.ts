import { NextRequest, NextResponse } from 'next/server';

const STOCK_AGENT_API_URL = process.env.NEXT_PUBLIC_STOCK_AGENT_API_URL || 'http://stock-analysis-agent:8080';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    console.log('Proxying request to stock-analysis-agent:', { url: `${STOCK_AGENT_API_URL}/chat`, body });
    
    // Proxy the request to the stock-analysis-agent service
    const response = await fetch(`${STOCK_AGENT_API_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      // FastAPI returns errors with { detail: "..." } format
      const errorText = await response.text();
      let error;
      try {
        error = JSON.parse(errorText);
      } catch {
        error = { detail: errorText || `HTTP error! status: ${response.status}` };
      }
      console.error('Stock-analysis-agent error:', error);
      // Preserve the error format for the client
      return NextResponse.json(
        error,
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error proxying request to stock-analysis-agent:', error);
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : 'Failed to communicate with stock analysis agent' },
      { status: 500 }
    );
  }
}

