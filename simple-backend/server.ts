#!/usr/bin/env node

import { query as agentSdkQuery } from "@anthropic-ai/claude-agent-sdk";
import { query as claudeCodeQuery } from "@anthropic-ai/claude-code";
import { Hono } from "hono";
import { serve } from "@hono/node-server";
import { z } from "zod";
import { execSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Resolve Claude Code executable path
function resolveClaudeCodePath(): string {
  // 1. Environment variable (highest priority)
  const envPath = process.env.CLAUDE_CODE_VIEWER_CC_EXECUTABLE_PATH;
  if (envPath) {
    return envPath;
  }

  // 2. System PATH lookup
  try {
    const whichResult = execSync("which claude", { encoding: "utf-8" }).trim();
    if (whichResult) {
      return whichResult;
    }
  } catch {
    // which command failed, continue to fallback
  }

  // 3. Project dependency @anthropic-ai/claude-code/cli.js (fallback)
  const projectPath = join(__dirname, "..", "node_modules", "@anthropic-ai", "claude-code", "cli.js");
  if (existsSync(projectPath)) {
    return projectPath;
  }

  throw new Error("Claude Code CLI not found. Please install @anthropic-ai/claude-code or set CLAUDE_CODE_VIEWER_CC_EXECUTABLE_PATH");
}

// Get Claude Code version
function getClaudeCodeVersion(executablePath: string): string | null {
  try {
    const version = execSync(`"${executablePath}" --version`, { encoding: "utf-8" }).trim();
    return version;
  } catch {
    return null;
  }
}

// Check if agent SDK is available (v1.0.125+)
function supportsAgentSdk(version: string | null): boolean {
  if (!version) return false;
  
  // Simple version check - assumes version format like "1.0.125"
  const match = version.match(/(\d+)\.(\d+)\.(\d+)/);
  if (!match) return false;
  
  const major = parseInt(match[1], 10);
  const minor = parseInt(match[2], 10);
  const patch = parseInt(match[3], 10);
  
  // Agent SDK available since v1.0.125
  return major > 1 || (major === 1 && minor > 0) || (major === 1 && minor === 0 && patch >= 125);
}

// Request schema
const executeTaskSchema = z.object({
  message: z.string().min(1, "Message is required"),
  cwd: z.string().optional().default(process.cwd()),
  sessionId: z.string().optional(),
});

// Initialize Claude Code path
let claudeCodeExecutablePath: string;
let claudeCodeVersion: string | null;
let useAgentSdk: boolean;

try {
  claudeCodeExecutablePath = resolveClaudeCodePath();
  claudeCodeVersion = getClaudeCodeVersion(claudeCodeExecutablePath);
  useAgentSdk = supportsAgentSdk(claudeCodeVersion);
  
  console.log(`Claude Code executable: ${claudeCodeExecutablePath}`);
  console.log(`Claude Code version: ${claudeCodeVersion || "unknown"}`);
  console.log(`Using Agent SDK: ${useAgentSdk}`);
} catch (error) {
  console.error("Failed to initialize Claude Code:", error);
  process.exit(1);
}

// Create Hono app
const app = new Hono();

// Health check endpoint
app.get("/health", (c) => {
  return c.json({ 
    status: "ok",
    claudeCodeVersion,
    executablePath: claudeCodeExecutablePath,
  });
});

// Main task execution endpoint with streaming
app.post("/execute", async (c) => {
  try {
    const body = await c.req.json();
    const parseResult = executeTaskSchema.safeParse(body);
    
    if (!parseResult.success) {
      return c.json(
        {
          success: false,
          error: "Invalid request body",
          details: parseResult.error.errors,
        },
        400
      );
    }
    
    const { message, cwd, sessionId } = parseResult.data;

    console.log(`Executing task: ${message.substring(0, 100)}...`);
    console.log(`Working directory: ${cwd}`);
    if (sessionId) {
      console.log(`Resuming session: ${sessionId}`);
    }

    // Create message generator
    async function* generateMessages() {
      yield {
        type: "user" as const,
        message: {
          role: "user" as const,
          content: message,
        },
        parent_tool_use_id: null,
      };
    }

    // Set up streaming response with Server-Sent Events
    const stream = new ReadableStream({
      async start(controller) {
        const encoder = new TextEncoder();
        
        // Helper function to send SSE message
        const sendSSE = (event: string, data: any) => {
          const jsonData = JSON.stringify(data);
          const sseMessage = `event: ${event}\ndata: ${jsonData}\n\n`;
          controller.enqueue(encoder.encode(sseMessage));
        };

        try {
          // Collect all messages from the execution
          const messages: any[] = [];
          let finalResult: any = null;
          let sessionIdFromExecution: string | undefined = sessionId;

          // Execute the task
          const options: any = {
            pathToClaudeCodeExecutable: claudeCodeExecutablePath,
            cwd,
            systemPrompt: { type: "preset" as const, preset: "claude_code" },
            settingSources: ["user", "project", "local"],
            permissionMode: "bypassPermissions" as const,
            dangerouslySkipPermissions: true,
          };

          if (sessionId) {
            options.resume = sessionId;
          }

          let messageIter: AsyncIterable<any>;
          
          if (useAgentSdk) {
            messageIter = await agentSdkQuery({
              prompt: generateMessages(),
              options,
            });
          } else {
            messageIter = await claudeCodeQuery({
              prompt: generateMessages(),
              options: {
                ...options,
                canUseTool: undefined,
              },
            });
          }

          // Send start event
          sendSSE("start", {
            message: message.substring(0, 100) + (message.length > 100 ? "..." : ""),
            cwd,
            sessionId,
          });

          // Process all messages and stream them in real-time
          for await (const msg of messageIter) {
            messages.push(msg);
            
            // Track session ID from init message
            if (msg.type === "system" && msg.subtype === "init") {
              sessionIdFromExecution = msg.session_id;
              sendSSE("session", {
                sessionId: sessionIdFromExecution,
              });
            }
            
            // Stream each message as it arrives
            sendSSE("message", {
              type: msg.type,
              subtype: msg.subtype,
              session_id: msg.session_id,
              content: msg.type === "assistant" ? msg.content : undefined,
              result: msg.type === "result" ? msg.result : undefined,
              // Include full message for detailed processing
              fullMessage: msg,
            });
            
            // Capture final result
            if (msg.type === "result") {
              finalResult = msg;
            }
          }

          // Send completion event with summary
          sendSSE("complete", {
            success: true,
            sessionId: sessionIdFromExecution,
            result: finalResult,
            messageCount: messages.length,
          });

          controller.close();
        } catch (error: any) {
          console.error("Task execution error:", error);
          sendSSE("error", {
            success: false,
            error: error.message || "Unknown error",
            stack: process.env.NODE_ENV === "development" ? error.stack : undefined,
          });
          controller.close();
        }
      },
    });

    // Return streaming response with SSE headers
    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no", // Disable buffering in nginx
      },
    });
  } catch (error: any) {
    console.error("Request setup error:", error);
    return c.json(
      {
        success: false,
        error: error.message || "Unknown error",
        stack: process.env.NODE_ENV === "development" ? error.stack : undefined,
      },
      500
    );
  }
});

// Start server
const port = parseInt(process.env.PORT || "3000", 10);

serve(
  {
    fetch: app.fetch,
    port,
  },
  (info) => {
    console.log(`Simple Claude Code Backend is running on http://localhost:${info.port}`);
    console.log(`Health check: http://localhost:${info.port}/health`);
    console.log(`Execute endpoint: POST http://localhost:${info.port}/execute (streaming enabled)`);
  }
);

