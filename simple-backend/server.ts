#!/usr/bin/env node

import { query as agentSdkQuery } from "@anthropic-ai/claude-agent-sdk";
import { query as claudeCodeQuery } from "@anthropic-ai/claude-code";
import { Hono } from "hono";
import { serve } from "@hono/node-server";
import { z } from "zod";
import { execSync } from "node:child_process";
import { existsSync, statSync } from "node:fs";
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
    hasApiKey: !!process.env.ANTHROPIC_API_KEY,
    apiKeyLength: process.env.ANTHROPIC_API_KEY?.length || 0,
    dangerousModeEnabled: process.env.CLAUDE_CODE_DANGEROUSLY_SKIP_PERMISSIONS === "1",
  });
});

// Main task execution endpoint with streaming
app.post("/execute", async (c) => {
  try {
    // Parse JSON body with error handling
    let body: any;
    try {
      // Try to parse JSON body (Hono will handle content-type automatically)
      body = await c.req.json();
      
      // Check if body is null or undefined (empty body)
      if (body === null || body === undefined) {
        return c.json(
          {
            success: false,
            error: "Request body is required",
          },
          400
        );
      }
    } catch (error: any) {
      // Handle JSON parsing errors
      const errorMessage = error.message || "Unknown error";
      if (errorMessage.includes("JSON") || 
          errorMessage.includes("Unexpected end") || 
          errorMessage.includes("Unexpected token") ||
          errorMessage.includes("parse")) {
        return c.json(
          {
            success: false,
            error: "Invalid or empty JSON in request body",
            details: errorMessage,
          },
          400
        );
      }
      // Re-throw unexpected errors to be handled by outer try-catch
      throw error;
    }

    // Validate request body schema
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

        // Store original environment variable values for restoration
        const originalDangerousMode = process.env.CLAUDE_CODE_DANGEROUSLY_SKIP_PERMISSIONS;
        const originalCCDangerousMode = process.env.CC_DANGEROUSLY_SKIP_PERMISSIONS;
        
        try {
          // Collect all messages from the execution
          const messages: any[] = [];
          let finalResult: any = null;
          let sessionIdFromExecution: string | undefined = sessionId;

          // Verify working directory exists
          if (!existsSync(cwd)) {
            throw new Error(`Working directory does not exist: ${cwd}`);
          }
          
          try {
            const cwdStat = statSync(cwd);
            if (!cwdStat.isDirectory()) {
              throw new Error(`Working directory is not a directory: ${cwd}`);
            }
          } catch (err: any) {
            throw new Error(`Cannot access working directory ${cwd}: ${err.message}`);
          }

          // Check for required environment variables
          if (!process.env.ANTHROPIC_API_KEY) {
            throw new Error("ANTHROPIC_API_KEY environment variable is not set. Claude Code requires an API key to function.");
          }
          
          console.log(`ANTHROPIC_API_KEY is set: ${!!process.env.ANTHROPIC_API_KEY} (length: ${process.env.ANTHROPIC_API_KEY?.length || 0})`);

          // Execute the task with dangerous mode enabled (no permission prompts)
          // Set environment variable to ensure dangerous mode is enabled
          process.env.CLAUDE_CODE_DANGEROUSLY_SKIP_PERMISSIONS = "1";
          
          // Also set it as a boolean for compatibility
          process.env.CC_DANGEROUSLY_SKIP_PERMISSIONS = "true";
          
          // Test the claude command directly to see if it works
          try {
            console.log("Testing Claude Code executable...");
            const testResult = execSync(
              `"${claudeCodeExecutablePath}" --version`,
              { 
                encoding: "utf-8",
                env: process.env,
                cwd: cwd,
                timeout: 5000,
              }
            );
            console.log(`Claude Code version check: ${testResult.trim()}`);
          } catch (testError: any) {
            console.error("Claude Code version check failed:", testError.message);
            // Don't throw, just log - the SDK might handle it differently
          }
          
          const options: any = {
            pathToClaudeCodeExecutable: claudeCodeExecutablePath,
            cwd,
            systemPrompt: { type: "preset" as const, preset: "claude_code" },
            settingSources: ["user", "project", "local"],
            // Dangerous mode: bypass all permission checks
          };
          
          console.log("Dangerous mode enabled - Environment variables set:");
          console.log(`  CLAUDE_CODE_DANGEROUSLY_SKIP_PERMISSIONS=${process.env.CLAUDE_CODE_DANGEROUSLY_SKIP_PERMISSIONS}`);
          console.log(`  CC_DANGEROUSLY_SKIP_PERMISSIONS=${process.env.CC_DANGEROUSLY_SKIP_PERMISSIONS}`);
          console.log(`  Working directory: ${cwd} (exists: ${existsSync(cwd)})`);
          console.log("Options:", JSON.stringify({
            permissionMode: options.permissionMode,
            dangerouslySkipPermissions: options.dangerouslySkipPermissions,
            cwd: options.cwd,
            executablePath: options.pathToClaudeCodeExecutable,
          }, null, 2));

          if (sessionId) {
            options.resume = sessionId;
          }

          let messageIter: AsyncIterable<any>;
          
          console.log("Starting Claude Code query...");
          try {
            if (useAgentSdk) {
              console.log("Using Agent SDK...");
              messageIter = await agentSdkQuery({
                prompt: generateMessages(),
                options,
              });
            } else {
              console.log("Using Claude Code query...");
              messageIter = await claudeCodeQuery({
                prompt: generateMessages(),
                options: {
                  ...options,
                  canUseTool: undefined,
                },
              });
            }
            console.log("Claude Code query started successfully");
          } catch (queryError: any) {
            console.error("Failed to start Claude Code query:", queryError);
            throw new Error(`Failed to start Claude Code: ${queryError.message}`);
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
          console.error("Error details:", {
            message: error.message,
            code: error.code,
            signal: error.signal,
            exitCode: error.exitCode,
            stack: error.stack,
          });
          
          // Try to extract more details from the error
          let errorDetails = error.message || "Unknown error";
          if (error.exitCode !== undefined) {
            errorDetails += ` (exit code: ${error.exitCode})`;
          }
          if (error.stderr) {
            console.error("Process stderr:", error.stderr);
            errorDetails += `\nStderr: ${error.stderr}`;
          }
          if (error.stdout) {
            console.error("Process stdout:", error.stdout);
          }
          
          // Add helpful diagnostic information
          const hasApiKey = !!process.env.ANTHROPIC_API_KEY;
          if (!hasApiKey) {
            errorDetails += "\n\n⚠️  ANTHROPIC_API_KEY is not set. Claude Code requires an API key to function.";
            errorDetails += "\n   Set it with: export ANTHROPIC_API_KEY=your_api_key";
          } else {
            errorDetails += `\n\n💡 API key is set (length: ${process.env.ANTHROPIC_API_KEY?.length || 0})`;
            errorDetails += "\n   If the error persists, verify the API key is valid and has proper permissions.";
            errorDetails += "\n   Check the /health endpoint for more diagnostic information.";
          }
          
          sendSSE("error", {
            success: false,
            error: errorDetails,
            exitCode: error.exitCode,
            hasApiKey: hasApiKey,
            stack: process.env.NODE_ENV === "development" ? error.stack : undefined,
          });
          controller.close();
        } finally {
          // Restore original environment variables
          if (originalDangerousMode === undefined) {
            delete process.env.CLAUDE_CODE_DANGEROUSLY_SKIP_PERMISSIONS;
          } else {
            process.env.CLAUDE_CODE_DANGEROUSLY_SKIP_PERMISSIONS = originalDangerousMode;
          }
          
          if (originalCCDangerousMode === undefined) {
            delete process.env.CC_DANGEROUSLY_SKIP_PERMISSIONS;
          } else {
            process.env.CC_DANGEROUSLY_SKIP_PERMISSIONS = originalCCDangerousMode;
          }
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

